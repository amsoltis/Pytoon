"""Storage abstraction — filesystem for V1, S3/MinIO-ready interface."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import BinaryIO

from pytoon.config import get_settings


class StorageBackend:
    """Simple filesystem storage."""

    def __init__(self, root: str | None = None):
        settings = get_settings()
        self.root = Path(root or settings.storage_root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ---- write ---------------------------------------------------------

    def save_bytes(self, key: str, data: bytes) -> str:
        dest = self.root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return self.uri(key)

    def save_file(self, key: str, src: str | Path) -> str:
        dest = self.root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dest))
        return self.uri(key)

    def save_stream(self, key: str, stream: BinaryIO) -> str:
        dest = self.root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as fh:
            while chunk := stream.read(1024 * 256):
                fh.write(chunk)
        return self.uri(key)

    # ---- read ----------------------------------------------------------

    def read_bytes(self, key: str) -> bytes:
        return (self.root / key).read_bytes()

    def local_path(self, key: str) -> Path:
        return self.root / key

    def exists(self, key: str) -> bool:
        return (self.root / key).exists()

    # ---- uri -----------------------------------------------------------

    def uri(self, key: str) -> str:
        return f"file://{self.root / key}"

    def key_from_uri(self, uri: str) -> str:
        prefix = f"file://{self.root}/"
        if uri.startswith(prefix):
            return uri[len(prefix):]
        if uri.startswith("file://"):
            return uri[len("file://"):]
        return uri


def get_storage() -> StorageBackend:
    return StorageBackend()
