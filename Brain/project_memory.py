"""
Brain/project_memory.py — Project Memory System

Vivie's project-aware memory for tracking ongoing work:
- Project name and purpose
- Current objectives
- Important files/references
- Architecture decisions
- Current status
- Outstanding tasks
- Known issues
- Recent milestones
- Next actions

Provides commands:
- "Create project [name]" - Initialize a new project
- "Remember for project [name]: [info]" - Add project note
- "What are my projects?" - List all projects
- "Show project [name]" - Display project details
- "Project [name] status" - Show current status
- "Close project [name]" - Mark as completed
- "Delete project [name]" - Remove project
"""

from __future__ import annotations
import json
import os
import datetime
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict, field
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
PROJECTS_FILE = BASE_DIR / "data" / "projects.json"


@dataclass
class Project:
    """Represents a project Vivie is tracking."""
    name: str
    purpose: str
    created_at: str
    updated_at: str
    status: str = "active"  # active, completed, paused
    objectives: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    tasks: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    milestones: List[str] = field(default_factory=list)
    next_actions: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


class ProjectMemory:
    """
    Manages project memory storage and retrieval.
    Projects persisted to data/projects.json
    """

    def __init__(self):
        self._projects: Dict[str, Project] = {}
        self._load_projects()

    def _load_projects(self):
        """Load projects from JSON file."""
        if not PROJECTS_FILE.exists():
            PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            return

        try:
            with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for name, proj_data in data.items():
                    self._projects[name] = Project(**proj_data)
        except Exception as e:
            print(f"[ProjectMemory] Load error: {e}")

    def _save_projects(self):
        """Save projects to JSON file."""
        try:
            PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {name: asdict(proj) for name, proj in self._projects.items()}
            with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ProjectMemory] Save error: {e}")

    def create_project(self, name: str, purpose: str) -> bool:
        """Create a new project."""
        if name in self._projects:
            print(f"[ProjectMemory] Project '{name}' already exists.")
            return False

        now = datetime.datetime.now().isoformat()
        self._projects[name] = Project(
            name=name,
            purpose=purpose,
            created_at=now,
            updated_at=now
        )
        self._save_projects()
        print(f"[ProjectMemory] Created project: {name}")
        return True

    def get_project(self, name: str) -> Optional[Project]:
        """Get a project by name."""
        return self._projects.get(name)

    def list_projects(self, status: Optional[str] = None) -> List[Project]:
        """List all projects, optionally filtered by status."""
        projects = list(self._projects.values())
        if status:
            projects = [p for p in projects if p.status == status]
        return projects

    def update_project(self, name: str, **kwargs) -> bool:
        """Update project fields."""
        if name not in self._projects:
            return False

        project = self._projects[name]
        for key, value in kwargs.items():
            if hasattr(project, key):
                if isinstance(value, list) and key in ["objectives", "files", "decisions", "tasks", "issues", "milestones", "next_actions", "notes"]:
                    getattr(project, key).extend(value)
                else:
                    setattr(project, key, value)

        project.updated_at = datetime.datetime.now().isoformat()
        self._save_projects()
        return True

    def add_note(self, name: str, note: str) -> bool:
        """Add a note to a project."""
        if name not in self._projects:
            return False

        self._projects[name].notes.append(note)
        self._projects[name].updated_at = datetime.datetime.now().isoformat()
        self._save_projects()
        return True

    def close_project(self, name: str) -> bool:
        """Mark a project as completed."""
        if name not in self._projects:
            return False

        self._projects[name].status = "completed"
        self._projects[name].updated_at = datetime.datetime.now().isoformat()
        self._save_projects()
        return True

    def delete_project(self, name: str) -> bool:
        """Delete a project."""
        if name not in self._projects:
            return False

        del self._projects[name]
        self._save_projects()
        return True

    def format_project(self, name: str) -> Optional[str]:
        """Format project details for display."""
        project = self.get_project(name)
        if not project:
            return None

        lines = [
            f"Project: {project.name}",
            f"Status: {project.status}",
            f"Purpose: {project.purpose}",
            f"Created: {project.created_at[:10]}",
            f"Updated: {project.updated_at[:10]}",
        ]

        if project.objectives:
            lines.append(f"\nObjectives:")
            for obj in project.objectives:
                lines.append(f"  • {obj}")

        if project.files:
            lines.append(f"\nFiles:")
            for f in project.files:
                lines.append(f"  • {f}")

        if project.decisions:
            lines.append(f"\nDecisions:")
            for d in project.decisions:
                lines.append(f"  • {d}")

        if project.tasks:
            lines.append(f"\nTasks:")
            for t in project.tasks:
                lines.append(f"  • {t}")

        if project.issues:
            lines.append(f"\nIssues:")
            for i in project.issues:
                lines.append(f"  • {i}")

        if project.next_actions:
            lines.append(f"\nNext Actions:")
            for a in project.next_actions:
                lines.append(f"  • {a}")

        if project.notes:
            lines.append(f"\nNotes:")
            for n in project.notes[-5:]:  # Last 5 notes
                lines.append(f"  • {n}")

        return "\n".join(lines)


# Singleton instance
_project_memory_instance: Optional[ProjectMemory] = None


def get_project_memory() -> ProjectMemory:
    """Get the singleton project memory instance."""
    global _project_memory_instance
    if _project_memory_instance is None:
        _project_memory_instance = ProjectMemory()
    return _project_memory_instance
