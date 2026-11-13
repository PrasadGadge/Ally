"""Text normalization utilities."""

import re

from vivie_core.config import AUTOCORRECT_MAP, WAKE_VARIANTS

# Longest first — avoids stripping "hey " before "hey vivie"
STRIP_WAKE_PREFIXES = sorted(
    [
        "hey vivie", "ok vivie", "yo vivie",
        "vivie", "vivi", "vivian", "ivy",
        "bibi", "biwi", "hey ", "ok ", "yo ",
    ],
    key=len,
    reverse=True,
)


def strip_wake_prefix(text: str) -> str:
    """Remove leading wake phrase (STT + pipeline). Preserves 'vivie' in the middle."""
    t = text.strip()
    tl = t.lower()
    for prefix in STRIP_WAKE_PREFIXES:
        if tl.startswith(prefix):
            t = t[len(prefix):].strip()
            tl = t.lower()
    if not t:
        return ""
    return t[0].upper() + t[1:] if len(t) > 1 else t.upper()


def normalize_input(text: str) -> str:
    text = text.strip().lower()
    return re.sub(r"\s+", " ", text)


def autocorrect_input(text: str) -> str:
    for wrong, correct in AUTOCORRECT_MAP.items():
        if wrong in text:
            text = text.replace(wrong, correct)
    return text


def fix_wake_word(text: str) -> str:
    """Normalize misheard wake variants using word boundaries (won't break 'vivie')."""
    text = text.lower()
    for variant in sorted(WAKE_VARIANTS, key=len, reverse=True):
        if variant in ("vivie",):
            continue
        text = re.sub(r"\b" + re.escape(variant) + r"\b", "vivie", text)
    return text


def remove_emojis_for_speech(text: str) -> str:
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002700-\U000027BF"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text)


def extract_city(text: str, keyword: str) -> str | None:
    if keyword in text:
        after = text.split(keyword, 1)[1].strip()
        if after.startswith("in "):
            return after[3:].strip()
    return None


def extract_number(text: str) -> int | None:
    match = re.search(r"\d+", text)
    if not match:
        return None
    n = int(match.group()) - 1
    return n if n >= 0 else None


def is_personal_statement(text: str) -> bool:
    text = text.lower().strip()
    question_words = [
        "what", "where", "when", "why", "how", "who", "which",
        "do", "does", "did", "can", "could",
    ]
    if any(text.startswith(q) for q in question_words):
        return False
    indicators = [
        "remember that", "remember", "i am", "i'm", "i live in",
        "my name is", "my favourite is", "my favorite is",
        "i like", "i love", "i work at", "i study at", "i prefer",
    ]
    return any(word in text for word in indicators)


def pad_time_text(text: str) -> str:
    from vivie_core.config import HOUR_NUMBERS, SPLIT_HOUR_NUMBERS

    text = text.replace(" p.m.", "PM").replace(" a.m.", "AM")
    if not any(n in text for n in SPLIT_HOUR_NUMBERS):
        for num in HOUR_NUMBERS:
            if num in text:
                text = text.replace(num, f"0{num}")
    return text
