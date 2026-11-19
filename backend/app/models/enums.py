from enum import StrEnum

from sqlalchemy import Enum as SAEnum


class UserRole(StrEnum):
    USER = "user"
    BUSINESS = "business"
    MODERATOR = "moderator"
    ADMIN = "admin"


class Language(StrEnum):
    EN = "en"
    TE = "te"


class CategoryKind(StrEnum):
    MARKETPLACE = "marketplace"  # items bought / sold / given away
    BUSINESS = "business"  # directory of local businesses & professionals
    COMMUNITY = "community"  # deals, jobs, movies, events (Phase 4)


class ListingType(StrEnum):
    SELL = "sell"
    BUY = "buy"  # "wanted" posts
    FREE = "free"


class ListingStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    SOLD = "sold"
    REMOVED = "removed"


class ItemCondition(StrEnum):
    NEW = "new"
    LIKE_NEW = "like_new"
    GOOD = "good"
    FAIR = "fair"
    FOR_PARTS = "for_parts"


def str_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    """Store enums as VARCHAR + CHECK constraint (easier to evolve than native PG enums)."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


class EntryKind(StrEnum):
    BUSINESS = "business"  # a shop, clinic, restaurant, firm: public address and phone
    # A helper, tutor or tailor working from home: contact details shown to members only.
    INDIVIDUAL = "individual"


class DirectoryStatus(StrEnum):
    PENDING_REVIEW = "pending_review"  # submitted, waiting for a moderator
    ACTIVE = "active"
    REJECTED = "rejected"
    REMOVED = "removed"
