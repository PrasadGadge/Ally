"""Execute planner actions inside the processing lock."""

from vivie_core.config import CODE_TRIGGERS
from vivie_core.handlers.actions import handle_action, handle_tool_or_agent
from vivie_core.handlers.post_process import finalize
from vivie_core.pipeline_context import PipelineContext
from vivie_core.ui import update_ui
from vivie_core.log_util import warn
from Core_structure.approval_manager import (
    get_approval_manager,
    check_action_requires_approval,
    requires_approval_for_side_effect,
    ActionRisk,
)


def _extract_message_from_result(result) -> str:
    """
    Extract user-facing message from a result.
    Handles both legacy string results and new ToolResult objects.
    """
    from Core_structure.tool_result import ToolResult
    
    if isinstance(result, ToolResult):
        return result.message
    return str(result) if result else ""


def _execute_task_plan(ctx: PipelineContext) -> str | None:
    """
    Execute a multi-step task plan using the TaskPlanner.
    
    This provides dependency management, progress tracking, and better
    error recovery than simple sequential execution.
    """
    from Core_structure.task_planner import get_task_planner
    from Core_structure.tool_result import ToolResult, ToolStatus, SideEffect
    
    task_planner = get_task_planner()
    approval_manager = get_approval_manager()
    plan = ctx.task_plan
    
    if not plan:
        return None
    
    print(f"[PlanExecutor] Executing task plan: {plan.task_id}")
    
    # Check for approval-required steps before execution
    approval_required = False
    for step in plan.steps:
        if check_action_requires_approval(step.action_type):
            approval_required = True
            print(f"[PlanExecutor] Step '{step.step_id}' requires approval: {step.description}")
    
    if approval_required:
        # For safety, log that approval would be needed
        print("[PlanExecutor] Task contains approval-required actions. Will request approval before execution.")
        # Emit approval_required event to UI
        try:
            update_ui("sig_approval_required", {
                "task_id": plan.task_id,
                "steps_requiring_approval": [
                    {
                        "step_id": step.step_id,
                        "description": step.description,
                        "action_type": step.action_type,
                    }
                    for step in plan.steps
                    if check_action_requires_approval(step.action_type)
                ],
            })
        except Exception as exc:
            print(f"[PlanExecutor] Failed to emit approval_required event: {exc}")
    
    # Define executor function that uses the actual tool router
    def tool_executor(action_type: str, parameters: dict) -> ToolResult:
        from vivie_core.engines import tool_router

        # Check if this action requires approval
        if check_action_requires_approval(action_type):
            # Request approval
            request = approval_manager.request_approval(
                action_type=action_type,
                description=f"Execute {action_type}",
                target=str(parameters.get("target", "")),
                risk=ActionRisk.HIGH,
                arguments_summary=str(parameters)[:100],  # Sanitized summary
                task_id=plan.task_id,
            )

            # Emit approval requested event
            try:
                update_ui("sig_approval_requested", {
                    "approval_id": request.approval_id,
                    "task_id": plan.task_id,
                    "step_id": action_type,
                    "action_type": action_type,
                    "description": request.description,
                    "target": request.target,
                    "risk": request.risk.value,
                    "arguments_summary": request.arguments_summary,
                })
            except Exception as exc:
                print(f"[PlanExecutor] Failed to emit approval_requested event: {exc}")

            # Non-blocking wait with shorter timeout (30 seconds instead of 5 minutes)
            # This prevents long blocking while still giving user time to respond
            import time
            max_wait = 30  # 30 seconds
            waited = 0
            poll_interval = 0.1
            while waited < max_wait:
                if approval_manager.check_approval(request.approval_id):
                    break
                time.sleep(poll_interval)
                waited += poll_interval

            if not approval_manager.check_approval(request.approval_id):
                # Approval not granted or expired
                try:
                    update_ui("sig_approval_rejected", {
                        "approval_id": request.approval_id,
                        "task_id": plan.task_id,
                        "reason": "Approval expired or not granted within timeout",
                    })
                except Exception as exc:
                    print(f"[PlanExecutor] Failed to emit approval_rejected event: {exc}")

                return ToolResult.permission_denied(
                    message=f"Action '{action_type}' was not approved by user (timeout)",
                    tool_name=action_type,
                )

            # Emit approval granted event
            try:
                update_ui("sig_approval_granted", {
                    "approval_id": request.approval_id,
                    "task_id": plan.task_id,
                })
            except Exception as exc:
                print(f"[PlanExecutor] Failed to emit approval_granted event: {exc}")

        # Execute through the real tool router
        result = tool_router.execute(action_type, ctx.text, **parameters)

        # Ensure it's a ToolResult
        if not isinstance(result, ToolResult):
            from Core_structure.tool_result import wrap_tool_result
            result = wrap_tool_result(result, tool_name=action_type)

        # Check for permission denied
        if result.status == ToolStatus.PERMISSION_DENIED:
            print(f"[PlanExecutor] Permission denied for action '{action_type}': {result.message}")

        return result
    
    # Execute the plan
    executed_plan = task_planner.execute_plan(plan, tool_executor)
    
    # Clean up approvals
    approval_manager.cleanup()
    
    # Report progress
    completed, total = executed_plan.get_progress()
    print(f"[PlanExecutor] Task completed: {completed}/{total} steps, status={executed_plan.status.value}")
    
    # Build response from results
    messages = []
    for step in executed_plan.steps:
        if step.result and step.result.message:
            status_emoji = "✓" if step.result.is_success() else "✗"
            messages.append(f"{status_emoji} {step.description}: {step.result.message}")
    
    if not messages:
        # Fallback: provide status summary
        if executed_plan.status.value == "completed":
            return f"Task completed successfully ({completed}/{total} steps)."
        elif executed_plan.status.value == "failed":
            failed_steps = [s.description for s in executed_plan.steps if s.status.value == "failed"]
            return f"Task partially completed. Failed steps: {', '.join(failed_steps)}."
        else:
            return f"Task status: {executed_plan.status.value} ({completed}/{total} steps)."
    
    # Add summary header
    summary = f"Task {executed_plan.status.value} ({completed}/{total} steps)\n\n"
    return summary + "\n\n".join(messages)


