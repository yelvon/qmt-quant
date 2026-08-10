"""TTL cache tests."""

from qmt_quant.core.ttl_cache import TtlCache


def test_ttl_cache_expires(monkeypatch):
    cache: TtlCache[int] = TtlCache(ttl_seconds=1.0)
    now = 1000.0
    monkeypatch.setattr("qmt_quant.core.ttl_cache.time.monotonic", lambda: now)

    cache.set("k", 42)
    assert cache.get("k") == 42

    now = 1001.1
    assert cache.get("k") is None


def test_ttl_cache_get_or_set(monkeypatch):
    cache: TtlCache[int] = TtlCache(ttl_seconds=30.0)
    monkeypatch.setattr("qmt_quant.core.ttl_cache.time.monotonic", lambda: 0.0)
    calls = {"n": 0}

    def factory() -> int:
        calls["n"] += 1
        return 7

    assert cache.get_or_set("k", factory) == 7
    assert cache.get_or_set("k", factory) == 7
    assert calls["n"] == 1
