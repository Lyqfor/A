"""
Tests for the Tool Call Layer.
"""

import pytest

from src.tools.command_executor import (
    CommandResult,
    execute_command,
    is_safe_command,
)
from src.tools.ocr_tool import extract_text
from src.tools.llm_client import LLMClient


# ---------------------------------------------------------------------------
# CommandExecutor tests
# ---------------------------------------------------------------------------

class TestIsSafeCommand:
    def test_safe_echo(self):
        assert is_safe_command("echo hello") is True

    def test_safe_pip_install(self):
        assert is_safe_command("pip install requests") is True

    def test_blocked_rm_rf(self):
        assert is_safe_command("rm -rf /") is False

    def test_blocked_case_insensitive(self):
        assert is_safe_command("RM -RF /home") is False

    def test_blocked_shutdown(self):
        assert is_safe_command("shutdown -h now") is False

    def test_blocked_sudo_rm(self):
        assert is_safe_command("sudo rm important_file") is False

    def test_blocked_dd(self):
        assert is_safe_command("dd if=/dev/zero of=/dev/sda") is False


class TestExecuteCommand:
    def test_echo_returns_output(self):
        result = execute_command("echo hello_world")
        assert result.returncode == 0
        assert "hello_world" in result.stdout

    def test_blocked_command_raises(self):
        with pytest.raises(ValueError, match="rejected by safety policy"):
            execute_command("rm -rf /tmp/test_dir")

    def test_nonexistent_command(self):
        result = execute_command("nonexistent_cmd_xyz_123")
        assert result.returncode != 0

    def test_result_is_named_tuple(self):
        result = execute_command("echo test")
        assert isinstance(result, CommandResult)
        assert hasattr(result, "returncode")
        assert hasattr(result, "stdout")
        assert hasattr(result, "stderr")


# ---------------------------------------------------------------------------
# OCR tool tests (unit — mocks PIL, does not require Tesseract)
# ---------------------------------------------------------------------------

class TestExtractText:
    def test_none_image_returns_empty(self):
        assert extract_text(None) == ""  # type: ignore[arg-type]

    def test_pytesseract_unavailable_returns_empty(self, monkeypatch):
        """When pytesseract raises an exception, extract_text returns ''."""
        import src.tools.ocr_tool as ocr_mod

        class FakeImage:
            pass

        def _raising_import(name, *args, **kwargs):
            if name == "pytesseract":
                raise ImportError("No module named 'pytesseract'")
            return original_import(name, *args, **kwargs)

        import builtins
        original_import = builtins.__import__
        monkeypatch.setattr(builtins, "__import__", _raising_import)
        result = ocr_mod.extract_text(FakeImage())  # type: ignore[arg-type]
        assert result == ""


# ---------------------------------------------------------------------------
# LLMClient tests (unit — no real API calls)
# ---------------------------------------------------------------------------

class TestLLMClient:
    def test_no_api_key_returns_placeholder(self):
        client = LLMClient(api_key="")
        suggestion = client.get_suggestion("coding_error", "Traceback...")
        assert "[LLM API key not configured]" in suggestion

    def test_get_suggestion_openai_error(self, monkeypatch):
        """Simulate an OpenAI SDK error; client should return an error message."""

        class FakeChoice:
            class message:
                content = "Fix the import"

        class FakeResponse:
            choices = [FakeChoice()]

        class FakeOpenAI:
            def __init__(self, **_kwargs):
                pass

            class chat:
                class completions:
                    @staticmethod
                    def create(**_kwargs):
                        raise RuntimeError("network error")

        import src.tools.llm_client as llm_mod
        monkeypatch.setattr(llm_mod, "LLMClient", LLMClient)

        client = LLMClient(api_key="fake-key")
        # Monkey-patch the lazy client creation to inject our fake
        client._client = FakeOpenAI()
        result = client.get_suggestion("coding_error", "some context")
        assert "[LLM error:" in result

    def test_get_suggestion_success(self, monkeypatch):
        class FakeMessage:
            content = "Run: pip install missing-lib"

        class FakeChoice:
            message = FakeMessage()

        class FakeResponse:
            choices = [FakeChoice()]

        class FakeChatCompletions:
            def create(self, **_kwargs):
                return FakeResponse()

        class FakeChat:
            completions = FakeChatCompletions()

        class FakeOpenAI:
            def __init__(self, **_kwargs):
                self.chat = FakeChat()

        client = LLMClient(api_key="fake-key")
        client._client = FakeOpenAI()
        result = client.get_suggestion("coding_error", "ImportError: No module named X")
        assert result == "Run: pip install missing-lib"
