"""
rag_retrieve.py — Vivie's Smart Knowledge Retrieval
Now powered by ChromaDB semantic search.
"""

from knowledge_core.chroma_manager import get_chroma_manager
import logging

logger = logging.getLogger("RAGRetrieve")


def retrieve_knowledge(query: str, top_k: int = 3, threshold: float = 0.55) -> str:
    """
    Retrieve relevant knowledge for a query.
    Returns formatted string ready to inject into LLM prompt.

    FIX: threshold was 0.4 and formula was 1-(dist/2).
    ChromaDB cosine distance is in [0,1] so correct formula is 1-dist.
    Old formula made minimum similarity 0.5, so threshold=0.4 NEVER filtered
    anything — every result always passed regardless of relevance.
    Raised threshold to 0.55 so only genuinely relevant chunks are injected.
    """
    try:
        chroma = get_chroma_manager()
        results = chroma.retrieve(query, top_k=top_k, threshold=threshold)

        if not results:
            return ""

        # Format for LLM prompt injection
        formatted = "\n".join([f"- {r}" for r in results])
        return f"[Relevant Knowledge]\n{formatted}"

    except Exception as e:
        logger.error(f"[RAGRetrieve] Failed: {e}")
        return ""


def retrieve_knowledge_detailed(query: str, top_k: int = 3) -> list:
    """
    Returns detailed results with similarity scores.
    Useful for debugging or advanced use.
    """
    try:
        chroma = get_chroma_manager()
        return chroma.retrieve_with_metadata(query, top_k=top_k)
    except Exception as e:
        logger.error(f"[RAGRetrieve Detailed] Failed: {e}")
        return []