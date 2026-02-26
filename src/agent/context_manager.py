"""
Core Agent Layer — context_manager.py

Maintains a rolling window of recent screen contexts, providing the
agent with short-term memory across consecutive capture cycles.
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Deque

logger = logging.getLogger(__name__)


@dataclass
class ContextEntry:
    """A single captured context snapshot."""

    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    scene: str = ""
    raw_text: str = ""
    extra: dict = field(default_factory=dict)


class ContextManager:
    """
    Maintains a sliding window of recent :class:`ContextEntry` objects.

    Parameters
    ----------
    max_entries:
        Maximum number of entries to keep in memory.
    """

    def __init__(self, max_entries: int = 20) -> None:
        self._window: Deque[ContextEntry] = deque(maxlen=max_entries)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, scene: str, raw_text: str, extra: dict | None = None) -> ContextEntry:
        """Create and store a new :class:`ContextEntry`."""
        entry = ContextEntry(scene=scene, raw_text=raw_text, extra=extra or {})
        self._window.append(entry)
        logger.debug("Context added: scene=%s, text_len=%d", scene, len(raw_text))
        return entry

    def clear(self) -> None:
        """Remove all stored context entries."""
        self._window.clear()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def latest(self) -> ContextEntry | None:
        """Return the most recently added entry, or ``None`` if empty."""
        return self._window[-1] if self._window else None

    def recent(self, n: int = 5) -> list[ContextEntry]:
        """Return up to *n* most recent entries, newest last."""
        entries = list(self._window)
        return entries[-n:]

    def summarise(self, n: int = 5) -> str:
        """
        Return a compact multi-line summary of the *n* most recent
        entries suitable for inclusion in an LLM prompt.
        """
        parts: list[str] = []
        for entry in self.recent(n):
            snippet = entry.raw_text[:200].replace("\n", " ")
            parts.append(f"[{entry.timestamp}] scene={entry.scene}: {snippet}")
        return "\n".join(parts)

    def __len__(self) -> int:
        return len(self._window)
