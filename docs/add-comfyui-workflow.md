# Add a ComfyUI workflow

Local workflows live under `engine_adapters/local/workflows/`.

## Steps

1. Export workflow JSON from ComfyUI
2. Save under `engine_adapters/local/workflows/<name>.json`
3. Add a mapping entry in adapter config:
   - `archetype -> workflow_name`
4. Validate I/O nodes match the adapter input contract

## Notes

- Keep brand-safe variants separate (overlay workflow)
- Prefer deterministic seeds for reproducibility
