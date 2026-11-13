# Vivie — Production Improvements Log

All production-hardening changes applied in May 2026.

---

## Bug Fixes

### 1. GROQ API Key Typo — `.env`
- **Before:** `GROQ_API_KJEY=...` (typo — key was silently ignored by python-dotenv)
- **After:** `GROQ_API_KEY=...` (correct variable name)
- **Impact:** Groq LLM calls no longer silently fail with missing-key errors.

### 2. Digital Life Controller — Slow Startup (`get_watch_status`)
- **File:** `Core_structure/digital_life_controller.py`
- **Before:** `Path(f).rglob("*")` — enumerates every file under Desktop / Downloads /
  Documents recursively, loading all into a list in RAM. On a full machine this can
  take 10–30 s and freeze startup.
- **After:** Fast `os.walk` counter that skips hidden dirs, `__pycache__`, `venv`,
  `node_modules`, and `".pytest_cache"`, capped at 9 999 items. Always completes in
  milliseconds.

### 3. Digital Life Controller — Routine Time Window (`check_and_execute`)
- **File:** `Core_structure/digital_life_controller.py`
- **Before:** `now.minute in range(routine["minute"], routine["minute"] + 5)` —
  Minutes 60–62 never exist, so routines exactly on the hour lost part of their
  5-minute window.
- **After:** Modular-distance check `(now.minute - routine["minute"]) % 60 < 5`
  works correctly for all clock positions including `XX:58–XX:02` boundaries.

---

## Architecture & Quality

- **`vivie_core/`** — Clean pipeline refactor separating listen / brain / TTS loops.
- **`vivie_core/health.py`** — Full dependency health check run at startup.
- **`vivie_core/registry.py`** — Engine bootstrap with graceful degradation.
- **`memory_core/`** — Session memory + Mem0 long-term memory wired together.
- **`knowledge_core/`** — ChromaDB vector store for persistent knowledge.

---

## Testing Suite Added
| File | Coverage |
|---|---|
| `tests/test_brain.py` | Brain / LLM routing |
| `tests/test_memory.py` | Session & long-term memory |
| `tests/test_engines.py` | Intent & planner engines |
| `tests/test_vivie_core.py` | Core pipeline |
| `tests/test_integration.py` | End-to-end flow |

Run all: `pytest tests/ -v`

---

## Documentation
- `docs/ARCHITECTURE.md` — Full system architecture
- `docs/PRODUCTION.md` — Deployment & monitoring guide
- `RUN_ON_WINDOWS.md` — Windows-specific setup guide
- `.env.example` — Safe template for environment variables

---

## Next Steps
1. Rotate any API keys committed to Git history.
2. Set up pre-commit hooks (`pre-commit install`).
3. Enable GitHub Actions CI (`.github/workflows/`).
4. Add Sentry DSN to `.env` for production error tracking.
