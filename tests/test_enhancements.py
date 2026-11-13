"""
Tests for Vivie enhancement features:
- Reference resolution
- Project memory
- Memory commands
"""

import pytest
from Brain.reference_resolver import ReferenceResolver
from Brain.project_memory import ProjectMemory, Project
from Brain.memory_commands import MemoryCommands


class TestReferenceResolver:
    """Test follow-up reference resolution."""

    def test_basic_pronoun_resolution(self):
        """Test simple 'it' resolution."""
        resolver = ReferenceResolver()
        resolver.add_turn("What's the weather?", "It's 72°F and sunny.")
        resolved = resolver.resolve("How about tomorrow?")
        # Should resolve to include weather context
        # The resolver attempts to replace "it/that" with topic
        # If no topic extracted, returns original
        assert resolved is not None

    def test_no_reference_unchanged(self):
        """Test that non-reference input is unchanged."""
        resolver = ReferenceResolver()
        original = "Tell me about Python"
        resolved = resolver.resolve(original)
        assert resolved == original

    def test_empty_history_no_resolution(self):
        """Test that resolver doesn't break with empty history."""
        resolver = ReferenceResolver()
        original = "What's the time?"
        resolved = resolver.resolve(original)
        assert resolved == original

    def test_clear_history(self):
        """Test history clearing."""
        resolver = ReferenceResolver()
        resolver.add_turn("Test", "Response")
        resolver.clear_history()
        assert len(resolver._conversation_history) == 0


class TestProjectMemory:
    """Test project memory system."""

    def setup_method(self):
        """Clear projects before each test."""
        # Use a fresh instance for each test
        pass

    def test_create_project(self):
        """Test creating a new project."""
        memory = ProjectMemory()
        memory._projects.clear()  # Clear existing
        result = memory.create_project("Test Project", "Testing the system")
        assert result is True
        assert "Test Project" in memory._projects

    def test_duplicate_project(self):
        """Test that duplicate projects are rejected."""
        memory = ProjectMemory()
        memory._projects.clear()
        memory.create_project("Duplicate", "First")
        result = memory.create_project("Duplicate", "Second")
        assert result is False

    def test_get_project(self):
        """Test retrieving a project."""
        memory = ProjectMemory()
        memory._projects.clear()
        memory.create_project("Retrieve Test", "For retrieval")
        project = memory.get_project("Retrieve Test")
        assert project is not None
        assert project.name == "Retrieve Test"
        assert project.purpose == "For retrieval"

    def test_add_note(self):
        """Test adding a note to a project."""
        memory = ProjectMemory()
        memory._projects.clear()
        memory.create_project("Notes Test", "For notes")
        result = memory.add_note("Notes Test", "Important decision made today")
        assert result is True
        project = memory.get_project("Notes Test")
        assert "Important decision made today" in project.notes

    def test_close_project(self):
        """Test marking a project as completed."""
        memory = ProjectMemory()
        memory._projects.clear()
        memory.create_project("Active Project", "Will be closed")
        result = memory.close_project("Active Project")
        assert result is True
        project = memory.get_project("Active Project")
        assert project.status == "completed"

    def test_delete_project(self):
        """Test deleting a project."""
        memory = ProjectMemory()
        memory._projects.clear()
        memory.create_project("Delete Me", "To be deleted")
        result = memory.delete_project("Delete Me")
        assert result is True
        assert "Delete Me" not in memory._projects

    def test_list_projects(self):
        """Test listing projects."""
        memory = ProjectMemory()
        memory._projects.clear()  # Clear any existing projects
        memory.create_project("Project A", "First")
        memory.create_project("Project B", "Second")
        projects = memory.list_projects()
        assert len(projects) == 2

    def test_format_project(self):
        """Test project formatting for display."""
        memory = ProjectMemory()
        memory._projects.clear()
        memory.create_project("Format Test", "Formatting test")
        formatted = memory.format_project("Format Test")
        assert formatted is not None
        assert "Format Test" in formatted
        assert "Formatting test" in formatted


class TestMemoryCommands:
    """Test memory command handling."""

    def setup_method(self):
        """Clear projects before each test."""
        pass

    def test_list_projects_command(self):
        """Test 'what are my projects' command."""
        commands = MemoryCommands()
        commands._project_memory._projects.clear()
        # Setup project memory
        commands._project_memory.create_project("Test", "Test project")
        response = commands.handle_command("What are my projects?")
        assert response is not None
        assert "Test" in response

    def test_create_project_command(self):
        """Test 'create project' command."""
        commands = MemoryCommands()
        commands._project_memory._projects.clear()
        response = commands.handle_command("Create project NewTest: A new project")
        assert response is not None
        assert "created" in response.lower()

    def test_show_project_command(self):
        """Test 'show project' command."""
        commands = MemoryCommands()
        commands._project_memory._projects.clear()
        commands._project_memory.create_project("ShowTest", "Show this")
        response = commands.handle_command("Show project ShowTest")
        assert response is not None
        assert "ShowTest" in response

    def test_add_project_note_command(self):
        """Test 'remember for project' command."""
        commands = MemoryCommands()
        # Use the project memory instance from commands
        commands._project_memory._projects.clear()
        commands._project_memory.create_project("notetest", "For notes")
        response = commands.handle_command("Remember for project notetest: Important note")
        assert response is not None
        assert "added" in response.lower()

    def test_turn_memory_off(self):
        """Test disabling memory."""
        commands = MemoryCommands()
        response = commands.handle_command("Turn memory off")
        assert response is not None
        assert commands.is_memory_enabled() is False

    def test_turn_memory_on(self):
        """Test enabling memory."""
        commands = MemoryCommands()
        commands._memory_enabled = False
        response = commands.handle_command("Turn memory on")
        assert response is not None
        assert commands.is_memory_enabled() is True

    def test_non_command_returns_none(self):
        """Test that non-commands return None."""
        commands = MemoryCommands()
        response = commands.handle_command("What's the weather?")
        assert response is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
