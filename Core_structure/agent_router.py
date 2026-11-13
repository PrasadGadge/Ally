# ==================================================
# agent_router.py — Vivie Multi-Agent Router
#
# Upgrades in this version:
#  • SMART DETECTION: keyword matching + LLM fallback
#    for ambiguous queries that keyword list misses
#  • PARALLEL SEARCH: research agent runs 3 web
#    searches simultaneously (was serial — 4-6s wait)
#  • MULTI-AGENT: research+planning can run together
#    for queries that need both
#  • CODE VALIDATION: Python syntax checked before
#    responding — catches obvious LLM code errors
#  • MEMORY-AWARE PLANNING: actually uses past episodes
#    to inform the plan instead of ignoring them
# ==================================================

import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from Brain.cl_brain       import Main_Brain
from Features.web_search  import search_web


# ─────────────────────────────────────────────────
# SAFE LLM WRAPPER
# ─────────────────────────────────────────────────

def _safe_llm(
    prompt: str,
    fallback: str = "",
    forced_tier: int = None,
    *,
    advanced: bool = False,
) -> str:
    try:
        if forced_tier is not None or advanced:
            from Brain.tiered_brain import TIER_ADVANCED, TIER_LOCAL, api_generate_response
            tier = forced_tier if forced_tier is not None else (
                TIER_ADVANCED if advanced else TIER_LOCAL
            )
            result = api_generate_response(prompt, forced_tier=tier)
        else:
            result = Main_Brain(prompt)

        if not result or not str(result).strip():
            return fallback or "I ran into an issue processing that."
        return str(result).strip()
    except Exception as e:
        print(f"[LLM] Error: {e}")
        return fallback or "I ran into an issue processing that."


# ─────────────────────────────────────────────────
# LANGUAGE DETECTOR
# ─────────────────────────────────────────────────

def _detect_language(text: str) -> str:
    t = text.lower()
    if re.search(r'\bjavascript\b|\bjs\b|\bnode\b|\breact\b', t): return "JavaScript"
    if 'c++' in t or 'cpp' in t or 'c plus plus' in t:            return "C++"
    if re.search(r'\bpython\b|\bdjango\b|\bflask\b', t):           return "Python"
    if re.search(r'\bjava\b|\bspring\b', t):                       return "Java"
    if re.search(r'\bhtml\b|\bcss\b|web page', t):                 return "HTML/CSS"
    return "Python"


# ─────────────────────────────────────────────────
# AGENT DETECTOR
# Two-stage: fast keyword check first,
# LLM fallback for ambiguous queries.
# ─────────────────────────────────────────────────

_CODE_TRIGGERS = {
    "write code", "write a code", "create code",
    "write program", "write a program", "write function",
    "write a function", "write script", "write a script",
    "code for", "program for", "how to code", "explain code",
    "debug", "fix code", "fix this code", "what does this code",
    "explain this code", "write in python", "write in c++",
    "write in javascript", "write in java", "implement",
    "make a function", "create a function", "build a function",
    "syntax error", "refactor", "optimise this", "optimize this",
}

_RESEARCH_TRIGGERS = {
    "research", "deep research", "find out about", "search about",
    "look up", "investigate", "tell me everything about",
    "full information", "detailed information", "give me details about",
    "what is the latest on", "find information about",
    "gather information", "study about", "tell me all about",
    "comprehensive", "in depth", "detailed report",
    "everything about", "full report on", "compare", "vs", "versus",
    "difference between", "knowledge map", "research history",
    "what have you researched", "what's happening with",
    "what's new in", "latest developments in",
}

_PLANNING_TRIGGERS = {
    "make a plan", "create a plan", "plan for", "plan to",
    "how should i", "help me plan", "break down", "break this down",
    "steps to", "roadmap", "strategy for", "how to achieve",
    "how to reach", "guide me", "walk me through",
    "step by step", "what steps", "how do i start",
    "where do i start", "help me build", "help me create",
    "schedule for", "timeline for", "learning path",
    "how can i learn", "how to get better at",
}

