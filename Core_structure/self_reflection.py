# ==================================================
# Core_structure/self_reflection.py
# Fixed: was a near-useless stub — only prepended
# one hardcoded phrase. Now does real signal-based
# response improvement before sending to TTS/UI.
# ==================================================


class SelfReflection:

    def evaluate(self, question: str, answer: str) -> str:
        """
        Review the answer before it reaches the user.
        Catches low-quality signals and patches them.
        Returns improved answer — or original if clean.
        """
        if not answer or len(answer) < 10:
            return answer

        q = question.lower().strip()
        a = answer.lower()

        # ── 1. Deflect uncertainty honestly ──────────
        uncertainty_phrases = [
            "i don't know", "i do not know",
            "i'm not sure", "i am not sure",
            "i have no idea", "i cannot answer",
            "i can't answer"
        ]
        if any(p in a for p in uncertainty_phrases):
            return (
                "I don't have confident information on that right now. "
                "Here's what I can offer: " + answer
            )

        # ── 2. Catch overly short answers for non-trivial questions ──
        is_trivial = len(q.split()) <= 4
        if not is_trivial and len(answer.split()) < 15:
            return answer + " Let me know if you'd like me to expand on this."

        # ── 3. Strip filler openers that leaked past the LLM ─────────
        filler_openers = [
            "certainly!", "of course!", "absolutely!",
            "great question!", "sure thing!",
            "certainly, boss.", "of course, boss.",
        ]
        stripped = answer
        for filler in filler_openers:
            if stripped.lower().startswith(filler.lower()):
                stripped = stripped[len(filler):].lstrip(" ,\n")
                break

        # ── 4. Repetition check — answer just echoing the question? ──
        q_words = set(q.split())
        a_words = set(stripped.lower().split())
        overlap = len(q_words & a_words)
        if len(q_words) > 3 and overlap / max(len(q_words), 1) > 0.85:
            return "I need more context to give a proper answer on that. Could you rephrase?"

        return stripped