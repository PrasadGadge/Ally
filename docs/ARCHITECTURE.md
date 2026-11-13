# Vivie 2.0 — Target Architecture

## Goals

1. **Single pipeline** — one path from user text to response.
2. **Single tool registry** — `tool_manifest` discovery + `ToolRouter` via `vivie_core/registry.py`.
3. **Single intent source** — `IntentEngine` only (removed duplicate `detect_intent` in the hot path).
4. **Handlers, not god files** — each concern in `vivie_core/handlers/`.
5. **Logged failures** — `vivie_core/log_util.py` instead of `except: pass`.

## Request lifecycle

1. **listen_loop** captures audio → STT → `input_queue`
2. **brain_loop** dequeues → `process_text()`
3. **processor** builds `PipelineContext`, runs handlers
4. Response → `output_queue` → **tts_loop** → `controlled_speak` / stream

## Concurrency

| Resource | Mechanism |
|----------|-----------|
| One request at a time | `state.processing_lock` |
| News headline list | `_news_results_lock` |
| LLM history file | `_history_lock` in `cl_brain.py` |
| Post-TTS echo | `POST_SPEAK_COOLDOWN` in listen loop |

## Handler order (process_text)

| Order | Handler | Returns |
|-------|---------|---------|
| 1 | TTS marker filter | `None` |
| 2 | control | str or continue |
| 3 | inactive check | `None` |
| 4 | time_schedule | `None` (handled) |
| 5 | fast_chat | str or continue |
| 6 | *lock* automation | str or continue |
| 7 | plan_executor | str or continue |
| 8 | fallback | str or `None` |

## UI contract

`sig_memory_update` always uses shape:

```json
{"episodes": <int>, "knowledge": <int>}
```

## Migration notes

- `main_brain.Vivie` → alias for `vivie_core.start_vivie`
- Old imports from `main_brain` still work via shim
- Further work: migrate built-in tools to `ToolManifest` subclasses and drop duplicate registration

## Brain (2-tier)

| Tier | Backend | Use |
|------|---------|-----|
| 0 | Ollama `gemma4:e4b` | Normal chat, Q&A, short requests |
| 1 | OpenRouter | Code, research, planning, long/complex reasoning |

Routing: `Brain/tiered_brain.py` · Firewalls: `Brain/brain_guard.py` · Internal JSON: `Brain/system_llm.py` (tier 1).

## Known limitations

- Cold start still loads Chroma / embedding stack when memory path runs
- Automation remains OS/display dependent (PyAutoGUI)
- Full `requirements.txt` is heavy; consider `requirements-core.txt` for minimal installs
