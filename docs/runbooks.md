# Pytoon V1 — Operational Runbooks

> **Ticket:** P5-12  
> **AC:** AC-021

---

## 1. Starting and Stopping the System

### Local Dev Mode
```bash
# Start (API + worker in one process)
python run_local.py

# Stop: Ctrl+C (graceful shutdown with SIGINT handling)
```

### Docker Compose
```bash
# Start all services
docker-compose up -d

# Stop all services (preserves data volumes)
docker-compose down

# Stop and remove data volumes
docker-compose down -v

# Restart a single service
docker-compose restart worker
```

---

## 2. Monitoring Health

### Health Check
```bash
curl http://localhost:8080/health
# Expected: {"status": "ok"}
```

### Metrics Check
```bash
curl http://localhost:8080/metrics | grep pytoon_
```

### Key Metrics to Watch

| Metric | Healthy Range | Alert If |
|---|---|---|
| `pytoon_render_success_total` | Increasing | Stops increasing for >5 min |
| `pytoon_render_failure_total` | Low/zero | Sudden spike |
| `pytoon_fallback_total` | Low/zero | >10% of total jobs |
| `pytoon_queue_depth` | 0–10 | >50 (jobs backing up) |
| `pytoon_segment_render_seconds` | 1–30s | >60s consistently |
| `pytoon_job_total_seconds` | 10–120s | >300s consistently |

### Log Monitoring
```bash
# Docker: follow worker logs
docker-compose logs -f worker

# Key log events to watch:
#   job_created       — new job submitted
#   job_dequeued      — worker picked up job
#   segment_rendered  — segment completed
#   assembly_complete — job finished
#   engine_fallback_used — fallback triggered (investigate)
#   job_runner_crash  — critical error (investigate immediately)
```

---

## 3. Handling a Stuck Job

### Identify Stuck Jobs
A job is "stuck" if it has been in PLANNING, RENDERING_SEGMENTS, or ASSEMBLING status for more than 10 minutes.

```bash
# Check via API
curl -H "X-API-Key: <key>" http://localhost:8080/api/v1/jobs/<job_id>
```

### Force-Fail a Stuck Job
There is no dedicated admin endpoint in V1. To force-fail a stuck job:

1. **Restart the worker** — on startup, the worker resumes all in-flight jobs. If the underlying issue is transient, the job may complete.

```bash
docker-compose restart worker
```

2. **Direct DB update** (last resort):
```sql
UPDATE jobs SET status = 'FAILED', error = 'Manual intervention: stuck job'
WHERE id = '<job_id>' AND status IN ('PLANNING', 'RENDERING_SEGMENTS', 'ASSEMBLING');
```

### Re-queue a Failed Job
Submit a new job with the same parameters. V1 does not support retrying existing jobs.

---

## 4. Handling Engine Fallback Spikes

If `pytoon_fallback_total` is spiking, investigate:

### Check Local Engine Health
```bash
# FFmpeg available?
ffmpeg -version

# ComfyUI healthy?
curl http://localhost:8188/system_stats
```

### Common Causes

| Symptom | Likely Cause | Fix |
|---|---|---|
| All jobs fallback to API | FFmpeg not installed / missing from PATH | Install FFmpeg |
| All jobs fallback to API | ComfyUI service down | `docker-compose restart comfyui` |
| Intermittent fallback | GPU memory exhausted | Reduce concurrent workers or restart ComfyUI |
| Template fallback | All engines down | Check connectivity to all engines |

### Temporary Workaround
Force all jobs to use the API engine:
```bash
# Set default engine policy to api_only (in .env or env var)
ENGINE_POLICY_DEFAULT=api_only
```

---

## 5. Scaling Workers

### Add More Workers (Docker Compose)
```bash
docker-compose up -d --scale worker=3
```

All workers share the same Redis queue and will automatically distribute jobs.

### Considerations
- Each worker needs access to the same storage volume
- Each worker needs FFmpeg installed
- SQLite does not support multiple concurrent writers — switch to PostgreSQL for multi-worker deployments

### Switch to PostgreSQL
```bash
# In .env:
DB_URL=postgresql://pytoon:password@postgres:5432/pytoon
```

---

## 6. Backup and Restore

### What to Back Up

| Component | Location | Method |
|---|---|---|
| Database | `data/pytoon.db` (SQLite) | `cp data/pytoon.db data/pytoon.db.bak` |
| Storage | `storage/` directory | Filesystem backup or rsync |
| Config | `config/*.yaml` | Include in version control |
| Environment | `.env` file | Include in secrets management |

### Restore from Backup
```bash
# Stop services
docker-compose down

# Restore database
cp data/pytoon.db.bak data/pytoon.db

# Restore storage
rsync -a backup/storage/ storage/

# Start services
docker-compose up -d
```

---

## 7. Upgrading / Redeploying Without Losing In-Flight Jobs

### Zero-Downtime Deployment Steps

1. **Stop accepting new jobs** (optional — or let the queue absorb them):
   ```bash
   # No built-in mechanism in V1. Consider putting a load balancer in maintenance mode.
   ```

2. **Wait for in-flight jobs to complete:**
   ```bash
   # Check queue depth
   curl http://localhost:8080/metrics | grep pytoon_queue_depth
   # Wait until pytoon_queue_depth == 0
   ```

3. **Deploy new code:**
   ```bash
   docker-compose build
   docker-compose up -d
   ```

4. **If you must deploy with in-flight jobs:**
   - Jobs in RENDERING_SEGMENTS or ASSEMBLING will be **resumed** automatically on worker startup
   - The worker's `_resume_interrupted()` function finds all in-flight jobs and re-runs them
   - Segments that were already DONE are not re-rendered (resume logic skips them)

### Rollback
```bash
# Revert to previous image
docker-compose down
git checkout <previous-tag>
docker-compose build
docker-compose up -d
```

---

## 8. Troubleshooting Quick Reference

| Problem | Check | Fix |
|---|---|---|
| API returns 500 | Worker logs | Check for crash trace, restart worker |
| Jobs stuck in QUEUED | Redis connectivity | `redis-cli ping`, restart Redis |
| Jobs stuck in RENDERING | Engine health | Check FFmpeg/ComfyUI, restart engines |
| Blank/corrupt video | Segment artifacts | Check `storage/jobs/<id>/segments/` for valid MP4s |
| High memory usage | 60s video assembly | Ensure temp files are cleaned up in assembly/ |
| Slow renders | Prometheus metrics | Check `pytoon_segment_render_seconds` histogram |
