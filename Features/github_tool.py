# ==================================================
# Features/github_tool.py — GitHub via REST API
# Requires: GITHUB_TOKEN in .env (no OAuth needed)
# Get token: github.com/settings/tokens → new classic token
# Scopes needed: repo, issues, read:user
# ==================================================

from __future__ import annotations
import os
from mcp_bridge import github_get, github_post, is_github_authorized

_GH_BASE = "https://api.github.com"


# ─────────────────────────────────────────────────
# GITHUB OPERATIONS
# ─────────────────────────────────────────────────

def get_my_repos(max_results: int = 8) -> list[dict]:
    data = github_get(f"{_GH_BASE}/user/repos",
                      {"sort": "updated", "per_page": max_results, "type": "owner"})
    return [{"name": r["name"], "description": r.get("description", ""),
             "language": r.get("language", ""), "stars": r["stargazers_count"],
             "updated": r["updated_at"][:10]} for r in data]


def get_open_issues(repo: str = None, max_results: int = 5) -> list[dict]:
    username = os.getenv("GITHUB_USERNAME", "").strip()
    if not username:
        # Fetch from /user endpoint
        user = github_get(f"{_GH_BASE}/user")
        username = user.get("login", "")

    if repo:
        url  = f"{_GH_BASE}/repos/{username}/{repo}/issues"
        data = github_get(url, {"state": "open", "per_page": max_results})
    else:
        data = github_get(f"{_GH_BASE}/issues",
                          {"filter": "created", "state": "open",
                           "per_page": max_results})

    return [{"title": i["title"], "number": i["number"],
             "repo":  i.get("repository", {}).get("name", repo or ""),
             "url":   i["html_url"]} for i in data]


def create_issue(repo: str, title: str, body: str = "") -> str:
    username = os.getenv("GITHUB_USERNAME", "").strip()
    if not username:
        user     = github_get(f"{_GH_BASE}/user")
        username = user.get("login", "")

    github_post(f"{_GH_BASE}/repos/{username}/{repo}/issues",
                {"title": title, "body": body})
    return f"Issue '{title}' created in {repo}."


def get_recent_activity(max_results: int = 5) -> list[dict]:
    username = os.getenv("GITHUB_USERNAME", "").strip()
    if not username:
        user     = github_get(f"{_GH_BASE}/user")
        username = user.get("login", "")

    data = github_get(f"{_GH_BASE}/users/{username}/events/public",
                      {"per_page": max_results})
    events = []
    for e in data[:max_results]:
        t    = e.get("type", "").replace("Event", "")
        repo = e.get("repo", {}).get("name", "")
        events.append({"type": t, "repo": repo, "date": e.get("created_at", "")[:10]})
    return events


# ─────────────────────────────────────────────────
# MAIN HANDLER — called by GitHubTool
# ─────────────────────────────────────────────────

def handle_github_request(details: str) -> str:
    if not is_github_authorized():
        return ("Boss, GitHub is not connected. "
                "Add GITHUB_TOKEN to your .env file. "
                "Get one at: github.com/settings/tokens")

    d = details.lower()

    try:
        # Create issue
        if "create issue" in d or "new issue" in d or "open issue" in d:
            return ("Boss, which repo and what should the issue say? "
                    "Say: create issue in [repo] title [title]")

        # Open issues
        if "issue" in d or "issues" in d:
            issues = get_open_issues()
            if not issues:
                return "Boss, no open issues found."
            lines = [f"{i+1}. [{e['repo']}] #{e['number']} — {e['title']}"
                     for i, e in enumerate(issues)]
            return f"Your open issues:\n" + "\n".join(lines)

        # Recent activity
        if "activity" in d or "recent" in d or "what's happening" in d:
            activity = get_recent_activity()
            if not activity:
                return "No recent GitHub activity found."
            lines = [f"• {e['type']} in {e['repo']} ({e['date']})"
                     for e in activity]
            return "Recent GitHub activity:\n" + "\n".join(lines)

        # Default: list repos
        repos = get_my_repos()
        if not repos:
            return "Boss, no repositories found."
        lines = [f"{i+1}. {r['name']} [{r['language'] or 'No lang'}] ⭐{r['stars']} — {r['description'][:50] or 'no description'}"
                 for i, r in enumerate(repos)]
        return "Your repositories:\n" + "\n".join(lines)

    except PermissionError as e:
        return str(e)
    except Exception as e:
        return f"Boss, GitHub error: {e}"