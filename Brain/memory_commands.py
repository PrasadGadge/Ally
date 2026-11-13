"""
Brain/memory_commands.py — Memory Management Commands

Provides user-facing commands for controlling Vivie's memory:
- "What do you remember about me?" - Show personal preferences
- "Remember this for my project" - Add to project memory
- "Forget this information" - Remove specific memory
- "Forget the current conversation" - Clear session memory
- "Turn memory off" - Disable memory storage
- "Show me my saved project notes" - Display project notes
- "What are my projects?" - List all projects
"""

from __future__ import annotations
from typing import Optional, Tuple
from memory_core.episodic_memory import load_episodes, get_memory_stats
from memory_core.session_memory import get_session_memory
from Brain.project_memory import get_project_memory


class MemoryCommands:
    """
    Handles memory management commands from the user.
    Provides safe, controlled access to memory operations.
    """

    def __init__(self):
        self._memory_enabled = True
        self._project_memory = get_project_memory()
        self._session_memory = get_session_memory()

    def handle_command(self, user_input: str) -> Optional[str]:
        """
        Process a memory management command.
        Returns response string if command handled, None otherwise.
        """
        d = user_input.lower().strip()

        # Show personal memory
        if any(phrase in d for phrase in ["what do you remember", "what have you remembered", "my preferences"]):
            return self._show_personal_memory()

        # List projects
        if any(phrase in d for phrase in ["what are my projects", "list my projects", "show my projects"]):
            return self._list_projects()

        # Show project details
        if "show project" in d or "project details" in d:
            # Extract project name
            words = d.split()
            for i, word in enumerate(words):
                if word == "project" and i + 1 < len(words):
                    project_name = " ".join(words[i+1:])
                    return self._show_project(project_name)

        # Remember for project
        if "remember for project" in d or "remember to project" in d:
            # Extract project name and note
            if "remember for project" in d:
                parts = d.split("remember for project", 1)[1].strip()
            else:
                parts = d.split("remember to project", 1)[1].strip()

            if ":" in parts:
                project_name, note = parts.split(":", 1)
                return self._add_project_note(project_name.strip(), note.strip())
            else:
                return "Boss, please use format: 'Remember for project [name]: [note]'"

        # Create project
        if "create project" in d or "new project" in d:
            parts = d.replace("create project", "").replace("new project", "").strip()
            if ":" in parts:
                name, purpose = parts.split(":", 1)
                return self._create_project(name.strip(), purpose.strip())
            else:
                return "Boss, please use format: 'Create project [name]: [purpose]'"

        # Turn memory off
        if "turn memory off" in d or "disable memory" in d:
            self._memory_enabled = False
            return "Boss, I've disabled memory storage for this session. I won't remember new information."

        # Turn memory on
        if "turn memory on" in d or "enable memory" in d:
            self._memory_enabled = True
            return "Boss, I've re-enabled memory storage."

        # Forget current conversation
        if "forget the current conversation" in d or "clear this conversation" in d:
            self._session_memory._current_turns = []
            return "Boss, I've cleared the current conversation from working memory."

        # Forget specific info (placeholder - would need more sophisticated deletion)
        if "forget" in d and "project" not in d:
            return "Boss, I can forget the current conversation or specific project information. What would you like me to forget?"

        return None

    def _show_personal_memory(self) -> str:
        """Show summary of what Vivie remembers about the user."""
        stats = get_memory_stats()
        total = stats.get("total", 0)
        positive = stats.get("positive", 0)
        negative = stats.get("negative", 0)
        top_topics = stats.get("top_topics", [])

        lines = [
            "Boss, here's what I remember about our interactions:",
            f"Total conversations recorded: {total}",
            f"Positive responses: {positive}",
            f"Negative responses: {negative}",
        ]

        if top_topics:
            lines.append("\nTopics we've discussed:")
            for topic in top_topics:
                lines.append(f"  • {topic}")

        projects = self._project_memory.list_projects(status="active")
        if projects:
            lines.append(f"\nActive projects: {len(projects)}")
            for proj in projects[:5]:
                lines.append(f"  • {proj.name} - {proj.purpose[:50]}")

        return "\n".join(lines)

    def _list_projects(self) -> str:
        """List all projects."""
        projects = self._project_memory.list_projects()
        if not projects:
            return "Boss, you don't have any projects tracked yet. Say 'Create project [name]: [purpose]' to start one."

        lines = [f"Boss, you have {len(projects)} project{'s' if len(projects) != 1 else ''}:"]
        for proj in projects:
            status_icon = "✓" if proj.status == "active" else "○"
            lines.append(f"  {status_icon} {proj.name} - {proj.purpose[:60]}")
            if proj.next_actions:
                lines.append(f"      Next: {proj.next_actions[0][:50]}")

        return "\n".join(lines)

    def _show_project(self, name: str) -> str:
        """Show project details."""
        formatted = self._project_memory.format_project(name)
        if formatted:
            return formatted
        return f"Boss, I don't have a project named '{name}'. Here are your projects: " + ", ".join(p.name for p in self._project_memory.list_projects())

    def _add_project_note(self, name: str, note: str) -> str:
        """Add a note to a project."""
        if self._project_memory.add_note(name, note):
            return f"Boss, I've added that note to project '{name}'."
        return f"Boss, I couldn't find project '{name}'. Create it first with 'Create project {name}: [purpose]'"

    def _create_project(self, name: str, purpose: str) -> str:
        """Create a new project."""
        if self._project_memory.create_project(name, purpose):
            return f"Boss, I've created project '{name}' with purpose: {purpose}"
        return f"Boss, project '{name}' already exists."

    def is_memory_enabled(self) -> bool:
        """Check if memory storage is enabled."""
        return self._memory_enabled


# Singleton instance
_memory_commands_instance: Optional[MemoryCommands] = None


def get_memory_commands() -> MemoryCommands:
    """Get the singleton memory commands instance."""
    global _memory_commands_instance
    if _memory_commands_instance is None:
        _memory_commands_instance = MemoryCommands()
    return _memory_commands_instance
