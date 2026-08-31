"""Single mount point for all route modules.

Route modules (health, regions, plantings, photos, ...) register themselves
on this router as they are implemented; `app.main` only ever imports
`api_router`, so it never needs to know which route modules currently exist.
"""

from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.photos import file_router as photo_files_router
from app.api.routes.photos import router as photos_router
from app.api.routes.plantings import router as plantings_router
from app.api.routes.regions import router as regions_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(regions_router)
api_router.include_router(plantings_router)
api_router.include_router(photos_router)
api_router.include_router(photo_files_router)
