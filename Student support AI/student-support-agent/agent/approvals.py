"""Human-in-the-loop approval for sensitive record changes (maker-checker).
The agent can only CREATE a pending request. The change is executed ONLY inside decide(), by a staff user."""
import re
from datetime import datetime

from agent import audit, auth, datastore, db

SENSITIVE_FIELDS = {"email", "phone", "programme"}
PROGRAMMES = {"bda": "PGDM (Big Data Analytics)", "aids": "PGDM (AI & Data Science)"}


def normalize_value(field, value):
    """Returns (ok, normalized_value_or_error)."""
    v = (value or "").strip()
    if field == "email":
        return (True, v.lower()) if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v) else (False, "invalid email address")
    if field == "phone":
        digits = re.sub(r"\D", "", v)[-10:]
        return (True, digits) if len(digits) == 10 else (False, "phone number must have 10 digits")
    if field == "programme":
        low = v.lower()
        if "big data" in low or "bda" in low:
            return True, PROGRAMMES["bda"]
        if "ai" in low or "artificial" in low or "data science" in low:
            return True, PROGRAMMES["aids"]
        return False, "unknown programme (use Big Data Analytics or AI & Data Science)"
    return False, f"field '{field}' cannot be changed through the assistant"


def create_request(student_id, field, new_value, reason, trace_id=None):
    old = (datastore.get_student(student_id) or {}).get(field)
    return db.execute(
        "INSERT INTO approvals(student_id,field,old_value,new_value,reason,status,requested_at,trace_id) "
        "VALUES(?,?,?,?,?,'PENDING',?,?)",
        (student_id, field, old, new_value, reason, datetime.now().isoformat(timespec="seconds"), trace_id))


def list_requests(status=None, student_id=None):
    sql, params = "SELECT * FROM approvals WHERE 1=1", []
    if status:
        sql += " AND status=?"; params.append(status)
    if student_id:
        sql += " AND student_id=?"; params.append(student_id)
    return db.query(sql + " ORDER BY id DESC", params)


def decide(approval_id, approver, approve: bool, note=""):
    """Staff decision. Returns dict(ok, status, message). Everything is written to the audit log."""
    rows = db.query("SELECT * FROM approvals WHERE id=?", (approval_id,))
    if not rows:
        return {"ok": False, "status": "NOT_FOUND", "message": "approval request not found"}
    req = rows[0]
    allowed, why = auth.can_decide_approval(approver, req["student_id"])
    details = {"approval_id": approval_id, "field": req["field"], "new_value": req["new_value"]}
    if not allowed:
        audit.log(approver.user_id, approver.role, "approval_decision", req["student_id"], details,
                  "DENIED", why, req["trace_id"])
        return {"ok": False, "status": "DENIED", "message": why}
    if req["status"] != "PENDING":
        return {"ok": False, "status": req["status"], "message": f"already {req['status']}"}
    now = datetime.now().isoformat(timespec="seconds")
    if approve:
        datastore.update_student_field(req["student_id"], req["field"], req["new_value"])
        status, result = "APPROVED", f"{req['field']} changed to '{req['new_value']}' (EXECUTED)"
    else:
        status, result = "REJECTED", "request rejected - change NOT executed"
    db.execute("UPDATE approvals SET status=?, decided_by=?, decided_at=?, decision_note=? WHERE id=?",
               (status, approver.user_id, now, note, approval_id))
    audit.log(approver.user_id, approver.role, "approval_decision", req["student_id"], details,
              status, result, req["trace_id"])
    return {"ok": True, "status": status, "message": result}
