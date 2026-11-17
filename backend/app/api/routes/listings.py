import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from geoalchemy2 import Geography, Geometry
from geoalchemy2.elements import WKTElement
from sqlalchemy import Select, cast, func, literal_column, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_profile, get_optional_user, get_storage, require_storage
from app.api.photos import read_photos, store_photos
from app.core.config import Settings, get_settings
from app.core.security import AuthUser
from app.db.session import get_db
from app.models import Category, Listing, ListingImage, Profile
from app.models.enums import ListingStatus, ListingType, UserRole
from app.schemas.common import GeoPoint, Page
from app.schemas.listing import ListingCreate, ListingImageOut, ListingOut, ListingUpdate
from app.services.storage import PhotoStorage

router = APIRouter(prefix="/listings", tags=["listings"])

# Stored pickup points are rounded to ~1 km so a seller's home address is never exposed.
LOCATION_PRECISION = 2
STAFF = (UserRole.MODERATOR, UserRole.ADMIN)
PUBLIC_STATUSES = (ListingStatus.ACTIVE, ListingStatus.SOLD)


def _point(p: GeoPoint) -> WKTElement:
    lat, lng = round(p.lat, LOCATION_PRECISION), round(p.lng, LOCATION_PRECISION)
    return WKTElement(f"POINT({lng} {lat})", srid=4326)


def _base_query(origin: WKTElement | None) -> Select[Any]:
    geom = cast(Listing.location, Geometry)
    cols: list[Any] = [Listing, func.ST_Y(geom).label("lat"), func.ST_X(geom).label("lng")]
    if origin is not None:
        cols.append(
            (func.ST_Distance(Listing.location, cast(origin, Geography)) / 1000.0).label("dist_km")
        )
    return select(*cols)


def _to_out(row: Any, urls: dict[str, str]) -> ListingOut:
    listing: Listing = row[0]
    out = ListingOut.model_validate(listing, from_attributes=True)
    if row.lat is not None:
        out.location = GeoPoint(lat=row.lat, lng=row.lng)
    if "dist_km" in row._fields and row.dist_km is not None:
        out.distance_km = round(float(row.dist_km), 1)
    out.images = [
        ListingImageOut(id=img.id, url=urls[img.storage_path], width=img.width, height=img.height)
        for img in listing.images
        if img.storage_path in urls
    ]
    return out


def render_listings(rows: Sequence[Any], storage: PhotoStorage | None) -> list[ListingOut]:
    """Turn query rows into API objects, signing all photo URLs in one storage call."""
    paths = [img.storage_path for row in rows for img in row[0].images]
    urls = storage.signed_urls(paths) if storage is not None and paths else {}
    return [_to_out(r, urls) for r in rows]