def execute_plan(ctx: PipelineContext) -> str | None:
    text = ctx.text

    # ── Task Planner Integration (Phase 2) ───────────────────────────
    # If a multi-step task plan was created, use it for execution
    if ctx.task_plan:
        result = _execute_task_plan(ctx)
        if result:
            update_ui("sig_vivie_message", result)
            return result
        # If task plan execution fails or returns None, fall through to legacy path

    # ── Code agent shortcut ───────────────────────────────────────────
    if any(t in text.lower() for t in CODE_TRIGGERS):
        from Core_structure.agent_router import code_agent
        from Core_structure.response_formatter import format_response

        response = code_agent(text)
        if response:
            response = format_response(response)
            update_ui("sig_vivie_message", response)
            return response

    # ── Phase 5: Multi-step action chaining (Legacy) ─────────────────
    # When the LLM returns multiple tools (compound query), we run each
    # in order and concatenate the results into one reply.
    results = []
    for act in ctx.actions:
        act_type = act["type"]
        details  = act["details"]
        ctx.details = details
        kwargs   = act.get("kwargs", {})

        # FIX: handle_action MUST run first — it handles known action types
        # like respond_text, check_internet_speed, vision_analysis, etc.
        # Running handle_tool_or_agent first caused ToolRouter to receive
        # 'respond_text' as a tool name → "Unknown tool" log + wasted Brain call.
        result = handle_action(ctx, act_type, details, kwargs)
        if result is not None:
            results.append(result)
            # If it was a respond_text (chat), stop — no need to chain further
            if act_type == "respond_text":
                break
            continue

        result = handle_tool_or_agent(ctx, act_type, details, kwargs)
        if result:
            results.append(result)

    # ── Return ────────────────────────────────────────────────────────
    if not results:
        return None

    # Single result — return as-is (backward compatible)
    if len(results) == 1:
        return _extract_message_from_result(results[0])

    # Multiple results from compound query — join with a separator
    messages = [_extract_message_from_result(r) for r in results if r]
    return "\n\n".join(filter(None, messages))