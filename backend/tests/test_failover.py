def test_failover_key1_429_and_500(client, fake_llm):
    r1 = client.post(
        "/chat",
        json={"session_id": "sim-429", "message": "Name a primary colour."},
        headers={"X-Simulate-Failure": "key_1=429"},
    )
    assert r1.status_code == 200
    m1 = r1.json()["metadata"]
    assert m1["key_id"] == "key_2"
    assert m1["fallback_attempts"] == 1
    assert m1["resolution_source"] == "LIVE_INFERENCE"

    # Simulated key_1 never called the provider; only key_2 was called
    assert fake_llm.calls[0]["api_key"] == "secret-test-key-2"

    r2 = client.post(
        "/chat",
        json={"session_id": "sim-500", "message": "Name a planet."},
        headers={"X-Simulate-Failure": "key_1=500"},
    )
    assert r2.status_code == 200
    m2 = r2.json()["metadata"]
    assert m2["key_id"] == "key_2"
    assert m2["fallback_attempts"] == 1


def test_failover_real_provider_error(client, fake_llm):
    fake_llm.set_key_failure("secret-test-key-1", RuntimeError("429 Quota Exceeded"))

    res = client.post(
        "/chat",
        json={"session_id": "real-fail", "message": "Hello failover"},
    )
    assert res.status_code == 200
    meta = res.json()["metadata"]
    assert meta["key_id"] == "key_2"
    assert meta["fallback_attempts"] == 1


def test_failover_all_fail(client):
    for header, sid in [("*=429", "fail-all-1"), ("key_1=429,key_2=500", "fail-all-2")]:
        res = client.post(
            "/chat",
            json={"session_id": sid, "message": "Should fail"},
            headers={"X-Simulate-Failure": header},
        )
        assert res.status_code == 503
        assert res.json() == {"detail": "all providers unavailable"}

        # Nothing saved to SQLite
        hist = client.get(f"/sessions/{sid}/messages")
        assert hist.status_code == 404
        assert hist.json() == {"detail": "session not found"}


def test_simulation_disabled_ignores_header(client, monkeypatch):
    monkeypatch.setenv("ENABLE_FAILURE_SIMULATION", "false")

    res = client.post(
        "/chat",
        json={"session_id": "sim-disabled", "message": "Hello"},
        headers={"X-Simulate-Failure": "*=429"},
    )
    assert res.status_code == 200
    assert res.json()["metadata"]["key_id"] == "key_1"
    assert res.json()["metadata"]["fallback_attempts"] == 0


def test_simulation_bypasses_cache(client):
    prompt = "What is the capital of France?"

    # Warm the cache
    r1 = client.post("/chat", json={"session_id": "warm-1", "message": prompt})
    assert r1.status_code == 200
    assert r1.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"

    # Confirm cache works normally
    r2 = client.post("/chat", json={"session_id": "warm-2", "message": prompt})
    assert r2.status_code == 200
    assert r2.json()["metadata"]["resolution_source"] == "LLM_CACHE"

    # Simulation must bypass cache and return 503
    r3 = client.post(
        "/chat",
        json={"session_id": "warm-3", "message": prompt},
        headers={"X-Simulate-Failure": "*=429"},
    )
    assert r3.status_code == 503
    assert r3.json() == {"detail": "all providers unavailable"}
