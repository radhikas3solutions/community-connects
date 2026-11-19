"""Read restaurants, fast food places and cafés from OpenStreetMap (Overpass API).

OpenStreetMap data is open (ODbL): we may reuse it with attribution ("© OpenStreetMap
contributors", linked from every imported entry). Google Maps and Yelp forbid copying
their listings, so they are not used.

One request = one area. Places without a name or a callable phone number, and places
inside the Dulles airport terminals (not reachable for the public without a ticket), are
skipped. A missing town is filled in from the nearest known town centre.
"""

import logging
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx2

from app.schemas.business import is_callable_phone

log = logging.getLogger(__name__)

OVERPASS_API = "https://overpass-api.de/api/interpreter"
OSM_URL = "https://www.openstreetmap.org"
AMENITIES = ("restaurant", "fast_food", "cafe")
QUERY_TIMEOUT_S = 120
RETRY_STATUSES = (429, 502, 503, 504)
RETRY_DELAY_S = 15


@dataclass(frozen=True)
class Area:
    key: str
    label: str
    selector: str  # Overpass filter appended to the amenity query


AREAS: dict[str, Area] = {
    a.key: a
    for a in (
        Area("loudoun", "Loudoun County", "(area.a)"),
        # Fairfax County, limited to the western part next to Loudoun.
        Area(
            "west_fairfax",
            "Herndon, Chantilly & Centreville",
            "(area.a)(38.80,-77.50,39.00,-77.33)",
        ),
    )
}
AREA_NAMES = {"loudoun": "Loudoun County", "west_fairfax": "Fairfax County"}

# Dulles airport terminals and concourses.
AIRPORT_BOX = (38.935, -77.470, 38.962, -77.435)

# Town centres, used when a place has no addr:city.
TOWNS: list[tuple[str, float, float]] = [
    ("Aldie", 38.975, -77.641),
    ("Stone Ridge", 38.929, -77.556),
    ("South Riding", 38.921, -77.507),
    ("Brambleton", 38.982, -77.539),
    ("Ashburn", 39.044, -77.488),
    ("Lansdowne", 39.087, -77.483),
    ("Sterling", 39.006, -77.429),
    ("Dulles", 38.996, -77.455),
    ("Potomac Falls", 39.050, -77.401),
    ("Leesburg", 39.116, -77.564),
    ("Purcellville", 39.137, -77.715),
    ("Hamilton", 39.134, -77.664),
    ("Round Hill", 39.133, -77.770),
    ("Lovettsville", 39.272, -77.637),
    ("Middleburg", 38.969, -77.735),
    ("Herndon", 38.970, -77.386),
    ("Reston", 38.958, -77.357),
    ("Chantilly", 38.894, -77.431),
    ("Centreville", 38.840, -77.429),
    ("Fair Oaks", 38.876, -77.366),
]

# Real addr:city values we accept; anything else (typos, "Space") gets the nearest town.
OTHER_PLACES = {"Fairfax", "Clifton", "Oak Hill", "Great Falls", "Vienna", "Oakton", "Gainesville",
                "Haymarket", "Manassas", "Hillsboro", "Bluemont", "Waterford", "Lucketts",
                "Paeonian Springs", "Philomont", "Arcola", "Lincoln", "Unison"}  # fmt: skip
KNOWN_CITIES = {t[0].lower(): t[0] for t in TOWNS} | {p.lower(): p for p in OTHER_PLACES}

TYPE_LABELS = {"restaurant": "Restaurant", "fast_food": "Fast food", "cafe": "Café"}
DAYS = {"Mo": "Mon", "Tu": "Tue", "We": "Wed", "Th": "Thu", "Fr": "Fri", "Sa": "Sat", "Su": "Sun",
        "PH": "holidays"}  # fmt: skip


class OsmError(RuntimeError):
    pass


class OsmClient(Protocol):
    def fetch(self, area: Area) -> list[dict[str, Any]]: ...


def overpass_query(area: Area) -> str:
    amenity = "|".join(AMENITIES)
    return (
        f"[out:json][timeout:{QUERY_TIMEOUT_S}];"
        f'area["name"="{AREA_NAMES[area.key]}"]["admin_level"="6"]->.a;'
        f'nwr["amenity"~"^({amenity})$"]["name"]{area.selector};'
        "out center tags;"
    )


class HttpOsmClient:
    def __init__(self, client: httpx2.Client | None = None) -> None:
        self._client = client or httpx2.Client(
            timeout=QUERY_TIMEOUT_S + 30,
            headers={"User-Agent": "CommunityConnect-directory-import/1.0"},
        )

    def fetch(self, area: Area) -> list[dict[str, Any]]:
        # The public server is shared and sometimes busy: retry a temporary error once.
        for attempt in range(2):
            try:
                r = self._client.post(OVERPASS_API, data={"data": overpass_query(area)})
            except httpx2.HTTPError as exc:
                raise OsmError(
                    "OpenStreetMap could not be reached. Please try again later."
                ) from exc
            if r.status_code in RETRY_STATUSES and attempt == 0:
                time.sleep(RETRY_DELAY_S)
                continue
            break
        if r.status_code in RETRY_STATUSES:
            raise OsmError("OpenStreetMap is busy right now. Please try again in a few minutes.")
        if r.status_code != 200:
            raise OsmError(f"OpenStreetMap returned an error ({r.status_code})")
        try:
            return list(r.json().get("elements", []))
        except ValueError as exc:
            raise OsmError("OpenStreetMap sent a response we couldn't read") from exc


