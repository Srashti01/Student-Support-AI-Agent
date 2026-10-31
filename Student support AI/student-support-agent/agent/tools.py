"""The agent's tools. Authorization / approval / audit are enforced HERE, in plain Python.
Every tool returns (result_dict, decision, target_student_id)."""
import json
import time
from dataclasses import dataclass

import config
from agent import approvals, audit, auth, datastore, db, memory, retrieval
from agent.tracing import Trace


@dataclass
class ToolContext:
    user: auth.User
    trace: Trace
    security: bool = True          # True = Assignment 2 controls (authz + approval + audit); False = Assignment 1 baseline


# ---------------------------------------------------------------- schemas shown to the LLM
SID = {"type": "string", "description": "Student ID the question is about (e.g. S1002). Omit for the signed-in student's own record."}
TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "get_student_profile", "description": "Get a student's profile (name, programme, batch, email, phone).",
        "parameters": {"type": "object", "properties": {"student_id": SID}}}},
    {"type": "function", "function": {"name": "get_fee_status", "description": "Get a student's fee status: total, paid, due amount, due date, status.",
        "parameters": {"type": "object", "properties": {"student_id": SID}}}},
    {"type": "function", "function": {"name": "get_scholarship_status", "description": "Get a student's scholarship scheme, amount, status and remarks.",
        "parameters": {"type": "object", "properties": {"student_id": SID}}}},
    {"type": "function", "function": {"name": "search_policy", "description": "Search the student handbook for rules/processes (fees, late fee, portal failure, scholarships, course change, attendance, refunds, record changes). Returns only the relevant policy sections.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Short keyword query"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "create_support_request", "description": "Create a support ticket for the signed-in student when they ask for help/escalation or the policy cannot answer.",
        "parameters": {"type": "object", "properties": {"category": {"type": "string", "enum": ["fee", "scholarship", "academic", "technical", "other"]},
                                                          "summary": {"type": "string"}}, "required": ["category", "summary"]}}},
    {"type": "function", "function": {"name": "request_record_change", "description": "Request a change to a student's record (email, phone or programme). Sensitive: it needs staff approval and is NOT applied immediately.",
        "parameters": {"type": "object", "properties": {"field": {"type": "string", "enum": ["email", "phone", "programme"]},
                                                          "new_value": {"type": "string"}, "reason": {"type": "string"}, "student_id": SID},
                       "required": ["field", "new_value"]}}},
    {"type": "function", "function": {"name": "save_memory", "description": "Save ONE short durable fact the student stated about themselves (specialization, interest, goal, preferred contact channel, language). NEVER for OTPs, passwords, card numbers or temporary things.",
        "parameters": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"},
                                                          "category": {"type": "string", "enum": sorted(memory.ALLOWED_CATEGORIES)}},
                       "required": ["key", "value", "category"]}}},
]


# ---------------------------------------------------------------- helpers
def _target(args, ctx):
    return str(args.get("student_id") or ctx.user.user_id).strip().upper()


def _check(ctx, target):
    if not ctx.security:
        return True, "security controls disabled (Assignment 1 baseline)"
    return auth.can_access_student(ctx.user, target)


def _denied(reason):
    return {"error": "ACCESS_DENIED", "message": reason}


# ---------------------------------------------------------------- tools
def t_get_student_profile(args, ctx):
    tid = _target(args, ctx)
    ok, why = _check(ctx, tid)
    if not ok:
        return _denied(why), "DENIED", tid
    rec = datastore.get_student(tid)
    if not rec:
        return {"error": "NOT_FOUND", "message": f"no student {tid}"}, "ERROR", tid
    return {k: rec[k] for k in ("student_id", "name", "programme", "batch", "email", "phone")}, "ALLOWED", tid


def t_get_fee_status(args, ctx):
    tid = _target(args, ctx)
    ok, why = _check(ctx, tid)
    if not ok:
        return _denied(why), "DENIED", tid
    rec = datastore.get_fee(tid)
    return (rec, "ALLOWED", tid) if rec else ({"error": "NOT_FOUND", "message": f"no fee record for {tid}"}, "ERROR", tid)


def t_get_scholarship_status(args, ctx):
    tid = _target(args, ctx)
    ok, why = _check(ctx, tid)
    if not ok:
        return _denied(why), "DENIED", tid
    rec = datastore.get_scholarship(tid)
    return (rec, "ALLOWED", tid) if rec else ({"error": "NOT_FOUND", "message": f"no scholarship record for {tid}"}, "ERROR", tid)


