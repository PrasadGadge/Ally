"""
Tests for web search with citations.
"""

import pytest
from Features.web_search import (
    format_search_with_citations,
    create_citation_marker,
    get_source_by_index,
)


class TestCitationFormatting:
    """Test citation formatting."""
    
    def test_format_search_with_citations(self):
        """Test formatting search results with citations."""
        results = [
            {
                "title": "Test 1",
                "url": "https://example.com/1",
                "content": "Content 1",
                "source": "Source 1",
                "published_date": "2024-01-15",
            },
            {
                "title": "Test 2",
                "url": "https://example.com/2",
                "content": "Content 2",
                "source": "Source 2",
                "published_date": "",
            },
        ]
        
        formatted = format_search_with_citations(results, "Test summary")
        
        assert "Test summary" in formatted
        assert "Sources:" in formatted
        assert "1. Test 1 (2024-01-15)" in formatted
        assert "https://example.com/1" in formatted
        assert "2. Test 2" in formatted
        assert "https://example.com/2" in formatted
    
    def test_format_search_with_citations_no_summary(self):
        """Test formatting without summary."""
        results = [
            {
                "title": "Test",
                "url": "https://example.com",
                "content": "Content",
                "source": "Source",
                "published_date": "",
            },
        ]
        
        formatted = format_search_with_citations(results)
        
        assert "Sources:" in formatted
        assert "1. Test" in formatted
    
    def test_format_search_with_citations_empty(self):
        """Test formatting with empty results."""
        formatted = format_search_with_citations([])
        
        assert formatted == "No search results found."
    
    def test_create_citation_marker(self):
        """Test citation marker creation."""
        assert create_citation_marker(1) == "[1]"
        assert create_citation_marker(5) == "[5]"
        assert create_citation_marker(10) == "[10]"
    
    def test_get_source_by_index(self):
        """Test retrieving source by index."""
        results = [
            {"title": "Source 1", "url": "url1"},
            {"title": "Source 2", "url": "url2"},
            {"title": "Source 3", "url": "url3"},
        ]
        
        source = get_source_by_index(results, 1)
        assert source["title"] == "Source 1"
        
        source = get_source_by_index(results, 3)
        assert source["title"] == "Source 3"
        
        source = get_source_by_index(results, 0)
        assert source is None
        
        source = get_source_by_index(results, 4)
        assert source is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
