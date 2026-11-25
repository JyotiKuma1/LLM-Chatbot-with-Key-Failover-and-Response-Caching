# AGENTS.md — LLM Chatbot with Key Failover and Response Caching

> **For the AI agent (Antigravity / any coding agent):** This file is the single source of truth. Read it fully before writing code. Build in the phases in §12, run the check at the end of each phase, and do not move on until it passes. The project is graded by **automated API and UI contract tests**: a renamed field, a different path, a wrong status code or a missing `data-testid` counts as a missing requirement. When in doubt, follow the contract in §4–§6 literally.
>
> (Antigravity reads `AGENTS.md` / `GEMINI.md` at the repo root. Keep this file at the root as `AGENTS.md`, and copy it to `GEMINI.md` if your setup prefers that name.)

---

## 0. Ground rules

1. **Contract first.** Paths, JSON field names, status codes, and `data-testid` values in this file are exact. Extra response fields are allowed; missing or renamed ones are not.
2. **Never leak secrets.** API keys appear only in env vars. `key_id` is `key_1`, `key_2`, … — never the key. Never log keys. Never commit `.env`.
3. **Never return a stack trace or HTML error page.** Every error is JSON with a `detail` field.
4. **Failed requests (422, 503) are never written to SQLite.**
5. **Persist atomically, only after success.** User message + assistant reply are inserted in one transaction after the LLM call succeeds.
6. **LiteLLM must be used for caching and failover** (graders look for it in the code).
7. **SQLite only.** No Redis, no Postgres, no external services.
8. **All configuration via environment variables.** No hard-coded URLs, keys, or origins.
9. Keep code simple, typed, and small. No speculative features before the contract is green.

---

## 1. Tech stack

| Tier | Choice |
|---|---|
| Frontend | React 18 + Vite + TypeScript + Tailwind CSS |
| Backend | Python 3.11+, FastAPI, Pydantic v2, Uvicorn, LiteLLM |
| Storage | SQLite (stdlib `sqlite3`), file under Docker volume `/data/app.db` |
| Tests | pytest, httpx / FastAPI `TestClient`, monkeypatch for the LLM call |
| Containers | Multi-stage Dockerfiles, docker-compose, Makefile |
| Deploy | Backend: Render / Railway / Fly.io / HF Spaces (Docker). Frontend: Vercel / Netlify / Cloudflare Pages |

---

## 2. Repository layout (create exactly this)

```
.
├── AGENTS.md
├── README.md
├── Makefile
├── docker-compose.yml
├── .env.example
├── .gitignore                  # must ignore .env, node_modules, __pycache__, *.db, dist
├── backend/
│   ├── Dockerfile              # multi-stage
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             # app factory, lifespan (init db + gateway), CORS, exception handlers
│   │   ├── config.py           # Settings from env (pydantic-settings or os.environ)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py       # /health, /chat, /sessions/{id}/messages
│   │   │   ├── schemas.py      # Pydantic request/response models
│   │   │   └── errors.py       # global handlers -> {"detail": ...}
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── chat_service.py # orchestration, latency timing, persistence
│   │   ├── gateway/
│   │   │   ├── __init__.py
│   │   │   ├── llm_gateway.py  # key pool, failover, cache, simulate hook
│   │   │   └── simulate.py     # X-Simulate-Failure parsing
│   │   └── db/
│   │       ├── __init__.py
│   │       └── repository.py   # connection, init_schema, CRUD
│   └── tests/
│       ├── conftest.py         # fake LLM fixture, temp DB, env setup
│       ├── test_health.py
│       ├── test_chat_multiturn.py
│       ├── test_cache.py
│       ├── test_failover.py
│       └── test_errors.py
└── frontend/
    ├── Dockerfile              # multi-stage: node build -> nginx serve on 3000
    ├── nginx.conf
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── index.css
        ├── api/
        │   └── chatApi.ts      # fetch wrapper, error normalisation
        ├── hooks/
        │   └── useChat.ts      # session id, messages, send(), loading, error
        ├── components/
        │   ├── ChatWindow.tsx
        │   ├── MessageBubble.tsx   # user bubble
        │   ├── AssistantMessage.tsx # reply + metadata, all meta-* testids
        │   ├── ChatInput.tsx       # chat-input + send-button
        │   ├── SystemPromptInput.tsx
        │   └── ErrorBanner.tsx
        └── types.ts
```

---

## 3. Environment variables

`.env.example` must list **every** variable with placeholder values:

