"""
Tests for the Core Agent Layer.
"""

import pytest

from src.agent.context_manager import ContextEntry, ContextManager
from src.agent.scene_recognizer import (
    SCENE_CODING_ERROR,
    SCENE_DOCUMENT_EDITING,
    SCENE_UNKNOWN,
    SCENE_UNKNOWN_TERM,
    SCENE_WEB_BROWSING,
    SceneRecognizer,
)


# ---------------------------------------------------------------------------
# ContextManager tests
# ---------------------------------------------------------------------------

class TestContextManager:
    def test_add_and_latest(self):
        cm = ContextManager()
        cm.add("coding_error", "Traceback (most recent call last):")
        latest = cm.latest()
        assert latest is not None
        assert latest.scene == "coding_error"
        assert "Traceback" in latest.raw_text

    def test_len_reflects_entries(self):
        cm = ContextManager()
        assert len(cm) == 0
        cm.add("web_browsing", "https://example.com")
        cm.add("unknown_term", "What is Docker?")
        assert len(cm) == 2

    def test_max_entries_evicts_old(self):
        cm = ContextManager(max_entries=3)
        for i in range(5):
            cm.add("coding_error", f"error {i}")
        assert len(cm) == 3
        # The oldest entry should have been evicted
        texts = [e.raw_text for e in cm.recent(10)]
        assert "error 0" not in texts
        assert "error 4" in texts

    def test_recent_returns_at_most_n(self):
        cm = ContextManager()
        for i in range(10):
            cm.add("coding_error", f"e{i}")
        assert len(cm.recent(5)) == 5

    def test_clear(self):
        cm = ContextManager()
        cm.add("coding_error", "err")
        cm.clear()
        assert len(cm) == 0
        assert cm.latest() is None

    def test_summarise_format(self):
        cm = ContextManager()
        cm.add("coding_error", "SyntaxError: invalid syntax")
        summary = cm.summarise(n=1)
        assert "scene=coding_error" in summary
        assert "SyntaxError" in summary

    def test_entry_has_timestamp(self):
        cm = ContextManager()
        entry = cm.add("web_browsing", "http://example.com")
        assert entry.timestamp  # non-empty string


# ---------------------------------------------------------------------------
# SceneRecognizer tests
# ---------------------------------------------------------------------------

class TestSceneRecognizer:
    def _rec(self):
        return SceneRecognizer()

    def test_coding_error_from_traceback(self):
        text = (
            "Traceback (most recent call last):\n"
            '  File "main.py", line 5, in <module>\n'
            "TypeError: unsupported operand type(s)"
        )
        result = self._rec().recognise(text)
        assert result.scene == SCENE_CODING_ERROR
        assert result.confidence > 0

    def test_coding_error_from_exception_name(self):
        result = self._rec().recognise("SyntaxError: invalid syntax on line 12")
        assert result.scene == SCENE_CODING_ERROR

    def test_web_browsing_from_url(self):
        result = self._rec().recognise(
            "Open your browser at https://github.com/user/repo"
        )
        assert result.scene == SCENE_WEB_BROWSING

    def test_document_editing_from_keywords(self):
        result = self._rec().recognise(
            "Abstract: This document presents an introduction to machine learning."
        )
        assert result.scene == SCENE_DOCUMENT_EDITING

    def test_unknown_term_from_question(self):
        result = self._rec().recognise("What is Kubernetes?")
        assert result.scene == SCENE_UNKNOWN_TERM

    def test_empty_text_returns_unknown(self):
        result = self._rec().recognise("")
        assert result.scene == SCENE_UNKNOWN
        assert result.confidence == 0.0

    def test_whitespace_only_returns_unknown(self):
        result = self._rec().recognise("   \n\t  ")
        assert result.scene == SCENE_UNKNOWN

    def test_matched_keywords_populated(self):
        result = self._rec().recognise("Traceback: ValueError on line 3")
        assert len(result.matched_keywords) > 0

    def test_disabled_scene_not_returned(self):
        recogniser = SceneRecognizer(
            enabled_scenes=[SCENE_WEB_BROWSING, SCENE_DOCUMENT_EDITING]
        )
        result = recogniser.recognise(
            "Traceback (most recent call last):\nTypeError: bad type"
        )
        # coding_error is disabled, so should not be returned
        assert result.scene != SCENE_CODING_ERROR

    def test_high_confidence_for_strong_signals(self):
        text = (
            "Traceback\nError\nException\nSyntaxError\nValueError\nTypeError"
        )
        result = self._rec().recognise(text)
        assert result.confidence == pytest.approx(1.0)