def fetch_listing_out(
    db: Session, listing_id: uuid.UUID, storage: PhotoStorage | None
) -> ListingOut:
    db.expire_all()  # pick up images added in this request
    row = db.execute(_base_query(None).where(Listing.id == listing_id)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    return render_listings([row], storage)[0]


def _get_owned(db: Session, listing_id: uuid.UUID, profile: Profile) -> Listing:
    listing = db.get(Listing, listing_id)
    if listing is None or listing.status == ListingStatus.REMOVED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    if listing.owner_id != profile.id and profile.role not in STAFF:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your listing")
    return listing


def _validate_category(db: Session, category_id: int | None) -> None:
    if category_id is not None and db.get(Category, category_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown category_id")


def _like(term: str) -> str:
    escaped = term.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("", response_model=Page[ListingOut])
def search_listings(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    storage: PhotoStorage | None = Depends(get_storage),
    q: str | None = Query(default=None, max_length=100),
    listing_type: ListingType | None = None,
    category: str | None = Query(default=None, description="Category slug"),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float | None = Query(default=None, gt=0, le=200),
    sort: str = Query(
        default="newest", pattern="^(newest|nearest|price_asc|price_desc|relevance)$"
    ),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[ListingOut]:
    origin = None
    if (lat is None) != (lng is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Provide both lat and lng")
    if lat is not None and lng is not None:
        origin = WKTElement(f"POINT({lng} {lat})", srid=4326)
    elif sort == "nearest" or radius_km:
        origin = WKTElement(f"POINT({settings.default_lng} {settings.default_lat})", srid=4326)

    stmt = _base_query(origin).where(Listing.status == ListingStatus.ACTIVE)
    filters = []
    if listing_type:
        filters.append(Listing.listing_type == listing_type)
    if category:
        stmt = stmt.join(Category, Listing.category_id == Category.id)
        filters.append(Category.slug == category)
    tsquery = None
    if q and q.strip():
        # English: stemmed full-text search ("sarees" finds "saree"). Telugu has no Postgres
        # stemmer, so Telugu text (and partial English titles) match by substring, which the
        # trigram indexes accelerate.
        # Literal regconfig: a bound parameter would be sent as VARCHAR, which has no cast.
        tsquery = func.websearch_to_tsquery(literal_column("'english'::regconfig"), q)
        pattern = _like(q)
        filters.append(
            or_(
                Listing.search_vector.op("@@")(tsquery),
                Listing.title_en.ilike(pattern, escape="\\"),
                Listing.title_te.ilike(pattern, escape="\\"),
                Listing.description_te.ilike(pattern, escape="\\"),
            )
        )
    if origin is not None and radius_km:
        filters.append(func.ST_DWithin(Listing.location, cast(origin, Geography), radius_km * 1000))
    stmt = stmt.where(*filters)

    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0

    if sort == "nearest" and origin is not None:
        stmt = stmt.order_by(func.ST_Distance(Listing.location, cast(origin, Geography)))
    elif sort == "price_asc":
        stmt = stmt.order_by(Listing.price_cents.asc().nulls_last())
    elif sort == "price_desc":
        stmt = stmt.order_by(Listing.price_cents.desc().nulls_last())
    elif sort == "relevance" and tsquery is not None:
        stmt = stmt.order_by(func.ts_rank(Listing.search_vector, tsquery).desc())
    stmt = stmt.order_by(Listing.created_at.desc())

    rows = db.execute(stmt.limit(limit).offset(offset)).unique().all()
    return Page(items=render_listings(rows, storage), total=total, limit=limit, offset=offset)


@router.get("/mine", response_model=list[ListingOut])
def my_listings(
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_current_profile),
    storage: PhotoStorage | None = Depends(get_storage),
) -> list[ListingOut]:
    stmt = (
        _base_query(None)
        .where(Listing.owner_id == profile.id, Listing.status != ListingStatus.REMOVED)
        .order_by(Listing.created_at.desc())
    )
    return render_listings(db.execute(stmt).unique().all(), storage)


@router.get("/{listing_id}", response_model=ListingOut)
def get_listing(
    listing_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser | None = Depends(get_optional_user),
    storage: PhotoStorage | None = Depends(get_storage),
) -> ListingOut:
    listing = db.get(Listing, listing_id)
    if listing is None or listing.status == ListingStatus.REMOVED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    if listing.status not in PUBLIC_STATUSES:
        # Drafts and listings awaiting moderation are visible only to their owner and staff.
        viewer = db.get(Profile, user.id) if user else None
        if viewer is None or (viewer.id != listing.owner_id and viewer.role not in STAFF):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    return fetch_listing_out(db, listing_id, storage)


@router.post("", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
def create_listing(
    payload: ListingCreate,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_current_profile),
    storage: PhotoStorage | None = Depends(get_storage),
) -> ListingOut:
    _validate_category(db, payload.category_id)
    data = payload.model_dump(exclude={"location"})
    listing = Listing(**data, owner_id=profile.id)
    if payload.location:
        listing.location = _point(payload.location)
    db.add(listing)
    db.commit()
    return fetch_listing_out(db, listing.id, storage)


@router.patch("/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: uuid.UUID,
    payload: ListingUpdate,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_current_profile),
    storage: PhotoStorage | None = Depends(get_storage),
) -> ListingOut:
    listing = _get_owned(db, listing_id, profile)
    changes = payload.model_dump(exclude_unset=True, exclude={"location"})
    is_staff = profile.role in STAFF
    if "status" in changes and listing.status == ListingStatus.PENDING_REVIEW and not is_staff:
        raise HTTPException(status.HTTP_409_CONFLICT, "Listing is awaiting moderation")
    if "category_id" in changes:
        _validate_category(db, changes["category_id"])
    for key, value in changes.items():
        setattr(listing, key, value)
    if "location" in payload.model_fields_set:
        listing.location = _point(payload.location) if payload.location else None
    if listing.listing_type == ListingType.FREE and listing.price_cents:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Free listings cannot have a price"
        )
    if not (listing.title_en or listing.title_te):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A title is required")
    if (
        listing.status == ListingStatus.ACTIVE
        and listing.listing_type == ListingType.SELL
        and listing.price_cents is None
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Items for sale need a price")
    db.commit()
    return fetch_listing_out(db, listing.id, storage)


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_listing(
    listing_id: uuid.UUID,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_current_profile),
) -> None:
    listing = _get_owned(db, listing_id, profile)
    listing.status = ListingStatus.REMOVED  # soft delete: keeps moderation history
    db.commit()


# ---------------------------------------------------------------- photos


@router.post("/{listing_id}/images", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
def add_images(
    listing_id: uuid.UUID,
    photos: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    profile: Profile = Depends(get_current_profile),
    storage: PhotoStorage = Depends(require_storage),
) -> ListingOut:
    listing = _get_owned(db, listing_id, profile)
    existing = len(listing.images)
    processed = read_photos(
        photos, settings, max_count=max(settings.max_photos_per_listing - existing, 0)
    )
    start = max((img.position for img in listing.images), default=-1) + 1
    rows = store_photos(storage, listing, processed, start=start)
    db.add_all(rows)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete([r.storage_path for r in rows])
        raise
    return fetch_listing_out(db, listing.id, storage)


@router.delete("/{listing_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(
    listing_id: uuid.UUID,
    image_id: uuid.UUID,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_current_profile),
    storage: PhotoStorage = Depends(require_storage),
) -> None:
    listing = _get_owned(db, listing_id, profile)
    image = db.get(ListingImage, image_id)
    if image is None or image.listing_id != listing.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found")
    path = image.storage_path
    db.delete(image)
    db.commit()
    storage.delete([path])
