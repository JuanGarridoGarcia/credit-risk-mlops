"""Where training set versions are stored (D-059).

A version is a folder named by its content hash, holding its files. Folders are written
once and never overwritten: a new folder is filled under a temporary name and renamed in
one step, so a reader never sees half a version. The local store is a folder; the S3
store arrives with the AWS phase and keeps the same interface.
"""

import shutil
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol


class StoreError(RuntimeError):
    """A version cannot be saved or read as asked."""


class Store(Protocol):
    """What the snapshot code needs from a store."""

    def has(self, version: str) -> bool:
        """Whether the folder of ``version`` exists."""
        ...

    def save(self, version: str, files: Mapping[str, Path]) -> None:
        """Move ``files`` (name -> local file) into a new version."""
        ...

    def location(self, version: str) -> str:
        """Where the version lives, as recorded in its manifest."""
        ...

    def local(self, version: str, name: str) -> Path:
        """A local path to read file ``name`` of ``version``."""
        ...


class LocalStore:
    """Versions as folders under ``root`` (``data/training_sets`` by default)."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _folder(self, version: str) -> Path:
        if not version.isalnum():
            raise StoreError(f"invalid version {version!r}")
        return self.root / version

    def has(self, version: str) -> bool:
        return self._folder(version).is_dir()

    def save(self, version: str, files: Mapping[str, Path]) -> None:
        target = self._folder(version)
        if target.exists():
            raise StoreError(f"{target} already exists; a version is never overwritten")
        self.root.mkdir(parents=True, exist_ok=True)
        staging = self.root / f".tmp-{uuid.uuid4().hex}"
        staging.mkdir()
        try:
            for name, source in files.items():
                shutil.move(source, staging / name)
            staging.rename(target)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    def location(self, version: str) -> str:
        return str(self._folder(version))

    def local(self, version: str, name: str) -> Path:
        path = self._folder(version) / name
        if not path.is_file():
            raise StoreError(f"{path} is missing")
        return path
