from profile_keywords import TITLE_KEYWORDS, STACK_KEYWORDS, ANTI_KEYWORDS, REMOTE_HINTS


def score_posting(title: str, description: str, location: str) -> dict:
    text = f"{title}\n{description}".lower()
    loc = (location or "").lower()

    title_hits = sum(1 for kw in TITLE_KEYWORDS if kw in text)
    stack_hits = [kw for kw in STACK_KEYWORDS if kw in text]
    anti_hits = sum(1 for kw in ANTI_KEYWORDS if kw in text)
    remote_ok = any(hint in loc for hint in REMOTE_HINTS)

    score = title_hits * 3 + len(stack_hits) * 2 + (5 if remote_ok else 0) - anti_hits * 10

    return {
        "score": score,
        "stack_matches": stack_hits,
        "remote_ok": remote_ok,
    }
