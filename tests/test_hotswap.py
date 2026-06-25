"""
Tests for the /admin/reconfigure hot-swap endpoint.
Tests verify: pool size actually changes, in-flight requests drain gracefully,
and config is updated atomically.

These tests require a running service DB. Run with:
  pytest tests/test_hotswap.py -v --live
or skip with:
  pytest tests/test_hotswap.py -v  (will skip live tests)
"""
import asyncio
import os
import sys
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "service"))


# ── Config swap unit tests (no DB required) ────────────────────────────────────

def test_config_swap_atomic():
    from config import ServiceConfig, get_config, swap_config

    original = get_config()
    new_cfg = ServiceConfig(pool_size=20, query_timeout_ms=2000, cache_ttl_seconds=30)
    swapped = swap_config(new_cfg)

    assert swapped.pool_size == 20
    assert swapped.query_timeout_ms == 2000
    current = get_config()
    assert current.pool_size == 20
    # Restore
    swap_config(original)


def test_config_clamps_are_respected():
    from config_agent import clamp_config, PARAM_BOUNDS

    raw = {"pool_size": 0, "query_timeout_ms": 99999, "cache_ttl_seconds": 5, "batch_size": 50, "retry_interval_ms": 5}
    clamped = clamp_config(raw)

    lo_pool, hi_pool = PARAM_BOUNDS["pool_size"]
    assert clamped["pool_size"] >= lo_pool

    lo_qt, hi_qt = PARAM_BOUNDS["query_timeout_ms"]
    assert clamped["query_timeout_ms"] <= hi_qt

    lo_ri, hi_ri = PARAM_BOUNDS["retry_interval_ms"]
    assert clamped["retry_interval_ms"] >= lo_ri


def test_config_to_dict():
    from config import ServiceConfig

    cfg = ServiceConfig(pool_size=7, cache_ttl_seconds=120)
    d = cfg.to_dict()
    assert d["pool_size"] == 7
    assert d["cache_ttl_seconds"] == 120
    assert "query_timeout_ms" in d


def test_config_update():
    from config import ServiceConfig

    cfg = ServiceConfig(pool_size=5)
    cfg.update(pool_size=15, cache_ttl_seconds=30)
    assert cfg.pool_size == 15
    assert cfg.cache_ttl_seconds == 30


def test_config_update_ignores_unknown_keys():
    from config import ServiceConfig

    cfg = ServiceConfig(pool_size=5)
    cfg.update(pool_size=10, unknown_param="should_be_ignored")
    assert cfg.pool_size == 10


# ── Hot-swap endpoint integration test (requires live service) ─────────────────

LIVE = os.getenv("LIVE_TEST_URL", "")  # set to http://localhost:8000 for live tests


@pytest.mark.skipif(not LIVE, reason="Set LIVE_TEST_URL=http://localhost:8000 to run live tests")
def test_reconfigure_endpoint_changes_pool():
    import httpx

    service_url = LIVE

    # Get current config
    resp = httpx.get(f"{service_url}/admin/config")
    assert resp.status_code == 200
    original_pool = resp.json()["pool_size"]

    new_pool = original_pool + 3 if original_pool < 47 else original_pool - 3

    # Reconfigure
    resp = httpx.post(
        f"{service_url}/admin/reconfigure",
        json={"pool_size": new_pool},
        timeout=30.0,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["new_config"]["pool_size"] == new_pool
    assert data["previous_config"]["pool_size"] == original_pool

    # Verify config is reflected
    resp2 = httpx.get(f"{service_url}/admin/config")
    assert resp2.json()["pool_size"] == new_pool

    # Restore
    httpx.post(f"{service_url}/admin/reconfigure", json={"pool_size": original_pool}, timeout=30.0)


@pytest.mark.skipif(not LIVE, reason="Set LIVE_TEST_URL=http://localhost:8000 to run live tests")
def test_inflight_requests_drain_gracefully():
    """
    Fire several concurrent requests, then reconfigure mid-flight.
    All requests (both before and after swap) should return 200 — no 500s.
    """
    import httpx
    import concurrent.futures

    service_url = LIVE
    errors = []

    def fire_requests():
        for _ in range(10):
            try:
                r = httpx.get(f"{service_url}/health", timeout=10.0)
                if r.status_code >= 500:
                    errors.append(r.status_code)
            except Exception as e:
                errors.append(str(e))
            time.sleep(0.05)

    # Start request flood in background
    t = threading.Thread(target=fire_requests)
    t.start()

    time.sleep(0.1)  # Let some requests land in-flight

    # Trigger hot-swap
    resp = httpx.post(
        f"{service_url}/admin/reconfigure",
        json={"pool_size": 8},
        timeout=30.0,
    )
    assert resp.status_code == 200

    t.join(timeout=10)
    assert errors == [], f"In-flight errors during hot-swap: {errors}"


# ── Cache reset on reconfigure ────────────────────────────────────────────────

def test_cache_reset_on_reconfigure():
    from cache import get_product_cache, reset_product_cache

    cache = get_product_cache()
    cache.set("test_key", {"data": "value"})
    assert cache.get("test_key") is not None

    reset_product_cache(ttl_seconds=120)
    # Cache should be cleared
    assert cache.get("test_key") is None
