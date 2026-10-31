"""Per-question trace: every LLM call and tool call with latency, tokens, decision and evidence."""
import json
import time
import uuid
from datetime import datetime

from agent import db


class Trace:
    def __init__(self, student_id, question, mode, model, sensitive_labels=None):
        self.t0 = time.perf_counter()
        self.d = {
            "trace_id": uuid.uuid4().hex[:10], "ts": datetime.now().isoformat(timespec="seconds"),
            "student_id": student_id, "mode": mode, "model": model, "question": question,
            "sensitive_redacted": sensitive_labels or [], "memory_used": [], "retrieved_chunks": [],
            "steps": [], "answer": "", "error": None, "metrics": {}}

    @property
    def trace_id(self):
        return self.d["trace_id"]

    def llm_step(self, latency, prompt_tokens, completion_tokens, tool_calls):
        self.d["steps"].append({"type": "llm", "latency_s": round(latency, 3), "prompt_tokens": prompt_tokens,
                                "completion_tokens": completion_tokens,
                                "requested_tools": [t["name"] for t in tool_calls]})

    def tool_step(self, name, args, decision, latency, summary):
        self.d["steps"].append({"type": "tool", "name": name, "args": args, "decision": decision,
                                "latency_s": round(latency, 4), "result": summary[:300]})

    def finish(self, answer, error=None):
        s = self.d["steps"]
        llm = [x for x in s if x["type"] == "llm"]
        tools = [x for x in s if x["type"] == "tool"]
        pt = sum(x["prompt_tokens"] for x in llm)
        ct = sum(x["completion_tokens"] for x in llm)
        self.d.update(answer=answer, error=error, metrics={
            "total_latency_s": round(time.perf_counter() - self.t0, 3),
            "llm_latency_s": round(sum(x["latency_s"] for x in llm), 3),
            "tool_latency_s": round(sum(x["latency_s"] for x in tools), 4),
            "llm_calls": len(llm), "tool_calls": len(tools),
            "prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct})
        db.execute("INSERT OR REPLACE INTO traces(trace_id,ts,student_id,mode,payload) VALUES(?,?,?,?,?)",
                   (self.trace_id, self.d["ts"], self.d["student_id"], self.d["mode"], json.dumps(self.d)))
        return self.d


def recent_traces(limit=50):
    return [json.loads(r["payload"]) for r in db.query("SELECT payload FROM traces ORDER BY ts DESC LIMIT ?", (limit,))]
