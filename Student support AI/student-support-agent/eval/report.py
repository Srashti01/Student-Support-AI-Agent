"""Turns evaluation results into tables + a downloadable Excel / CSV latency report."""
import io
import json

import pandas as pd

from eval.runner import CATEGORY_LABEL

FLAT = ["id", "category", "student", "mode", "passed", "tool_choice_ok", "tools_called", "decisions", "retrieved_chunks",
        "memory_used", "turns", "total_latency_s", "llm_latency_s", "tool_latency_s", "llm_calls", "prompt_tokens",
        "completion_tokens", "total_tokens", "failure_reasons", "question", "answer", "error"]


def results_df(results):
    return pd.DataFrame([{k: r.get(k) for k in FLAT} for r in results], columns=FLAT) if results else pd.DataFrame(columns=FLAT)


def latency_df(results):
    cols = ["id", "category", "mode", "turns", "total_latency_s", "llm_latency_s", "tool_latency_s", "llm_calls",
            "prompt_tokens", "completion_tokens", "total_tokens"]
    return results_df(results)[cols]


def _pct(s):
    return round(100 * s.mean(), 1) if len(s) else None


def summary_df(results):
    df = results_df(results)
    if df.empty:
        return pd.DataFrame()
    rows = []
    for cat, g in [("ALL TESTS", df)] + [(CATEGORY_LABEL.get(c, c), x) for c, x in df.groupby("category", sort=False)]:
        rows.append({"group": cat, "tests": len(g), "passed": int(g["passed"].sum()), "success_%": _pct(g["passed"]),
                     "tool_choice_ok_%": _pct(g["tool_choice_ok"]), "avg_latency_s": round(g["total_latency_s"].mean(), 2),
                     "p95_latency_s": round(g["total_latency_s"].quantile(0.95), 2),
                     "avg_prompt_tokens": round(g["prompt_tokens"].mean()), "avg_completion_tokens": round(g["completion_tokens"].mean()),
                     "total_tokens": int(g["total_tokens"].sum())})
    return pd.DataFrame(rows)


def comparison_df(baseline, secure):
    """Assignment 1 (controls OFF) vs Assignment 2 (controls ON)."""
    def stats(res):
        df = results_df(res)
        if df.empty: return {}
        func = df[df["category"].isin(["normal", "memory", "unanswerable"])]
        priv, unsafe = df[df["category"] == "privacy"], df[df["category"] == "unsafe_action"]
        return {"Functional task accuracy (normal + memory + missing-info) %": _pct(func["passed"]),
                "Privacy tests passed (other student's data blocked) %": _pct(priv["passed"]),
                "Unsafe-action tests passed (waited for approval) %": _pct(unsafe["passed"]),
                "Avg latency per test (s)": round(df["total_latency_s"].mean(), 2),
                "p95 latency per test (s)": round(df["total_latency_s"].quantile(0.95), 2),
                "Avg input tokens per test": round(df["prompt_tokens"].mean()),
                "Avg output tokens per test": round(df["completion_tokens"].mean()),
                "Avg LLM calls per test": round(df["llm_calls"].mean(), 2)}
    a, b = stats(baseline), stats(secure)
    rows = [{"Measure": k, "Assignment 1 (controls OFF)": a.get(k), "Assignment 2 (controls ON)": b.get(k)}
            for k in (b or a)]
    return pd.DataFrame(rows)


def tool_calls_df(results):
    rows = []
    for r in results:
        for t in r["traces"]:
            for s in t["steps"]:
                if s["type"] == "tool":
                    rows.append({"test": r["id"], "mode": r["mode"], "trace_id": t["trace_id"], "tool": s["name"],
                                 "args": json.dumps(s["args"]), "decision": s["decision"], "latency_s": s["latency_s"],
                                 "result": s["result"]})
    return pd.DataFrame(rows)


def audit_df(results):
    rows = [{"test": r["id"], **a} for r in results for a in reversed(r["audit"])]
    return pd.DataFrame(rows)


def build_excel(results_by_mode: dict) -> bytes:
    buf = io.BytesIO()
    allres = [r for rs in results_by_mode.values() for r in rs]
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        if "baseline" in results_by_mode and "secure" in results_by_mode:
            comparison_df(results_by_mode["baseline"], results_by_mode["secure"]).to_excel(xw, sheet_name="A1_vs_A2", index=False)
        for mode, rs in results_by_mode.items():
            summary_df(rs).to_excel(xw, sheet_name=f"Summary_{mode}"[:31], index=False)
        results_df(allres).to_excel(xw, sheet_name="Test_Results", index=False)
        latency_df(allres).to_excel(xw, sheet_name="Latency_Report", index=False)
        tool_calls_df(allres).to_excel(xw, sheet_name="Tool_Trace", index=False)
        audit_df(allres).to_excel(xw, sheet_name="Audit_Records", index=False)
        for ws in xw.book.worksheets:
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(60, max(10, max(len(str(c.value or "")) for c in col[:60]) + 2))
    return buf.getvalue()
