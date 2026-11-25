import os
from dataclasses import dataclass, field
from typing import Any, Callable

# Prevent LiteLLM from attempting remote cost-map fetches during offline tests
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
os.environ.setdefault("LITELLM_LOG", "ERROR")
os.environ.setdefault("LLM_API_KEYS", "secret-test-key-1,secret-test-key-2")
os.environ.setdefault("LLM_MODEL", "gemini/gemini-2.0-flash")
os.environ.setdefault("ENABLE_FAILURE_SIMULATION", "true")
os.environ.setdefault("DEFAULT_SYSTEM_PROMPT", "You are a helpful assistant.")

import litellm
import pytest
from fastapi.testclient import TestClient
from litellm import Cache
from litellm.types.utils import Choices, Message, ModelResponse, Usage

from app.main import create_app


@dataclass
class FakeLLMController:
    calls: list[dict[str, Any]] = field(default_factory=list)
    fail_keys: dict[str, Exception] = field(default_factory=dict)
    reply_fn: Callable[[list[dict[str, str]]], str] | None = None

    def set_key_failure(self, key_value: str, exc: Exception | None = None) -> None:
        self.fail_keys[key_value] = exc or RuntimeError(f"Simulated provider error for {key_value}")


@pytest.fixture(autouse=True)
def reset_litellm_cache():
    litellm.cache = Cache(type="local", max_messages=None)
    yield
    litellm.cache = None


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch) -> FakeLLMController:
    ctrl = FakeLLMController()

    async def fake_acompletion(*args, **kwargs):
        messages = kwargs.get("messages", [])
        api_key = kwargs.get("api_key", "")
        model = kwargs.get("model", "gemini/gemini-2.0-flash")
        ctrl.calls.append({"messages": messages, "api_key": api_key, "model": model})

        if api_key in ctrl.fail_keys:
            raise ctrl.fail_keys[api_key]

        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            "",
        )
        if ctrl.reply_fn:
            reply_text = ctrl.reply_fn(messages)
        elif "capital of France" in last_user:
            reply_text = "The capital of France is Paris."
        else:
            reply_text = f"Reply to: {last_user}"

        prompt_tokens = sum(len(m["content"].split()) + 4 for m in messages)
        completion_tokens = max(1, len(reply_text.split()))

        return ModelResponse(
            model=model,
            choices=[Choices(index=0, message=Message(role="assistant", content=reply_text))],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    return ctrl


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test_app.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("LLM_API_KEYS", "secret-test-key-1,secret-test-key-2")
    monkeypatch.setenv("LLM_MODEL", "gemini/gemini-2.0-flash")
    monkeypatch.setenv("ENABLE_FAILURE_SIMULATION", "true")
    monkeypatch.setenv("DEFAULT_SYSTEM_PROMPT", "You are a helpful assistant.")

    app = create_app()
    with TestClient(app) as c:
        yield c
