"""
Core_structure/approval_manager.py — Human Approval Workflow

Manages authorization requests for consequential actions.
Provides enforceable approval checks that prevent execution without user consent.
"""

from __future__ import annotations
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Any


class ApprovalStatus(Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ActionRisk(Enum):
    """Risk classification for actions."""
    SAFE = "safe"  # Read-only, no side effects
    LOW = "low"  # Reversible changes
    MODERATE = "moderate"  # Data modifications
    HIGH = "high"  # External communications
    CRITICAL = "critical"  # Destructive or irreversible


@dataclass
class ApprovalRequest:
    """
    A request for user approval before executing an action.
    
    Attributes:
        approval_id: Unique identifier for this approval
        task_id: Associated task ID (if part of a multi-step task)
        action_type: Tool or action being requested
        description: Human-readable description
        target: Target of the action (e.g., file path, email recipient)
        risk: Risk classification
        arguments_summary: Sanitized summary of arguments
        created_at: Timestamp when request was created
        expires_at: Timestamp when request expires
        status: Current approval status
        callback: Function to call when approved
    """
    approval_id: str
    action_type: str
    description: str
    target: str = ""
    risk: ActionRisk = ActionRisk.LOW
    arguments_summary: str = ""
    task_id: str = ""
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    expires_at: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    callback: Callable | None = None
    
    def __post_init__(self):
        if not self.expires_at:
            # Default 5 minute expiration
            expires = time.time() + 300
            self.expires_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expires))
    
    def is_expired(self) -> bool:
        """Check if approval has expired."""
        expires_timestamp = time.mktime(time.strptime(self.expires_at, "%Y-%m-%d %H:%M:%S"))
        return time.time() >= expires_timestamp
    
    def to_dict(self) -> dict:
        """Convert to dictionary for UI/logging."""
        return {
            "approval_id": self.approval_id,
            "task_id": self.task_id,
            "action_type": self.action_type,
            "description": self.description,
            "target": self.target,
            "risk": self.risk.value,
            "arguments_summary": self.arguments_summary,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "status": self.status.value,
        }