```dotenv
# Comma-separated key pool. At least 2. Order defines ids: key_1, key_2, ...
LLM_API_KEYS=your-key-1,your-key-2
# LiteLLM model name used for all keys
LLM_MODEL=gemini/gemini-2.0-flash
DATABASE_URL=sqlite:////data/app.db
# Comma-separated CORS origins (add the deployed frontend URL)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
# Must be "true" on the deployed backend
ENABLE_FAILURE_SIMULATION=true
DEFAULT_SYSTEM_PROMPT=You are a helpful assistant.
LLM_TIMEOUT_SECONDS=30
# Frontend (build-time, Vite)
VITE_API_BASE_URL=http://localhost:8000
```

Notes:
- `LLM_MODEL` is configurable so the model can be swapped if a provider retires or rate-limits one. **Verify the chosen model is currently available on the provider's free tier before the demo** (e.g. a current Gemini Flash model or a Groq model). The contract example uses `gemini/gemini-2.0-flash`; any LiteLLM model name is valid.
- Keys may be for the same provider (several free-tier keys) — that is expected.
- `DATABASE_URL` format: `sqlite:////data/app.db` → strip the `sqlite:///` prefix to get `/data/app.db`. Also support relative `sqlite:///./app.db` for local/test use. Create the parent directory if missing.

---

## 4. Backend API contract (exact)

All bodies are JSON.

### 4.1 `GET /health` → 200
Returns 200 only when the app is running, SQLite is reachable (`SELECT 1`), and the key pool is loaded.
```json
{ "status": "ok", "keys_configured": 2, "cache_enabled": true }
```

### 4.2 `POST /chat`

Request:
```json
{ "session_id": "s-7f3a", "message": "What is the capital of France?", "system_prompt": "optional" }
```

| Field | Type | Rule |
|---|---|---|
| `session_id` | string | required, 1–128 chars. Unknown id starts a new session |
| `message` | string | required, **1–4000 chars after trimming whitespace** (whitespace-only → 422) |
| `system_prompt` | string \| null | optional; overrides the default system prompt **for this session** |

Response 200:
```json
{
  "session_id": "s-7f3a",
  "reply": "The capital of France is Paris.",
  "metadata": {
    "resolution_source": "LIVE_INFERENCE",
    "model": "gemini/gemini-2.0-flash",
    "latency_ms": 812,
    "input_tokens": 42,
    "output_tokens": 9,
    "key_id": "key_1",
    "fallback_attempts": 0
  }
}
```

| Field | Rule |
|---|---|
| `resolution_source` | exactly `"LIVE_INFERENCE"` or `"LLM_CACHE"` |
| `model` | LiteLLM model name that produced the reply |
| `latency_ms` | **integer**, server-measured for the whole request, ms |
| `input_tokens` | integer, this request's prompt tokens (system + history + new message). Never a running total |
| `output_tokens` | integer, this reply's completion tokens |
| `key_id` | `"key_N"` on live; **`null` on cache hit**. Never the key |
| `fallback_attempts` | keys that failed before success; **0 on cache hit** |

`reply` must be non-empty.

### 4.3 `GET /sessions/{session_id}/messages` → 200
Oldest first, system prompt excluded.
```json
{
  "session_id": "s-7f3a",
  "messages": [
    { "role": "user", "content": "What is the capital of France?" },
    { "role": "assistant", "content": "The capital of France is Paris.",
      "metadata": { "resolution_source": "LIVE_INFERENCE", "input_tokens": 42, "output_tokens": 9 } }
  ]
}
```
User messages have no `metadata` key (or it may be omitted). Assistant `metadata` is the stored JSON (may include all fields; must include at least the three shown).

### 4.4 Error contract

| Case | Status | Body |
|---|---|---|
| Missing/empty `message` or `session_id`, `message` > 4000 chars, malformed JSON | **422** | `{"detail": ...}` (FastAPI default shape is fine) |
| Every key failed (429 / quota / 5xx / simulated) | **503** | `{"detail": "all providers unavailable"}` |
| Unknown session in `GET /sessions/...` | **404** | `{"detail": "session not found"}` |
| Anything unexpected | 500 | `{"detail": "internal server error"}` (no trace, no HTML) |

A session "exists" only if it has at least one stored message. A 422 or 503 on `/chat` must not create or modify a session (so a later GET on that id still returns 404 if it was new).

---

## 5. Behaviour rules

### 5.1 Multi-turn state
- Client sends only the new message. Backend loads prior messages for `session_id` from SQLite, builds `[system] + history + [new user]`, calls the LLM.
- Sessions are isolated by `session_id`.
- System prompt resolution: request `system_prompt` if provided (non-empty) → store it for the session (a `sessions` table: `session_id PRIMARY KEY, system_prompt, created_at`) → else the stored session prompt → else `DEFAULT_SYSTEM_PROMPT`. Do **not** put the system prompt in the `messages` table (history endpoint excludes it).

