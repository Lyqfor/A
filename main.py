"""
Entry point — main.py

Wires together all four architectural layers and starts the application:
  1. Data Storage Layer  — ConfigManager + Database
  2. Core Agent Layer    — AgentCore (background thread)
  3. Tool Call Layer     — used internally by AgentCore
  4. Frontend Layer      — FloatingWindow (main thread)
"""

import logging
import sys

from src.agent.agent_core import AgentCore
from src.storage.config_manager import ConfigManager
from src.storage.database import Database
from src.tools.command_executor import execute_command, is_safe_command
from src.ui.floating_window import FloatingWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _handle_execute(scene: str, suggestion: str) -> None:
    """
    Called by the floating window when the user clicks "Execute".

    For coding-error scenes the suggestion may contain a shell command
    (e.g. ``pip install …``); we attempt to run it safely.  For all
    other scenes we simply log the action.
    """
    if scene == "coding_error":
        # Extract the first code-fence or line that looks like a command
        for line in suggestion.splitlines():
            line = line.strip().strip("`")
            if line and is_safe_command(line):
                logger.info("Executing suggested command: %s", line)
                result = execute_command(line)
                logger.info(
                    "Command finished (rc=%d): %s", result.returncode, result.stdout
                )
                return
    logger.info("Suggestion for scene '%s' noted (no command executed).", scene)


def main() -> None:
    # ------------------------------------------------------------------
    # Layer 1 – Data Storage
    # ------------------------------------------------------------------
    config = ConfigManager()
    db = Database()

    # ------------------------------------------------------------------
    # Layer 2 – Core Agent (background thread)
    # ------------------------------------------------------------------
    agent = AgentCore(config=config, db=db)

    # ------------------------------------------------------------------
    # Layer 4 – Frontend (floating window)
    # ------------------------------------------------------------------
    opacity = config.get("floating_window_opacity", 0.92)
    window = FloatingWindow(on_execute=_handle_execute, opacity=opacity)

    # Connect the agent's output to the floating window
    agent.register_callback(window.show_suggestion)
    agent.register_capture_callback(window.notify_capture)

    # Start the agent loop before entering the Tk event loop
    agent.start()
    logger.info("AI Assistant started. Press Ctrl-C in terminal to quit.")

    try:
        window.run()  # blocks until window is closed
    except KeyboardInterrupt:
        pass
    finally:
        agent.stop()
        db.close()
        logger.info("AI Assistant shut down cleanly.")


if __name__ == "__main__":
    main()
