import pytest
from pydantic import ValidationError

from app.models.enums import ListingStatus, ListingType
from app.schemas.listing import ListingCreate, ListingUpdate
from app.schemas.profile import ProfileUpdate


def test_free_listing_forces_zero_price() -> None:
    listing = ListingCreate(listing_type=ListingType.FREE, title_en="Free couch")
    assert listing.price_cents == 0


def test_free_listing_with_price_rejected() -> None:
    with pytest.raises(ValidationError, match="Free listings"):
        ListingCreate(listing_type=ListingType.FREE, title_en="Couch", price_cents=500)


def test_sell_listing_needs_price() -> None:
    with pytest.raises(ValidationError, match="need a price"):
        ListingCreate(listing_type=ListingType.SELL, title_en="Bike")


def test_buy_listing_without_price_ok() -> None:
    assert ListingCreate(listing_type=ListingType.BUY, title_en="Looking for a crib")


def test_title_required_in_some_language() -> None:
    with pytest.raises(ValidationError, match="title"):
        ListingCreate(listing_type=ListingType.BUY)


def test_telugu_only_title_ok() -> None:
    listing = ListingCreate(listing_type=ListingType.FREE, title_te="ఉచిత సోఫా", source_language="te")
    assert listing.title_te == "ఉచిత సోఫా"


def test_owner_cannot_set_moderation_status() -> None:
    with pytest.raises(ValidationError):
        ListingUpdate(status=ListingStatus.REMOVED)
    assert ListingUpdate(status=ListingStatus.SOLD).status == ListingStatus.SOLD


def test_profile_zip_validation() -> None:
    assert ProfileUpdate(zip_code="22030").zip_code == "22030"
    with pytest.raises(ValidationError):
        ProfileUpdate(zip_code="ABCDE")
