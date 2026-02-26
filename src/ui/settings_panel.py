"""
Frontend Interaction Layer — settings_panel.py

A simple Tkinter dialog that lets the user view and modify the
application configuration (API key, model, capture interval, …).
"""

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from src.storage.config_manager import ConfigManager

logger = logging.getLogger(__name__)

_EDITABLE_FIELDS = [
    ("LLM API Key", "llm_api_key", "password"),
    ("LLM Model", "llm_model", "text"),
    ("LLM Base URL", "llm_base_url", "text"),
    ("Capture Interval (seconds)", "capture_interval_seconds", "int"),
    ("OCR Language", "ocr_language", "text"),
    ("Window Opacity (0.1–1.0)", "floating_window_opacity", "float"),
]


class SettingsPanel:
    """
    Modal settings dialog.

    Parameters
    ----------
    config:
        The :class:`~storage.config_manager.ConfigManager` instance to
        read from and write to.
    on_saved:
        Optional callback invoked after settings are saved.
    """

    def __init__(
        self,
        config: ConfigManager,
        on_saved: Callable[[], None] | None = None,
    ) -> None:
        self.config = config
        self.on_saved = on_saved
        self._entries: dict[str, tk.StringVar] = {}

    def show(self, parent: tk.Misc | None = None) -> None:
        """Open the settings dialog (blocks until closed)."""
        win = tk.Toplevel(parent) if parent else tk.Tk()
        win.title("AI Assistant — Settings")
        win.resizable(False, False)
        win.grab_set()

        frame = ttk.Frame(win, padding=16)
        frame.pack(fill="both", expand=True)

        for row_idx, (label_text, key, field_type) in enumerate(_EDITABLE_FIELDS):
            ttk.Label(frame, text=label_text).grid(
                row=row_idx, column=0, sticky="w", pady=4, padx=(0, 12)
            )
            var = tk.StringVar(value=str(self.config.get(key, "")))
            self._entries[key] = var

            if field_type == "password":
                entry = ttk.Entry(frame, textvariable=var, show="*", width=36)
            else:
                entry = ttk.Entry(frame, textvariable=var, width=36)
            entry.grid(row=row_idx, column=1, sticky="ew", pady=4)

        frame.columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(win, padding=(16, 0, 16, 16))
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="Save", command=lambda: self._save(win)).pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side="right")

        win.wait_window()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save(self, win: tk.Toplevel | tk.Tk) -> None:
        updates: dict = {}
        for _label, key, field_type in _EDITABLE_FIELDS:
            raw = self._entries[key].get().strip()
            try:
                if field_type == "int":
                    updates[key] = int(raw)
                elif field_type == "float":
                    updates[key] = float(raw)
                else:
                    updates[key] = raw
            except ValueError:
                messagebox.showerror(
                    "Invalid value",
                    f"Invalid value for '{label_text}': {raw!r}",
                    parent=win,
                )
                return

        self.config.update(updates)
        logger.info("Settings saved.")
        if self.on_saved:
            self.on_saved()
        win.destroy()
