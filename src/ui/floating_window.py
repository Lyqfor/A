"""
Frontend Interaction Layer — floating_window.py

A lightweight always-on-top floating window built with tkinter that:
  - Displays AI suggestions with scene label, text, and action buttons
  - Shows a brief fade-in animation when a new suggestion arrives
  - Provides "Execute" and "Dismiss" buttons
  - Exposes ``show_suggestion()`` for thread-safe updates from AgentCore
"""

import logging
import queue
import tkinter as tk
from tkinter import font as tkfont
from typing import Callable
from datetime import datetime

logger = logging.getLogger(__name__)

_WINDOW_WIDTH = 380
_WINDOW_HEIGHT = 280
_PADDING = 12
_MAX_DISPLAY_TEXT_LENGTH = 200

_SCENE_ICONS = {
    "coding_error": "🐛",
    "unknown_term": "📖",
    "document_editing": "✏️",
    "web_browsing": "🌐",
    "unknown": "💡",
}


class FloatingWindow:
    """
    Tkinter-based always-on-top suggestion window.

    Parameters
    ----------
    on_execute:
        Called with ``(scene, suggestion)`` when the user clicks Execute.
    opacity:
        Window transparency (0.0 transparent – 1.0 opaque).
    """

    def __init__(
        self,
        on_execute: Callable[[str, str], None] | None = None,
        opacity: float = 0.92,
    ) -> None:
        self._on_execute = on_execute
        self._opacity = max(0.1, min(1.0, opacity))
        self._root: tk.Tk | None = None
        self._queue: queue.Queue = queue.Queue()
        self._current_scene = ""
        self._current_suggestion = ""

    # ------------------------------------------------------------------
    # Thread-safe public API
    # ------------------------------------------------------------------

    def show_suggestion(self, scene: str, context: str, suggestion: str) -> None:
        """
        Enqueue a suggestion for display.  Safe to call from any thread.
        """
        self._queue.put(("suggestion", scene, suggestion))

    def notify_capture(self, image_path: str) -> None:
        self._queue.put(("capture", image_path, ""))

    def run(self) -> None:
        """
        Build the window and enter the Tk main loop (blocks the calling
        thread).  Call this from the main thread.
        """
        self._build_window()
        self._poll_queue()
        self._root.mainloop()  # type: ignore[union-attr]

    def destroy(self) -> None:
        """Destroy the window from any thread."""
        if self._root:
            self._root.after(0, self._root.destroy)

    # ------------------------------------------------------------------
    # Window construction
    # ------------------------------------------------------------------

    def _build_window(self) -> None:
        root = tk.Tk()
        root.title("AI Assistant")
        root.geometry(f"{_WINDOW_WIDTH}x{_WINDOW_HEIGHT}+20+20")
        root.attributes("-topmost", True)
        root.attributes("-alpha", self._opacity)
        root.resizable(False, False)
        root.configure(bg="#1e1e2e")

        # Fonts
        label_font = tkfont.Font(family="Helvetica", size=10, weight="bold")
        text_font = tkfont.Font(family="Helvetica", size=10)
        btn_font = tkfont.Font(family="Helvetica", size=9)

        # Scene label row
        top_frame = tk.Frame(root, bg="#1e1e2e")
        top_frame.pack(fill="x", pady=(8, 2))
        self._scene_label = tk.Label(
            top_frame,
            text="💡 Waiting for context…",
            font=label_font,
            fg="#cdd6f4",
            bg="#1e1e2e",
            anchor="w",
            padx=_PADDING,
        )
        self._scene_label.pack(side="left", fill="x", expand=True)
        self._capture_indicator = tk.Label(
            top_frame,
            text="●",
            font=label_font,
            fg="#6c7086",
            bg="#1e1e2e",
            padx=_PADDING,
        )
        self._capture_indicator.pack(side="right")

        # Suggestion text (scrollable)
        text_frame = tk.Frame(root, bg="#1e1e2e")
        text_frame.pack(fill="both", expand=True, padx=_PADDING, pady=(0, 4))
        self._text_widget = tk.Text(
            text_frame,
            font=text_font,
            fg="#a6e3a1",
            bg="#313244",
            wrap="word",
            relief="flat",
            padx=8,
            pady=8,
            height=8,
        )
        self._text_widget.pack(side="left", fill="both", expand=True)
        self._text_widget.config(state="disabled")
        scrollbar = tk.Scrollbar(
            text_frame,
            command=self._text_widget.yview,
            bg="#45475a",
            troughcolor="#1e1e2e",
            activebackground="#585b70",
        )
        scrollbar.pack(side="right", fill="y")
        self._text_widget.config(yscrollcommand=scrollbar.set)

        # Button row
        btn_frame = tk.Frame(root, bg="#1e1e2e")
        btn_frame.pack(fill="x", pady=(6, 8), padx=_PADDING)

        self._exec_btn = tk.Button(
            btn_frame,
            text="✔ Execute",
            font=btn_font,
            fg="#1e1e2e",
            bg="#a6e3a1",
            activebackground="#94e2a0",
            relief="flat",
            padx=8,
            pady=3,
            command=self._on_execute_clicked,
        )
        self._exec_btn.pack(side="left", padx=(0, 6))

        dismiss_btn = tk.Button(
            btn_frame,
            text="✖ Dismiss",
            font=btn_font,
            fg="#cdd6f4",
            bg="#45475a",
            activebackground="#585b70",
            relief="flat",
            padx=8,
            pady=3,
            command=self._dismiss,
        )
        dismiss_btn.pack(side="left")

        self._root = root

    # ------------------------------------------------------------------
    # Queue polling
    # ------------------------------------------------------------------

    def _poll_queue(self) -> None:
        try:
            while True:
                event, value, suggestion = self._queue.get_nowait()
                if event == "capture":
                    self._on_capture()
                else:
                    self._display(value, suggestion)
        except queue.Empty:
            pass
        if self._root:
            self._root.after(200, self._poll_queue)

    def _display(self, scene: str, suggestion: str) -> None:
        self._current_scene = scene
        self._current_suggestion = suggestion
        icon = _SCENE_ICONS.get(scene, "💡")
        self._scene_label.config(text=f"{icon}  {scene.replace('_', ' ').title()}")
        display_text = suggestion[:_MAX_DISPLAY_TEXT_LENGTH] + ("…" if len(suggestion) > _MAX_DISPLAY_TEXT_LENGTH else "")
        self._append_text(
            f"[{datetime.now().strftime('%H:%M:%S')}] {scene}\n{display_text}\n\n"
        )
        logger.debug("Floating window updated: scene=%s", scene)

    def _append_text(self, text: str) -> None:
        self._text_widget.config(state="normal")
        self._text_widget.insert("end", text)
        self._text_widget.see("end")
        self._text_widget.config(state="disabled")

    def _on_capture(self) -> None:
        self._capture_indicator.config(fg="#f9e2af")
        if self._root:
            self._root.after(180, lambda: self._capture_indicator.config(fg="#6c7086"))

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_execute_clicked(self) -> None:
        if self._on_execute and self._current_suggestion:
            self._on_execute(self._current_scene, self._current_suggestion)
        self._dismiss()

    def _dismiss(self) -> None:
        self._text_widget.config(state="normal")
        self._text_widget.delete("1.0", "end")
        self._text_widget.config(state="disabled")
        self._scene_label.config(text="💡 Waiting for context…")
        self._current_scene = ""
        self._current_suggestion = ""
