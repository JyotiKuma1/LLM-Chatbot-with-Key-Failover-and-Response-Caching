import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def resolve_db_path(database_url: str) -> str:
    """Resolve SQLite file path from DATABASE_URL and ensure parent directory exists."""
    if database_url.startswith("sqlite:///"):
        path_str = database_url[len("sqlite:///"):]
    else:
        path_str = database_url

    db_path = Path(path_str)
    if db_path.parent and str(db_path.parent) not in ("", "."):
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return str(db_path)


class ChatRepository:
    def __init__(self, database_url: str):
        self.db_path = resolve_db_path(database_url)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    system_prompt TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.commit()

    def ping(self) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1;").fetchone()
            return row is not None and row[0] == 1

    def session_exists(self, session_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM messages WHERE session_id = ? LIMIT 1;",
                (session_id,),
            ).fetchone()
            return row is not None

    def get_session_prompt(self, session_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT system_prompt FROM sessions WHERE session_id = ?;",
                (session_id,),
            ).fetchone()
            return row["system_prompt"] if row else None

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        """Return oldest-first user/assistant messages for LLM prompt context."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC;",
                (session_id,),
            ).fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in rows]

    def get_messages_with_metadata(self, session_id: str) -> list[dict[str, Any]]:
        """Return oldest-first messages with assistant metadata for GET /sessions/{id}/messages."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content, metadata FROM messages WHERE session_id = ? ORDER BY id ASC;",
                (session_id,),
            ).fetchall()
            out: list[dict[str, Any]] = []
            for r in rows:
                item: dict[str, Any] = {"role": r["role"], "content": r["content"]}
                if r["role"] == "assistant" and r["metadata"]:
                    item["metadata"] = json.loads(r["metadata"])
                out.append(item)
            return out

    def list_sessions(self) -> list[dict[str, Any]]:
        """Return all persisted sessions ordered by most recent activity."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    s.session_id,
                    s.system_prompt,
                    s.created_at,
                    (
                        SELECT m.content
                        FROM messages m
                        WHERE m.session_id = s.session_id AND m.role = 'user'
                        ORDER BY m.id ASC
                        LIMIT 1
                    ) AS title,
                    (
                        SELECT MAX(m.created_at)
                        FROM messages m
                        WHERE m.session_id = s.session_id
                    ) AS updated_at,
                    (
                        SELECT COUNT(*)
                        FROM messages m
                        WHERE m.session_id = s.session_id
                    ) AS message_count
                FROM sessions s
                WHERE EXISTS (SELECT 1 FROM messages m WHERE m.session_id = s.session_id)
                ORDER BY updated_at DESC, s.created_at DESC;
                """
            ).fetchall()
            return [
                {
                    "session_id": r["session_id"],
                    "title": (r["title"] or "New Chat").strip(),
                    "system_prompt": r["system_prompt"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"] or r["created_at"],
                    "message_count": int(r["message_count"] or 0),
                }
                for r in rows
            ]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages from SQLite."""
        conn = self._connect()
        try:
            with conn:
                cur = conn.execute("DELETE FROM messages WHERE session_id = ?;", (session_id,))
                conn.execute("DELETE FROM sessions WHERE session_id = ?;", (session_id,))
                return cur.rowcount > 0
        finally:
            conn.close()

    def save_exchange(
        self,
        session_id: str,
        system_prompt: str | None,
        user_msg: str,
        assistant_msg: str,
        metadata: dict[str, Any],
    ) -> None:
        """Atomically upsert session and insert user + assistant messages in one transaction."""
        now = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(metadata)

        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO sessions (session_id, system_prompt, created_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        system_prompt = COALESCE(excluded.system_prompt, sessions.system_prompt);
                    """,
                    (session_id, system_prompt, now),
                )
                conn.execute(
                    """
                    INSERT INTO messages (session_id, role, content, metadata, created_at)
                    VALUES (?, 'user', ?, NULL, ?);
                    """,
                    (session_id, user_msg, now),
                )
                conn.execute(
                    """
                    INSERT INTO messages (session_id, role, content, metadata, created_at)
                    VALUES (?, 'assistant', ?, ?, ?);
                    """,
                    (session_id, assistant_msg, metadata_json, now),
                )
        finally:
            conn.close()