### 5.2 Key pool and failover
- Parse `LLM_API_KEYS` (split on comma, trim, drop empties). Key ids are `key_1`, `key_2`, … in order. Warn at startup if fewer than 2 keys.
- For each request, try keys **in order**. On any provider failure (429, quota/`RateLimitError`, 5xx, connection error, timeout, auth error) record it, increment `fallback_attempts`, try the next key.
- If a key succeeds: 200 with that `key_id` and `fallback_attempts` = number of keys that failed before it.
- If all keys fail: raise `AllProvidersUnavailable` → 503 `{"detail": "all providers unavailable"}`; nothing is saved.
- Never surface provider error text to the client.

### 5.3 Caching (LiteLLM built-in)
- Enable `litellm.cache = Cache(type="local")` (in-memory) at startup. Call LiteLLM with `caching=True`.
- Cache key must reflect **model + full message list** (system + history + new message). LiteLLM's default key does this. Keep `temperature` fixed (use `0`) and pass identical params on every call so identical inputs produce identical keys. Do **not** add per-request unique values (timestamps, request ids, `user=`, metadata) to the completion call.
- Detect a hit with `getattr(response, "_hidden_params", {}).get("cache_hit") is True`.
- Cache hit response: `resolution_source="LLM_CACHE"`, `key_id=None`, `fallback_attempts=0`, identical reply text, tokens = the usage stored with the cached response, `model` = the model name.
- The same first message in a brand-new session (same system prompt) must hit. A different message (or different system prompt / history) must miss.
- **Verify the installed LiteLLM version supports per-call `caching=True` with `acompletion`.** If hit detection or per-call caching misbehaves, fall back to explicit `litellm.cache.async_get_cache(...)` / `async_add_cache(...)` or a thin wrapper around LiteLLM's `Cache.get_cache_key`, but still use LiteLLM's `Cache` object.
- Failure-simulation requests **bypass the cache** (see 5.4) so that failover is always demonstrable and `*=429` always returns 503 even for previously cached prompts.

### 5.4 `X-Simulate-Failure` hook
- Only on `POST /chat`, only when `ENABLE_FAILURE_SIMULATION=true` (case-insensitive). Otherwise the header is ignored.
- Format: comma-separated `<key_id>=<status>` pairs; `*` = every key. Statuses: `429, 500, 502, 503`. Trim whitespace. Ignore malformed pairs or unsupported statuses.
- Effect: a listed key behaves as if the provider returned that status — **raise before calling the provider** (no real call, no quota burnt) — for this request only. No global state.
- Examples with 2 keys:
  - `key_1=429` → 200, `key_id=key_2`, `fallback_attempts=1`
  - `key_1=500` → 200, `key_id=key_2`
  - `key_1=429,key_2=500` → 503, nothing saved
  - `*=429` → 503 `{"detail": "all providers unavailable"}`, nothing saved
- A simulated request that falls over to a healthy key must return a **real LLM answer**, never an error wrapped in a 200.
- If a request carries a valid simulation header, skip cache read/write for that request (`caching=False`).

