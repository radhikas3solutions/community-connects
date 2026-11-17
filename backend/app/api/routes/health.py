from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok"}


@router.get("/health/ready")
def ready(response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    """Readiness: database and PostGIS reachable."""
    try:
        version = db.execute(text("SELECT postgis_version()")).scalar_one()
        return {"status": "ok", "postgis": str(version)}
    except Exception:  # noqa: BLE001 - report, never crash the probe
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable"}
