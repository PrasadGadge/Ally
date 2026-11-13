# ==================================================
# Tools/mcp_tools.py — MCP-connected ToolManifests
#
# Auto-discovered by discover_tools() at startup.
# No edits needed to registry.py, engines.py, or
# main_brain.py — just this file + the feature modules.
#
# Services connected:
#   • Gmail     (Google OAuth — run setup_mcp.py once)
#   • Calendar  (Google OAuth — same setup)
#   • GitHub    (GITHUB_TOKEN in .env — instant)
# ==================================================

from Core_structure.tool_manifest import ToolManifest


# ─────────────────────────────────────────────────
# GMAIL
# ─────────────────────────────────────────────────

class GmailTool(ToolManifest):
    name        = "gmail"
    description = "Read, search, and send Gmail emails"
    keywords    = [
        "check email", "check my email", "check my emails",
        "my emails", "unread emails", "new emails", "inbox",
        "any emails", "do i have email", "gmail",
        "read email", "email from", "search email",
        "send email", "send an email",
    ]
    action_type     = "gmail"
    category        = "communication"
    requires_online = True
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The natural language email request (e.g., 'check unread emails', 'send email to john')"}
        },
        "required": ["query"]
    }

    @staticmethod
    def handler(details: str, **kwargs) -> str:
        from Features.gmail_tool import handle_gmail_request
        return handle_gmail_request(details)


# ─────────────────────────────────────────────────
# GOOGLE CALENDAR
# ─────────────────────────────────────────────────

class CalendarTool(ToolManifest):
    name        = "calendar"
    description = "Check and manage Google Calendar events"
    keywords    = [
        "my schedule", "what's my schedule", "calendar",
        "what do i have today", "today's events", "any meetings today",
        "tomorrow schedule", "tomorrow events", "what's tomorrow",
        "this week schedule", "weekly schedule", "upcoming events",
        "add event", "create event", "schedule meeting",
        "do i have anything", "am i free",
    ]
    action_type     = "calendar"
    category        = "productivity"
    requires_online = True
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The natural language calendar request (e.g., 'what is my schedule today', 'create meeting at 3pm')"}
        },
        "required": ["query"]
    }

    @staticmethod
    def handler(details: str, **kwargs) -> str:
        from Features.calendar_tool import handle_calendar_request
        return handle_calendar_request(details)


# ─────────────────────────────────────────────────
# GITHUB
# ─────────────────────────────────────────────────

class GitHubTool(ToolManifest):
    name        = "github"
    description = "Access GitHub repos, issues, and activity"
    keywords    = [
        "github", "my repos", "my repositories", "github issues",
        "open issues", "create issue", "new issue",
        "github activity", "recent commits", "what's happening on github",
        "check my github", "pull request", "my projects",
    ]
    action_type     = "github"
    category        = "development"
    requires_online = True
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The natural language GitHub request (e.g., 'check my open issues', 'recent commits')"}
        },
        "required": ["query"]
    }

    @staticmethod
    def handler(details: str, **kwargs) -> str:
        from Features.github_tool import handle_github_request
        return handle_github_request(details)