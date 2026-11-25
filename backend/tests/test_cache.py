def test_cross_session_cache_hit(client, fake_llm):
    prompt = "What is the capital of France?"

    r1 = client.post("/chat", json={"session_id": "cache-s1", "message": prompt})
    assert r1.status_code == 200
    d1 = r1.json()
    m1 = d1["metadata"]
    assert m1["resolution_source"] == "LIVE_INFERENCE"
    assert m1["key_id"] == "key_1"
    assert m1["fallback_attempts"] == 0

    # Same first message in a brand-new session -> cache hit
    r2 = client.post("/chat", json={"session_id": "cache-s2", "message": prompt})
    assert r2.status_code == 200
    d2 = r2.json()
    m2 = d2["metadata"]
    assert m2["resolution_source"] == "LLM_CACHE"
    assert d2["reply"] == d1["reply"]
    assert m2["key_id"] is None
    assert m2["fallback_attempts"] == 0
    assert m2["input_tokens"] == m1["input_tokens"]
    assert m2["output_tokens"] == m1["output_tokens"]
    assert m2["model"] == m1["model"]
    assert m2["latency_ms"] <= m1["latency_ms"] or m2["latency_ms"] <= 20

    # Ensure provider was only called once
    assert len(fake_llm.calls) == 1

    # Different message -> cache miss (LIVE_INFERENCE)
    r3 = client.post("/chat", json={"session_id": "cache-s3", "message": "Name a planet."})
    assert r3.status_code == 200
    assert r3.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert len(fake_llm.calls) == 2


def test_different_system_prompt_misses_cache(client, fake_llm):
    r1 = client.post(
        "/chat",
        json={"session_id": "sys-c1", "message": "Hi", "system_prompt": "Be formal."},
    )
    assert r1.status_code == 200
    assert r1.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"

    r2 = client.post(
        "/chat",
        json={"session_id": "sys-c2", "message": "Hi", "system_prompt": "Be casual."},
    )
    assert r2.status_code == 200
    assert r2.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert len(fake_llm.calls) == 2
