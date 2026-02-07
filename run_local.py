"""Local dev launcher — runs API + embedded worker in a single process.

Usage:
    python run_local.py

No Redis or Docker needed. Uses fakeredis in-memory queue + SQLite.
"""

import os
import sys
from pathlib import Path

# Ensure storage and data dirs exist
root = Path(__file__).parent
(root / "storage").mkdir(exist_ok=True)
(root / "data").mkdir(exist_ok=True)

# Set local-friendly env defaults (won't override if already set)
os.environ.setdefault("PYTOON_ENV", "local")
os.environ.setdefault("API_KEY", "dev-key-change-me")
os.environ.setdefault("DB_URL", f"sqlite:///{root / 'data' / 'pytoon.db'}")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("STORAGE_ROOT", str(root / "storage"))
os.environ.setdefault("COMFYUI_BASE_URL", "http://localhost:8188")

# Enable embedded worker before importing the app
from pytoon.api_orchestrator.app import enable_embedded_worker, create_app

enable_embedded_worker()
app = create_app()

if __name__ == "__main__":
    import uvicorn

    print()
    print("=" * 60)
    print("  Pytoon Render Engine — Local Dev Mode")
    print("=" * 60)
    print(f"  API:     http://localhost:8080")
    print(f"  Docs:    http://localhost:8080/docs")
    print(f"  Metrics: http://localhost:8080/metrics")
    print(f"  API Key: {os.environ['API_KEY']}")
    print(f"  DB:      {os.environ['DB_URL']}")
    print(f"  Storage: {os.environ['STORAGE_ROOT']}")
    print("=" * 60)
    print()

    uvicorn.run(
        "run_local:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        reload_dirs=[str(root / "pytoon")],
    )