class ApprovalManager:
    """
    Manages approval requests and enforces authorization.
    
    - Stores pending approvals server-side
    - Validates approval before execution
    - Prevents duplicate approvals
    - Handles expiration and cancellation
    """
    
    def __init__(self):
        self._approvals: dict[str, ApprovalRequest] = {}
        self._lock = threading.Lock()
        self._counter = 0
    
    def _generate_approval_id(self) -> str:
        """Generate a unique approval ID."""
        self._counter += 1
        return f"approval_{self._counter:04d}"
    
    def request_approval(
        self,
        action_type: str,
        description: str,
        target: str = "",
        risk: ActionRisk = ActionRisk.LOW,
        arguments_summary: str = "",
        task_id: str = "",
        callback: Callable | None = None,
    ) -> ApprovalRequest:
        """
        Create an approval request and notify the UI.
        
        Returns the approval request. Execution should wait for approval.
        """
        with self._lock:
            approval_id = self._generate_approval_id()
            request = ApprovalRequest(
                approval_id=approval_id,
                action_type=action_type,
                description=description,
                target=target,
                risk=risk,
                arguments_summary=arguments_summary,
                task_id=task_id,
                callback=callback,
            )
            self._approvals[approval_id] = request
        
        # Notify UI of approval request
        print(f"[ApprovalManager] Requesting approval for {action_type}: {description}")
        try:
            from vivie_core.ui import update_ui
            update_ui("sig_approval_request", request.to_dict())
        except Exception as e:
            print(f"[ApprovalManager] UI notification failed: {e}")
        
        return request
    
    def check_approval(self, approval_id: str) -> bool:
        """
        Check if an approval is valid and granted.
        
        Returns True if approved and not expired, False otherwise.
        """
        with self._lock:
            request = self._approvals.get(approval_id)
            if not request:
                print(f"[ApprovalManager] Unknown approval ID: {approval_id}")
                return False
            
            if request.is_expired():
                request.status = ApprovalStatus.EXPIRED
                print(f"[ApprovalManager] Approval expired: {approval_id}")
                return False
            
            if request.status == ApprovalStatus.APPROVED:
                return True
            
            if request.status == ApprovalStatus.REJECTED:
                return False
            
            if request.status == ApprovalStatus.CANCELLED:
                return False
            
            # Still pending
            return False
    
    def approve(self, approval_id: str) -> bool:
        """
        Approve a pending request.
        
        Returns True if successfully approved, False if invalid/expired.
        """
        with self._lock:
            request = self._approvals.get(approval_id)
            if not request:
                print(f"[ApprovalManager] Cannot approve unknown ID: {approval_id}")
                return False
            
            if request.status != ApprovalStatus.PENDING:
                print(f"[ApprovalManager] Cannot approve non-pending request: {approval_id} (status={request.status.value})")
                return False
            
            if request.is_expired():
                request.status = ApprovalStatus.EXPIRED
                print(f"[ApprovalManager] Cannot approve expired request: {approval_id}")
                return False
            
            request.status = ApprovalStatus.APPROVED
            print(f"[ApprovalManager] Approved: {approval_id}")
            try:
                from vivie_core.ui import update_ui
                update_ui("sig_approval_status", {"approval_id": approval_id, "status": "approved"})
            except Exception as e:
                print(f"[ApprovalManager] UI notification failed: {e}")
            
            # Execute callback if provided
            if request.callback:
                try:
                    request.callback()
                except Exception as e:
                    print(f"[ApprovalManager] Callback execution failed: {e}")
            
            return True
    
    def reject(self, approval_id: str) -> bool:
        """
        Reject a pending request.
        
        Returns True if successfully rejected, False if invalid.
        """
        with self._lock:
            request = self._approvals.get(approval_id)
            if not request:
                return False
            
            if request.status != ApprovalStatus.PENDING:
                return False
            
            request.status = ApprovalStatus.REJECTED
            print(f"[ApprovalManager] Rejected: {approval_id}")
            try:
                from vivie_core.ui import update_ui
                update_ui("sig_approval_status", {"approval_id": approval_id, "status": "rejected"})
            except Exception as e:
                print(f"[ApprovalManager] UI notification failed: {e}")
            
            return True
    
    def cancel(self, approval_id: str) -> bool:
        """
        Cancel a pending request (e.g., task cancelled).
        
        Returns True if successfully cancelled, False if invalid.
        """
        with self._lock:
            request = self._approvals.get(approval_id)
            if not request:
                return False
            
            if request.status != ApprovalStatus.PENDING:
                return False
            
            request.status = ApprovalStatus.CANCELLED
            print(f"[ApprovalManager] Cancelled: {approval_id}")
            try:
                from vivie_core.ui import update_ui
                update_ui("sig_approval_status", {"approval_id": approval_id, "status": "cancelled"})
            except Exception as e:
                print(f"[ApprovalManager] UI notification failed: {e}")
            
            return True
    
    def cleanup(self, approval_id: str | None = None) -> None:
        """
        Remove completed or expired approvals.
        
        If approval_id is provided, only remove that one.
        Otherwise, clean up all completed approvals.
        """
        with self._lock:
            if approval_id:
                self._approvals.pop(approval_id, None)
            else:
                to_remove = [
                    aid for aid, req in self._approvals.items()
                    if req.status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, 
                                   ApprovalStatus.EXPIRED, ApprovalStatus.CANCELLED)
                ]
                for aid in to_remove:
                    self._approvals.pop(aid, None)
    
    def get_pending_approvals(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        with self._lock:
            return [req for req in self._approvals.values() if req.status == ApprovalStatus.PENDING]


# Singleton instance
_approval_manager_instance: ApprovalManager | None = None


def get_approval_manager() -> ApprovalManager:
    """Get the singleton approval manager instance."""
    global _approval_manager_instance
    if _approval_manager_instance is None:
        _approval_manager_instance = ApprovalManager()
    return _approval_manager_instance


def check_action_requires_approval(action_type: str) -> bool:
    """
    Determine if an action type requires approval based on its risk.
    
    Returns True if approval is required, False otherwise.
    """
    # Define risk classification for common actions
    high_risk_actions = {
        "delete_file",
        "send_email",
        "send_whatsapp",
        "publish",
        "modify_repository",
        "delete_calendar_event",
        "modify_calendar_event",
    }
    
    moderate_risk_actions = {
        "create_file",
        "modify_file",
        "create_calendar_event",
    }
    
    if action_type in high_risk_actions:
        return True
    
    if action_type in moderate_risk_actions:
        return True  # Can be configured to be optional
    
    return False


def requires_approval_for_side_effect(side_effect: str) -> bool:
    """
    Check if a side-effect classification requires approval.
    
    Matches ToolResult.SideEffect values.
    """
    from Core_structure.tool_result import SideEffect
    
    if side_effect in (SideEffect.DESTRUCTIVE, SideEffect.EXTERNAL):
        return True
    
    return False
