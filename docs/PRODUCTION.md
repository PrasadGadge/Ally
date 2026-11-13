# Vivie Production Guide

## Startup checklist

1. `copy .env.example .env` and set `GROQ_API_KEY`
2. `python validate_deps.py` — fix any missing critical packages
3. `python validate_deps.py --health` — verify runtime services
4. `python -m pytest tests/ -q` — all tests should pass
5. `python Vivie.py` — read the **Health** block in the console

## Architecture (2.0)

| Layer | Module | Role |
|-------|--------|------|
| Entry | `Vivie.py` | Process supervisor + UI launcher |
| Core | `vivie_core/` | Pipeline, handlers, health, settings |
| STT | `SpeechToText/vivie_stt.py` | Groq → local Whisper fallback |
| TTS | `TextToSpeech/Fast_DF_TTS.py` | Edge-TTS streaming + cache |
| Memory | `memory_core/memory_service.py` | mem0 + episodic, cached, deduped |
| Tools | `Tools/` + `Core_structure/tool_manifest.py` | Auto-discovery |
| Automation | `Automation/Automation_brain.py` | Desktop / browser control |

## Health API

```python
from vivie_core.health import run_full_check, format_report
print(format_report(run_full_check()))
```

## Adding a tool

1. Create `Tools/my_tool.py` inheriting `ToolManifest`
2. Set `name`, `action_type`, `keywords`, implement `handler()`
3. Restart Vivie — `discover_tools()` registers it automatically

## Degraded mode

Vivie runs with warnings if optional services are missing:

- No Groq → local Whisper STT (slower)
- No mem0 → episodic memory only
- No ffmpeg → whole-file TTS (higher latency)
- No pyautogui → automation commands limited

## Dependencies

| File | Use |
|------|-----|
| `requirements-core.txt` | Voice, LLM, memory, UI |
| `requirements-optional.txt` | Automation, vision, Tavily, torch |
| `requirements.txt` | Both (full install) |

```bash
python setup.py          # core
python setup.py --full   # core + optional
```

## Docker & CI

```bash
docker compose run test
```

GitHub Actions: `.github/workflows/ci.yml`

## Metrics

```python
from vivie_core.metrics import snapshot
print(snapshot())
```

## Security

- Never commit `.env`
- Rotate keys if exposed
- `.gitignore` must include `.env`
- Runtime API keys must come from `.env`, not source defaults
