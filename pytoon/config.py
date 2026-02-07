"""Configuration loading from YAML files + env vars."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_DIR = _PROJECT_ROOT / "config"


# ---------------------------------------------------------------------------
# Pydantic settings (env‑var overrides)
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    pytoon_env: str = "local"
    api_port: int = 8080
    api_key: str = "dev-key-change-me"
    worker_concurrency: int = 1
    engine_policy_default: str = "local_preferred"
    brand_safe_default: bool = True
    comfyui_base_url: str = "http://comfyui:8188"
    api_engine_base_url: str = ""
    api_engine_key: str = ""
    storage_backend: str = "filesystem"
    storage_root: str = str(_PROJECT_ROOT / "storage")
    db_url: str = f"sqlite:///{_PROJECT_ROOT / 'data' / 'pytoon.db'}"
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# ---------------------------------------------------------------------------
# YAML config helpers
# ---------------------------------------------------------------------------

def _load_yaml(name: str) -> dict[str, Any]:
    path = _CONFIG_DIR / name
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@lru_cache()
def get_defaults() -> dict[str, Any]:
    return _load_yaml("defaults.yaml")


@lru_cache()
def get_presets_map() -> dict[str, dict[str, Any]]:
    raw = _load_yaml("presets.yaml")
    presets = raw.get("presets", [])
    return {p["id"]: p for p in presets}


@lru_cache()
def get_engine_config() -> dict[str, Any]:
    return _load_yaml("engine.yaml")


def get_preset(preset_id: str) -> dict[str, Any] | None:
    return get_presets_map().get(preset_id)
