"""
Tool Call Layer — command_executor.py

Safely executes whitelisted shell commands that the agent may suggest
(e.g. ``pip install <package>``, ``git stash``).
"""

import logging
import shlex
import subprocess
from typing import NamedTuple

logger = logging.getLogger(__name__)

# Commands that may never be executed regardless of input
_BLOCKED_PREFIXES = (
    "rm -rf",
    "sudo rm",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",  # fork bomb
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
)


class CommandResult(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


def is_safe_command(command: str) -> bool:
    """
    Return *True* when *command* does not match any blocked prefix.

    This is a basic safety gate; production deployments should use a
    proper allow-list approach.
    """
    normalised = command.strip().lower()
    return not any(normalised.startswith(blocked) for blocked in _BLOCKED_PREFIXES)


def execute_command(command: str, timeout: int = 30) -> CommandResult:
    """
    Execute *command* in a subprocess and return the result.

    Parameters
    ----------
    command:
        The shell command to run.
    timeout:
        Maximum seconds to wait before raising ``TimeoutError``.

    Returns
    -------
    CommandResult
        A named tuple with ``returncode``, ``stdout``, and ``stderr``.

    Raises
    ------
    ValueError
        If *command* matches a blocked pattern.
    """
    if not is_safe_command(command):
        raise ValueError(f"Command rejected by safety policy: {command!r}")

    logger.info("Executing command: %s", command)
    try:
        result = subprocess.run(
            shlex.split(command),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return CommandResult(
            returncode=result.returncode,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
        )
    except subprocess.TimeoutExpired:
        logger.error("Command timed out after %ds: %s", timeout, command)
        return CommandResult(returncode=-1, stdout="", stderr="Command timed out")
    except FileNotFoundError as exc:
        logger.error("Command not found: %s", exc)
        return CommandResult(returncode=127, stdout="", stderr=str(exc))
