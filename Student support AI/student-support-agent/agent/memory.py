"""Long-term memory with privacy filters.
Rules enforced in CODE:
  1. Sensitive data (OTP, passwords, PIN/CVV, card, Aadhaar, PAN) is redacted from the user's message BEFORE it
     reaches the LLM, logs or memory.
  2. Only whitelisted categories of durable facts can be stored.
  3. Temporary statements ("today", "tomorrow", "right now") are rejected."""
import re
from datetime import datetime

import config
from agent import db
from agent.textsearch import BM25

ALLOWED_CATEGORIES = {"programme", "specialization", "preference", "interest", "goal", "language", "contact_preference"}

_SENSITIVE = [
    ("OTP", r"\b(?:otp|one[- ]time[- ](?:password|code|pin)|verification code|security code)\b\s*(?:is|was|:|=|-)?\s*\d{4,8}\b"),
    ("OTP", r"\b\d{4,8}\b\s*(?:is|was)?\s*(?:my|the)\s*(?:otp|one[- ]time[- ](?:password|code|pin)|verification code)\b"),
    ("PASSWORD", r"\b(?:password|passcode|passwd|pwd)\b\s*(?:is|was|:|=|-)\s*\S+"),
    ("PIN/CVV", r"\b(?:pin|cvv|cvc)\b\s*(?:is|was|:|=|-)?\s*\d{3,6}\b"),
    ("CARD", r"\b(?:\d[ -]?){13,16}\b"),
    ("AADHAAR", r"\b\d{4}\s\d{4}\s\d{4}\b|\baadhaa?r\b\D{0,15}\d{12}\b"),
    ("PAN", r"\b[A-Z]{5}\d{4}[A-Z]\b"),
]
_SENSITIVE = [(label, re.compile(p, re.I if label != "PAN" else 0)) for label, p in _SENSITIVE]

_TEMPORARY = re.compile(r"\b(today|tomorrow|tonight|yesterday|right now|this (?:week|morning|evening|afternoon)|"
                        r"currently|at the moment|just now|for now)\b", re.I)


def redact(text: str):
    """Returns (clean_text, [labels]). Replaces sensitive spans with [REDACTED:LABEL]."""
    labels = []
    for label, pat in _SENSITIVE:
        def _sub(_m, label=label):
            labels.append(label)
            return f"[REDACTED:{label}]"
        text = pat.sub(_sub, text)
    return text, sorted(set(labels))


def validate_memory(key: str, value: str, category: str):
    """Returns (ok, reason)."""
    if category not in ALLOWED_CATEGORIES:
        return False, f"category '{category}' is not allowed for long-term memory (allowed: {sorted(ALLOWED_CATEGORIES)})"
    blob = f"{key} {value}"
    if redact(blob)[1]:
        return False, "contains sensitive data (OTP/password/card/ID number) - never stored"
    if _TEMPORARY.search(blob):
        return False, "temporary information is not stored in long-term memory"
    if len(value) > 160 or len(key) > 40:
        return False, "memory item too long - store short durable facts only"
    return True, "ok"


def save_memory(student_id, key, value, category):
    ok, reason = validate_memory(key, value, category)
    if not ok:
        return {"saved": False, "reason": reason}
    key = re.sub(r"[^a-z0-9_]+", "_", key.lower()).strip("_")
    with db.conn() as c:
        c.execute("INSERT INTO memory(student_id,key,value,category,created_at) VALUES(?,?,?,?,?) "
                  "ON CONFLICT(student_id,key) DO UPDATE SET value=excluded.value, category=excluded.category, created_at=excluded.created_at",
                  (student_id, key, value, category, datetime.now().isoformat(timespec="seconds")))
    return {"saved": True, "key": key, "value": value}


def all_memories(student_id):
    return db.query("SELECT key,value,category,created_at FROM memory WHERE student_id=? ORDER BY id", (student_id,))


def forget_all(student_id):
    db.execute("DELETE FROM memory WHERE student_id=?", (student_id,))


def select_relevant(student_id, question, k=None):
    """Context selection: inject only the memories that match the question (top-k), not all of them."""
    k = k or config.TOP_K_MEMORIES
    mems = all_memories(student_id)
    if not mems:
        return []
    bm = BM25([f"{m['key'].replace('_', ' ')} {m['category'].replace('_', ' ')} {m['value']}" for m in mems])
    ranked = sorted(zip(bm.scores(question), mems), key=lambda x: x[0][0], reverse=True)
    return [m for (s, matched), m in ranked if s > 0 and matched >= 1][:k]
