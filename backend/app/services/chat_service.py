import asyncio
from time import perf_counter
from typing import Any

from app.db.repository import ChatRepository
from app.gateway.llm_gateway import LLMGateway, LLMResult


class ChatService:
    def __init__(
        self,
        repo: ChatRepository,
        gateway: LLMGateway,
        default_system_prompt: str,
    ):
        self.repo = repo
        self.gateway = gateway
        self.default_system_prompt = default_system_prompt
        self._locks: dict[str, asyncio.Lock] = {}

    def _session_lock(self, session_id: str) -> asyncio.Lock:
        lock = self._locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[session_id] = lock
        return lock

    async def chat(
        self,
        session_id: str,
        message: str,
        system_prompt: str | None = None,
        simulate: dict[str, int] | None = None,
        model: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """
        Orchestrate one chat turn:
        1. Measure latency from start of request handling.
        2. Lock session to prevent concurrent history interleaving.
        3. Load prompt + oldest-first history from SQLite.
        4. Call LiteLLM gateway (fails over or hits cache).
        5. Atomically persist user + assistant turn ONLY on success.
        """
        t0 = perf_counter()

        clean_sys = system_prompt.strip() if system_prompt and system_prompt.strip() else None

        async with self._session_lock(session_id):
            stored_prompt = await asyncio.to_thread(self.repo.get_session_prompt, session_id)
            effective_prompt = clean_sys or stored_prompt or self.default_system_prompt
            system_prompt_to_store = clean_sys if clean_sys else stored_prompt

            history = await asyncio.to_thread(self.repo.get_history, session_id)
            messages = [
                {"role": "system", "content": effective_prompt},
                *history,
                {"role": "user", "content": message},
            ]

            result: LLMResult = await self.gateway.complete(
                messages, simulate=simulate, model=model
            )
            latency_ms = int(round((perf_counter() - t0) * 1000))

            metadata: dict[str, Any] = {
                "resolution_source": "LLM_CACHE" if result.cache_hit else "LIVE_INFERENCE",
                "model": result.model,
                "latency_ms": latency_ms,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "key_id": result.key_id,
                "fallback_attempts": result.fallback_attempts,
            }

            await asyncio.to_thread(
                self.repo.save_exchange,
                session_id,
                system_prompt_to_store,
                message,
                result.reply,
                metadata,
            )

            return result.reply, metadata
