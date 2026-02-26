"""
Data Storage Layer — config_manager.py

Persists and retrieves user-facing configuration settings using a
JSON file stored in the user's home directory.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path.home() / ".ai_assistant" / "config.json"

_DEFAULTS: dict[str, Any] = {
    "llm_api_key": "75130a63-7342-4c55-8cf7-1f8f276d6818",  # 替换为你的Bearer后的真实API密钥（即curl里的XXX）
    "llm_model": "doubao-1-5-lite-32k-250115",
    "llm_base_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
    # "llm_api_key": "",
    # "llm_model": "gpt-4o-mini",
    # "llm_base_url": "https://api.openai.com/v1",
    "capture_interval_seconds": 3,
    "ocr_language": "chi_sim+eng",
    "floating_window_opacity": 0.92,
    "max_suggestion_history": 100,
    "enabled_scenes": [
        "coding_error",
        "unknown_term",
        "document_editing",
        "web_browsing",
    ],
}


class ConfigManager:
    """Read/write persistent JSON configuration."""

    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if self.config_path.exists():
            try:
                with self.config_path.open("r", encoding="utf-8") as fh:
                    self._data = json.load(fh)
                logger.debug("Config loaded from %s", self.config_path)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load config (%s); using defaults.", exc)
                self._data = {}
        # Merge missing keys from defaults
        for key, value in _DEFAULTS.items():
            self._data.setdefault(key, value)

    def _save(self) -> None:
        try:
            with self.config_path.open("w", encoding="utf-8") as fh:
                json.dump(self._data, fh, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.error("Failed to save config: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Return a configuration value, falling back to *default*."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Persist a configuration value."""
        self._data[key] = value
        self._save()

    def update(self, updates: dict[str, Any]) -> None:
        """Batch-update multiple configuration values."""
        self._data.update(updates)
        self._save()

    def all(self) -> dict[str, Any]:
        """Return a shallow copy of the full configuration dict."""
        return dict(self._data)

    def reset_to_defaults(self) -> None:
        """Overwrite the configuration with built-in defaults."""
        self._data = dict(_DEFAULTS)
        self._save()
