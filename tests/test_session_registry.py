from api.session_registry import SessionRegistry


def test_evicts_oldest_when_over_capacity():
    registry = SessionRegistry(max_sessions=2, ttl_seconds=3600)
    registry["a"] = 1
    registry["b"] = 2
    registry["c"] = 3

    assert "a" not in registry
    assert "b" in registry
    assert "c" in registry


def test_evicts_idle_sessions_past_ttl():
    clock = {"now": 0.0}
    registry = SessionRegistry(max_sessions=10, ttl_seconds=60, now_fn=lambda: clock["now"])
    registry["a"] = 1
    clock["now"] = 61.0
    registry["b"] = 2

    assert "a" not in registry
    assert "b" in registry


def test_get_refreshes_last_access():
    clock = {"now": 0.0}
    registry = SessionRegistry(max_sessions=2, ttl_seconds=3600, now_fn=lambda: clock["now"])
    registry["a"] = 1
    clock["now"] = 1.0
    registry["b"] = 2
    clock["now"] = 2.0
    assert registry.get("a") == 1
    clock["now"] = 3.0
    registry["c"] = 3

    assert "a" in registry
    assert "b" not in registry


def test_pop_and_clear_drop_access_tracking():
    registry = SessionRegistry(max_sessions=2, ttl_seconds=3600)
    registry["a"] = 1
    registry.set_owner("a", "u1")
    assert registry.pop("a") == 1
    assert registry.pop("missing") is None
    assert registry.owner("a") is None
    registry["b"] = 2
    registry.set_owner("b", "u2")
    registry.clear()
    assert len(registry) == 0
    assert registry.owner("b") is None


def test_owner_metadata_follows_capacity_eviction():
    registry = SessionRegistry(max_sessions=2, ttl_seconds=3600)
    registry["a"] = 1
    registry.set_owner("a", "u1")
    registry["b"] = 2
    registry.set_owner("b", "u2")
    registry["c"] = 3
    registry.set_owner("c", "u3")

    assert "a" not in registry
    assert registry.owner("a") is None
    assert registry.owner("b") == "u2"
    assert registry.owner("c") == "u3"


def test_owner_metadata_follows_ttl_eviction():
    clock = {"now": 0.0}
    registry = SessionRegistry(max_sessions=10, ttl_seconds=60, now_fn=lambda: clock["now"])
    registry["a"] = 1
    registry.set_owner("a", "u1")
    clock["now"] = 61.0
    registry["b"] = 2
    registry.set_owner("b", "u2")

    assert "a" not in registry
    assert registry.owner("a") is None
    assert registry.owner("b") == "u2"
