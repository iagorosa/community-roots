"""FastAPI dependency selecting the configured `StorageBackend` implementation.

Kept separate from `app/db/session.py`'s `get_db` pattern only by module, not
by shape: same "cheap-to-construct, one-per-request, overridable via
`app.dependency_overrides` in tests" design (see `tests/conftest.py`'s
`db_session`/`get_db` pair for the precedent this follows).
"""

from app.core.config import settings
from app.storage.base import StorageBackend
from app.storage.local import LocalFilesystemStorage


def get_storage_backend() -> StorageBackend:
    """Select the `StorageBackend` implementation configured by
    `settings.storage_backend`.

    Only `"local"` exists today — `Settings.storage_backend` is typed as
    `Literal["local"]`, so this `if` is exhaustive as written. It's still an
    `if`, not a bare `return LocalFilesystemStorage(...)`, so the extension
    point for a future `S3Storage` branch (architecture.md §6, "amanhã ele
    devolve um 302 para uma URL assinada do S3") is visible here rather than
    requiring a rewrite of this function's shape.
    """
    if settings.storage_backend == "local":
        return LocalFilesystemStorage(settings.local_storage_path)

    raise NotImplementedError(f"Backend de storage não suportado: {settings.storage_backend!r}")
