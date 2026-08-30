"""FastAPI application factory.

Kept deliberately thin: configuration, CORS and error handling are wired
here; actual behavior lives in the routers, services and models that later
issues add under `app/api/routes`.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings
from app.core.errors import register_error_handlers


def create_app() -> FastAPI:
    app = FastAPI(
        title="Community Roots API",
        description="API do canteiro digital do Community Roots.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(api_router)

    return app


app = create_app()
