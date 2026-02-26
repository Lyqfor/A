"""
Core Agent Layer — agent_core.py

The central scheduling hub that orchestrates the full
``capture → OCR → recognise → analyse → suggest`` pipeline.

Each cycle runs in a background thread.  Detected suggestions are
delivered to registered callbacks so the UI layer remains decoupled.
"""

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable
import json

from src.agent.context_manager import ContextManager
from src.agent.scene_recognizer import SceneRecognizer, SCENE_UNKNOWN
from src.storage.config_manager import ConfigManager
from src.storage.database import Database
from src.tools import llm_client as llm_module
from src.tools import ocr_tool, screen_capture

logger = logging.getLogger(__name__)

SuggestionCallback = Callable[[str, str, str], None]
"""Callback signature: ``(scene, context_snippet, suggestion) -> None``."""
CaptureCallback = Callable[[str], None]

# Minimum confidence threshold to trigger an LLM call
_MIN_CONFIDENCE = 0.2


class AgentCore:
    """
    Orchestrates the perception–reasoning–action loop.

    Parameters
    ----------
    config:
        Application configuration (API keys, intervals, …).
    db:
        Persistent storage for logs and suggestion history.
    """

    def __init__(self, config: ConfigManager, db: Database) -> None:
        self.config = config
        self.db = db
        self.context_manager = ContextManager()
        self.scene_recognizer = SceneRecognizer(
            enabled_scenes=config.get("enabled_scenes")
        )
        self._llm: llm_module.LLMClient | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._callbacks: list[SuggestionCallback] = []
        self._capture_callbacks: list[CaptureCallback] = []
        self._lock = threading.Lock()
        self._log_dir = Path.home() / ".ai_assistant"
        self._capture_dir = self._log_dir / "captures"
        self._pipeline_log_path = self._log_dir / "pipeline_log.jsonl"
        self._capture_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # LLM client (lazily initialised when needed)
    # ------------------------------------------------------------------

    def _get_llm(self) -> llm_module.LLMClient:
        if self._llm is None:
            self._llm = llm_module.LLMClient(
                api_key=self.config.get("llm_api_key", ""),
                model=self.config.get("llm_model", "gpt-4o-mini"),
                base_url=self.config.get("llm_base_url", "https://api.openai.com/v1"),
            )
        return self._llm

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def register_callback(self, callback: SuggestionCallback) -> None:
        """Register a function to be called whenever a suggestion is ready."""
        with self._lock:
            self._callbacks.append(callback)

    def register_capture_callback(self, callback: CaptureCallback) -> None:
        """Register a function called after each screenshot capture."""
        with self._lock:
            self._capture_callbacks.append(callback)

    def _fire_callbacks(self, scene: str, context: str, suggestion: str) -> None:
        with self._lock:
            callbacks = list(self._callbacks)
        for cb in callbacks:
            try:
                cb(scene, context, suggestion)
            except Exception as exc:
                logger.error("Callback %s raised: %s", cb, exc)

    def _fire_capture_callbacks(self, image_path: str) -> None:
        with self._lock:
            callbacks = list(self._capture_callbacks)
        for cb in callbacks:
            try:
                cb(image_path)
            except Exception as exc:
                logger.error("Capture callback %s raised: %s", cb, exc)

    def _append_pipeline_log(
        self,
        image_path: str,
        ocr_text: str,
        scene: str,
        intent: str,
        confidence: float = 0.0,
    ) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "image_path": image_path,
            "ocr_text": ocr_text,
            "scene": scene,
            "intent_result": intent,
            "confidence": confidence,
        }
        try:
            with self._pipeline_log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("Failed to write pipeline log: %s", exc)

    # ------------------------------------------------------------------
    # Single pipeline cycle (public for testing)
    # ------------------------------------------------------------------

    def run_once(self) -> str | None:
        """
        Execute one full capture→OCR→recognise→suggest cycle.

        Returns the suggestion string, or ``None`` when no action was
        taken (low confidence, empty screen, …).
        """
        # 1. Screen capture
        image = screen_capture.capture_screen()
        image_path = ""
        if image is not None:
            image_name = f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
            image_file = self._capture_dir / image_name
            try:
                image.save(image_file)
                image_path = str(image_file)
            except OSError as exc:
                logger.warning("Failed to save screenshot: %s", exc)
        self._fire_capture_callbacks(image_path)

        # 2. OCR
        lang = self.config.get("ocr_language", "chi_sim+eng")
        text = ocr_tool.extract_text(image, ocr_language=lang) if image else ""

        if not text:
            logger.debug("No text extracted from screen; skipping cycle.")
            self._append_pipeline_log(
                image_path=image_path,
                ocr_text="",
                scene=SCENE_UNKNOWN,
                intent="",
            )
            return None

        # 3. Scene recognition
        result = self.scene_recognizer.recognise(text)
        if result.scene == SCENE_UNKNOWN or result.confidence < _MIN_CONFIDENCE:
            logger.debug(
                "Scene unrecognised or low confidence (%.2f); skipping.",
                result.confidence,
            )
            self._append_pipeline_log(
                image_path=image_path,
                ocr_text=text,
                scene=result.scene,
                intent="",
                confidence=result.confidence,
            )
            return None

        # 4. Store context
        context_entry = self.context_manager.add(
            scene=result.scene,
            raw_text=text,
            extra={"confidence": result.confidence},
        )
        self.db.log_operation(
            scene=result.scene,
            context=text[:500],
            extra={"confidence": result.confidence, "image_path": image_path},
        )

        # 5. Build context for LLM (include short history)
        history_summary = self.context_manager.summarise(n=3)
        llm_context = f"{history_summary}\n\nLatest capture:\n{text[:1000]}"

        # 6. LLM call
        prompt_template = self.config.get_intent_prompt()
        suggestion_count = int(self.config.get("next_step_suggestion_count", 3))
        try:
            system_prompt = prompt_template.format(suggestion_count=suggestion_count)
        except Exception as exc:
            logger.warning(
                "Failed to format intent prompt template with suggestion_count=%s: %s",
                suggestion_count,
                exc,
            )
            system_prompt = prompt_template
        suggestion = self._get_llm().get_suggestion(
            result.scene,
            llm_context,
            system_prompt=system_prompt,
        )

        # 7. Persist and dispatch
        suggestion_id = self.db.save_suggestion(result.scene, suggestion)
        logger.info(
            "Suggestion #%d generated for scene '%s'.", suggestion_id, result.scene
        )
        self._append_pipeline_log(
            image_path=image_path,
            ocr_text=text,
            scene=result.scene,
            intent=suggestion,
            confidence=result.confidence,
        )
        self._fire_callbacks(result.scene, text[:300], suggestion)
        return suggestion

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background capture-analyse loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, name="AgentCoreLoop", daemon=True
        )
        self._thread.start()
        logger.info("AgentCore started.")

    def stop(self) -> None:
        """Signal the background loop to stop and wait for it to exit."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None
        logger.info("AgentCore stopped.")

    def _loop(self) -> None:
        interval = self.config.get("capture_interval_seconds", 3)
        while self._running:
            try:
                self.run_once()
            except Exception as exc:
                logger.error("Unhandled error in agent loop: %s", exc)
            time.sleep(interval)
