"""Single mount point for all route modules.

Route modules (health, regions, photos, ...) register themselves on this
router as they are implemented in later issues; `app.main` only ever imports
`api_router`, so it never needs to know which route modules currently exist.
"""

from fastapi import APIRouter

api_router = APIRouter()
