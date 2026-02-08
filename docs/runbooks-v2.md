# V2 Operational Runbooks

**Ticket:** P5-17

---

## 1. Engine Health Monitoring

### Symptoms
- Scene render failures increasing
- Jobs stuck in `rendering_scenes`
- Prometheus metric `pytoon_v2_engine_invocations_total{result="failure"}` spiking

### Investigation
1. Check engine API status pages:
   - Runway: https://status.runwayml.com
   - Pika: https://status.pika.art
   - Luma: https://status.lumalabs.ai
2. Check API key validity: `echo $RUNWAY_API_KEY | head -c 5`
3. Check metrics: `curl localhost:8000/metrics | grep v2_engine`
4. Check logs: `docker compose logs worker | grep engine_fallback`

### Resolution
- If one engine is down: the fallback chain handles it automatically. Monitor `pytoon_v2_engine_fallbacks_total`.
- If all engines are down: local FFmpeg fallback activates. Videos will be simpler but functional.
- For API key issues: rotate keys via `.env` file and restart: `docker compose restart worker`

---

## 2. Fallback Spike Handling

### Symptoms
- `pytoon_v2_engine_fallbacks_total` counter rising rapidly
- Multiple jobs using `local` engine
- Visual quality degradation reports

### Investigation
1. Identify which engine is failing: `grep "engine_fallback" /var/log/pytoon/*.log`
2. Check engine rotation: metric `engine_rotation_triggered` in logs
3. Verify engine rate limits haven't been exceeded

### Resolution
1. If rate-limited: reduce `max_concurrent` in engine config, or add backoff
2. If engine is degraded: temporarily disable in `config/engine.yaml` by setting `enabled: false`
3. If persistent: escalate to engine provider support

---

## 3. TTS Troubleshooting

### Symptoms
- Videos with no voiceover
- `pytoon_v2_tts_failure_total` increasing
- "All TTS providers failed" in logs

### Investigation
1. Check TTS API keys: `ELEVENLABS_API_KEY`, `OPENAI_API_KEY`
2. Check provider status pages
3. Check logs: `grep "tts_provider_failed" worker.log`

### Resolution
- Verify API keys are set: `docker compose exec worker env | grep API_KEY`
- Try backup provider: update `config/defaults.yaml` → `tts.primary_provider`
- If all cloud TTS fail: local pyttsx3 fallback or silence track will be used

---

## 4. Caption Alignment Quality

### Symptoms
- Captions appear out of sync with voiceover
- `pytoon_v2_caption_alignment_ms` metric showing high values
- "alignment_fallback_to_even_split" in logs

### Investigation
1. Check which alignment method was used: `grep "alignment_" worker.log`
2. Check if WhisperX/stable-ts are installed: `pip list | grep -i whisper`
3. Check audio quality (noisy recordings cause poor alignment)

### Resolution
- Install WhisperX for best accuracy: `pip install whisperx`
- For noisy audio: pre-process with noise reduction before alignment
- Even-split fallback works but has ~±200ms accuracy vs ±50ms with WhisperX

---

## 5. Adding a New Engine Adapter

1. Create `pytoon/engine_adapters/new_engine.py` implementing `ExternalEngineAdapter`
2. Implement: `generate()`, `health_check()`, `max_duration()`, `supports_image_input()`
3. Register in `engine_manager._get_engine()` name-to-class mapping
4. Add config in `config/engine.yaml` under `v2.engines`
5. Add to fallback chain if desired
6. Add acceptance tests in `tests/v2/`
7. Update metrics labels

---

## 6. Updating Engine Selection Rules

Config-driven approach (no code changes needed):

1. Edit `config/engine.yaml` → `v2.preset_engine_prefs`
2. Add per-preset engine preferences:
   ```yaml
   preset_engine_prefs:
     my_new_preset:
       preferred_engine: luma
       fallback_override: [luma, runway, pika]
   ```
3. Restart worker: `docker compose restart worker`

Code-driven (for new selection logic):
1. Modify `pytoon/engine_adapters/engine_selector.py` → `resolve_engine()`
2. Add new capability keywords to `config/engine.yaml` → `v2.engines.*.capabilities`

---

## 7. API Key Rotation

1. Generate new keys from provider dashboards
2. Update `.env` file:
   ```
   RUNWAY_API_KEY=new_key_here
   OPENAI_API_KEY=new_key_here
   ```
3. Restart services: `docker compose restart api worker`
4. Verify: `docker compose logs api | grep "health_check"`

**Important:** Never log API keys. The `_sanitize_sensitive_data` log processor redacts them automatically.

---

## 8. Audio Sync Debugging

### Symptoms
- Audio/video out of sync in final output
- Captions not matching voice timing

### Investigation
1. Check timeline JSON: `cat storage/jobs/{id}/timeline.json | jq .tracks`
2. Check voice mapper output: `grep "voice_mapped" worker.log`
3. Check alignment method: `grep "alignment_" worker.log`
4. Verify audio duration: `ffprobe -show_entries format=duration storage/jobs/{id}/assembly/audio/mixed.wav`

### Resolution
- If TTS duration mismatch: check `voice_processor.py` trimming behavior
- If alignment inaccurate: install WhisperX for word-level precision
- If mixing issue: check `mixer.py` target_duration_seconds parameter
- If normalization issue: check `loudnorm` output LUFS values in logs
