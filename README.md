# AI Assistant — 主动式上下文感知桌面AI助手

A lightweight, proactive, context-aware desktop AI assistant that monitors your screen and automatically suggests actions — no manual prompt typing required.

## Architecture

The project follows a four-layer architecture designed for low coupling and easy extensibility:

```
Frontend Interaction Layer  (src/ui/)
        ↓
Core Agent Layer            (src/agent/)
        ↓
Tool Call Layer             (src/tools/)
        ↓
Data Storage Layer          (src/storage/)
```

| Layer | Responsibility |
|-------|----------------|
| **Frontend Interaction Layer** | Floating always-on-top window; displays AI suggestions and action buttons |
| **Core Agent Layer** | Orchestrates the capture → OCR → scene recognition → LLM → suggest pipeline |
| **Tool Call Layer** | Wraps screen capture (mss/PIL), OCR (Tesseract), LLM (OpenAI-compatible API), and safe command execution |
| **Data Storage Layer** | SQLite operation logs + suggestion history; JSON-based persistent configuration |

## Features

- **Proactive suggestions** — no manual prompting needed
- **Scene detection** — automatically recognises coding errors, unknown terms, document editing, web browsing
- **One-click execution** — runs suggested shell commands through a safety-checked executor
- **Persistent history** — all suggestions and operation logs stored in `~/.ai_assistant/`
- **Pipeline logging** — each screenshot path, OCR result, and intent output is appended to `~/.ai_assistant/pipeline_log.jsonl`
- **Configurable** — model, API key, capture interval, OCR language all editable via the Settings panel

## Requirements

- Python 3.11+
- Tesseract OCR installed on the system (for OCR functionality)
- An OpenAI-compatible API key

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

On first run a default configuration is written to `~/.ai_assistant/config.json`.
Edit it directly or use the in-app Settings panel.

Key settings:

| Key | Default | Description |
|-----|---------|-------------|
| `llm_api_key` | `""` | OpenAI (or compatible) API key |
| `llm_model` | `"gpt-4o-mini"` | Model name |
| `llm_base_url` | `"https://api.openai.com/v1"` | API base URL |
| `capture_interval_seconds` | `3` | Screen capture frequency |
| `ocr_language` | `"chi_sim+eng"` | Tesseract language string |
| `next_step_suggestion_count` | `3` | Number of next-step suggestions requested from the model |
| `intent_prompt_file` | `~/.ai_assistant/intent_prompt.txt` | Editable intent prompt template file (`{suggestion_count}` placeholder supported) |

## Running

```bash
python main.py
```

## Running Tests

```bash
pytest tests/
```

## Project Structure

```
main.py                       # Application entry point
requirements.txt
src/
  agent/
    agent_core.py             # Central scheduling hub
    context_manager.py        # Rolling context window
    scene_recognizer.py       # Heuristic scene classification
  tools/
    screen_capture.py         # mss / PIL screenshot capture
    ocr_tool.py               # Tesseract OCR wrapper
    llm_client.py             # OpenAI-compatible LLM client
    command_executor.py       # Safe shell command execution
  storage/
    config_manager.py         # JSON configuration persistence
    database.py               # SQLite storage
  ui/
    floating_window.py        # Always-on-top suggestion window
    settings_panel.py         # Settings dialog
tests/
  test_agent.py
  test_storage.py
  test_tools.py
```
