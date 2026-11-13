"""
Core_structure/task_planner.py — Lightweight Multi-Step Task Planner

Breaks down complex user requests into executable steps with:
- Step dependencies
- Validation before execution
- Progress tracking
- Error recovery
- Result verification

Example: "Research this library, create a technical summary, and save it to my project notes"
  Step 1: Research library (web_search)
  Step 2: Create summary (LLM generation)
  Step 3: Save to project (project_memory.add_note)
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from Core_structure.tool_result import ToolResult, ToolStatus


class StepStatus(Enum):
    """Status of a task step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class TaskStep:
    """
    A single step in a multi-step task.

    Attributes:
        step_id: Unique identifier for this step
        description: Human-readable description
        action_type: Tool/action to execute
        parameters: Parameters for the action
        dependencies: List of step_ids this step depends on
        status: Current status
        result: Result from execution
        error: Error message if failed
        execution_time_ms: Time taken to execute
    """
    step_id: str
    description: str
    action_type: str
    parameters: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: ToolResult | None = None
    error: str | None = None
    execution_time_ms: float = 0.0

    def is_ready(self, completed_steps: set) -> bool:
        """Check if all dependencies are satisfied."""
        return all(dep in completed_steps for dep in self.dependencies)

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/UI."""
        return {
            "step_id": self.step_id,
            "description": self.description,
            "action_type": self.action_type,
            "parameters": self.parameters,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "result": self.result.to_dict() if self.result else None,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class TaskPlan:
    """
    A complete multi-step task plan.

    Attributes:
        task_id: Unique identifier for this task
        description: Overall task description
        steps: List of steps to execute
        current_step_index: Index of currently executing step
        status: Overall task status
        created_at: Timestamp when plan was created
        started_at: Timestamp when execution started
        completed_at: Timestamp when execution completed
    """
    task_id: str
    description: str
    steps: list[TaskStep] = field(default_factory=list)
    current_step_index: int = 0
    status: StepStatus = StepStatus.PENDING
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    started_at: str | None = None
    completed_at: str | None = None

    def add_step(self, step: TaskStep) -> None:
        """Add a step to the plan."""
        self.steps.append(step)

    def get_next_ready_step(self) -> TaskStep | None:
        """Get the next step that's ready to execute (dependencies satisfied)."""
        completed = {s.step_id for s in self.steps if s.status == StepStatus.COMPLETED}

        for step in self.steps:
            if step.status == StepStatus.PENDING and step.is_ready(completed):
                return step
        return None

    def get_progress(self) -> tuple[int, int]:
        """Get (completed, total) step count."""
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        return completed, len(self.steps)

    def is_complete(self) -> bool:
        """Check if all steps are complete (success or skipped)."""
        return all(
            s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED)
            for s in self.steps
        )

    def has_failure(self) -> bool:
        """Check if any step failed."""
        return any(s.status == StepStatus.FAILED for s in self.steps)

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/UI."""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress": f"{self.get_progress()[0]}/{self.get_progress()[1]}",
            "steps": [s.to_dict() for s in self.steps],
        }


class TaskPlanner:
    """
    Lightweight multi-step task planner.

    Analyzes complex requests and breaks them into executable steps.
    Executes steps in dependency order with validation and error recovery.
    """

    def __init__(self):
        self._active_tasks: dict[str, TaskPlan] = {}
        self._task_counter = 0

    def _generate_task_id(self) -> str:
        """Generate a unique task ID."""
        self._task_counter += 1
        return f"task_{self._task_counter:04d}"

    def analyze_request(self, user_text: str, intent: dict) -> TaskPlan | None:
        """
        Analyze a user request to determine if it requires multi-step planning.

        Returns a TaskPlan if multi-step execution is needed, None otherwise.
        """
        primary = intent.get("primary", "")
        parameters = intent.get("parameters", {})
        extra_tools = intent.get("extra_tools", [])

        # Simple check: if LLM already provided multiple tools, use that
        if extra_tools:
            return self._plan_from_llm_tools(user_text, primary, parameters, extra_tools)

        # Pattern: compound requests with "and", "then", "after that"
        compound_indicators = [" and ", " then ", " after that ", " followed by ", " next "]
        if any(indicator in user_text.lower() for indicator in compound_indicators):
            return self._plan_compound_request(user_text, intent)

        # Pattern: explicit multi-step verbs
        multi_step_verbs = ["research and", "analyze and", "create and", "generate and"]
        if any(verb in user_text.lower() for verb in multi_step_verbs):
            return self._plan_compound_request(user_text, intent)

        # Not a multi-step request
        return None

    def _plan_from_llm_tools(self, user_text: str, primary: str,
                            parameters: dict, extra_tools: list) -> TaskPlan:
        """Create a plan from LLM-provided multi-tool response."""
        task_id = self._generate_task_id()
        plan = TaskPlan(
            task_id=task_id,
            description=f"Execute multi-tool request: {user_text[:80]}...",
        )

        # Add primary tool as first step
        if primary and primary != "null":
            plan.add_step(TaskStep(
                step_id=f"{task_id}_step_1",
                description=f"Execute {primary}",
                action_type=primary,
                parameters=parameters,
            ))

        # Add extra tools as subsequent steps
        for i, tool in enumerate(extra_tools, start=2):
            tool_name = tool.get("tool") or tool.get("action_type")
            tool_params = tool.get("arguments", {})
            if tool_name and tool_name != "null":
                plan.add_step(TaskStep(
                    step_id=f"{task_id}_step_{i}",
                    description=f"Execute {tool_name}",
                    action_type=tool_name,
                    parameters=tool_params,
                    dependencies=[f"{task_id}_step_{i-1}"] if i > 1 else [],
                ))

        return plan

    def _plan_compound_request(self, user_text: str, intent: dict) -> TaskPlan | None:
        """
        Plan a compound request by analyzing the text structure.
        This is a simplified heuristic-based planner.
        """
        task_id = self._generate_task_id()
        plan = TaskPlan(
            task_id=task_id,
            description=f"Compound request: {user_text[:80]}...",
        )

        # Split by common compound indicators
        parts = []
        text = user_text
        for indicator in [" and then ", " then ", " and ", " after that "]:
            if indicator in text.lower():
                parts = text.lower().split(indicator)
                break

        if not parts:
            # Fallback: treat as single step
            return None

        # Create steps for each part (simplified - would need NLP for real parsing)
        for i, part in enumerate(parts):
            plan.add_step(TaskStep(
                step_id=f"{task_id}_step_{i+1}",
                description=f"Process: {part.strip()[:60]}...",
                action_type="respond_text",  # Default to LLM processing
                parameters={"query": part.strip()},
                dependencies=[f"{task_id}_step_{i}"] if i > 0 else [],
            ))

        return plan

    def execute_plan(self, plan: TaskPlan, executor: Callable) -> TaskPlan:
        """
        Execute a task plan using the provided executor function.

        Args:
            plan: The task plan to execute
            executor: Function that takes (action_type, parameters) and returns ToolResult

        Returns:
            The executed plan with results populated
        """
        plan.status = StepStatus.RUNNING
        plan.started_at = time.strftime("%Y-%m-%d %H:%M:%S")

        # Emit task started event
        try:
            from vivie_core.ui import update_ui
            update_ui("sig_task_started", {
                "task_id": plan.task_id,
                "description": plan.description,
                "total_steps": len(plan.steps),
            })
        except Exception as exc:
            print(f"[TaskPlanner] Failed to emit task_started event: {exc}")

        max_iterations = len(plan.steps) * 2  # Prevent infinite loops
        iteration = 0

        while not plan.is_complete() and iteration < max_iterations:
            iteration += 1

            step = plan.get_next_ready_step()
            if not step:
                # No ready step - either failed dependency or deadlock
                if plan.has_failure():
                    plan.status = StepStatus.FAILED
                    break
                else:
                    # All pending, waiting for something - break to avoid infinite loop
                    break

            # Execute the step
            step.status = StepStatus.RUNNING
            start_time = time.perf_counter()

            # Emit step started event
            try:
                from vivie_core.ui import update_ui
                update_ui("sig_step_started", {
                    "task_id": plan.task_id,
                    "step_id": step.step_id,
                    "description": step.description,
                    "action_type": step.action_type,
                })
            except Exception as exc:
                print(f"[TaskPlanner] Failed to emit step_started event: {exc}")

            try:
                result = executor(step.action_type, step.parameters)

                # Ensure result is a ToolResult
                from Core_structure.tool_result import wrap_tool_result
                if not isinstance(result, ToolResult):
                    result = wrap_tool_result(result, tool_name=step.action_type)

                step.result = result
                step.execution_time_ms = (time.perf_counter() - start_time) * 1000

                if result.is_success():
                    step.status = StepStatus.COMPLETED
                else:
                    step.status = StepStatus.FAILED
                    step.error = result.error or "Execution failed"

                    # Emit step failed event
                    try:
                        from vivie_core.ui import update_ui
                        update_ui("sig_step_failed", {
                            "task_id": plan.task_id,
                            "step_id": step.step_id,
                            "description": step.description,
                            "error": step.error,
                        })
                    except Exception as exc:
                        print(f"[TaskPlanner] Failed to emit step_failed event: {exc}")

                    # Optional: fail fast on critical errors
                    if result.status == ToolStatus.PERMISSION_DENIED:
                        plan.status = StepStatus.FAILED
                        break

            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)
                step.execution_time_ms = (time.perf_counter() - start_time) * 1000

                # Emit step failed event
                try:
                    from vivie_core.ui import update_ui
                    update_ui("sig_step_failed", {
                        "task_id": plan.task_id,
                        "step_id": step.step_id,
                        "error": str(e),
                    })
                except Exception as exc:
                    print(f"[TaskPlanner] Failed to emit step_failed event: {exc}")

        plan.completed_at = time.strftime("%Y-%m-%d %H:%M:%S")

        if plan.is_complete():
            plan.status = StepStatus.COMPLETED
        elif plan.has_failure():
            plan.status = StepStatus.FAILED
        else:
            plan.status = StepStatus.CANCELLED

        # Emit task completed event
        try:
            from vivie_core.ui import update_ui
            completed, total = plan.get_progress()
            update_ui("sig_task_completed", {
                "task_id": plan.task_id,
                "status": plan.status.value,
                "completed": completed,
                "total": total,
            })
        except Exception as exc:
            print(f"[TaskPlanner] Failed to emit task_completed event: {exc}")

        return plan

    def get_task(self, task_id: str) -> TaskPlan | None:
        """Get an active task by ID."""
        return self._active_tasks.get(task_id)

    def cleanup_completed(self) -> None:
        """Remove completed tasks from active registry."""
        to_remove = [
            task_id for task_id, plan in self._active_tasks.items()
            if plan.status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.CANCELLED)
        ]
        for task_id in to_remove:
            del self._active_tasks[task_id]


# Singleton instance
_task_planner_instance: TaskPlanner | None = None


def get_task_planner() -> TaskPlanner:
    """Get the singleton task planner instance."""
    global _task_planner_instance
    if _task_planner_instance is None:
        _task_planner_instance = TaskPlanner()
    return _task_planner_instance