# Queries needing BOTH research and planning
_MULTI_TRIGGERS = {
    "research and plan", "learn and create a plan",
    "find out and plan", "research then plan",
    "understand and build a roadmap",
}


def _keyword_detect(text: str) -> str:
    t = text.lower().strip()

    # Multi-agent check first
    if any(trigger in t for trigger in _MULTI_TRIGGERS):
        return "research+planning"

    # Single agent checks
    if any(trigger in t for trigger in _CODE_TRIGGERS):
        return "code"
    if any(trigger in t for trigger in _RESEARCH_TRIGGERS):
        return "research"
    if any(trigger in t for trigger in _PLANNING_TRIGGERS):
        return "planning"
    return "none"


def _llm_detect(text: str) -> str:
    """
    LLM fallback for queries that keyword matching misses.
    Uses the fast brain tier for one-word classification only.
    """
    prompt = f"""Classify this user request into one agent type.

User request: "{text}"

Options:
- code: writing, debugging, or explaining code
- research: looking up information, comparing topics, deep dives
- planning: creating plans, roadmaps, step-by-step guides
- none: casual chat, greetings, simple questions

Reply with ONE word only: code, research, planning, or none."""

    result = _safe_llm(prompt, forced_tier=0).strip().lower()

    # Extract first word in case LLM adds explanation
    first_word = result.split()[0] if result else "none"
    if first_word in ("code", "research", "planning"):
        return first_word
    return "none"


def detect_agent(text: str) -> str:
    """
    Detect which agent(s) should handle this query.
    Stage 1: fast keyword check.
    Stage 2: LLM classification for ambiguous queries.
    """
    result = _keyword_detect(text)
    if result != "none":
        return result

    # Only invoke LLM if query is complex enough to warrant it
    if len(text.split()) >= 5:
        return _llm_detect(text)

    return "none"


# ─────────────────────────────────────────────────
# RESEARCH AGENT
# FIX: parallel search — 3 queries run simultaneously
# Was serial: 4-6s total wait. Now ~1.5s.
# ─────────────────────────────────────────────────

def _parallel_search(queries: list) -> str:
    """Run multiple searches in parallel, combine results."""
    all_content = {}

    def _search(q: str) -> tuple:
        try:
            return (q, search_web(q))
        except Exception:
            return (q, [])

    with ThreadPoolExecutor(max_workers=len(queries)) as ex:
        futures = {ex.submit(_search, q): q for q in queries}
        for future in as_completed(futures, timeout=8):
            try:
                q, results = future.result()
                all_content[q] = results
            except Exception:
                pass

    combined = ""
    seen_titles = set()
    for results in all_content.values():
        if not results:
            continue
        for r in results[:2]:
            title   = r.get("title", "")
            content = r.get("content", "") or r.get("snippet", "")
            if title in seen_titles:
                continue
            seen_titles.add(title)
            if title or content:
                combined += f"Source: {title}\n{content}\n\n"

    return combined[:4000]


