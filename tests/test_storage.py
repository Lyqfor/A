"""
Tests for the Data Storage Layer.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.storage.config_manager import ConfigManager, _DEFAULTS
from src.storage.database import Database


# ---------------------------------------------------------------------------
# ConfigManager tests
# ---------------------------------------------------------------------------

class TestConfigManager:
    def _make_config(self, tmp_path: Path) -> ConfigManager:
        return ConfigManager(config_path=tmp_path / "config.json")

    def test_defaults_applied_on_first_load(self, tmp_path):
        cfg = self._make_config(tmp_path)
        for key, value in _DEFAULTS.items():
            assert cfg.get(key) == value

    def test_set_and_get(self, tmp_path):
        cfg = self._make_config(tmp_path)
        cfg.set("llm_model", "gpt-4o")
        assert cfg.get("llm_model") == "gpt-4o"

    def test_persistence_across_instances(self, tmp_path):
        path = tmp_path / "config.json"
        cfg1 = ConfigManager(config_path=path)
        cfg1.set("llm_api_key", "test-key-123")

        cfg2 = ConfigManager(config_path=path)
        assert cfg2.get("llm_api_key") == "test-key-123"

    def test_update_multiple_keys(self, tmp_path):
        cfg = self._make_config(tmp_path)
        cfg.update({"llm_model": "gpt-3.5-turbo", "capture_interval_seconds": 5})
        assert cfg.get("llm_model") == "gpt-3.5-turbo"
        assert cfg.get("capture_interval_seconds") == 5

    def test_reset_to_defaults(self, tmp_path):
        cfg = self._make_config(tmp_path)
        cfg.set("llm_model", "custom-model")
        cfg.reset_to_defaults()
        assert cfg.get("llm_model") == _DEFAULTS["llm_model"]

    def test_all_returns_copy(self, tmp_path):
        cfg = self._make_config(tmp_path)
        data = cfg.all()
        data["llm_model"] = "mutated"
        # Original should be unaffected
        assert cfg.get("llm_model") == _DEFAULTS["llm_model"]

    def test_get_missing_key_with_default(self, tmp_path):
        cfg = self._make_config(tmp_path)
        assert cfg.get("nonexistent_key", "fallback") == "fallback"

    def test_corrupt_config_falls_back_to_defaults(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text("{ not valid json }", encoding="utf-8")
        cfg = ConfigManager(config_path=path)
        assert cfg.get("llm_model") == _DEFAULTS["llm_model"]

    def test_get_intent_prompt_reads_from_file(self, tmp_path):
        cfg = self._make_config(tmp_path)
        prompt_path = tmp_path / "intent_prompt.txt"
        prompt_path.write_text("test prompt {suggestion_count}", encoding="utf-8")
        cfg.set("intent_prompt_file", str(prompt_path))
        assert "test prompt" in cfg.get_intent_prompt()


# ---------------------------------------------------------------------------
# Database tests
# ---------------------------------------------------------------------------

class TestDatabase:
    def _make_db(self, tmp_path: Path) -> Database:
        return Database(db_path=tmp_path / "test.db")

    def test_log_operation_returns_id(self, tmp_path):
        db = self._make_db(tmp_path)
        row_id = db.log_operation("coding_error", "Traceback...")
        assert isinstance(row_id, int)
        assert row_id >= 1
        db.close()

    def test_get_recent_logs(self, tmp_path):
        db = self._make_db(tmp_path)
        db.log_operation("coding_error", "err1")
        db.log_operation("web_browsing", "url1")
        logs = db.get_recent_logs(limit=10)
        assert len(logs) == 2
        # Most recent first
        assert logs[0]["scene"] == "web_browsing"
        db.close()

    def test_save_and_retrieve_suggestion(self, tmp_path):
        db = self._make_db(tmp_path)
        sid = db.save_suggestion("unknown_term", "This term means X.")
        history = db.get_suggestion_history(limit=10)
        assert len(history) == 1
        assert history[0]["id"] == sid
        assert history[0]["scene"] == "unknown_term"
        assert history[0]["executed"] == 0
        db.close()

    def test_mark_suggestion_executed(self, tmp_path):
        db = self._make_db(tmp_path)
        sid = db.save_suggestion("coding_error", "Run: pip install X")
        db.mark_suggestion_executed(sid)
        history = db.get_suggestion_history()
        assert history[0]["executed"] == 1
        db.close()

    def test_record_feedback(self, tmp_path):
        db = self._make_db(tmp_path)
        sid = db.save_suggestion("document_editing", "Polish this paragraph.")
        db.record_feedback(sid, "helpful")
        history = db.get_suggestion_history()
        assert history[0]["feedback"] == "helpful"
        db.close()

    def test_get_recent_logs_limit(self, tmp_path):
        db = self._make_db(tmp_path)
        for i in range(10):
            db.log_operation("coding_error", f"context {i}")
        logs = db.get_recent_logs(limit=3)
        assert len(logs) == 3
        db.close()

    def test_log_operation_with_extra(self, tmp_path):
        db = self._make_db(tmp_path)
        db.log_operation("web_browsing", "some url", extra={"confidence": 0.8})
        logs = db.get_recent_logs()
        extra = json.loads(logs[0]["extra"])
        assert extra["confidence"] == pytest.approx(0.8)
        db.close()