@dataclass
class Place:
    key: str  # "node/123", the OpenStreetMap id
    name: str
    amenity: str
    phone: str | None
    website: str | None
    address: str | None
    city: str | None
    zip_code: str | None
    hours: str | None
    description: str
    data: dict[str, Any] = field(default_factory=dict)


def _phone(raw: str | None) -> str | None:
    if not raw:
        return None
    first = re.split(r"[;,/]", raw)[0].strip()
    digits = re.sub(r"\D", "", first)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return first[:32] or None


def _website(raw: str | None) -> str | None:
    if not raw:
        return None
    raw = raw.split(";")[0].strip()
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    return raw[:500]


def _hours(raw: str | None) -> str | None:
    if not raw:
        return None
    text = re.sub(r"\b(Mo|Tu|We|Th|Fr|Sa|Su|PH)\b", lambda m: DAYS[m.group(1)], raw)
    return text.replace(";", ",")[:200]


def nearest_town(lat: float, lon: float) -> str:
    def dist(t: tuple[str, float, float]) -> float:
        return math.hypot(t[1] - lat, (t[2] - lon) * math.cos(math.radians(lat)))

    return min(TOWNS, key=dist)[0]


def _words(value: str) -> str:
    return value.replace("_", " ").strip()


def describe(tags: dict[str, str]) -> str:
    amenity = tags.get("amenity", "restaurant")
    cuisines = [_words(c).title() for c in tags.get("cuisine", "").split(";") if c.strip()]
    parts = [TYPE_LABELS.get(amenity, "Restaurant")]
    if cuisines:
        parts[0] += f" · {', '.join(cuisines)}"
    extras = []
    if tags.get("diet:vegetarian") == "only":
        extras.append("Vegetarian only")
    elif tags.get("diet:vegetarian") == "yes":
        extras.append("Vegetarian options")
    if tags.get("diet:vegan") in ("yes", "only"):
        extras.append("Vegan options")
    if tags.get("diet:halal") in ("yes", "only"):
        extras.append("Halal")
    for tag, label in (
        ("takeaway", "Takeout"),
        ("delivery", "Delivery"),
        ("drive_through", "Drive-through"),
        ("outdoor_seating", "Outdoor seating"),
    ):
        if tags.get(tag) in ("yes", "only"):
            extras.append(label)
    text = parts[0] + "."
    if extras:
        text += " " + ", ".join(extras) + "."
    if tags.get("brand") and tags["brand"] != tags.get("name"):
        text += f" Part of {tags['brand']}."
    return text + " Listed from OpenStreetMap; please call to check hours before visiting."


def _in_box(lat: float, lon: float, box: tuple[float, float, float, float]) -> bool:
    return box[0] <= lat <= box[2] and box[1] <= lon <= box[3]


def places_from_elements(elements: list[dict[str, Any]]) -> list[Place]:
    places: list[Place] = []
    seen: set[str] = set()
    for el in elements:
        tags: dict[str, str] = el.get("tags") or {}
        name = (tags.get("name") or "").strip()
        lat = el.get("lat", (el.get("center") or {}).get("lat"))
        lon = el.get("lon", (el.get("center") or {}).get("lon"))
        if not name or lat is None or lon is None or tags.get("amenity") not in AMENITIES:
            continue
        if _in_box(lat, lon, AIRPORT_BOX):
            continue
        phone = _phone(tags.get("phone") or tags.get("contact:phone"))
        if not is_callable_phone(phone):
            continue  # only places people can call are listed
        key = f"{el.get('type')}/{el.get('id')}"
        if key in seen:
            continue
        seen.add(key)

        street = " ".join(
            p for p in (tags.get("addr:housenumber"), tags.get("addr:street")) if p
        ).strip()
        if street and tags.get("addr:unit"):
            street += f" #{tags['addr:unit']}"
        zip5 = (tags.get("addr:postcode") or "")[:5]
        places.append(
            Place(
                key=key,
                name=name[:120],
                amenity=tags["amenity"],
                phone=phone,
                website=_website(tags.get("website") or tags.get("contact:website")),
                address=street[:200] or None,
                city=KNOWN_CITIES.get((tags.get("addr:city") or "").strip().lower())
                or nearest_town(lat, lon),
                zip_code=zip5 if re.fullmatch(r"\d{5}", zip5) else None,
                hours=_hours(tags.get("opening_hours")),
                description=describe(tags),
                data={
                    "osm": key,
                    "lat": lat,
                    "lon": lon,
                    "amenity": tags["amenity"],
                    "cuisine": tags.get("cuisine"),
                    "brand": tags.get("brand"),
                },
            )
        )
    return places


def osm_url(external_id: str) -> str:
    return f"{OSM_URL}/{external_id}"
