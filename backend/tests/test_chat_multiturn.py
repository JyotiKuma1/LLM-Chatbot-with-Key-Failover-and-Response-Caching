def test_chat_returns_contract_fields(client):
    res = client.post(
        "/chat",
        json={"session_id": "s-contract", "message": "What is the capital of France?"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["session_id"] == "s-contract"
    assert isinstance(body["reply"], str) and len(body["reply"]) > 0

    meta = body["metadata"]
    assert meta["resolution_source"] == "LIVE_INFERENCE"
    assert meta["model"] == "gemini/gemini-2.0-flash"
    assert isinstance(meta["latency_ms"], int)
    assert isinstance(meta["input_tokens"], int) and meta["input_tokens"] > 0
    assert isinstance(meta["output_tokens"], int) and meta["output_tokens"] > 0
    assert meta["key_id"] == "key_1"
    assert meta["fallback_attempts"] == 0


def test_multi_turn_persists_and_remembers(client, fake_llm):
    session_id = "s-multi-1"

    r1 = client.post(
        "/chat",
        json={"session_id": session_id, "message": "What is the capital of France?"},
    )
    assert r1.status_code == 200

    r2 = client.post(
        "/chat",
        json={"session_id": session_id, "message": "What is its population?"},
    )
    assert r2.status_code == 200

    # Second LLM call received [system, user1, assistant1, user2]
    assert len(fake_llm.calls) == 2
    second_msgs = fake_llm.calls[1]["messages"]
    assert [m["role"] for m in second_msgs] == ["system", "user", "assistant", "user"]
    assert second_msgs[1]["content"] == "What is the capital of France?"
    assert second_msgs[2]["content"] == r1.json()["reply"]
    assert second_msgs[3]["content"] == "What is its population?"

    # GET history returns 4 messages oldest-first, assistant with metadata, no system prompt
    hist = client.get(f"/sessions/{session_id}/messages")
    assert hist.status_code == 200
    data = hist.json()
    assert data["session_id"] == session_id
    msgs = data["messages"]
    assert len(msgs) == 4
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert "metadata" not in msgs[0]
    assert "metadata" not in msgs[2]
    for assistant_msg in (msgs[1], msgs[3]):
        m = assistant_msg["metadata"]
        assert "resolution_source" in m
        assert "input_tokens" in m
        assert "output_tokens" in m


def test_sessions_are_isolated(client, fake_llm):
    r1 = client.post("/chat", json={"session_id": "iso-a", "message": "Alpha one"})
    r2 = client.post("/chat", json={"session_id": "iso-b", "message": "Beta one"})
    assert r1.status_code == 200
    assert r2.status_code == 200

    # iso-b must only receive [system, user] — never iso-a's messages
    assert len(fake_llm.calls[1]["messages"]) == 2
    assert fake_llm.calls[1]["messages"][1]["content"] == "Beta one"

    ha = client.get("/sessions/iso-a/messages").json()["messages"]
    hb = client.get("/sessions/iso-b/messages").json()["messages"]
    assert len(ha) == 2 and ha[0]["content"] == "Alpha one"
    assert len(hb) == 2 and hb[0]["content"] == "Beta one"


def test_tokens_are_per_request(client, fake_llm):
    session_id = "s-tokens"
    r1 = client.post("/chat", json={"session_id": session_id, "message": "Short question"})
    assert r1.status_code == 200
    t1_in = r1.json()["metadata"]["input_tokens"]

    r2 = client.post(
        "/chat",
        json={"session_id": session_id, "message": "Follow up question with extra words"},
    )
    assert r2.status_code == 200
    t2_in = r2.json()["metadata"]["input_tokens"]

    # Calculate expected per-request prompt tokens for turn 2 from fake's formula
    turn2_messages = fake_llm.calls[1]["messages"]
    expected_t2_in = sum(len(m["content"].split()) + 4 for m in turn2_messages)

    assert t2_in == expected_t2_in
    assert t2_in > t1_in
    assert t2_in != t1_in + expected_t2_in  # Not a cumulative running sum


def test_session_system_prompt_override(client, fake_llm):
    session_id = "s-sys"
    r1 = client.post(
        "/chat",
        json={
            "session_id": session_id,
            "message": "Hello",
            "system_prompt": "Speak like a pirate.",
        },
    )
    assert r1.status_code == 200
    assert fake_llm.calls[0]["messages"][0]["content"] == "Speak like a pirate."

    # Subsequent turn without system_prompt keeps the session's stored override
    r2 = client.post("/chat", json={"session_id": session_id, "message": "How are you?"})
    assert r2.status_code == 200
    assert fake_llm.calls[1]["messages"][0]["content"] == "Speak like a pirate."


def test_list_and_delete_sessions(client):
    r1 = client.post("/chat", json={"session_id": "hist-1", "message": "First chat title"})
    r2 = client.post("/chat", json={"session_id": "hist-2", "message": "Second chat title"})
    assert r1.status_code == 200 and r2.status_code == 200

    res = client.get("/sessions")
    assert res.status_code == 200
    sessions = res.json()["sessions"]
    assert len(sessions) == 2
    assert {s["session_id"] for s in sessions} == {"hist-1", "hist-2"}
    assert all(s["message_count"] == 2 for s in sessions)

    del_res = client.delete("/sessions/hist-1")
    assert del_res.status_code == 200
    assert client.get("/sessions/hist-1/messages").status_code == 404
    remaining = client.get("/sessions").json()["sessions"]
    assert [s["session_id"] for s in remaining] == ["hist-2"]


def test_model_override_and_list_models(client):
    m_res = client.get("/models")
    assert m_res.status_code == 200
    m_data = m_res.json()
    assert m_data["default_model"] == "gemini/gemini-2.0-flash"
    assert len(m_data["models"]) >= 2

    r1 = client.post(
        "/chat",
        json={
            "session_id": "mod-1",
            "message": "Hello model",
            "model": "gemini/gemini-3.5-flash-lite",
        },
    )
    assert r1.status_code == 200
    assert r1.json()["metadata"]["model"] == "gemini/gemini-3.5-flash-lite"
    assert r1.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"

    # Different model on same prompt must not collide in cache
    r2 = client.post(
        "/chat",
        json={
            "session_id": "mod-2",
            "message": "Hello model",
            "model": "gemini/gemini-3.6-flash",
        },
    )
    assert r2.status_code == 200
    assert r2.json()["metadata"]["model"] == "gemini/gemini-3.6-flash"
    assert r2.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"
