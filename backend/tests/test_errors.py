def test_validation_422(client):
    cases = [
        {"session_id": "val-1", "message": ""},
        {"session_id": "val-2", "message": "   \t\n  "},
        {"session_id": "val-3", "message": "x" * 4001},
        {"message": "missing session id"},
        {"session_id": "   ", "message": "hello"},
        {"session_id": "x" * 129, "message": "hello"},
    ]

    for idx, payload in enumerate(cases):
        res = client.post("/chat", json=payload)
        assert res.status_code == 422, f"Case {idx} expected 422, got {res.status_code}"
        body = res.json()
        assert "detail" in body

        if "session_id" in payload and payload["session_id"].strip():
            hist = client.get(f"/sessions/{payload['session_id']}/messages")
            assert hist.status_code == 404

    # Malformed JSON -> 422 JSON with detail
    bad_res = client.post(
        "/chat",
        content="{bad json",
        headers={"Content-Type": "application/json"},
    )
    assert bad_res.status_code == 422
    assert "detail" in bad_res.json()


def test_unknown_session_404(client):
    res = client.get("/sessions/does-not-exist/messages")
    assert res.status_code == 404
    assert res.json() == {"detail": "session not found"}


def test_no_secret_leak(client, fake_llm):
    secrets = ("secret-test-key-1", "secret-test-key-2")

    # 1. Normal response
    r1 = client.post("/chat", json={"session_id": "leak-1", "message": "Hello"})
    assert r1.status_code == 200
    for s in secrets:
        assert s not in r1.text

    # 2. All keys failing (uncached prompt) with secret included in provider exception
    fake_llm.set_key_failure("secret-test-key-1", RuntimeError("Auth failed for secret-test-key-1"))
    fake_llm.set_key_failure("secret-test-key-2", RuntimeError("Auth failed for secret-test-key-2"))
    r2 = client.post("/chat", json={"session_id": "leak-2", "message": "Uncached secret check"})
    assert r2.status_code == 503
    assert r2.json() == {"detail": "all providers unavailable"}
    for s in secrets:
        assert s not in r2.text
