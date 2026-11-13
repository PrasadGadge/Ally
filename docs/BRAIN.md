# Vivie Brain — 2-Tier Routing

There are **only two tiers** (not four). Think of them as **first** and **second**:

| You say | Code | Engine | When it runs |
|---------|------|--------|----------------|
| **First tier** | `0` | Ollama `gemma4:e4b` | Default for normal chat |
| **Second tier** | `1` | OpenRouter | Hard tasks + fallback |

---

## When Tier 0 (local) is chosen

- Greetings, thanks, short chat (“hello”, “how are you”)
- Simple questions without code/research/planning keywords
- Messages under ~40 words without advanced keywords

## When Tier 1 (OpenRouter) is chosen immediately

- Code: `write code`, `debug`, `implement`, `python function`, code blocks
- Deep work: `research`, `step by step`, `comprehensive`, `roadmap`, `architecture`
- Long messages: **40+ words**
- **Forced** by agents: code agent, planning agent, research synthesis
- **System JSON** tasks: intent classification (`system_llm` → tier 1)

---

## Escalation (fail-up) — Tier 0 → Tier 1 only

```
User message
     │
     ▼
 classify_tier()  ──► start at 0 or 1
     │
     ├─ Ollama offline?          → skip to 1 (if key exists)
     ├─ Advanced task but no OR key? → try 0 if Ollama up
     │
     ▼
 Try start tier
     │
     ├─ Success → done
     └─ Error/timeout → escalate 0 → 1 (only step; no tier 2)
```

**There is no Tier 2.** If both fail, Vivie says reasoning systems are offline.

---

## Examples

| User says | Starts on | Why |
|-----------|-----------|-----|
| “Hey Vivie” | 0 | Short chat |
| “What is Python?” | 0 | Simple Q&A |
| “Write a python function to sort a list” | 1 | Code keyword |
| “Research quantum computing in depth” | 1 | Research keyword |
| “Hello” but Ollama is down | 1 | Auto-skip local |
| “Hello” on 0, Ollama errors mid-call | 1 | Fail-up |

---

## Ollama — auto-start vs manual (HTTP API)

Vivie does **not** embed the model in Python. It calls Ollama like any API:

`POST http://localhost:11434/api/generate` (streaming JSON)

| Situation | What happens |
|-----------|----------------|
| Ollama app already open / `ollama serve` running | Vivie connects immediately — **nothing to start** |
| Port 11434 closed, `VIVIE_OLLAMA_AUTO_START=true` | Vivie runs `ollama serve` in the background (~5–20s) |
| Auto-start off | You start Ollama yourself; Vivie only talks to the API |

On `python Vivie.py`, warmup runs in the background if `VIVIE_OLLAMA_WARMUP_AT_START=true`.

**One-time:** `ollama pull gemma4:e4b`

## `.env` keys

```env
OLLAMA_MODEL=gemma4:e4b
VIVIE_OLLAMA_AUTO_START=true
VIVIE_OLLAMA_WARMUP_AT_START=true
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=deepseek/deepseek-chat
```
