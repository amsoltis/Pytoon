"""API-key authentication dependency."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from pytoon.config import get_settings


async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    settings = get_settings()
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
