"""
Tests for multi-step task planner.
"""

import pytest
from Core_structure.task_planner import TaskPlanner, TaskPlan, TaskStep, StepStatus
from Core_structure.tool_result import ToolResult, ToolStatus


class TestTaskStep:
    """Test TaskStep functionality."""
    
    def test_step_creation(self):
        """Test creating a task step."""
        step = TaskStep(
            step_id="step_1",
            description="Test step",
            action_type="test_action",
        )
        assert step.step_id == "step_1"
        assert step.description == "Test step"
        assert step.action_type == "test_action"
        assert step.status == StepStatus.PENDING
    
    def test_step_with_dependencies(self):
        """Test step dependency checking."""
        step = TaskStep(
            step_id="step_2",
            description="Dependent step",
            action_type="test_action",
            dependencies=["step_1"],
        )
        
        # Not ready when dependency not completed
        assert step.is_ready(set()) is False
        
        # Ready when dependency completed
        assert step.is_ready({"step_1"}) is True
    
    def test_step_to_dict(self):
        """Test converting step to dictionary."""
        step = TaskStep(
            step_id="step_1",
            description="Test",
            action_type="test",
        )
        d = step.to_dict()
        assert d["step_id"] == "step_1"
        assert d["description"] == "Test"
        assert d["status"] == "pending"


class TestTaskPlan:
    """Test TaskPlan functionality."""
    
    def test_plan_creation(self):
        """Test creating a task plan."""
        plan = TaskPlan(
            task_id="task_1",
            description="Test task",
        )
        assert plan.task_id == "task_1"
        assert plan.description == "Test task"
        assert plan.status == StepStatus.PENDING
        assert len(plan.steps) == 0
    
    def test_add_step(self):
        """Test adding steps to a plan."""
        plan = TaskPlan(task_id="task_1", description="Test")
        step = TaskStep(step_id="step_1", description="Test", action_type="test")
        plan.add_step(step)
        assert len(plan.steps) == 1
        assert plan.steps[0] is step
    
    def test_get_next_ready_step(self):
        """Test getting the next ready step."""
        plan = TaskPlan(task_id="task_1", description="Test")
        
        step1 = TaskStep(step_id="step_1", description="First", action_type="test")
        step2 = TaskStep(step_id="step_2", description="Second", action_type="test", dependencies=["step_1"])
        
        plan.add_step(step1)
        plan.add_step(step2)
        
        # First step should be ready
        next_step = plan.get_next_ready_step()
        assert next_step.step_id == "step_1"
        
        # Complete first step
        step1.status = StepStatus.COMPLETED
        
        # Now second step should be ready
        next_step = plan.get_next_ready_step()
        assert next_step.step_id == "step_2"
    
    def test_get_progress(self):
        """Test getting progress."""
        plan = TaskPlan(task_id="task_1", description="Test")
        plan.add_step(TaskStep(step_id="s1", description="1", action_type="test"))
        plan.add_step(TaskStep(step_id="s2", description="2", action_type="test"))
        plan.add_step(TaskStep(step_id="s3", description="3", action_type="test"))
        
        completed, total = plan.get_progress()
        assert completed == 0
        assert total == 3
        
        plan.steps[0].status = StepStatus.COMPLETED
        plan.steps[1].status = StepStatus.COMPLETED
        
        completed, total = plan.get_progress()
        assert completed == 2
        assert total == 3
    
    def test_is_complete(self):
        """Test checking if plan is complete."""
        plan = TaskPlan(task_id="task_1", description="Test")
        plan.add_step(TaskStep(step_id="s1", description="1", action_type="test"))
        plan.add_step(TaskStep(step_id="s2", description="2", action_type="test"))
        
        assert plan.is_complete() is False
        
        plan.steps[0].status = StepStatus.COMPLETED
        plan.steps[1].status = StepStatus.COMPLETED
        
        assert plan.is_complete() is True
    
    def test_has_failure(self):
        """Test checking if plan has failures."""
        plan = TaskPlan(task_id="task_1", description="Test")
        plan.add_step(TaskStep(step_id="s1", description="1", action_type="test"))
        
        assert plan.has_failure() is False
        
        plan.steps[0].status = StepStatus.FAILED
        
        assert plan.has_failure() is True


class TestTaskPlanner:
    """Test TaskPlanner functionality."""
    
    def test_planner_initialization(self):
        """Test creating a task planner."""
        planner = TaskPlanner()
        assert planner is not None
        assert len(planner._active_tasks) == 0
    
    def test_analyze_simple_request(self):
        """Test analyzing a simple (non-multi-step) request."""
        planner = TaskPlanner()
        intent = {"primary": "weather", "confidence": 0.9}
        plan = planner.analyze_request("What's the weather?", intent)
        
        # Simple request should return None (no multi-step planning needed)
        assert plan is None
    
    def test_plan_from_llm_tools(self):
        """Test creating a plan from LLM-provided tools."""
        planner = TaskPlanner()
        plan = planner._plan_from_llm_tools(
            user_text="Research and summarize",
            primary="web_search",
            parameters={"query": "AI agents"},
            extra_tools=[
                {"tool": "respond_text", "arguments": {"content": "summary"}},
            ],
        )
        
        assert plan is not None
        assert len(plan.steps) == 2
        assert plan.steps[0].action_type == "web_search"
        assert plan.steps[1].action_type == "respond_text"
    
    def test_execute_plan_success(self):
        """Test executing a plan successfully."""
        planner = TaskPlanner()
        plan = TaskPlan(task_id="task_1", description="Test")
        plan.add_step(TaskStep(step_id="s1", description="Step 1", action_type="test"))
        
        def mock_executor(action_type, parameters):
            return ToolResult.success("Success", tool_name=action_type)
        
        result = planner.execute_plan(plan, mock_executor)
        
        assert result.status == StepStatus.COMPLETED
        assert plan.steps[0].status == StepStatus.COMPLETED
        assert plan.steps[0].result.is_success() is True
    
    def test_execute_plan_with_failure(self):
        """Test executing a plan with a failed step."""
        planner = TaskPlanner()
        plan = TaskPlan(task_id="task_1", description="Test")
        plan.add_step(TaskStep(step_id="s1", description="Step 1", action_type="test"))
        
        def mock_executor(action_type, parameters):
            return ToolResult.failure("Failed", error="Test error", tool_name=action_type)
        
        result = planner.execute_plan(plan, mock_executor)
        
        assert result.status == StepStatus.FAILED
        assert plan.steps[0].status == StepStatus.FAILED
    
    def test_execute_plan_with_dependencies(self):
        """Test executing a plan with step dependencies."""
        planner = TaskPlanner()
        plan = TaskPlan(task_id="task_1", description="Test")
        plan.add_step(TaskStep(step_id="s1", description="Step 1", action_type="test"))
        plan.add_step(TaskStep(step_id="s2", description="Step 2", action_type="test", dependencies=["s1"]))
        
        execution_order = []
        
        def mock_executor(action_type, parameters):
            execution_order.append(action_type)
            return ToolResult.success("Success", tool_name=action_type)
        
        planner.execute_plan(plan, mock_executor)
        
        # Steps should execute in dependency order
        assert execution_order == ["test", "test"]
        assert plan.steps[0].status == StepStatus.COMPLETED
        assert plan.steps[1].status == StepStatus.COMPLETED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
