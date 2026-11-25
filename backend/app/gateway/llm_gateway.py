import logging
import os
from dataclasses import dataclass
from typing import Any

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import httpx
import litellm
from litellm import Cache
from pydantic import BaseModel

logger = logging.getLogger("gateway")


class AllProvidersUnavailable(Exception):
    """Raised when every configured API key fails or no keys are configured."""


class SimulatedProviderError(Exception):
    """Raised before calling the provider when X-Simulate-Failure targets a key."""

    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"Simulated provider error: HTTP {status_code}")


@dataclass
class LLMResult:
    reply: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_hit: bool
    key_id: str | None
    fallback_attempts: int


def _extract_reply_and_usage(obj: Any) -> tuple[str, int, int]:
    """Extract reply content and token counts from a dict or ModelResponse-like object."""
    if isinstance(obj, dict):
        choices = obj.get("choices") or []
        reply = ""
        if choices:
            msg = choices[0].get("message") or {}
            reply = msg.get("content") or ""
        usage = obj.get("usage") or {}
        in_tok = int(usage.get("prompt_tokens") or 0)
        out_tok = int(usage.get("completion_tokens") or 0)
        return str(reply), in_tok, out_tok

    choices = getattr(obj, "choices", None) or []
    reply = ""
    if choices:
        msg = getattr(choices[0], "message", None)
        reply = getattr(msg, "content", None) or ""
    usage = getattr(obj, "usage", None)
    in_tok = int(getattr(usage, "prompt_tokens", 0) or 0)
    out_tok = int(getattr(usage, "completion_tokens", 0) or 0)
    return str(reply), in_tok, out_tok


def _to_cache_serializable(resp: Any, reply: str, input_tokens: int, output_tokens: int) -> dict[str, Any]:
    """Convert any provider response (BaseModel or mock object) to a JSON-cacheable dict."""
    if isinstance(resp, BaseModel):
        return resp.model_dump(exclude_unset=True)
    return {
        "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}}],
        "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens},
    }


class LLMGateway:
    def __init__(
        self,
        keys: list[str],
        model: str,
        timeout: float,
        fallback_models: list[str] | None = None,
    ):
        self.keys = keys
        self.model = model
        self.timeout = timeout
        self.fallback_models = fallback_models or []
        if len(self.keys) < 2:
            logger.warning("Fewer than 2 LLM_API_KEYS configured (count=%d)", len(self.keys))
        litellm.cache = Cache(type="local", max_messages=None)
        litellm.drop_params = True
        litellm.suppress_debug_info = True
        litellm.telemetry = False
        self._http_client: httpx.AsyncClient | None = None

    def ensure_http_client(self) -> None:
        """Initialize a shared keep-alive HTTPX client for connection reuse."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
            litellm.aclient_session = self._http_client

    async def aclose(self) -> None:
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
            litellm.aclient_session = None

    @property
    def cache_enabled(self) -> bool:
        return litellm.cache is not None

    async def complete(
        self,
        messages: list[dict[str, str]],
        simulate: dict[str, int] | None = None,
        model: str | None = None,
    ) -> LLMResult:
        """
        Execute an LLM completion with LiteLLM caching and sequential key failover.
        Valid simulation headers bypass both cache lookup and cache write.
        """
        use_cache = not simulate
        primary_model = model or self.model
        candidate_models = (
            [primary_model]
            if (simulate or model is not None or not self.fallback_models)
            else [primary_model, *[m for m in self.fallback_models if m != primary_model]]
        )

        # Check cache across primary model first
        if use_cache and litellm.cache is not None and self.keys:
            cache_params: dict[str, Any] = {
                "model": primary_model,
                "messages": messages,
                "temperature": 0,
            }
            try:
                cached = await litellm.cache.async_get_cache(**cache_params)
                if cached is not None:
                    reply, in_tok, out_tok = _extract_reply_and_usage(cached)
                    if reply.strip():
                        return LLMResult(
                            reply=reply,
                            model=primary_model,
                            input_tokens=in_tok,
                            output_tokens=out_tok,
                            cache_hit=True,
                            key_id=None,
                            fallback_attempts=0,
                        )
            except Exception as exc:
                logger.warning("cache lookup failed type=%s", type(exc).__name__)

        failures = 0
        for target_model in candidate_models:
            cache_params = {
                "model": target_model,
                "messages": messages,
                "temperature": 0,
            }
            for i, key in enumerate(self.keys, start=1):
                key_id = f"key_{i}"
                try:
                    status = (simulate or {}).get(key_id) or (simulate or {}).get("*")
                    if status:
                        raise SimulatedProviderError(status)

                    self.ensure_http_client()
                    resp = await litellm.acompletion(
                        model=target_model,
                        messages=messages,
                        api_key=key,
                        temperature=0,
                        timeout=self.timeout,
                        num_retries=0,
                        caching=False,
                    )

                    reply, in_tok, out_tok = _extract_reply_and_usage(resp)
                    if not reply.strip():
                        raise ValueError(f"Empty reply from provider {key_id}")

                    hidden = getattr(resp, "_hidden_params", None) or {}
                    hit = bool(hidden.get("cache_hit"))

                    if use_cache and not hit and litellm.cache is not None:
                        try:
                            cache_payload = _to_cache_serializable(resp, reply, in_tok, out_tok)
                            await litellm.cache.async_add_cache(result=cache_payload, **cache_params)
                        except Exception as exc:
                            logger.warning("cache store failed type=%s", type(exc).__name__)

                    return LLMResult(
                        reply=reply,
                        model=target_model,
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        cache_hit=hit,
                        key_id=None if hit else key_id,
                        fallback_attempts=0 if hit else failures,
                    )
                except Exception as exc:
                    logger.warning(
                        "provider failure model=%s key_id=%s type=%s",
                        target_model,
                        key_id,
                        type(exc).__name__,
                    )
                    failures += 1

        raise AllProvidersUnavailable()
