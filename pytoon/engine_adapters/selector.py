"""Engine selection logic — picks adapter based on policy, health, constraints."""

from __future__ import annotations

from typing import Any

from pytoon.config import get_engine_config
from pytoon.engine_adapters.base import EngineAdapter
from pytoon.engine_adapters.local_comfyui import LocalComfyUIAdapter
from pytoon.engine_adapters.api_adapter import APIEngineAdapter
from pytoon.log import get_logger
from pytoon.metrics import FALLBACK_USED
from pytoon.models import EnginePolicy

logger = get_logger(__name__)

# Registry of adapter classes by name
_ADAPTER_REGISTRY: dict[str, type[EngineAdapter]] = {
    "local_comfyui": LocalComfyUIAdapter,
    "api_luma": APIEngineAdapter,
}

# Cached adapter instances
_adapter_instances: dict[str, EngineAdapter] = {}


def get_adapter(name: str) -> EngineAdapter:
    if name not in _adapter_instances:
        cls = _ADAPTER_REGISTRY.get(name)
        if cls is None:
            raise ValueError(f"Unknown engine adapter: {name}")
        _adapter_instances[name] = cls()
    return _adapter_instances[name]


def get_fallback_chain() -> list[str]:
    cfg = get_engine_config()
    return cfg.get("engine_fallback_chain", ["local_comfyui", "api_luma"])


async def select_engine(
    policy: EnginePolicy,
    archetype: str,
    brand_safe: bool,
) -> EngineAdapter:
    """Select the best engine adapter given policy and constraints.

    Returns the adapter to use. Raises RuntimeError if no engine available.
    """
    chain = get_fallback_chain()

    if policy == EnginePolicy.API_ONLY:
        # Only use API adapters
        for name in chain:
            adapter = get_adapter(name)
            caps = adapter.get_capabilities()
            if caps.get("type") == "api":
                healthy = await adapter.health_check()
                if healthy:
                    return adapter
        raise RuntimeError("No healthy API engine available (policy=api_only)")

    if policy == EnginePolicy.LOCAL_ONLY:
        for name in chain:
            adapter = get_adapter(name)
            caps = adapter.get_capabilities()
            if caps.get("type") == "local":
                healthy = await adapter.health_check()
                if healthy:
                    return adapter
        raise RuntimeError("No healthy local engine available (policy=local_only)")

    # LOCAL_PREFERRED — try local first, then fallback to API
    for name in chain:
        adapter = get_adapter(name)
        healthy = await adapter.health_check()
        if healthy:
            caps = adapter.get_capabilities()
            if archetype in caps.get("archetypes", []):
                return adapter

    # Nothing healthy — last resort
    FALLBACK_USED.labels(fallback_type="engine_fallback").inc()
    logger.warning("no_healthy_engine", policy=policy.value)
    raise RuntimeError("No healthy engine available in fallback chain")


async def select_engine_with_fallback(
    policy: EnginePolicy,
    archetype: str,
    brand_safe: bool,
) -> tuple[EngineAdapter, bool]:
    """Like select_engine but returns (adapter, fallback_used) tuple.

    If the primary engine selection fails, tries the entire chain
    regardless of policy as a final attempt.
    """
    try:
        adapter = await select_engine(policy, archetype, brand_safe)
        return adapter, False
    except RuntimeError:
        # Absolute fallback — try anything alive
        chain = get_fallback_chain()
        for name in chain:
            try:
                adapter = get_adapter(name)
                if await adapter.health_check():
                    FALLBACK_USED.labels(fallback_type="engine_fallback").inc()
                    logger.warning("engine_fallback_used", engine=name)
                    return adapter, True
            except Exception:
                continue
        raise RuntimeError("All engines exhausted, no fallback available")
