"""
Tests for structured tool result verification.
"""

import pytest
from Core_structure.tool_result import ToolResult, ToolStatus, SideEffect, wrap_tool_result


class TestToolResult:
    """Test ToolResult structured results."""
    
    def test_success_result(self):
        """Test creating a success result."""
        result = ToolResult.success(
            message="Operation completed",
            data={"key": "value"},
            tool_name="test_tool",
        )
        assert result.status == ToolStatus.SUCCESS
        assert result.message == "Operation completed"
        assert result.data == {"key": "value"}
        assert result.tool_name == "test_tool"
        assert result.is_success() is True
        assert result.is_failure() is False
    
    def test_failure_result(self):
        """Test creating a failure result."""
        result = ToolResult.failure(
            message="Operation failed",
            error="Connection error",
            tool_name="test_tool",
        )
        assert result.status == ToolStatus.FAILURE
        assert result.message == "Operation failed"
        assert result.error == "Connection error"
        assert result.is_success() is False
        assert result.is_failure() is True
    
    def test_permission_denied_result(self):
        """Test creating a permission denied result."""
        result = ToolResult.permission_denied(
            message="Access denied",
            tool_name="delete_file",
        )
        assert result.status == ToolStatus.PERMISSION_DENIED
        assert result.requires_confirmation() is True
    
    def test_invalid_arguments_result(self):
        """Test creating an invalid arguments result."""
        result = ToolResult.invalid_arguments(
            message="Missing required parameter",
            tool_name="search",
        )
        assert result.status == ToolStatus.INVALID_ARGUMENTS
        assert result.is_failure() is True
    
    def test_side_effect_classification(self):
        """Test side effect classification."""
        none_result = ToolResult.success("test", side_effect=SideEffect.NONE)
        assert none_result.requires_confirmation() is False
        
        reversible_result = ToolResult.success("test", side_effect=SideEffect.REVERSIBLE)
        assert reversible_result.requires_confirmation() is False
        
        destructive_result = ToolResult.success("test", side_effect=SideEffect.DESTRUCTIVE)
        assert destructive_result.requires_confirmation() is True
        
        external_result = ToolResult.success("test", side_effect=SideEffect.EXTERNAL)
        assert external_result.requires_confirmation() is True
    
    def test_to_dict(self):
        """Test converting to dictionary."""
        result = ToolResult.success(
            message="Test",
            data={"key": "value"},
            tool_name="test_tool",
        )
        d = result.to_dict()
        assert d["status"] == "success"
        assert d["message"] == "Test"
        assert d["data"] == {"key": "value"}
        assert d["tool_name"] == "test_tool"
        assert "timestamp" in d


class TestWrapToolResult:
    """Test wrapping legacy tool results."""
    
    def test_wrap_string_success(self):
        """Test wrapping a successful string result."""
        result = wrap_tool_result("Operation completed", tool_name="test")
        assert result.is_success() is True
        assert result.message == "Operation completed"
        assert result.data == {"raw_output": "Operation completed"}
    
    def test_wrap_string_failure(self):
        """Test wrapping an empty/failure string result."""
        result = wrap_tool_result("", tool_name="test")
        assert result.is_failure() is True
        assert result.message == "Tool returned no result"
    
    def test_wrap_none_failure(self):
        """Test wrapping a None result."""
        result = wrap_tool_result(None, tool_name="test")
        assert result.is_failure() is True
    
    def test_wrap_dict_success(self):
        """Test wrapping a dict result."""
        result = wrap_tool_result({"result": "data"}, tool_name="test")
        assert result.is_success() is True
        assert result.data == {"result": "data"}
    
    def test_wrap_list_success(self):
        """Test wrapping a list result."""
        result = wrap_tool_result([1, 2, 3], tool_name="test")
        assert result.is_success() is True
        assert result.data == [1, 2, 3]
    
    def test_wrap_tool_result_passthrough(self):
        """Test that ToolResult objects pass through unchanged."""
        original = ToolResult.success("test", tool_name="test")
        result = wrap_tool_result(original, tool_name="test")
        assert result is original
    
    def test_wrap_primitive_success(self):
        """Test wrapping a primitive type result."""
        result = wrap_tool_result(42, tool_name="test")
        assert result.is_success() is True
        assert result.data == {"value": 42}
        assert result.message == "42"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
