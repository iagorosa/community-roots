"""`StorageBackend` — the protocol every photo storage implementation follows.

Exists as its own module (rather than living next to `LocalFilesystemStorage`)
so callers that only need the interface — the FastAPI dependency, a future
`S3Storage` — don't import filesystem-specific code to get it. See
docs/architecture.md §6 for the literal signature and the rationale: routes
and services program against this `Protocol`, never against
`LocalFilesystemStorage` directly, so swapping to S3 later touches only
`app/storage/`, not the callers.
"""

from typing import BinaryIO, Protocol


class StorageBackend(Protocol):
    def save(self, key: str, data: BinaryIO, content_type: str) -> None: ...

    def open(self, key: str) -> BinaryIO: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...
