"""Tests for `app/storage/local.py`: `LocalFilesystemStorage`. See
docs/architecture.md §6 for the `StorageBackend` protocol this implements.

Every test writes under `tmp_path`, never `backend/storage/` — see
docs/architecture.md §6 and the module docstring of `tests/conftest.py` on why
tests must never touch real on-disk/database state.
"""

from pathlib import Path

import pytest

from app.storage.local import LocalFilesystemStorage


def test_open_reads_back_bytes_written_directly_to_disk(tmp_path: Path) -> None:
    (tmp_path / "photos").mkdir()
    (tmp_path / "photos" / "a.png").write_bytes(b"fake-png-bytes")
    storage = LocalFilesystemStorage(tmp_path)

    with storage.open("photos/a.png") as file:
        assert file.read() == b"fake-png-bytes"


def test_open_missing_key_raises_file_not_found(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(tmp_path)

    with pytest.raises(FileNotFoundError):
        storage.open("photos/does-not-exist.png")


def test_exists_true_for_a_key_present_on_disk(tmp_path: Path) -> None:
    (tmp_path / "photos").mkdir()
    (tmp_path / "photos" / "a.png").write_bytes(b"fake-png-bytes")
    storage = LocalFilesystemStorage(tmp_path)

    assert storage.exists("photos/a.png") is True


def test_exists_false_for_a_key_absent_from_disk(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(tmp_path)

    assert storage.exists("photos/does-not-exist.png") is False
