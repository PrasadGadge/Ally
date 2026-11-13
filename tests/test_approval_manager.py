"""
Tests for approval manager and human approval workflow.
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from Core_structure.approval_manager import (
    ApprovalManager,
    ApprovalRequest,
    ApprovalStatus,
    ActionRisk,
    get_approval_manager,
    check_action_requires_approval,
    requires_approval_for_side_effect,
)

# Mock UI module to prevent hanging in tests
import sys
sys.modules['vivie_core.ui'] = MagicMock()
sys.modules['vivie_core.ui'].update_ui = MagicMock()


class TestApprovalManager:
    """Test ApprovalManager functionality."""
    
    def test_approval_manager_initialization(self):
        """Test creating an approval manager."""
        manager = ApprovalManager()
        assert manager is not None
        assert len(manager._approvals) == 0
    
    def test_request_approval(self):
        """Test creating an approval request."""
        manager = ApprovalManager()
        
        request = manager.request_approval(
            action_type="delete_file",
            description="Delete important file",
            target="/path/to/file.txt",
            risk=ActionRisk.CRITICAL,
        )
        
        assert request.approval_id.startswith("approval_")
        assert request.status == ApprovalStatus.PENDING
        assert request.action_type == "delete_file"
        assert request.risk == ActionRisk.CRITICAL
    
    def test_approve_request(self):
        """Test approving a pending request."""
        manager = ApprovalManager()
        
        request = manager.request_approval(
            action_type="send_email",
            description="Send email",
            risk=ActionRisk.HIGH,
        )
        
        result = manager.approve(request.approval_id)
        
        assert result is True
        assert request.status == ApprovalStatus.APPROVED
        assert manager.check_approval(request.approval_id) is True
    
    def test_reject_request(self):
        """Test rejecting a pending request."""
        manager = ApprovalManager()
        
        request = manager.request_approval(
            action_type="delete_file",
            description="Delete file",
            risk=ActionRisk.CRITICAL,
        )
        
        result = manager.reject(request.approval_id)
        
        assert result is True
        assert request.status == ApprovalStatus.REJECTED
        assert manager.check_approval(request.approval_id) is False
    
    def test_cancel_request(self):
        """Test cancelling a pending request."""
        manager = ApprovalManager()
        
        request = manager.request_approval(
            action_type="send_email",
            description="Send email",
            risk=ActionRisk.HIGH,
        )
        
        result = manager.cancel(request.approval_id)
        
        assert result is True
        assert request.status == ApprovalStatus.CANCELLED
        assert manager.check_approval(request.approval_id) is False
    
    def test_check_approval_pending(self):
        """Test that pending requests are not approved."""
        manager = ApprovalManager()
        
        request = manager.request_approval(
            action_type="send_email",
            description="Send email",
            risk=ActionRisk.HIGH,
        )
        
        assert manager.check_approval(request.approval_id) is False
    
    def test_check_approval_unknown_id(self):
        """Test checking approval for unknown ID."""
        manager = ApprovalManager()
        
        assert manager.check_approval("unknown_id") is False
    
    def test_approve_non_pending(self):
        """Test that approving a non-pending request fails."""
        manager = ApprovalManager()
        
        request = manager.request_approval(
            action_type="send_email",
            description="Send email",
            risk=ActionRisk.HIGH,
        )
        
        # First approve it
        manager.approve(request.approval_id)
        
        # Try to approve again
        result = manager.approve(request.approval_id)
        
        assert result is False  # Cannot approve already-approved request
    
    def test_reject_non_pending(self):
        """Test that rejecting a non-pending request fails."""
        manager = ApprovalManager()
        
        request = manager.request_approval(
            action_type="send_email",
            description="Send email",
            risk=ActionRisk.HIGH,
        )
        
        # First approve it
        manager.approve(request.approval_id)
        
        # Try to reject it
        result = manager.reject(request.approval_id)
        
        assert result is False  # Cannot reject already-approved request
    
    def test_approval_expiration(self):
        """Test that expired approvals are rejected."""
        manager = ApprovalManager()
        
        request = manager.request_approval(
            action_type="send_email",
            description="Send email",
            risk=ActionRisk.HIGH,
        )
        
        # Manually set expiration to past
        request.expires_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 100))
        
        assert request.is_expired() is True
        assert manager.check_approval(request.approval_id) is False
    
    def test_cleanup(self):
        """Test cleaning up completed approvals."""
        manager = ApprovalManager()
        
        request1 = manager.request_approval(
            action_type="send_email",
            description="Send email",
            risk=ActionRisk.HIGH,
        )
        manager.approve(request1.approval_id)
        
        request2 = manager.request_approval(
            action_type="delete_file",
            description="Delete file",
            risk=ActionRisk.CRITICAL,
        )
        manager.reject(request2.approval_id)
        
        # Should have 2 approvals
        assert len(manager._approvals) == 2
        
        # Cleanup
        manager.cleanup()
        
        # Should have 0 approvals
        assert len(manager._approvals) == 0
    
    def test_cleanup_specific(self):
        """Test cleaning up a specific approval."""
        manager = ApprovalManager()
        
        request = manager.request_approval(
            action_type="send_email",
            description="Send email",
            risk=ActionRisk.HIGH,
        )
        manager.approve(request.approval_id)
        
        assert len(manager._approvals) == 1
        
        manager.cleanup(request.approval_id)
        
        assert len(manager._approvals) == 0
    
    def test_get_pending_approvals(self):
        """Test getting pending approvals."""
        manager = ApprovalManager()
        
        request1 = manager.request_approval(
            action_type="send_email",
            description="Send email",
            risk=ActionRisk.HIGH,
        )
        
        request2 = manager.request_approval(
            action_type="delete_file",
            description="Delete file",
            risk=ActionRisk.CRITICAL,
        )
        manager.approve(request2.approval_id)
        
        pending = manager.get_pending_approvals()
        
        assert len(pending) == 1
        assert pending[0].approval_id == request1.approval_id


class TestActionRiskClassification:
    """Test action risk classification."""
    
    def test_check_action_requires_approval_high_risk(self):
        """Test that high-risk actions require approval."""
        assert check_action_requires_approval("delete_file") is True
        assert check_action_requires_approval("send_email") is True
        assert check_action_requires_approval("send_whatsapp") is True
        assert check_action_requires_approval("publish") is True
    
    def test_check_action_requires_approval_moderate_risk(self):
        """Test that moderate-risk actions require approval."""
        assert check_action_requires_approval("create_file") is True
        assert check_action_requires_approval("modify_file") is True
        assert check_action_requires_approval("create_calendar_event") is True
    
    def test_check_action_requires_approval_safe(self):
        """Test that safe actions do not require approval."""
        assert check_action_requires_approval("web_search") is False
        assert check_action_requires_approval("get_weather") is False
        assert check_action_requires_approval("respond_text") is False
        assert check_action_requires_approval("calculator") is False
    
    def test_requires_approval_for_side_effect(self):
        """Test side-effect based approval requirements."""
        from Core_structure.tool_result import SideEffect
        
        assert requires_approval_for_side_effect(SideEffect.DESTRUCTIVE) is True
        assert requires_approval_for_side_effect(SideEffect.EXTERNAL) is True
        assert requires_approval_for_side_effect(SideEffect.NONE) is False
        assert requires_approval_for_side_effect(SideEffect.REVERSIBLE) is False


class TestApprovalCallback:
    """Test approval callback execution."""
    
    def test_callback_on_approval(self):
        """Test that callback executes on approval."""
        manager = ApprovalManager()
        
        callback_executed = []
        
        def test_callback():
            callback_executed.append(True)
        
        request = manager.request_approval(
            action_type="send_email",
            description="Send email",
            risk=ActionRisk.HIGH,
            callback=test_callback,
        )
        
        # Callback should not have executed yet
        assert len(callback_executed) == 0
        
        # Approve
        manager.approve(request.approval_id)
        
        # Callback should have executed
        assert len(callback_executed) == 1
    
    def test_callback_not_on_rejection(self):
        """Test that callback does not execute on rejection."""
        manager = ApprovalManager()
        
        callback_executed = []
        
        def test_callback():
            callback_executed.append(True)
        
        request = manager.request_approval(
            action_type="send_email",
            description="Send email",
            risk=ActionRisk.HIGH,
            callback=test_callback,
        )
        
        # Reject
        manager.reject(request.approval_id)
        
        # Callback should not have executed
        assert len(callback_executed) == 0


class TestApprovalSingleton:
    """Test approval manager singleton."""
    
    def test_singleton(self):
        """Test that get_approval_manager returns singleton."""
        manager1 = get_approval_manager()
        manager2 = get_approval_manager()
        assert manager1 is manager2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
