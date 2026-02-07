# Local setup

## Prereqs

- Docker Desktop + NVIDIA Container Toolkit
- NVIDIA driver compatible with your GPU
- Optional: Python 3.11 for local dev tooling

## Start stack

1. Copy `.env.example` to `.env`
2. Start services:
   - `docker-compose up -d`
3. Check ports:
   - API: `localhost:8080`
   - ComfyUI: `localhost:8188`
   - MinIO: `localhost:9000` / console `:9001`

## Notes

- Default DB uses SQLite at `/data/pytoon.db`
- Switch to Postgres by setting `DB_URL` and enabling migrations
