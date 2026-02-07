# Add an engine adapter

Adapters live in `engine_adapters/` and must implement a consistent interface.

## Steps

1. Create a new adapter module under `engine_adapters/<name>/`
2. Implement:
   - `health_check()`
   - `render_segment(render_spec, segment_index)`
   - `get_capabilities()`
3. Register the adapter in configuration
4. Add it to the `engine_fallback_chain`

## Notes

- Adapters should respect `engine_policy` and `brand_safe`
- Return structured errors for observability
