"""
Tests for the Frontend Interaction Layer.
"""

from pathlib import Path
import sys
import types

fake_tk = types.ModuleType("tkinter")
fake_tk.Tk = type("Tk", (), {})
fake_tk.Toplevel = type("Toplevel", (), {})
fake_tk.Misc = type("Misc", (), {})
fake_tk.StringVar = type("StringVar", (), {})
fake_messagebox = types.ModuleType("tkinter.messagebox")
fake_messagebox.showerror = lambda *args, **kwargs: None
fake_ttk = types.ModuleType("tkinter.ttk")
fake_font = types.ModuleType("tkinter.font")
fake_font.Font = type("Font", (), {})
fake_tk.messagebox = fake_messagebox
fake_tk.ttk = fake_ttk
fake_tk.font = fake_font
sys.modules.setdefault("tkinter", fake_tk)
sys.modules.setdefault("tkinter.messagebox", fake_messagebox)
sys.modules.setdefault("tkinter.ttk", fake_ttk)
sys.modules.setdefault("tkinter.font", fake_font)

import pytest

from src.storage.config_manager import ConfigManager
from src.ui.floating_window import FloatingWindow
from src.ui.settings_panel import SettingsPanel, _EDITABLE_FIELDS


class _DummyVar:
    def __init__(self, value: str) -> None:
        self._value = value

    def get(self) -> str:
        return self._value


class _DummyWin:
    def __init__(self) -> None:
        self.destroyed = False

    def destroy(self) -> None:
        self.destroyed = True


def test_settings_panel_invalid_value_shows_error(tmp_path: Path, monkeypatch):
    config = ConfigManager(config_path=tmp_path / "config.json")
    panel = SettingsPanel(config=config)

    entries = {}
    for _label, key, field_type in _EDITABLE_FIELDS:
        if field_type in {"int", "float"}:
            entries[key] = _DummyVar("1")
        else:
            entries[key] = _DummyVar("ok")
    entries["capture_interval_seconds"] = _DummyVar("not-an-int")
    panel._entries = entries

    captured = {}

    def fake_showerror(title, message, parent=None):
        captured["title"] = title
        captured["message"] = message
        captured["parent"] = parent

    monkeypatch.setattr("src.ui.settings_panel.messagebox.showerror", fake_showerror)
    monkeypatch.setattr(
        config, "update", lambda _updates: pytest.fail("update should not be called")
    )

    win = _DummyWin()
    panel._save(win)

    assert captured["title"] == "Invalid value"
    assert "Capture Interval (seconds)" in captured["message"]
    assert captured["parent"] is win
    assert win.destroyed is False


def test_floating_window_queue_updates_scene_and_capture_indicator():
    class _DummyLabel:
        def __init__(self):
            self.values = {}

        def config(self, **kwargs):
            self.values.update(kwargs)

    class _DummyText:
        def __init__(self):
            self.content = ""

        def config(self, **_kwargs):
            return None

        def insert(self, _where, text):
            self.content += text

        def see(self, _where):
            return None

        def delete(self, _start, _end):
            self.content = ""

    class _DummyRoot:
        def after(self, ms, callback):
            if ms == 180:
                callback()

    window = FloatingWindow()
    window._scene_label = _DummyLabel()
    window._capture_indicator = _DummyLabel()
    window._text_widget = _DummyText()
    window._root = _DummyRoot()

    window.notify_capture("")
    window.show_suggestion("coding_error", "ctx", "建议内容")
    window._poll_queue()

    assert "Coding Error" in window._scene_label.values["text"]
    assert "建议内容" in window._text_widget.content
    assert window._capture_indicator.values["fg"] == "#6c7086"
