"""Tamper-evident audit log. Every record stores hash(prev_hash + record), forming a hash chain.
If anyone edits or deletes a past row, verify_chain() detects it."""
import hashlib
import json
from datetime import datetime

from agent import db

GENESIS = "0" * 64


def _hash(prev, fields):
    return hashlib.sha256((prev + json.dumps(fields, sort_keys=True, default=str)).encode()).hexdigest()


def log(actor, role, action, target, details, decision, result, trace_id=None):
    """decision: ALLOWED | DENIED | PENDING_APPROVAL | APPROVED | REJECTED | ERROR"""
    ts = datetime.now().isoformat(timespec="seconds")
    details_s = json.dumps(details or {}, sort_keys=True, default=str)
    with db.conn() as c:
        row = c.execute("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
        prev = row["hash"] if row else GENESIS
        fields = [ts, actor, role, action, target, details_s, decision, str(result)[:500], trace_id]
        h = _hash(prev, fields)
        cur = c.execute(
            "INSERT INTO audit_log(ts,actor,role,action,target,details,decision,result,trace_id,prev_hash,hash)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (ts, actor, role, action, target, details_s, decision, str(result)[:500], trace_id, prev, h))
        return cur.lastrowid


def records(limit=500):
    return db.query("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))


def verify_chain():
    """Returns (ok: bool, message: str)."""
    rows = db.query("SELECT * FROM audit_log ORDER BY id ASC")
    prev = GENESIS
    for r in rows:
        fields = [r["ts"], r["actor"], r["role"], r["action"], r["target"], r["details"],
                  r["decision"], r["result"], r["trace_id"]]
        if r["prev_hash"] != prev or r["hash"] != _hash(prev, fields):
            return False, f"Chain broken at audit record #{r['id']} (record was modified or a previous one deleted)."
        prev = r["hash"]
    return True, f"Audit chain intact - {len(rows)} records verified."
