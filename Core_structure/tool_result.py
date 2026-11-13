"""
Core_structure/tool_result.py — Structured Tool Result Verification

Provides a consistent interface for tool execution results:
- Success/failure status
- Structured data output
- Error representation
- Verification metadata
- Side-effect classification

This ensures tools return predictable, verifiable results instead of
ambiguous strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ToolStatus(Enum):
    """Status of tool execution."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    INVALID_ARGUMENTS = "invalid_arguments"


class SideEffect(Enum):
    """Classification of tool side effects."""
    NONE = "none"  # Read-only, no side effects
    REVERSIBLE = "reversible"  # Can be undone (e.g., create file that can be deleted)
    MODERATE = "moderate"  # Changes data but not critical (e.g., update note)
    DESTRUCTIVE = "destructive"  # Irreversible or high-impact (e.g., delete file, send email)
    EXTERNAL = "external"  # Affects external systems (e.g., send email, publish)


@dataclass
class ToolResult:
    """
    Structured result from tool execution.

    Attributes:
        status: Execution status (SUCCESS, FAILURE, etc.)
        data: Structured output data (dict, list, or primitive types)
        message: Human-readable message for the user
        error: Error details if status is FAILURE
        tool_name: Name of the tool that produced this result
        execution_time_ms: Time taken to execute in milliseconds
        verified: Whether the result was verified against expected outcome
        side_effect: Classification of side effects
        metadata: Additional tool-specific metadata
    """
    status: ToolStatus = ToolStatus.SUCCESS
    data: Any = None
    message: str = ""
    error: str | None = None
    tool_name: str = ""
    execution_time_ms: float = 0.0
    verified: bool = False
    side_effect: SideEffect = SideEffect.NONE
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def is_success(self) -> bool:
        """Check if execution was successful."""
        return self.status == ToolStatus.SUCCESS

    def is_failure(self) -> bool:
        """Check if execution failed."""
        return self.status in (ToolStatus.FAILURE, ToolStatus.TIMEOUT,
                             ToolStatus.PERMISSION_DENIED, ToolStatus.INVALID_ARGUMENTS)

    def requires_confirmation(self) -> bool:
        """Check if this result requires user confirmation before proceeding."""
        return self.side_effect in (SideEffect.DESTRUCTIVE, SideEffect.EXTERNAL)

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/UI display."""
        return {
            "status": self.status.value,
            "data": self.data,
            "message": self.message,
            "error": self.error,
            "tool_name": self.tool_name,
            "execution_time_ms": self.execution_time_ms,
            "verified": self.verified,
            "side_effect": self.side_effect.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }

    @classmethod
    def success(cls, message: str, data: Any = None, tool_name: str = "",
                side_effect: SideEffect = SideEffect.NONE, **metadata) -> ToolResult:
        """Create a successful result."""
        return cls(
            status=ToolStatus.SUCCESS,
            message=message,
            data=data,
            tool_name=tool_name,
            side_effect=side_effect,
            metadata=metadata,
        )

    @classmethod
    def failure(cls, message: str, error: str = "", tool_name: str = "",
                **metadata) -> ToolResult:
        """Create a failed result."""
        return cls(
            status=ToolStatus.FAILURE,
            message=message,
            error=error,
            tool_name=tool_name,
            metadata=metadata,
        )

    @classmethod
    def permission_denied(cls, message: str, tool_name: str = "",
                          **metadata) -> ToolResult:
        """Create a permission denied result."""
        return cls(
            status=ToolStatus.PERMISSION_DENIED,
            message=message,
            tool_name=tool_name,
            side_effect=SideEffect.EXTERNAL,  # Permission denied implies attempting an external action
            metadata=metadata,
        )

    @classmethod
    def invalid_arguments(cls, message: str, tool_name: str = "",
                         **metadata) -> ToolResult:
        """Create an invalid arguments result."""
        return cls(
            status=ToolStatus.INVALID_ARGUMENTS,
            message=message,
            tool_name=tool_name,
            metadata=metadata,
        )


def wrap_tool_result(result: Any, tool_name: str = "",
                     side_effect: SideEffect = SideEffect.NONE) -> ToolResult:
    """
    Wrap a legacy tool result (string) into a structured ToolResult.

    This provides backward compatibility for tools that return strings.
    A non-empty string is treated as success, empty string as failure.
    """
    if isinstance(result, ToolResult):
        return result

    if result is None or (isinstance(result, str) and not result.strip()):
        return ToolResult.failure(
            message="Tool returned no result",
            tool_name=tool_name,
        )

    if isinstance(result, str):
        return ToolResult.success(
            message=result,
            data={"raw_output": result},
            tool_name=tool_name,
            side_effect=side_effect,
        )

    if isinstance(result, (dict, list)):
        return ToolResult.success(
            message="Operation completed",
            data=result,
            tool_name=tool_name,
            side_effect=side_effect,
        )

    # Fallback for other types
    return ToolResult.success(
        message=str(result),
        data={"value": result},
        tool_name=tool_name,
        side_effect=side_effect,
    )
