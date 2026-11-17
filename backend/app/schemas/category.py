from app.models.enums import CategoryKind
from app.schemas.common import ORMModel


class CategoryOut(ORMModel):
    id: int
    slug: str
    kind: CategoryKind
    name_en: str
    name_te: str
    icon: str | None
    parent_id: int | None
    is_community_specific: bool
