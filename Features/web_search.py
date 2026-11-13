# ==========================================
# WEB SEARCH MODULE (STABLE VERSION)
# Enhanced with source citations
# ==========================================

import requests
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    load_dotenv = None

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


def search_web(query: str) -> list:
    """
    Search the web and return results with source citations.
    
    Returns a list of source records with:
    - title: Source title
    - url: Source URL
    - content: Excerpt/snippet
    - source: Source name
    - published_date: Publication date if available
    """
    url = "https://api.tavily.com/search"

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "include_answer": False,
        "include_raw_content": False,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()

        results = data.get("results", [])

        structured_results = []

        for r in results[:5]:
            structured_results.append({
                "title": r.get("title", "No Title"),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "source": r.get("source", "Unknown Source"),
                "published_date": r.get("published_date", ""),  # May be empty
                "score": r.get("score", 0.0),  # Relevance score from Tavily
            })

        return structured_results

    except Exception as e:
        print("[Web Search Error]", e)
        return []


def format_search_with_citations(results: list, summary: str = "") -> str:
    """
    Format search results with numbered citations.
    
    Args:
        results: List of search result dicts from search_web()
        summary: Optional summary text to prepend
    
    Returns:
        Formatted string with inline citations and reference list
    """
    if not results:
        return summary or "No search results found."
    
    lines = []
    
    if summary:
        lines.append(summary)
        lines.append("")
    
    # Add source list
    lines.append("Sources:")
    for i, result in enumerate(results, 1):
        title = result.get("title", "Unknown")
        url = result.get("url", "")
        published = result.get("published_date", "")
        
        line = f"{i}. {title}"
        if published:
            line += f" ({published})"
        line += f"\n   {url}"
        lines.append(line)
    
    return "\n".join(lines)


def create_citation_marker(index: int) -> str:
    """Create a citation marker for inline references."""
    return f"[{index}]"


def get_source_by_index(results: list, index: int) -> dict | None:
    """Get a source by its 1-based index."""
    if 1 <= index <= len(results):
        return results[index - 1]
    return None
