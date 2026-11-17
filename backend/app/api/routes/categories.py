from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Category
from app.models.enums import CategoryKind
from app.schemas.category import CategoryOut

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(
    response: Response,
    kind: CategoryKind | None = None,
    db: Session = Depends(get_db),
) -> list[Category]:
    stmt = select(Category).where(Category.is_active.is_(True))
    if kind:
        stmt = stmt.where(Category.kind == kind)
    stmt = stmt.order_by(Category.kind, Category.sort_order, Category.name_en)
    response.headers["Cache-Control"] = "public, max-age=300"
    return list(db.scalars(stmt))