def research_agent(query: str) -> str:
    print(f"[ResearchAgent] Activated for: '{query[:50]}'")

    try:
        from Core_structure.research_engine import get_research_engine
        engine = get_research_engine()
        t      = query.lower().strip()

        # Knowledge map / history
        if any(w in t for w in ["knowledge map", "what have you researched",
                                 "research history", "past research",
                                 "previous research", "show knowledge graph"]):
            if any(w in t for w in ["history", "previous", "past"]):
                return engine.get_research_history() or "No research history yet."
            for prep in ["about", "for", "on"]:
                m = re.search(rf'\b{prep}\s+(.+)', t)
                if m:
                    return engine.get_knowledge_map(m.group(1).strip()) or "No knowledge map available."
            return engine.get_knowledge_map(None) or "No knowledge map available."

        # Comparison
        for cw in ["vs", "versus", "compare between", "compare", "difference between"]:
            if cw in t:
                parts = [p.strip() for p in t.split(cw, 1) if p.strip()]
                if len(parts) == 2:
                    for filler in ["what is the", "what are", "tell me about",
                                   "explain", "the difference between"]:
                        parts[0] = parts[0].replace(filler, "").strip()
                        parts[1] = parts[1].replace(filler, "").strip()
                    if parts[0] and parts[1]:
                        return engine.compare_topics(parts[0], parts[1])

        return engine.deep_research(query, depth=3) or _research_fallback(query)

    except Exception as e:
        print(f"[ResearchAgent] Engine unavailable: {e} — using fallback")
        return _research_fallback(query)


def _research_fallback(query: str) -> str:
    print(f"[ResearchAgent] Parallel fallback for: '{query[:50]}'")
    try:
        queries  = [query, f"{query} latest 2026", f"{query} explained"]
        combined = _parallel_search(queries)   # PARALLEL — was serial

        if not combined.strip():
            raise ValueError("No web content found")

        prompt = f"""You are Vivie's Research Agent — analytical, precise, no filler.

Research Query: {query}

Web Sources:
{combined}

Deliver a sharp research brief:
1. Executive summary (2–3 sentences)
2. Key findings (bullets, evidence-based)
3. Recent developments / risks
4. Actionable insight for Boss

Rules: no invented sources; if evidence is thin, say so once."""

        return _safe_llm(prompt)

    except Exception as e:
        print(f"[ResearchAgent] Fallback failed: {e} — LLM only")
        return _safe_llm(
            f"Research this topic thoroughly: {query}\n"
            f"Provide overview, key facts, recent developments, and insights."
        )


# ─────────────────────────────────────────────────
# CODE AGENT
# FIX: Python syntax validation before responding
# ─────────────────────────────────────────────────

def _validate_python_syntax(code: str) -> tuple:
    """Returns (is_valid, error_message)."""
    try:
        compile(code, "<string>", "exec")
        return (True, "")
    except SyntaxError as e:
        return (False, f"Line {e.lineno}: {e.msg}")