def t_search_policy(args, ctx):
    q = str(args.get("query", "")).strip()
    if not q:
        return {"error": "INVALID_REQUEST", "message": "query is empty"}, "ERROR", None
    hits = retrieval.search(q)
    ctx.trace.d["retrieved_chunks"] += [{"id": h["id"], "title": h["title"], "score": h["score"]} for h in hits]
    if not hits:
        return {"results": [], "message": "No relevant policy found in the handbook for this query."}, "ALLOWED", None
    return {"results": [{"id": h["id"], "title": h["title"], "text": h["text"]} for h in hits]}, "ALLOWED", None


def t_create_support_request(args, ctx):
    cat, summ = str(args.get("category", "other")), str(args.get("summary", "")).strip()
    if not summ:
        return {"error": "INVALID_REQUEST", "message": "summary is empty"}, "ERROR", ctx.user.user_id
    summ, labels = memory.redact(summ)       # never store credentials inside tickets either
    tid = db.execute("INSERT INTO tickets(student_id,category,summary,status,created_at) VALUES(?,?,?,?,datetime('now'))",
                     (ctx.user.user_id, cat, summ, "OPEN"))
    return {"ticket_id": f"SR-{tid:04d}", "status": "OPEN", "category": cat}, "ALLOWED", ctx.user.user_id


def t_request_record_change(args, ctx):
    tid = _target(args, ctx)
    ok, why = _check(ctx, tid)
    if not ok:
        return _denied(why), "DENIED", tid
    field_, raw = str(args.get("field", "")).lower(), str(args.get("new_value", ""))
    if field_ not in approvals.SENSITIVE_FIELDS:
        return {"error": "INVALID_REQUEST", "message": f"field must be one of {sorted(approvals.SENSITIVE_FIELDS)}"}, "ERROR", tid
    valid, val = approvals.normalize_value(field_, raw)
    if not valid:
        return {"error": "INVALID_REQUEST", "message": val}, "ERROR", tid
    if not datastore.get_student(tid):
        return {"error": "NOT_FOUND", "message": f"no student {tid}"}, "ERROR", tid
    reason = str(args.get("reason", ""))[:200]
    if ctx.security:
        aid = approvals.create_request(tid, field_, val, reason, ctx.trace.trace_id)
        return {"status": "PENDING_APPROVAL", "approval_id": aid, "field": field_, "new_value": val,
                "message": "Change NOT applied yet. It needs approval from a registrar office staff member."}, "PENDING_APPROVAL", tid
    datastore.update_student_field(tid, field_, val)     # baseline (Assignment 1): executes immediately
    return {"status": "APPLIED", "field": field_, "new_value": val}, "ALLOWED", tid


def t_save_memory(args, ctx):
    res = memory.save_memory(ctx.user.user_id, str(args.get("key", "")), str(args.get("value", "")), str(args.get("category", "")))
    return res, ("ALLOWED" if res["saved"] else "REJECTED"), ctx.user.user_id


REGISTRY = {"get_student_profile": t_get_student_profile, "get_fee_status": t_get_fee_status,
            "get_scholarship_status": t_get_scholarship_status, "search_policy": t_search_policy,
            "create_support_request": t_create_support_request, "request_record_change": t_request_record_change,
            "save_memory": t_save_memory}


def run_tool(name, args, ctx: ToolContext) -> dict:
    t0 = time.perf_counter()
    fn = REGISTRY.get(name)
    if fn is None:
        result, decision, target = {"error": "UNKNOWN_TOOL", "message": f"no tool named {name}"}, "ERROR", None
    else:
        try:
            result, decision, target = fn(args, ctx)
        except Exception as e:                               # tool errors are handled, never crash the agent
            result, decision, target = {"error": "TOOL_ERROR", "message": str(e)}, "ERROR", None
    latency = time.perf_counter() - t0
    summary = json.dumps(result, default=str)
    if ctx.security and name != "search_policy":             # public policy lookups are not audited; everything else is
        audit.log(ctx.user.user_id, ctx.user.role, name, target, args, decision, summary, ctx.trace.trace_id)
    ctx.trace.tool_step(name, args, decision, latency, summary)
    return result
