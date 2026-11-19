"""Search assistant: tools search real data, answers only show entries the tools returned."""

import uuid
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.api.deps import get_search_agent
from app.core.config import Settings, get_settings
from app.db.session import get_sessionmaker
from app.models import AIUsage, Category, Profile
from app.models.enums import UserRole
from app.services.ai_search import (
    SearchAnswer,
    SearchDirectoryArgs,
    SearchError,
    SearchMarketplaceArgs,
    SearchResult,
    SearchTools,
    SearchUsage,
    build_system,
    run_tool,
)
from tests.conftest import auth_header, make_token

pytestmark = pytest.mark.db

URL = "/api/v1/assistant/ask"
Script = Callable[[SearchTools], SearchAnswer]


class FakeAgent:
    """Runs a scripted sequence of tool calls instead of Claude."""

    def __init__(self) -> None:
        self.script: Script = lambda tools: SearchAnswer(
            reply="Hi", business_ids=[], listing_ids=[]
        )
        self.error: SearchError | None = None
        self.calls: list[tuple] = []

    def answer(self, messages, tools, directory, marketplace, lang, today) -> SearchResult:  # type: ignore[no-untyped-def]
        self.calls.append((messages, directory, marketplace, lang, today))
        if self.error:
            raise self.error
        usage = SearchUsage(
            model="claude-opus-5-5", input_tokens=3000, output_tokens=400, latency_ms=5000
        )
        return SearchResult(self.script(tools), usage)


@pytest.fixture
def ask(db_client: TestClient) -> Iterator[tuple[TestClient, FakeAgent]]:
    fake = FakeAgent()
    db_client.app.dependency_overrides[get_search_agent] = lambda: fake  # type: ignore[attr-defined]
    yield db_client, fake
    db_client.app.dependency_overrides.clear()  # type: ignore[attr-defined]


def _user(client: TestClient, role: UserRole = UserRole.USER) -> tuple[uuid.UUID, dict]:
    uid = uuid.uuid4()
    headers = auth_header(make_token(uid))
    assert client.get("/api/v1/me", headers=headers).status_code == 200
    if role != UserRole.USER:
        with get_sessionmaker()() as db:
            db.execute(update(Profile).where(Profile.id == uid).values(role=role))
            db.commit()
    return uid, headers


def _category_id(slug: str) -> int:
    with get_sessionmaker()() as db:
        return db.scalars(select(Category.id).where(Category.slug == slug)).one()


