"""`LocalFilesystemStorage` — the MVP's only `StorageBackend` implementation.
Reads and writes under `settings.local_storage_path` (default `backend/storage/`,
outside Git — see `.gitignore`). See docs/architecture.md §6.
"""

import shutil
from pathlib import Path
from typing import BinaryIO


class LocalFilesystemStorage:
    """Stores each photo as a plain file at `<root>/<key>`.

    Satisfies `app.storage.base.StorageBackend` structurally — it's a
    `Protocol`, so no explicit inheritance is needed.
    """

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def _path_for(self, key: str) -> Path:
        # No path-traversal guard (`../`, absolute paths, etc.): `key` is
        # always `Photo.storage_key`, itself always server-generated
        # (`regions/{region_id}/{ano}/{uuid4}.{ext}`, architecture.md §6) —
        # never taken directly from client input. If a future caller ever
        # passes a client-supplied key, add an `is_relative_to(self._root)`
        # check here first.
        return self._root / key

    def save(self, key: str, data: BinaryIO, content_type: str) -> None:
        """Write `data` to `<root>/<key>`, creating parent directories as needed.

        `content_type` isn't used here — the filesystem has nowhere to store
        it, so the caller persists it separately, on `Photo.content_type`
        (it's kept as a parameter only because it's part of the documented
        `StorageBackend` protocol, architecture.md §6).

        Not exercised by an integration test in this issue: the upload path
        that calls `save` (`POST /api/regions/{region}/photos`) is Phase 5 —
        this method exists now because the protocol it implements is
        specified in full today (architecture.md §6), not because this
        issue's endpoint uses it.
        """
        destination = self._path_for(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as file:
            shutil.copyfileobj(data, file)

    def open(self, key: str) -> BinaryIO:
        """Open `<root>/<key>` for reading.

        Raises the standard library's own `FileNotFoundError` when `key`
        doesn't exist on disk — deliberately not a custom exception, so
        callers (`photo_service.open_photo_file`) can catch the same error
        type regardless of which `StorageBackend` implementation is
        configured, and translate it into a 404 instead of letting it
        surface as a 500.
        """
        return self._path_for(key).open("rb")

    def delete(self, key: str) -> None:
        """Not exercised by a dedicated test in this issue — see `save`."""
        self._path_for(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path_for(key).is_file()