def _extract_code_block(response: str) -> str:
    """Extract code between [CODE] and [EXPLANATION] tags."""
    m = re.search(r'\[CODE\](.*?)\[EXPLANATION\]', response, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Fallback: try markdown code fences
    m = re.search(r'```(?:\w+)?\n(.*?)```', response, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


def code_agent(query: str) -> str:
    print(f"[CodeAgent] Activated for: '{query[:50]}'")

    language = _detect_language(query)

    prompt = f"""You are Vivie's Code Agent — senior engineer, production mindset.

User Request: {query}
Preferred Language: {language}

Deliver:
1. Correct, runnable code (handle obvious edge cases)
2. Minimal comments only where logic is non-obvious
3. Brief explanation of design choice and pitfalls

Format:
[CODE]
<code>
[EXPLANATION]
<2-4 sentences>
[USAGE]
<minimal example>

No pseudo-code. No placeholder APIs unless you label them clearly."""

    response = _safe_llm(
        prompt,
        fallback="I had trouble generating the code. Please try rephrasing.",
        advanced=True,
    )

    # FIX: validate Python syntax before returning
    if language == "Python":
        code_block = _extract_code_block(response)
        if code_block:
            valid, error = _validate_python_syntax(code_block)
            if not valid:
                print(f"[CodeAgent] Syntax error detected: {error} — retrying")
                retry_prompt = f"""{prompt}

IMPORTANT: Your previous attempt had a Python syntax error: {error}
Fix it. The code must be syntactically valid Python."""
                response = _safe_llm(
                    retry_prompt,
                    fallback=response,
                    advanced=True,
                )

    return response


# ─────────────────────────────────────────────────
# PLANNING AGENT
# FIX: actually uses memory to inform the plan
# ─────────────────────────────────────────────────

def _get_relevant_past_plans(query: str) -> str:
    """Pull past planning episodes relevant to this query from memory."""
    try:
        from memory_core.episodic_memory import load_episodes
        episodes = load_episodes()
        query_words = set(query.lower().split())

        relevant = []
        for ep in reversed(episodes[-50:]):
            if ep.get("intent") not in ("planning", "general"):
                continue
            ui = ep.get("user_input", "").lower()
            # Simple relevance: word overlap
            overlap = len(set(ui.split()) & query_words)
            if overlap >= 2:
                resp = ep.get("vivie_response", "")[:150]
                relevant.append(f"- Previously discussed: {ui[:80]} → {resp}")
            if len(relevant) >= 3:
                break

        return "\n".join(relevant) if relevant else ""

    except Exception:
        return ""


def planning_agent(query: str, memory_block: str = "") -> str:
    print(f"[PlanningAgent] Activated for: '{query[:50]}'")

    past_context = _get_relevant_past_plans(query)
    memory_ctx   = ""

    if memory_block and memory_block.strip():
        memory_ctx += f"\nUser context from memory:\n{memory_block[:300]}"
    if past_context:
        memory_ctx += f"\nRelevant past conversations:\n{past_context}"

    prompt = f"""You are Vivie's Planning Agent — strategic, realistic, execution-focused.

Planning Request: {query}
{memory_ctx}

Build an actionable plan:
• Phases with time ranges (realistic, not optimistic fiction)
• Concrete steps Boss can do today
• Dependencies and blockers called out early

Format:
GOAL: <one line>

PHASE 1 — <name> (<estimate>)
- <step>

PRIORITY: <single highest-leverage move now>
RISKS: <top 2-3 failure modes>

No motivational fluff. Specific beats vague."""

    return _safe_llm(
        prompt,
        fallback="I had trouble creating a plan. Please try rephrasing.",
        advanced=True,
    )


# ─────────────────────────────────────────────────
# MAIN ROUTER
# FIX: supports multi-agent (research + planning)
# ─────────────────────────────────────────────────

def route_to_agent(
    text:         str,
    memory_block: str = "",
    knowledge:    str = ""
) -> tuple:
    """
    Detect agent type and route automatically.
    Returns: (agent_name, response_string)
    Supports multi-agent for research+planning combos.
    ALWAYS returns a tuple — never raises.
    """
    try:
        agent_type = detect_agent(text)

        if agent_type == "none":
            return ("none", "")

        print(f"[AgentRouter] Routing to: {agent_type.upper()} agent")

        if agent_type == "research":
            return ("research", research_agent(text))

        if agent_type == "code":
            return ("code", code_agent(text))

        if agent_type == "planning":
            return ("planning", planning_agent(text, memory_block))

        # Multi-agent: research + planning in parallel
        if agent_type == "research+planning":
            print("[AgentRouter] Multi-agent: research + planning in parallel")
            results = {}

            def _do_research(): results["research"] = research_agent(text)
            def _do_planning():  results["planning"] = planning_agent(text, memory_block)

            t1 = threading.Thread(target=_do_research, daemon=True)
            t2 = threading.Thread(target=_do_planning,  daemon=True)
            t1.start(); t2.start()
            t1.join(timeout=30); t2.join(timeout=30)

            research_out = results.get("research", "")
            planning_out = results.get("planning", "")

            if research_out and planning_out:
                combined = (
                    f"RESEARCH FINDINGS:\n{research_out}\n\n"
                    f"---\n\nACTION PLAN:\n{planning_out}"
                )
                return ("research+planning", combined)

            return ("research+planning", research_out or planning_out or "")

        return ("none", "")

    except Exception as e:
        print(f"[AgentRouter] Unexpected error routing '{text[:50]}': {e}")
        return ("none", "")