def _add(client: TestClient, headers: dict, **fields) -> str:
    body = {"kind": "business", "category_id": _category_id("doctors"), **fields}
    r = client.post("/api/v1/businesses", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _ask(text: str, **kw) -> dict:
    return {"messages": [{"role": "user", "content": text}], **kw}


def test_requires_sign_in(ask: tuple[TestClient, FakeAgent]) -> None:
    client, _ = ask
    assert client.post(URL, json=_ask("dentist in aldie")).status_code == 401


def test_dentist_near_aldie(ask: tuple[TestClient, FakeAgent]) -> None:
    client, fake = ask
    _, staff = _user(client, UserRole.ADMIN)
    _, member = _user(client)
    dentist = _add(
        client,
        staff,
        name="Smile Dental",
        description_en="Family dentist: cleanings and braces.",
        phone="7035550199",
        city="South Riding",
        languages=["te", "en"],
    )
    _add(client, staff, name="Loudoun Pediatrics", description_en="Children's doctor.",
         phone="7035550111", city="Aldie")  # fmt: skip
    pending = _add(client, member, name="Pending Dental", description_en="dentist",
                   phone="7035550122", city="Aldie")  # fmt: skip
    seen: dict[str, dict] = {}

    def script(tools: SearchTools) -> SearchAnswer:
        args = {"query": "dentist or dental", "category_slug": "doctors", "language": None}
        seen["aldie"] = tools.search_directory(SearchDirectoryArgs(**args, towns=["Aldie"]))
        seen["near"] = tools.search_directory(
            SearchDirectoryArgs(**args, towns=["South Riding", "Stone Ridge"])
        )
        seen["te"] = tools.search_directory(
            SearchDirectoryArgs(query=None, category_slug=None, towns=[], language="TE")
        )
        return SearchAnswer(
            reply="Nothing in Aldie itself, but Smile Dental is nearby in South Riding.",
            # A made-up id, a pending entry and a malformed id are all ignored.
            business_ids=[dentist, str(uuid.uuid4()), pending, "nope", dentist],
            listing_ids=[],
        )

    fake.script = script
    r = client.post(URL, json=_ask("give dentist in aldie"), headers=member)
    assert r.status_code == 200, r.text
    body = r.json()
    assert seen["aldie"]["total"] == 0  # the pending entry is not searchable
    assert [x["name"] for x in seen["near"]["results"]] == ["Smile Dental"]
    assert seen["near"]["results"][0]["phone"] == "7035550199"
    assert [x["name"] for x in seen["te"]["results"]] == ["Smile Dental"]
    assert [b["id"] for b in body["businesses"]] == [dentist]
    assert body["businesses"][0]["phone"] == "7035550199"
    assert body["listings"] == []
    assert body["reply"].startswith("Nothing in Aldie")

    messages, directory, marketplace, lang, _ = fake.calls[0]
    assert messages[0].content == "give dentist in aldie" and lang == "en"
    assert "doctors" in {c.slug for c in directory}
    assert "furniture" in {c.slug for c in marketplace}


def test_marketplace_tool_and_bad_arguments(ask: tuple[TestClient, FakeAgent]) -> None:
    client, fake = ask
    _, h = _user(client)
    seen: dict[str, object] = {}

    def script(tools: SearchTools) -> SearchAnswer:
        seen["items"] = tools.search_marketplace(
            SearchMarketplaceArgs(query="crib", category_slug="kids-baby", listing_type="free")
        )
        seen["bad_category"] = run_tool(
            tools, "search_directory",
            {"query": None, "category_slug": "spaceships", "towns": [], "language": None},
        )  # fmt: skip
        seen["bad_language"] = run_tool(
            tools, "search_directory",
            {"query": None, "category_slug": None, "towns": [], "language": "xx"},
        )  # fmt: skip
        seen["bad_args"] = run_tool(tools, "search_marketplace", {"query": 5})
        seen["unknown"] = run_tool(tools, "delete_everything", {})
        return SearchAnswer(reply="No cribs right now.", business_ids=[], listing_ids=["x"])

    fake.script = script
    r = client.post(URL, json=_ask("free crib?"), headers=h)
    assert r.status_code == 200, r.text
    assert seen["items"] == {"total": 0, "results": []}
    for key in ("bad_category", "bad_language", "bad_args", "unknown"):
        content, is_error = seen[key]  # type: ignore[misc]
        assert is_error, key
        assert "error" in content
    assert r.json()["listings"] == []


def test_usage_logged_limits_and_errors(ask: tuple[TestClient, FakeAgent]) -> None:
    client, fake = ask
    uid, h = _user(client)
    client.app.dependency_overrides[get_settings] = lambda: Settings(  # type: ignore[attr-defined]
        ai_chat_turns_per_hour=2, ai_chat_turns_per_day=5
    )
    assert client.post(URL, json=_ask("hi", lang="te"), headers=h).status_code == 200
    assert fake.calls[0][3] == "te"
    with get_sessionmaker()() as db:
        usage = db.scalars(select(AIUsage).where(AIUsage.profile_id == uid)).one()
        assert usage.feature == "search_assistant" and usage.outcome == "ok"
        assert usage.input_tokens == 3000 and usage.cost_usd is not None

    fake.error = SearchError("AI service error", usage=SearchUsage(model="claude-opus-5-5"))
    r = client.post(URL, json=_ask("hi"), headers=h)
    assert r.status_code == 502 and r.json()["detail"]["code"] == "ai_error"
    r = client.post(URL, json=_ask("hi"), headers=h)
    assert r.status_code == 429 and r.json()["detail"]["code"] == "rate_limited"


def test_request_validation(ask: tuple[TestClient, FakeAgent]) -> None:
    client, _ = ask
    _, h = _user(client)
    ends_with_assistant = {"messages": [{"role": "assistant", "content": "hi"}]}
    assert client.post(URL, json=ends_with_assistant, headers=h).status_code == 422
    assert client.post(URL, json=_ask("x" * 1001), headers=h).status_code == 422
    too_many = {"messages": [{"role": "user", "content": "x"}] * 31}
    assert client.post(URL, json=too_many, headers=h).status_code == 422


def test_system_prompt_lists_categories_and_language() -> None:
    from app.services.ai_intake import CategoryChoice

    system = build_system(
        [CategoryChoice("doctors", "Doctors & Clinics")],
        [CategoryChoice("furniture", "Furniture")],
        "te",
        "2026-11-18",
    )
    assert "- doctors: Doctors & Clinics" in system
    assert "- furniture: Furniture" in system
    assert "Site language: Telugu. Today's date: 2026-11-18." in system
    assert "{" not in system.split("Directory categories")[1]
