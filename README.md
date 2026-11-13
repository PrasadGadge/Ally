<<<<<<< HEAD
# Vivie — Personal AI Assistant

Voice-first personal assistant with Web UI, memory (mem0 + Chroma), tool routing, and desktop automation.

## Vivie 2.0 architecture

```
Vivie.py (entry)
    └── vivie_core/runtime.py      → start engines + threads
            ├── listen_loop        → STT → input_queue
            ├── brain_loop         → process_text (pipeline)
            └── tts_loop           → speak responses

vivie_core/processor.py            → thin orchestrator
    ├── handlers/control.py        → kill / wake / feedback
    ├── handlers/time_schedule.py  → alarms & schedule
    ├── handlers/fast_chat.py      → quick LLM path
    ├── handlers/automation.py     → desktop automation
    ├── handlers/plan_executor.py  → planner actions
    └── handlers/fallback.py       → LLM fallback
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/PRODUCTION.md](docs/PRODUCTION.md).

## Production features (2.0)

- Startup **health report** (STT / TTS / memory / automation)
- Central **settings** via `.env` (`vivie_core/settings.py`)
- **Tools/** folder — add `ToolManifest` classes, auto-discovered
- Memory: timeout, cache cap, duplicate-store prevention
- Wake-word fix (no more `vivie` → `viviee`)

## Quick start

1. **Python 3.10+** (3.11 recommended)
2. Install dependencies:
   ```bash
   python setup.py              # core only (~fast)
   python setup.py --full       # + automation, vision, torch
   ```
   Or: `pip install -r requirements.txt` (everything)
3. Copy environment template:
   ```bash
   copy .env.example .env
   ```
   Add at least `GROQ_API_KEY` for speech-to-text.
4. Validate:
   ```bash
   python validate_deps.py
   python validate_deps.py --health
   ```
5. Run:
   ```bash
   python Vivie.py
   ```

## Tests

```bash
python -m pytest tests/ -q
```

## Project layout

| Path | Role |
|------|------|
| `vivie_core/` | Vivie 2.0 pipeline (new) |
| `main_brain.py` | Compatibility shim |
| `Brain/` | 2-tier LLM (NVIDIA fast + OpenRouter advanced) |
| `Core_structure/` | Intent, planner, engines |
| `Features/` | Tools (weather, search, …) |
| `memory_core/` | Session + episodic + mem0 |
| `knowledge_core/` | Chroma RAG |

## License

Personal project — use and modify for learning.
=======
# Ally
>>>>>>> 82d99ce048be304fa0432bb9abec4c81c26566d1
