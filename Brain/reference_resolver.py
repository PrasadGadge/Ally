"""
Brain/reference_resolver.py — Follow-up Reference Resolution

Resolves pronouns and references in follow-up questions:
- "it", "that", "those", "this", "they", "them"
- "the previous one", "the last result"
- Context-aware resolution based on recent conversation

Example:
  User: "What's the weather?"
  Vivie: "It's 72°F and sunny."
  User: "How about tomorrow?" → Resolves to "What's the weather tomorrow?"
"""

from __future__ import annotations
import re
from typing import Optional, List, Tuple


class ReferenceResolver:
    """
    Resolves references in follow-up questions to their actual referents.
    Uses recent conversation history to determine what pronouns refer to.
    """

    # Common reference patterns
    _REFERENCE_PATTERNS = [
        (r"\bit\b", "it"),
        (r"\bthat\b", "that"),
        (r"\bthis\b", "this"),
        (r"\bthose\b", "those"),
        (r"\bthey\b", "they"),
        (r"\bthem\b", "them"),
        (r"\bthe previous one\b", "the previous one"),
        (r"\bthe last one\b", "the last one"),
        (r"\bthe first one\b", "the first one"),
    ]

    # Topic extractors - extract nouns/topics from sentences
    _TOPIC_PATTERN = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b')

    def __init__(self, history_limit: int = 5):
        self.history_limit = history_limit
        self._conversation_history: List[Tuple[str, str]] = []  # (user, assistant)

    def add_turn(self, user_input: str, assistant_response: str):
        """Add a conversation turn to history."""
        self._conversation_history.append((user_input, assistant_response))
        # Keep only recent history
        if len(self._conversation_history) > self.history_limit:
            self._conversation_history = self._conversation_history[-self.history_limit:]

    def resolve(self, current_input: str) -> str:
        """
        Resolve references in current_input based on conversation history.
        Returns the resolved input string.
        """
        if not self._conversation_history:
            return current_input

        resolved = current_input
        has_reference = False

        # Check for reference patterns
        for pattern, ref_type in self._REFERENCE_PATTERNS:
            if re.search(pattern, current_input, re.IGNORECASE):
                has_reference = True
                break

        if not has_reference:
            return current_input

        # Get most recent relevant context
        last_user, last_assistant = self._conversation_history[-1]

        # Extract topics from previous turn
        topics = self._extract_topics(last_user, last_assistant)

        if not topics:
            return current_input

        # Simple resolution: replace "it/that" with the primary topic
        primary_topic = topics[0]

        # Build resolved version
        resolved = self._replace_references(current_input, primary_topic, topics)

        return resolved

    def _extract_topics(self, user_input: str, assistant_response: str) -> List[str]:
        """Extract potential topic nouns from conversation turn."""
        combined = f"{user_input} {assistant_response}"
        # Find capitalized words (likely proper nouns/topics)
        matches = self._TOPIC_PATTERN.findall(combined)
        # Filter out common words
        common_words = {"What", "How", "Why", "When", "Where", "Who", "It", "This", "That", "Boss", "Vivie"}
        topics = [m for m in matches if m not in common_words]
        return topics[:3]  # Return top 3 topics

    def _replace_references(self, text: str, primary_topic: str, all_topics: List[str]) -> str:
        """Replace reference words with actual topics."""
        resolved = text

        # Simple heuristics for replacement
        lower_text = text.lower()

        # "it", "that", "this" → primary topic
        if any(word in lower_text for word in ["it", "that", "this"]):
            resolved = re.sub(r'\b(it|that|this)\b', primary_topic, text, flags=re.IGNORECASE)

        # "they", "them", "those" → use all topics joined
        if any(word in lower_text for word in ["they", "them", "those"]):
            if len(all_topics) > 1:
                topics_str = " and ".join(all_topics)
                resolved = re.sub(r'\b(they|them|those)\b', topics_str, text, flags=re.IGNORECASE)
            else:
                resolved = re.sub(r'\b(they|them|those)\b', primary_topic, text, flags=re.IGNORECASE)

        return resolved

    def clear_history(self):
        """Clear conversation history."""
        self._conversation_history.clear()


# Singleton instance
_resolver_instance: Optional[ReferenceResolver] = None


def get_reference_resolver() -> ReferenceResolver:
    """Get the singleton reference resolver instance."""
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = ReferenceResolver()
    return _resolver_instance
