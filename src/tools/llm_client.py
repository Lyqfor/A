"""
Tool Call Layer — llm_client.py

Wraps the OpenAI-compatible Chat Completions API.  The base URL and
model are read from ConfigManager so that users can point the client
at any OpenAI-compatible endpoint (e.g. local Ollama, Azure OpenAI).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# System prompt shared across all scene analyses
_SYSTEM_PROMPT = (
    "You are a proactive desktop AI assistant. "
    "Analyse the provided screen context and return a concise, actionable "
    "suggestion in the same language as the context. "
    "Keep the reply under 120 words."
)


class LLMClient:
    """Thin wrapper around the OpenAI Chat Completions API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client: Any = None

    # ------------------------------------------------------------------
    # Lazy client initialisation
    # ------------------------------------------------------------------

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI

                self._client = OpenAI(
                    api_key=self.api_key, base_url=self.base_url
                )
            except ImportError as exc:
                raise RuntimeError(
                    "openai package is required. Install it with: pip install openai"
                ) from exc
        return self._client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_suggestion(self, scene: str, context: str) -> str:
        """
        Request a suggestion from the LLM for *scene* and *context*.

        Parameters
        ----------
        scene:
            A short label describing the detected scene
            (e.g. ``"coding_error"``, ``"unknown_term"``).
        context:
            The screen text / context relevant to the scene.

        Returns
        -------
        str
            The LLM's suggestion, or an error message string on failure.
        """
        if not self.api_key:
            logger.warning("LLM API key not configured; skipping request.")
            return "[LLM API key not configured]"

        user_message = f"Scene: {scene}\n\nContext:\n{context}"
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=200,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.error("LLM request failed: %s", exc)
            return f"[LLM error: {exc}]"