### 5.5 Latency and tokens
- `latency_ms = int(round((time.perf_counter() - t0) * 1000))`, measured in the service layer from the start of request handling (before history load) to just before building the response.
- Cache hits must be faster than live calls (they naturally are — don't add sleeps anywhere).
- Tokens come from `response.usage.prompt_tokens` / `completion_tokens`. Two equal-length first messages in two new sessions report about the same `input_tokens` (because the same default system prompt is used) — do not inflate with history from other sessions.

---

## 6. Frontend contract (exact `data-testid`s)

| `data-testid` | Element | Content / behaviour |
|---|---|---|
| `chat-input` | textarea/input | user message; **cleared after sending**; Enter sends (Shift+Enter newline) |
| `send-button` | button | sends the message; disabled while loading or when input is blank |
| `assistant-message` | container, **one per assistant reply** | reply text + the metadata elements below |
| `meta-source` | inside `assistant-message` | text is **exactly** `LIVE_INFERENCE` or `LLM_CACHE` (no labels/prefix inside this element) |
| `meta-model` | inside | the `model` value |
| `meta-latency` | inside | e.g. `812 ms` |
| `meta-input-tokens` | inside | the `input_tokens` integer only |
| `meta-output-tokens` | inside | the `output_tokens` integer only |
| `system-prompt-input` | textarea/input | optional system prompt field (we implement it) |

Rules:
- Put labels **outside** the testid elements (e.g. `<span>Source</span><span data-testid="meta-source">LIVE_INFERENCE</span>`) so `textContent` is exact.
- A **new `session_id` is generated on every page load** (`crypto.randomUUID()` or `s-` + random, ≤128 chars).
- 422 and 503 render as a readable message in the chat area (e.g. a red error bubble / banner), never a blank screen. Network failures too ("Could not reach the server"). Errored messages are not shown as assistant replies (do **not** render an `assistant-message` for errors).
- Show the user's message immediately; show a typing/loading indicator while waiting.
- If `system-prompt-input` has a non-empty value, include `system_prompt` in the request body.
- Backend base URL from `import.meta.env.VITE_API_BASE_URL` (default `http://localhost:8000`).
- Keep the UI clean and responsive with Tailwind: centered chat column, user bubbles right, assistant bubbles left, small muted metadata row under each assistant reply.

---

## 7. SQLite schema (auto-created on startup, idempotent)

```sql
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,        -- 'user' or 'assistant'
    content TEXT NOT NULL,
    metadata TEXT,             -- JSON string, assistant messages only
    created_at TEXT NOT NULL   -- server time, ISO-8601 (UTC)
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    system_prompt TEXT,
    created_at TEXT NOT NULL
);
```

Repository notes:
- Open a connection per operation (or per request) with `check_same_thread=False` as needed; enable `PRAGMA journal_mode=WAL`.
- `save_exchange(session_id, system_prompt, user_msg, assistant_msg, metadata)` does both inserts (and session upsert) in **one transaction**.
- `get_history(session_id)` returns `[{role, content}]` ordered by `id` ASC.
- `session_exists(session_id)` = any message row exists.
- SQLite calls are blocking: either call them via `run_in_threadpool` / `asyncio.to_thread`, or use sync route handlers carefully. Do not block the event loop for long.
- Concurrency: use an `asyncio.Lock` per `session_id` (dict of locks) in the service layer so two simultaneous requests to one session don't interleave history.

---

## 8. Backend implementation guide

### 8.1 Layering (strict, one-way dependencies)
`api → services → gateway` and `services → db`. The API layer never touches SQLite or LiteLLM directly; the gateway never touches SQLite.

### 8.2 `schemas.py`
```python
class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str
    system_prompt: str | None = None

    @field_validator("message")
    @classmethod
    def _trim(cls, v: str) -> str:
        v = v.strip()
        if not 1 <= len(v) <= 4000:
            raise ValueError("message must be 1-4000 characters after trimming")
        return v
```
Also trim/validate `session_id` (reject whitespace-only). Response models: `ChatMetadata`, `ChatResponse`, `HistoryMessage`, `HistoryResponse`, `HealthResponse`.

### 8.3 Gateway sketch (`llm_gateway.py`)
```python
import litellm
from litellm.caching.caching import Cache  # import path may differ by version: `from litellm import Cache`

class AllProvidersUnavailable(Exception): ...

@dataclass
class LLMResult:
    reply: str; model: str; input_tokens: int; output_tokens: int
    cache_hit: bool; key_id: str | None; fallback_attempts: int

class LLMGateway:
    def __init__(self, keys: list[str], model: str, timeout: float):
        self.keys = keys; self.model = model; self.timeout = timeout
        litellm.cache = Cache(type="local")
        litellm.drop_params = True
        litellm.suppress_debug_info = True

    @property
    def cache_enabled(self) -> bool: return litellm.cache is not None

    async def complete(self, messages: list[dict], simulate: dict[str, int] | None) -> LLMResult:
        use_cache = not simulate               # simulation bypasses cache
        failures = 0
        for i, key in enumerate(self.keys, start=1):
            key_id = f"key_{i}"
            try:
                status = (simulate or {}).get(key_id) or (simulate or {}).get("*")
                if status:
                    raise SimulatedProviderError(status)   # never calls the provider
                resp = await litellm.acompletion(
                    model=self.model, messages=messages, api_key=key,
                    temperature=0, timeout=self.timeout, num_retries=0,
                    caching=use_cache,
                )
                hit = bool(getattr(resp, "_hidden_params", {}).get("cache_hit"))
                return LLMResult(
                    reply=resp.choices[0].message.content,
                    model=self.model,
                    input_tokens=resp.usage.prompt_tokens,
                    output_tokens=resp.usage.completion_tokens,
                    cache_hit=hit,
                    key_id=None if hit else key_id,
                    fallback_attempts=0 if hit else failures,
                )
            except Exception as exc:               # log type + key_id only, never the key
                logger.warning("provider failure key_id=%s type=%s", key_id, type(exc).__name__)
                failures += 1
        raise AllProvidersUnavailable()
```
Important details:
- `num_retries=0` so LiteLLM doesn't silently retry the same key; **our loop** is the failover.
- A cache hit can occur on the first key attempt; then `key_id=None`, `fallback_attempts=0`.
- Treat an empty/None `content` from a provider as a failure for that key (so `reply` is never empty).
- Cache key does not include `api_key` by default — good: a reply cached from `key_1` is served for any key. Verify this once with the installed version.
- Optional (bonus): per-key cooldown after a real 429 so dead keys are skipped for N seconds. Must not affect simulated requests' semantics (simulation is per-request only) and must not change `key_id` ordering expectations in tests.

`simulate.py`:
```python
VALID = {429, 500, 502, 503}
def parse_simulate_header(value: str | None, enabled: bool) -> dict[str, int] | None:
    if not enabled or not value: return None
    out = {}
    for pair in value.split(","):
        if "=" not in pair: continue
        k, v = (p.strip() for p in pair.split("=", 1))
        if k and v.isdigit() and int(v) in VALID: out[k] = int(v)
    return out or None
```

### 8.4 Service (`chat_service.py`)
```
async def chat(session_id, message, system_prompt, simulate) -> (reply, metadata):
    t0 = perf_counter()
    async with session_lock(session_id):
        stored_prompt = repo.get_session_prompt(session_id)
        effective = system_prompt or stored_prompt or settings.default_system_prompt
        history = repo.get_history(session_id)
        messages = [{"role":"system","content":effective}, *history, {"role":"user","content":message}]
        result = await gateway.complete(messages, simulate)     # may raise AllProvidersUnavailable
        latency_ms = int(round((perf_counter()-t0)*1000))
        metadata = {resolution_source, model, latency_ms, input_tokens, output_tokens, key_id, fallback_attempts}
        repo.save_exchange(session_id, system_prompt_to_store, message, result.reply, metadata)  # one transaction
    return result.reply, metadata
```
Compute `latency_ms` **before** the DB write or include write time — be consistent, but the value stored/returned must be the same integer.

### 8.5 API layer (`routes.py`, `errors.py`, `main.py`)
- `POST /chat` reads `X-Simulate-Failure` via `Header(default=None, alias="X-Simulate-Failure")`.
- Exception handlers: `AllProvidersUnavailable` → 503 `{"detail": "all providers unavailable"}`; `RequestValidationError` → 422 `{"detail": exc.errors()}` (make sure the body is JSON-serializable — convert non-serializable `ctx` values to strings); `StarletteHTTPException` → `{"detail": exc.detail}`; bare `Exception` → 500 `{"detail": "internal server error"}`.
- Malformed JSON must yield 422 JSON (FastAPI default does this; verify it is not 400/HTML).
- CORS: `CORSMiddleware(allow_origins=settings.allowed_origins, allow_methods=["*"], allow_headers=["*"], expose_headers=["*"])`. `allow_headers` must permit `X-Simulate-Failure` and `Content-Type`.
- Lifespan: init DB schema, build gateway once, store on `app.state`.
- `/health`: run `SELECT 1`; if DB or keys unavailable return 503 `{"status":"error",...}`; else the OK payload with `keys_configured=len(keys)` and `cache_enabled=True`.
- Run with `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`.

---

## 9. Backend tests (pytest) — required

Never call a real provider in tests. In `conftest.py`:
- Use a temp SQLite file via `DATABASE_URL`, set `LLM_API_KEYS=k1,k2`, `ENABLE_FAILURE_SIMULATION=true`.
- Monkeypatch `litellm.acompletion` (or use LiteLLM's `mock_response` param) with a fake that returns an object with `.choices[0].message.content`, `.usage.prompt_tokens/completion_tokens`, `._hidden_params`, and honors the in-memory cache semantics. **Preferred:** use `mock_response="..."` with the real `Cache(type="local")` so LiteLLM's real cache path is exercised; ensure a fresh cache per test (`litellm.cache = Cache(type="local")` in a fixture).
- Provide a fixture to make a given key's call raise (to test real, non-simulated failover too).

Required tests (name them clearly):
1. `test_health_ok` — 200, `status=="ok"`, `keys_configured==2`, `cache_enabled is True`.
2. `test_chat_returns_contract_fields` — all metadata fields present and typed; `latency_ms` is int; `key_id=="key_1"`; `fallback_attempts==0`.
3. `test_multi_turn_persists_and_remembers` — two messages in one session; the second LLM call received `[system, user1, assistant1, user2]`; GET history returns 4 messages in order, assistant ones with metadata, no system message.
4. `test_sessions_are_isolated`.
5. `test_cross_session_cache_hit` — same first message in two new sessions: second is `LLM_CACHE`, same reply, `key_id is None`, `fallback_attempts==0`, same tokens as first, `latency_ms` lower or equal-and-small; different message → `LIVE_INFERENCE`.
6. `test_failover_key1_429` → 200, `key_id=="key_2"`, `fallback_attempts==1`; also `key_1=500`.
7. `test_failover_all_fail` — `*=429` and `key_1=429,key_2=500` → 503 `{"detail": "all providers unavailable"}`, and the session has no stored messages (GET → 404 for a new session).
8. `test_simulation_disabled_ignores_header` — with `ENABLE_FAILURE_SIMULATION=false`, header has no effect.
9. `test_simulation_bypasses_cache` — warm cache, then `*=429` still returns 503.
10. `test_validation_422` — empty message, whitespace-only message, >4000 chars, missing session_id, malformed JSON; all JSON with `detail`; nothing persisted.
11. `test_unknown_session_404` — `{"detail": "session not found"}`.
12. `test_tokens_are_per_request` — second turn's `input_tokens` ≥ first's, and is the prompt size of that request, not a sum of totals (assert against the fake's reported usage).
13. `test_no_secret_leak` — response bodies never contain the key strings.

Run: `cd backend && pytest -q`.

---

## 10. Frontend implementation guide

- `src/types.ts`: `ChatMetadata`, `ChatResponse`, `UiMessage = {id, role: 'user'|'assistant'|'error', content, metadata?}`.
- `src/api/chatApi.ts`: `sendChat(body)` → `POST ${BASE}/chat`; on non-2xx parse `{detail}` and throw an `ApiError(status, message)`. Convert 422 `detail` arrays to a readable string (join `msg` fields); for 503 show "All AI providers are currently unavailable. Please try again shortly."; network errors → "Could not reach the server."
- `src/hooks/useChat.ts`: holds `sessionId` (generated once per page load via `useRef`/`useState` initializer), `messages`, `loading`, `error`, `systemPrompt`, `send(text)`. On send: append user message, clear input is handled by the component (clear immediately on submit), call API, append assistant message with metadata or an error message.
- `AssistantMessage.tsx` renders:
  ```tsx
  <div data-testid="assistant-message">
    <p>{reply}</p>
    <div className="meta">
      <span>Source: </span><span data-testid="meta-source">{m.resolution_source}</span>
      <span>Model: </span><span data-testid="meta-model">{m.model}</span>
      <span>Latency: </span><span data-testid="meta-latency">{m.latency_ms} ms</span>
      <span>In: </span><span data-testid="meta-input-tokens">{m.input_tokens}</span>
      <span>Out: </span><span data-testid="meta-output-tokens">{m.output_tokens}</span>
    </div>
  </div>
  ```
  Optionally add a colored badge style for cache vs live, but the testid element's text must stay exact.
- Auto-scroll to the latest message; disable send while loading; show errors via `ErrorBanner` / error bubble.
- `frontend/Dockerfile`: stage 1 `node:20-alpine` → `npm ci` → `ARG VITE_API_BASE_URL` → `npm run build`; stage 2 `nginx:alpine` copying `dist` to `/usr/share/nginx/html` with an `nginx.conf` that listens on **3000** and falls back to `index.html` (SPA).

---

## 11. Docker, Compose, Makefile

**`backend/Dockerfile`** (multi-stage):
- Stage `builder`: `python:3.11-slim`, create venv (or `pip install --prefix=/install`), install `requirements.txt` with `--no-cache-dir`.
- Stage `runtime`: `python:3.11-slim`, copy the installed packages and `app/`, create `/data`, run as a non-root user that owns `/data`, `ENV PYTHONUNBUFFERED=1`, `EXPOSE 8000`, `CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]`.
- Add a `HEALTHCHECK` hitting `/health` (optional).

**`docker-compose.yml`** (repo root):
```yaml
services:
  backend:
    build: ./backend
    env_file: .env
    environment:
      DATABASE_URL: sqlite:////data/app.db
    ports: ["8000:8000"]
    volumes: ["app_data:/data"]
    restart: unless-stopped
  frontend:
    build:
      context: ./frontend
      args:
        VITE_API_BASE_URL: ${VITE_API_BASE_URL:-http://localhost:8000}
    ports: ["3000:3000"]
    depends_on: [backend]
volumes:
  app_data:
```
Ensure `ALLOWED_ORIGINS` includes `http://localhost:3000`.

**`Makefile`**:
```make
.PHONY: up down logs test
up:
	docker compose up --build -d
down:
	docker compose down
logs:
	docker compose logs -f
test:
	cd backend && pytest -q
```
(Use real tab characters for recipe lines.) `make up` must work from a fresh clone after `cp .env.example .env` and filling in keys. Document that step in the README.

---

## 12. Build order (do in this order, verify at each step)

**Phase 1 — Backend core.** Create `config.py`, `db/repository.py`, `gateway/`, `services/`, `api/`, `main.py`. 
✅ Check: `uvicorn app.main:app` starts; `curl localhost:8000/health` returns the exact JSON.

**Phase 2 — Backend tests.** Write §9 tests. 
✅ Check: `pytest -q` is green with no network access.

**Phase 3 — Live smoke test with real keys.** Run the §14 curl script locally. 
✅ Check: live reply, then cache hit with `key_id: null`; failover works; `*=429` gives 503.

**Phase 4 — Frontend.** Vite + Tailwind app per §6 and §10. 
✅ Check: `npm run build` passes; in the browser all testids exist; cache hit badge shows on repeated first message after a page reload (new session).

**Phase 5 — Docker.** Dockerfiles, compose, Makefile. 
✅ Check: `make up` → frontend on :3000, backend on :8000; restart containers (`make down && make up`) and confirm history persists in the volume (GET history for an old session id still returns data).

**Phase 6 — Deploy.** See §13. 
✅ Check: deployed frontend chats with deployed backend; the §14 script passes against the live URL.

**Phase 7 — README + demo.** Complete README (§15) and record the demo (§16).

---

## 13. Deployment notes

**Backend (Render / Railway / Fly / HF Spaces, Docker):**
- Deploy from `backend/` Dockerfile. Set env vars: `LLM_API_KEYS`, `LLM_MODEL`, `DATABASE_URL=sqlite:////data/app.db`, `ALLOWED_ORIGINS=<deployed frontend origin>[,http://localhost:3000]`, `ENABLE_FAILURE_SIMULATION=true`.
- Listen on `$PORT` (the Dockerfile CMD already does).
- If the platform offers a persistent disk/volume, mount it at `/data`. On free tiers without disks the DB is ephemeral across redeploys — acceptable for the demo; mention it in the README.
- Free instances may cold-start; hit `/health` a minute before the demo and before submitting.
- `ALLOWED_ORIGINS` must contain the exact frontend origin (scheme + host, no trailing slash).

**Frontend (Vercel / Netlify / Cloudflare Pages):**
- Root directory `frontend`, build `npm run build`, output `dist`.
- Set `VITE_API_BASE_URL=https://<deployed-backend>` as a **build-time** env var, then redeploy.
- Confirm in the browser network tab there are no CORS errors.

Both URLs must be public (no login/auth wall) — test from an incognito window.

---

## 14. Verification script (use for the demo; replace `$API`)

```bash
API=https://YOUR-BACKEND-URL   # or http://localhost:8000

# 1. Health
curl -s $API/health

# 2. Live inference (new session)
curl -s -X POST $API/chat -H 'Content-Type: application/json' \
  -d '{"session_id":"demo-1","message":"What is the capital of France?"}'

# 3. Cache hit: same first message, NEW session -> LLM_CACHE, key_id null, lower latency
curl -s -X POST $API/chat -H 'Content-Type: application/json' \
  -d '{"session_id":"demo-2","message":"What is the capital of France?"}'

# 4. Multi-turn memory
curl -s -X POST $API/chat -H 'Content-Type: application/json' \
  -d '{"session_id":"demo-1","message":"What is its population?"}'

# 5. History from SQLite
curl -s $API/sessions/demo-1/messages

# 6. Failover: key_1 fails with 429 -> answered by key_2
curl -s -X POST $API/chat -H 'Content-Type: application/json' -H 'X-Simulate-Failure: key_1=429' \
  -d '{"session_id":"demo-3","message":"Name a primary colour."}'

# 7. Failover with 500
curl -s -X POST $API/chat -H 'Content-Type: application/json' -H 'X-Simulate-Failure: key_1=500' \
  -d '{"session_id":"demo-4","message":"Name a planet."}'

# 8. All keys fail -> 503, nothing saved
curl -s -i -X POST $API/chat -H 'Content-Type: application/json' -H 'X-Simulate-Failure: *=429' \
  -d '{"session_id":"demo-5","message":"Hello"}'
curl -s -i $API/sessions/demo-5/messages     # -> 404 session not found

# 9. Validation 422
curl -s -i -X POST $API/chat -H 'Content-Type: application/json' -d '{"session_id":"x","message":"   "}'
curl -s -i -X POST $API/chat -H 'Content-Type: application/json' -d '{bad json'
```

---

## 15. README.md (use these exact six headings, in this order)

1. `## 1. Live URLs` — frontend URL, backend URL, `/health` link, repo link.
2. `## 2. Run locally: with Docker and without` — Docker: `cp .env.example .env`, add keys, `make up`, open :3000, `make down`. Without Docker: backend (`python -m venv`, `pip install -r requirements.txt`, `uvicorn app.main:app --reload`), frontend (`npm i`, `npm run dev`), `pytest`.
3. `## 3. Design decisions: key fallback, caching, SQLite session storage` — sequential key failover loop with `num_retries=0`; why simulation raises before provider call and bypasses cache; LiteLLM in-memory cache keyed on model+messages, hit detection; SQLite with transactional writes after success, volume at `/data`; 4-layer architecture; trade-offs (in-memory cache lost on restart, single-instance assumption).
4. `## 4. Verification: how to see failover, cache hits and per-message token usage` — the §14 commands plus what to look for in the UI.
5. `## 5. Setup Used: your editor and AI tools` — Antigravity (editor/agent), models used, any other tools.
6. `## 6. Bonus features (if any): what you added beyond the requirements and why` — e.g. session system prompt field, health check in Docker, per-session locks, tests for secret non-leakage.

Also include an architecture diagram (Mermaid or ASCII) and the API contract table.

---

## 16. Demo video checklist (2–3 min, with voice)

1. Show repo + live URLs, `/health` on the deployed backend (10s).
2. UI: send a message → show all five metadata fields (20s).
3. Reload the page (new session), send the **same** message → `LLM_CACHE`, lower latency (25s).
4. Multi-turn: ask a follow-up that needs memory (20s).
5. curl history endpoint, 404 and 422 examples (25s).
6. Failover: `X-Simulate-Failure: key_1=429` → `key_id=key_2`, `fallback_attempts=1`; then `*=429` → 503 and confirm nothing saved (40s).
7. Mention `make up`, multi-stage Docker, tests (`pytest -q` green) (20s).

---

## 17. Final pre-submission checklist

- [ ] `GET /health` exact shape; 200
- [ ] `POST /chat` returns every metadata field with correct types
- [ ] Same first message in new session → `LLM_CACHE`, identical reply, `key_id: null`, `fallback_attempts: 0`, lower latency
- [ ] Different message never hits cache
- [ ] Token counts are per-request
- [ ] History endpoint: oldest first, no system prompt, assistant has `metadata`
- [ ] `key_1=429` / `key_1=500` → 200 via `key_2`; `*=429` → 503, nothing saved
- [ ] 422 / 404 / 503 bodies are JSON with `detail`; no stack traces
- [ ] `ENABLE_FAILURE_SIMULATION=true` on the deployed backend
- [ ] CORS allows the deployed frontend origin
- [ ] All `data-testid`s present and exact; `chat-input` clears after send; new session each page load
- [ ] Errors render in the chat; no blank screen
- [ ] `make up` works from a fresh clone; volume persists history across restarts
- [ ] Multi-stage Dockerfiles; compose with named volume at `/data`; Makefile has `up`, `down`
- [ ] `.env.example` lists every variable; no real keys committed (check git history)
- [ ] `pytest -q` passes
- [ ] README has the six exact headings
- [ ] Public GitHub repo; both live URLs open in incognito; demo video recorded and uploaded
- [ ] Submission form completed **within 24 hours**

---

## 18. Common pitfalls (read before coding)

- **Cache never hits:** something unique is in the call kwargs (timestamp, `user`, random metadata) or `temperature` varies. Keep call params constant.
- **Cache hit not detected:** check `_hidden_params["cache_hit"]` on the installed LiteLLM version; adjust if it moved.
- **LiteLLM retries hide failover:** set `num_retries=0` and keep failover in our loop.
- **Simulated 429 returns 200 with key_1:** simulation check must happen before any provider call and before the cache.
- **`*=429` returns cached 200:** simulation requests must skip the cache.
- **Failed request still saved:** persist only after a successful gateway result, in one transaction.
- **422 body not serializable:** stringify `ctx` errors in the validation handler.
- **CORS blocks `X-Simulate-Failure`:** allow all headers.
- **Docker DB lost on restart:** `DATABASE_URL` must point inside `/data`, and the volume must be mounted there; the non-root user must own `/data`.
- **Frontend points to localhost in production:** `VITE_API_BASE_URL` is build-time; redeploy after changing it.
- **testid text not exact:** keep labels outside `meta-*` elements.
- **Model retired/rate-limited at demo time:** change `LLM_MODEL` via env and redeploy; no code changes needed.
