# Vivie AI Enhancement Roadmap

## Current Capability Assessment

### ✅ Working Features
- Tiered LLM brain (NVIDIA fast + OpenRouter advanced)
- Intent detection with LLM router
- 13 registered tools (calculator, calendar, create_file, forecast, github, gmail, image_gen, internet_speed, morning_brief, vision, weather, web_search, whatsapp)
- Session memory, episodic memory, ChromaDB knowledge base, mem0 cloud
- Groq Whisper STT, Edge-TTS TTS
- Adaptive context builder with token budget (12k char max)
- Proactive engine (reminders, suggestions, news)
- Digital life controller (file monitoring, routines)
- WebSocket UI bridge with volume control

### ⚠️ Requires Authorization
- Gmail (Google OAuth via setup_mcp.py)
- Calendar (Google OAuth via setup_mip.py)
- GitHub (GITHUB_TOKEN in .env)

### 🔧 Enhancement Opportunities Identified

## Prioritized Improvements

| Priority | Improvement | User Benefit | Effort | Dependencies | Status |
|----------|-------------|--------------|--------|--------------|--------|
| P1 | Follow-up conversation context resolution | Vivie understands "it", "that", "those" references | Medium | None | Planned |
| P1 | Tool result verification and structured outputs | Tools confirm success/failure, return structured data | Medium | None | Planned |
| P1 | Memory management commands | User can control what Vivie remembers | Low | None | Planned |
| P1 | Project memory system | Track ongoing projects, decisions, tasks | High | None | Planned |
| P2 | Multi-step task planner | Execute complex workflows with multiple tools | High | None | Planned |
| P2 | Intent confidence fallback | Low-confidence requests trigger clarification | Medium | None | Planned |
| P2 | Diagnostic event logging | Correlation IDs, performance metrics | Medium | None | Planned |
| P2 | Enhanced Gmail assistant | Summarize, filter, search capabilities | Medium | Google OAuth | Planned |
| P2 | Enhanced Calendar assistant | Conflict detection, suggestions | Medium | Google OAuth | Planned |
| P3 | GitHub workflow enhancement | Issue tracking, PR review assistance | Medium | GITHUB_TOKEN | Planned |
| P3 | Research assistant improvements | Source citations, conflict detection | High | None | Planned |
| P3 | Skill system architecture | Modular capability registry | High | None | Blocked |
| P3 | Barge-scale TTS streaming | FFmpeg integration for low latency | Low | ffmpeg | Blocked |

## Implementation Plan

### Phase 1: Core Intelligence (P1)
1. Add reference resolution to context builder
2. Implement structured tool outputs
3. Add memory management commands
4. Create project memory system

### Phase 2: Productivity Tools (P2)
1. Build lightweight task planner
2. Add intent confidence fallback
3. Implement diagnostic logging
4. Enhance Gmail/Calendar tools

### Phase 3: Advanced Features (P3)
1. Research assistant with citations
2. GitHub workflow enhancement
3. Design skill system architecture

## Metrics to Track
- Follow-up conversation accuracy
- Tool execution success rate
- Memory operations completed
- Task planning success rate
- Latency improvements
- Test coverage percentage
