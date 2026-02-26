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
fake_tk.messagebox = fake_messagebox
fake_tk.ttk = fake_ttk
sys.modules.setdefault("tkinter", fake_tk)
sys.modules.setdefault("tkinter.messagebox", fake_messagebox)
sys.modules.setdefault("tkinter.ttk", fake_ttk)

import pytest

from src.storage.config_manager import ConfigManager
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
