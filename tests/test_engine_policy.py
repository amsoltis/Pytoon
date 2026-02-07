"""C) Engine policy tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pytoon.engine_adapters.selector import select_engine, select_engine_with_fallback
from pytoon.engine_adapters.base import EngineAdapter, SegmentResult
from pytoon.models import EnginePolicy


def _make_adapter(name: str, adapter_type: str, healthy: bool) -> AsyncMock:
    adapter = AsyncMock(spec=EngineAdapter)
    adapter.name = name
    adapter.health_check = AsyncMock(return_value=healthy)
    adapter.get_capabilities = MagicMock(return_value={
        "name": name,
        "type": adapter_type,
        "archetypes": ["PRODUCT_HERO", "OVERLAY", "MEME_TEXT"],
    })
    return adapter


class TestEnginePolicy:
    @pytest.mark.asyncio
    async def test_local_only_local_healthy(self):
        """local_only + local healthy → uses local."""
        local = _make_adapter("local_comfyui", "local", True)
        api = _make_adapter("api_luma", "api", True)

        with patch("pytoon.engine_adapters.selector.get_adapter") as mock_get, \
             patch("pytoon.engine_adapters.selector.get_fallback_chain",
                   return_value=["local_comfyui", "api_luma"]):
            mock_get.side_effect = lambda n: local if n == "local_comfyui" else api
            result = await select_engine(EnginePolicy.LOCAL_ONLY, "OVERLAY", True)
            assert result.name == "local_comfyui"

    @pytest.mark.asyncio
    async def test_local_only_local_down_raises(self):
        """local_only + local down → raises RuntimeError."""
        local = _make_adapter("local_comfyui", "local", False)
        api = _make_adapter("api_luma", "api", True)

        with patch("pytoon.engine_adapters.selector.get_adapter") as mock_get, \
             patch("pytoon.engine_adapters.selector.get_fallback_chain",
                   return_value=["local_comfyui", "api_luma"]):
            mock_get.side_effect = lambda n: local if n == "local_comfyui" else api
            with pytest.raises(RuntimeError, match="No healthy local engine"):
                await select_engine(EnginePolicy.LOCAL_ONLY, "OVERLAY", True)

    @pytest.mark.asyncio
    async def test_local_preferred_local_down_uses_api(self):
        """local_preferred + local down → falls back to API."""
        local = _make_adapter("local_comfyui", "local", False)
        api = _make_adapter("api_luma", "api", True)

        with patch("pytoon.engine_adapters.selector.get_adapter") as mock_get, \
             patch("pytoon.engine_adapters.selector.get_fallback_chain",
                   return_value=["local_comfyui", "api_luma"]):
            mock_get.side_effect = lambda n: local if n == "local_comfyui" else api
            result = await select_engine(EnginePolicy.LOCAL_PREFERRED, "OVERLAY", True)
            assert result.name == "api_luma"

    @pytest.mark.asyncio
    async def test_api_only_uses_api_even_if_local_healthy(self):
        """api_only → uses API even when local is healthy."""
        local = _make_adapter("local_comfyui", "local", True)
        api = _make_adapter("api_luma", "api", True)

        with patch("pytoon.engine_adapters.selector.get_adapter") as mock_get, \
             patch("pytoon.engine_adapters.selector.get_fallback_chain",
                   return_value=["local_comfyui", "api_luma"]):
            mock_get.side_effect = lambda n: local if n == "local_comfyui" else api
            result = await select_engine(EnginePolicy.API_ONLY, "OVERLAY", True)
            assert result.name == "api_luma"

    @pytest.mark.asyncio
    async def test_api_only_no_api_raises(self):
        """api_only + no API healthy → raises."""
        local = _make_adapter("local_comfyui", "local", True)
        api = _make_adapter("api_luma", "api", False)

        with patch("pytoon.engine_adapters.selector.get_adapter") as mock_get, \
             patch("pytoon.engine_adapters.selector.get_fallback_chain",
                   return_value=["local_comfyui", "api_luma"]):
            mock_get.side_effect = lambda n: local if n == "local_comfyui" else api
            with pytest.raises(RuntimeError, match="No healthy API engine"):
                await select_engine(EnginePolicy.API_ONLY, "OVERLAY", True)

    @pytest.mark.asyncio
    async def test_fallback_with_fallback(self):
        """select_engine_with_fallback tries anything as last resort."""
        local = _make_adapter("local_comfyui", "local", False)
        api = _make_adapter("api_luma", "api", True)

        with patch("pytoon.engine_adapters.selector.get_adapter") as mock_get, \
             patch("pytoon.engine_adapters.selector.get_fallback_chain",
                   return_value=["local_comfyui", "api_luma"]):
            mock_get.side_effect = lambda n: local if n == "local_comfyui" else api
            adapter, fallback = await select_engine_with_fallback(
                EnginePolicy.LOCAL_ONLY, "OVERLAY", True,
            )
            assert adapter.name == "api_luma"
            assert fallback is True
