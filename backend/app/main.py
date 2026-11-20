import logging

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    ai,
    ask,
    assistant,
    businesses,
    categories,
    health,
    imports,
    listings,
    me,
)
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AskMitra API",
        version="0.1.0",
        description="Northern Virginia community marketplace, directory and events.",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(health.router)
    v1 = APIRouter(prefix="/api/v1")
    for module in (me, categories, listings, ai, businesses, assistant, ask, imports):
        v1.include_router(module.router)
    app.include_router(v1)
    return app


app = create_app()
