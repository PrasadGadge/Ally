"""Per-request context passed through pipeline handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PipelineContext:
    raw: str
    text: str = ""
    text_lower: str = ""
    intent: dict = field(default_factory=dict)
    primary_intent: str = "chat"
    confidence: float = 0.0
    actions: list = field(default_factory=list)
    memory_block: str = ""
    knowledge_context: str = ""
    details: str = ""
    cot_context: str = ""          # chain-of-thought reasoning block
    user_model_context: str = ""   # what Vivie knows about the user
    task_plan: Any = None          # multi-step task plan (if compound request)

    @classmethod
    def from_raw(cls, raw: str) -> PipelineContext:
        import os
        import time
        from threading import Thread
        from vivie_core import text as text_util
        from vivie_core.engines import context_manager, intent_engine, planner
        from Core_structure.llm_intent_router import route_with_llm

        text = text_util.normalize_input(raw)
        text = text_util.autocorrect_input(text)
        text = text_util.fix_wake_word(text)

        # Resolve follow-up references (it, that, those, etc.)
        try:
            from Brain.reference_resolver import get_reference_resolver
            resolver = get_reference_resolver()
            resolved_text = resolver.resolve(text)
            if resolved_text != text:
                print(f"[Pipeline] Resolved reference: '{text}' → '{resolved_text}'")
                text = resolved_text
        except Exception as exc:
            from vivie_core.log_util import warn
            warn("reference_resolver", exc)

        text_lower = text.lower()

        # ── PHASE 4: LLM is primary router ──────────────────────────────
        # LLM routing is always attempted first. If it succeeds, the
        # keyword engine is skipped entirely. If LLM fails, times out,
        # or returns null (chat), the keyword engine handles it as a
        # safe fallback. Zero downtime risk.
        # ────────────────────────────────────────────────────────────────

        llm_intent = None
        llm_result = route_with_llm(text)

        if llm_result and llm_result.get("tool"):
            # LLM confidently identified a tool — build the intent dict
            llm_intent = {
                "primary":    llm_result["tool"],
                "confidence": llm_result.get("confidence", 0.9),
                "parameters": llm_result.get("arguments", {}),
                # multi-tool support: list of additional tool calls if present
                "extra_tools": llm_result.get("extra_tools", []),
            }
            print(f"[Pipeline] LLM routed to: {llm_intent['primary']} "
                  f"(conf={llm_intent['confidence']:.2f}) args={llm_intent['parameters']}")

        # ── SHADOW LOGGING (runs in background regardless) ──────────────
        is_shadow = os.getenv("VIVIE_LLM_ROUTING_SHADOW", "false").lower() == "true"
        if is_shadow:
            kw_intent_snap = dict(intent_engine.detect(text, context_manager.__dict__))

            def run_shadow(query, kw_intent, llm_res):
                latency_ms = 0  # already computed above, reuse llm_result
                llm_tool = llm_res.get("tool") if llm_res else "null"
                log_line = (
                    f"{time.time()},{kw_intent.get('primary')},"
                    f"{llm_tool},\"{query}\"\n"
                )
                try:
                    with open("shadow_metrics.csv", "a") as f:
                        if os.path.getsize("shadow_metrics.csv") == 0:
                            f.write("timestamp,keyword_intent,llm_intent,query\n")
                        f.write(log_line)
                except Exception:
                    try:
                        with open("shadow_metrics.csv", "w") as f:
                            f.write("timestamp,keyword_intent,llm_intent,query\n" + log_line)
                    except Exception:
                        pass

            Thread(
                target=run_shadow,
                args=(text, kw_intent_snap, llm_result or {}),
                daemon=True
            ).start()

        # ── Choose intent source ─────────────────────────────────────────
        if llm_intent:
            intent = llm_intent
        else:
            # Fallback: keyword engine (also handles chat/null LLM responses)
            intent = intent_engine.detect(text, context_manager.__dict__)

        primary    = str(intent.get("primary",    "chat")).lower()
        confidence = float(intent.get("confidence", 0) or 0)
        actions    = planner.generate_plan(intent, {"last_input": text})

        # ── Task Planner Integration (Phase 2) ────────────────────────
        # Check if this is a compound request that needs multi-step planning
        task_plan = None
        try:
            from Core_structure.task_planner import get_task_planner
            task_planner = get_task_planner()
            task_plan = task_planner.analyze_request(text, intent)
            if task_plan:
                print(f"[Pipeline] Multi-step task plan created: {task_plan.task_id}")
        except Exception as exc:
            from vivie_core.log_util import warn
            warn("task_planner_analyze", exc)

        return cls(
            raw=raw,
            text=text,
            text_lower=text_lower,
            intent=intent,
            primary_intent=primary,
            confidence=confidence,
            actions=actions,
            details=text,
            task_plan=task_plan,  # New field for multi-step task planning
        )

    def load_memory_if_needed(self) -> None:
        from vivie_core.config import MEMORY_INTENTS
        from memory_core.memory_service import retrieve_memory
        from knowledge_core.rag_retrieve import retrieve_knowledge
        from vivie_core.log_util import warn

        needs = (
            self.primary_intent in MEMORY_INTENTS
            or len(self.text.split()) > 6
        )
        if not needs:
            return

        try:
            mem_ctx = retrieve_memory(self.text)
            msgs = mem_ctx.get() if mem_ctx else []
            self.memory_block = "".join(
                m.get("content", "") + "\n" for m in msgs
            )
        except Exception as exc:
            warn("retrieve_memory", exc)

        try:
            self.knowledge_context = retrieve_knowledge(self.text) or ""
        except Exception as exc:
            warn("retrieve_knowledge", exc)

        # User model — zero latency (just reads in-memory dict)
        try:
            from Brain.user_model import get_context_string
            self.user_model_context = get_context_string()
        except Exception as exc:
            warn("user_model", exc)