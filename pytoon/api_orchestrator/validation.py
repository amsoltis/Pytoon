"""Input validation helpers for uploaded assets."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from pytoon.config import get_defaults

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
ALLOWED_AUDIO_TYPES = {"audio/mpeg", "audio/wav", "audio/x-wav"}
ALLOWED_MASK_TYPES = {"image/png"}

ALLOWED_EXTENSIONS_IMAGE = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_EXTENSIONS_AUDIO = {".mp3", ".wav"}


def validate_upload(file: UploadFile, category: str = "image") -> None:
    """Raise 400 if file is unsupported."""
    defaults = get_defaults()
    max_mb = defaults.get("limits", {}).get("max_asset_mb", 20)

    # Check content type
    ct = (file.content_type or "").lower()
    if category == "image" and ct not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Unsupported image type: {ct}")
    if category == "mask" and ct not in ALLOWED_MASK_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Mask must be PNG with alpha, got: {ct}")
    if category == "audio" and ct not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Unsupported audio type: {ct}")

    # Check file size (UploadFile doesn't always have size; read-and-check)
    if file.size and file.size > max_mb * 1024 * 1024:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"File exceeds {max_mb}MB limit")


def validate_image_dimensions(width: int, height: int) -> None:
    defaults = get_defaults()
    max_edge = defaults.get("limits", {}).get("max_image_edge_px", 4096)
    if max(width, height) > max_edge:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Image dimensions exceed {max_edge}px limit: {width}x{height}",
        )
