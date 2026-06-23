"""
Groq integration: generates a short, human-readable track record summary
for a circle creator/admin reviewing a join request.

No raw PII (phone, NIN, BVN) is ever sent to the model — only aggregate
stats that are already visible elsewhere in the app (trust score, circle
history, contribution reliability).
"""

import os
from typing import Optional

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

try:
    from groq import Groq
    _client: Optional["Groq"] = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
except ImportError:
    _client = None


def _fallback_summary(stats: dict) -> str:
    """Deterministic template used if Groq is unavailable, has no API key,
    or errors out mid-demo — keeps the Join Requests screen demo-safe
    even with no network."""
    name = stats.get("name", "This user")
    circles = stats.get("circles_completed", 0)
    on_time_rate = stats.get("on_time_rate", 100)
    missed = stats.get("missed_payments", 0)

    if circles == 0:
        return (
            f"{name} is new to àjó with no completed circles yet. "
            "Consider starting them with a smaller contribution amount."
        )

    reliability = "an excellent" if on_time_rate >= 90 else "a solid" if on_time_rate >= 70 else "a mixed"
    missed_clause = (
        f" They have {missed} missed payment(s) on record."
        if missed
        else " They have no missed payments on record."
    )
    return (
        f"{name} has completed {circles} circle(s) with {reliability} on-time contribution "
        f"rate of {on_time_rate}%.{missed_clause}"
    )


def generate_join_summary(stats: dict) -> str:
    """
    stats: {
        "name": str, "trust_score": int, "circles_completed": int,
        "on_time_rate": float, "late_payments": int, "missed_payments": int,
        "total_saved": float,
    }
    """
    if not _client:
        return _fallback_summary(stats)

    prompt = (
        "You are helping a savings-circle (ajo) admin decide whether to approve a join request. "
        "Given this member's track record, write 2-4 plain, friendly sentences summarizing their "
        "reliability for the admin. Do not mention their phone number, ID numbers, or any data not "
        f"given below.\n\nTrack record: {stats}"
    )

    try:
        response = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.4,
        )
        text = response.choices[0].message.content.strip()
        return text or _fallback_summary(stats)
    except Exception:
        return _fallback_summary(stats)
