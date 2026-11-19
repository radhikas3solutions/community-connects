"""Read doctors, dentists and clinics from the NPI Registry (public US government data).

https://npiregistry.cms.hhs.gov/api-page. A ZIP search matches any address on a record,
including mailing addresses (often homes, sometimes out of state), so only the practice
LOCATION address is used and it must be in the requested ZIP. Providers who share a
practice phone at the same ZIP are merged into one entry for the practice.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx2

log = logging.getLogger(__name__)

NPI_API = "https://npiregistry.cms.hhs.gov/api/"
PAGE_SIZE = 200  # API maximum per request
MAX_SKIP = 1000  # API maximum offset


@dataclass(frozen=True)
class Preset:
    key: str
    label: str
    taxonomy: str  # sent as taxonomy_description; matched as a substring of a specialty
    exclude: tuple[str, ...] = ()


PRESETS: dict[str, Preset] = {
    p.key: p
    for p in (
        # Dental public health is a non-clinical role; its addresses are often personal.
        Preset("dentists", "Dentists", "Dentist", exclude=("Dental Public Health",)),
        Preset("pediatricians", "Pediatricians", "Pediatrics"),
        Preset("family", "Family doctors", "Family Medicine"),
        Preset("internal", "Internal medicine", "Internal Medicine"),
        Preset("obgyn", "OB/GYN", "Obstetrics & Gynecology"),
        Preset("eye", "Eye doctors (optometrists)", "Optometrist"),
    )
}

# Northern Virginia ZIPs around the community (Loudoun and western Fairfax).
DEFAULT_ZIPS = [
    "20105",  # Aldie, Stone Ridge
    "20152",  # South Riding
    "20147",  # Ashburn
    "20148",  # Ashburn, Brambleton
    "20151",  # Chantilly
    "20166",  # Dulles, Sterling
    "20164",  # Sterling
    "20165",  # Potomac Falls
    "20171",  # Herndon
    "20120",  # Centreville
    "20175",  # Leesburg
    "20176",  # Leesburg
]

DOCTOR_CREDENTIALS = {"MD", "DO", "DDS", "DMD", "OD", "DPM", "DC"}
UPPER_WORDS = DOCTOR_CREDENTIALS | {"NP", "PA", "PT", "DPT", "FNP", "MPH", "MS", "PHD", "II", "III"}
LEGAL_SUFFIXES = {"LLC", "PLLC", "PC", "INC", "LTD", "PA", "LLP", "CORP", "CO", "CORPORATION"}


class NpiError(RuntimeError):
    pass


class NpiClient(Protocol):
    def search(self, postal_code: str, taxonomy: str) -> list[dict[str, Any]]: ...


class HttpNpiClient:
    def __init__(self, client: httpx2.Client | None = None) -> None:
        self._client = client or httpx2.Client(timeout=30)

    def search(self, postal_code: str, taxonomy: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for skip in range(0, MAX_SKIP + 1, PAGE_SIZE):
            params = {
                "version": "2.1",
                "postal_code": postal_code,
                "taxonomy_description": taxonomy,
                "limit": PAGE_SIZE,
                "skip": skip,
            }
            try:
                response = self._client.get(NPI_API, params=params)
                response.raise_for_status()
                data = response.json()
            except (httpx2.HTTPError, ValueError) as exc:
                log.error("NPI Registry request failed: %s", exc)
                raise NpiError("The NPI Registry could not be reached") from exc
            if data.get("Errors"):
                raise NpiError(f"NPI Registry error: {data['Errors']}")
            page = data.get("results") or []
            results += page
            if len(page) < PAGE_SIZE:
                break
        return results


@dataclass
class Practice:
    key: str  # "<zip>:<phone digits>": stable across imports
    name: str
    is_organization: bool
    address: str
    city: str
    zip_code: str
    phone: str
    providers: list[str] = field(default_factory=list)
    specialties: list[str] = field(default_factory=list)
    npis: list[str] = field(default_factory=list)


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _tidy(text: str) -> str:
    """'24560 SOUTHPOINT DR # 370' -> '24560 Southpoint Dr # 370'."""
    words = []
    for word in text.split():
        bare = word.replace(".", "").upper()
        words.append(
            bare if bare in UPPER_WORDS else "-".join(w.capitalize() for w in word.split("-"))
        )
    return " ".join(words)


def _organization_name(name: str) -> str:
    """'ALDIE SMILES, PLLC' -> 'Aldie Smiles'."""
    words = name.replace(",", " ").split()
    while len(words) > 1 and words[-1].replace(".", "").upper() in LEGAL_SUFFIXES:
        words.pop()
    return _tidy(" ".join(words))


def _person_name(basic: dict[str, Any]) -> str:
    """'Dr. Sowmya Kanumilli, DMD'."""
    first = _tidy(basic.get("first_name") or "")
    last = _tidy(basic.get("last_name") or "")
    raw = (basic.get("credential") or "").replace(".", "").upper()
    credentials = [c for c in re.split(r"[\s,;/]+", raw) if c]
    prefix = "Dr. " if any(c in DOCTOR_CREDENTIALS for c in credentials) else ""
    name = f"{prefix}{first} {last}".strip()
    return f"{name}, {', '.join(credentials)}" if credentials else name


def _matching_specialties(record: dict[str, Any], preset: Preset) -> list[str]:
    term = preset.taxonomy.lower()
    found = []
    for t in record.get("taxonomies") or []:
        desc = t.get("desc") or ""
        if term in desc.lower() and not any(x.lower() in desc.lower() for x in preset.exclude):
            found.append(desc)
    return found


def _location(record: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (a for a in record.get("addresses") or [] if a.get("address_purpose") == "LOCATION"),
        None,
    )


def practices_from_results(
    results: list[dict[str, Any]], postal_code: str, preset: Preset
) -> list[Practice]:
    """Active providers whose practice is in `postal_code`, grouped by practice phone."""
    practices: dict[str, Practice] = {}
    for record in results:
        basic = record.get("basic") or {}
        if basic.get("status", "A") != "A":
            continue
        specialties = _matching_specialties(record, preset)
        loc = _location(record)
        if not specialties or loc is None:
            continue
        zip5 = (loc.get("postal_code") or "")[:5]
        phone = _digits(loc.get("telephone_number"))
        if zip5 != postal_code or loc.get("state") != "VA" or len(phone) != 10:
            continue

        is_org = record.get("enumeration_type") == "NPI-2"
        if is_org:
            dba = next(
                (
                    o.get("organization_name")
                    for o in record.get("other_names") or []
                    if o.get("type") == "Doing Business As" and o.get("organization_name")
                ),
                None,
            )
            name = _organization_name(dba or basic.get("organization_name") or "")
        else:
            name = _person_name(basic)
        if not name:
            continue

        key = f"{zip5}:{phone}"
        practice = practices.get(key)
        if practice is None:
            street = " ".join(
                x for x in (loc.get("address_1"), loc.get("address_2")) if x and x.strip()
            )
            practice = practices[key] = Practice(
                key=key,
                name=name,
                is_organization=is_org,
                address=_tidy(street)[:200],
                city=_tidy(loc.get("city") or "")[:80],
                zip_code=zip5,
                phone=f"{phone[:3]}-{phone[3:6]}-{phone[6:]}",
            )
        elif is_org and not practice.is_organization:
            # The practice's own name beats the first provider's name.
            practice.name, practice.is_organization = name, True
        if not is_org and name not in practice.providers:
            practice.providers.append(name)
        for s in specialties:
            if s not in practice.specialties:
                practice.specialties.append(s)
        if record.get("number") and record["number"] not in practice.npis:
            practice.npis.append(str(record["number"]))
    return list(practices.values())


def describe(specialties: list[str], providers: list[str], name: str) -> str:
    """English description built from the public record (no invented details)."""
    # "Dentist" adds nothing next to "Dentist, Orthodontics".
    specific = [s for s in specialties if not any(o.startswith(f"{s},") for o in specialties)]
    parts = [f"{'; '.join(specific)}." if specific else ""]
    others = [p for p in providers if p != name]
    if others:
        shown = ", ".join(others[:8]) + (f" and {len(others) - 8} more" if len(others) > 8 else "")
        parts.append(f"Providers: {shown}.")
    parts.append("Details from the public NPI Registry: please call to confirm before visiting.")
    return " ".join(p for p in parts if p)
