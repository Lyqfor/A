"""
Data Storage Layer — database.py

Provides a lightweight SQLite-based store for:
  - Operation logs
  - Suggestion history
  - User feedback on suggestions
"""

import sqlite3
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.home() / ".ai_assistant" / "assistant.db"


class Database:
    """Manages a local SQLite database for the AI assistant."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        self._init_db()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path), check_same_thread=False
            )
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Schema initialisation
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS operation_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                scene       TEXT    NOT NULL,
                context     TEXT    NOT NULL,
                extra       TEXT    DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS suggestion_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                scene       TEXT    NOT NULL,
                suggestion  TEXT    NOT NULL,
                executed    INTEGER NOT NULL DEFAULT 0,
                feedback    TEXT    DEFAULT NULL
            );
            """
        )
        conn.commit()
        logger.debug("Database schema initialised at %s", self.db_path)

    # ------------------------------------------------------------------
    # Operation logs
    # ------------------------------------------------------------------

    def log_operation(
        self, scene: str, context: str, extra: dict[str, Any] | None = None
    ) -> int:
        """Insert a new operation log entry and return its row id."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "INSERT INTO operation_logs (timestamp, scene, context, extra) VALUES (?, ?, ?, ?)",
                (
                    datetime.now(timezone.utc).isoformat(),
                    scene,
                    context,
                    json.dumps(extra or {}),
                ),
            )
            conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]

    def get_recent_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent operation logs."""
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM operation_logs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Suggestion history
    # ------------------------------------------------------------------

    def save_suggestion(self, scene: str, suggestion: str) -> int:
        """Persist a suggestion and return its row id."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "INSERT INTO suggestion_history (timestamp, scene, suggestion) VALUES (?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), scene, suggestion),
            )
            conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]

    def mark_suggestion_executed(self, suggestion_id: int) -> None:
        """Mark a suggestion as executed by the user."""
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "UPDATE suggestion_history SET executed = 1 WHERE id = ?",
                (suggestion_id,),
            )
            conn.commit()

    def record_feedback(self, suggestion_id: int, feedback: str) -> None:
        """Store free-text user feedback for a suggestion."""
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "UPDATE suggestion_history SET feedback = ? WHERE id = ?",
                (feedback, suggestion_id),
            )
            conn.commit()

    def get_suggestion_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return the most recent suggestion history entries."""
        with self._lock:
            rows = self._get_conn().execute(
                "SELECT * FROM suggestion_history ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
