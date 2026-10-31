"""Student Support Agent - Streamlit front-end (Assignment).  Run:  streamlit run app.py"""
import json

import pandas as pd
import streamlit as st

import config
from agent import approvals, audit, auth, db, memory
from agent.agent import StudentSupportAgent
from agent.tracing import recent_traces
from eval import report, runner

st.set_page_config(page_title="Student Support Agent", page_icon="🎓", layout="wide")
config.ensure_live_data()

ss = st.session_state
for k, v in {"user": None, "messages": [], "agent": None, "agent_key": None, "eval": {}, "tamper": None}.items():
    ss.setdefault(k, v)


# ------------------------------------------------------------------ helpers
def api_key():
    return config.GROQ_API_KEY or ss.get("key_input", "")


def get_agent():
    key = (ss.user.user_id, ss.security, ss.model, api_key())
    if ss.agent is None or ss.agent_key != key:
        ss.agent = StudentSupportAgent(ss.user, security=ss.security, model=ss.model, api_key=api_key())
        ss.agent_key = key
    return ss.agent


def render_trace(tr):
    m = tr["metrics"]
    c = st.columns(5)
    c[0].metric("Latency", f"{m['total_latency_s']} s")
    c[1].metric("Input tokens", m["prompt_tokens"])
    c[2].metric("Output tokens", m["completion_tokens"])
    c[3].metric("LLM calls", m["llm_calls"])
    c[4].metric("Tool calls", m["tool_calls"])
    icon = {"ALLOWED": "✅", "DENIED": "⛔", "PENDING_APPROVAL": "⏳", "REJECTED": "🚫", "ERROR": "⚠️"}
    for s in tr["steps"]:
        if s["type"] == "tool":
            st.markdown(f"{icon.get(s['decision'], '•')} **{s['name']}** → `{s['decision']}` ({s['latency_s']}s)")
            st.code(f"args  = {json.dumps(s['args'])}\nresult = {s['result']}", language="text")
        else:
            st.caption(f"🧠 LLM call · {s['latency_s']}s · {s['prompt_tokens']} in / {s['completion_tokens']} out"
                       + (f" · asked for: {', '.join(s['requested_tools'])}" if s["requested_tools"] else " · final answer"))
    if tr["retrieved_chunks"]:
        st.markdown("**Retrieved policy evidence:** " + ", ".join(f"`{c['id']}` ({c['score']})" for c in tr["retrieved_chunks"]))
    if tr["memory_used"]:
        st.markdown("**Memory used:** " + ", ".join(f"`{x['key']}`={x['value']}" for x in tr["memory_used"]))
    if tr["sensitive_redacted"]:
        st.warning(f"Sensitive data removed before reaching the model / logs: {', '.join(tr['sensitive_redacted'])}")
    if tr.get("error"):
        st.error(tr["error"])


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.title("🎓 Student Support Agent")
    st.caption("Agentic AI Engineering · Assignment 1 + 2")
    if not config.GROQ_API_KEY:
        st.text_input("Groq API key (session only)", type="password", key="key_input",
                      help="Or put GROQ_API_KEY in a .env file")
    st.selectbox("Groq model", config.MODEL_CHOICES, key="model")
    st.toggle("Assignment 2 controls ON (privacy · approval · audit)", value=True, key="security",
              help="OFF = Assignment 1 baseline: no authorization, changes execute immediately, no audit log. Used for the A1 vs A2 comparison.")
    st.divider()
    if ss.user is None:
        with st.form("login"):
            st.subheader("Sign in")
            uid = st.text_input("Student / Staff ID", placeholder="S1001")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Sign in"):
                u = auth.authenticate(uid, pw)
                audit.log(uid.strip().upper() or "?", u.role if u else "unknown", "login", uid.strip().upper(), {},
                          "ALLOWED" if u else "DENIED", "signed in" if u else "bad credentials")
                if u:
                    ss.user, ss.messages, ss.agent = u, [], None
                    st.rerun()
                else:
                    st.error("Invalid ID or password")
        with st.expander("Demo accounts"):
            st.markdown("Students `S1001`…`S1005` → password `Pass@1001`…`Pass@1005`\n\nStaff approver `STF001` → `Staff@123`")
    else:
        st.success(f"Signed in as **{ss.user.name}** ({ss.user.user_id}, {ss.user.role})")
        c1, c2 = st.columns(2)
        if c1.button("New session", help="Clears the chat but keeps long-term memory"):
            ss.messages, ss.agent = [], None
            st.rerun()
        if c2.button("Sign out"):
            audit.log(ss.user.user_id, ss.user.role, "logout", ss.user.user_id, {}, "ALLOWED", "signed out")
            ss.user, ss.messages, ss.agent = None, [], None
            st.rerun()
        if ss.user.role == "student":
            with st.expander("🧠 My long-term memory"):
                mems = memory.all_memories(ss.user.user_id)
                st.dataframe(pd.DataFrame(mems), hide_index=True) if mems else st.caption("Nothing stored yet.")
                if mems and st.button("Forget everything"):
                    memory.forget_all(ss.user.user_id)
                    st.rerun()
    st.divider()
    if st.button("♻️ Reset demo data", help="Restores the Excel data and clears memory, audit log, approvals and traces"):
        config.reset_live_data(); ss.user, ss.messages, ss.agent, ss.tamper = None, [], None, None
        st.rerun()

tab_chat, tab_appr, tab_eval, tab_audit = st.tabs(["💬 Chat", "✅ Approvals", "🧪 Evaluation", "🔍 Traces & Audit"])

# ------------------------------------------------------------------ chat
with tab_chat:
    if ss.user is None:
        st.info("Sign in from the sidebar to start. Try student **S1001** / `Pass@1001`.")
    elif ss.user.role != "student":
        st.info("Staff accounts do not use the student chat - open the **Approvals** tab.")
    else:
        mode = "🔒 Secure mode (Assignment 2)" if ss.security else "🔓 Baseline mode (Assignment 1 - no controls)"
        st.caption(f"{mode} · model `{ss.model}`")
        if not ss.messages:
            st.markdown("**Try:** *What is my current fee status?* · *The payment portal failed. Can I pay on the next working day?* · "
                        "*Show me the fee status of S1002* · *Please change my phone number to 9876543210* · "
                        "*My OTP is 482913* · *I'm specializing in Finance Analytics*")
        for m in ss.messages:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
                if m.get("trace"):
                    with st.expander("🔎 Trace"):
                        render_trace(m["trace"])
        if prompt := st.chat_input("Ask about fees, scholarships, course changes, support…"):
            ss.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                if not api_key():
                    st.error("Add your Groq API key in the sidebar (or in .env).")
                else:
                    with st.spinner("Thinking…"):
                        res = get_agent().ask(prompt)
                    st.markdown(res.answer)
                    with st.expander("🔎 Trace", expanded=False):
                        render_trace(res.trace)
                    ss.messages.append({"role": "assistant", "content": res.answer, "trace": res.trace})

# ------------------------------------------------------------------ approvals
with tab_appr:
    st.subheader("Sensitive change requests (human approval)")
    if ss.user is None:
        st.info("Sign in first. Staff (`STF001`) can approve/reject; students see the status of their own requests.")
    elif ss.user.role == "staff":
        pending = approvals.list_requests("PENDING")
        st.write(f"**{len(pending)} pending request(s)**")
        for r in pending:
            with st.container(border=True):
                st.markdown(f"**#{r['id']}** · student `{r['student_id']}` wants to change **{r['field']}**: "
                            f"`{r['old_value']}` → `{r['new_value']}`  \nReason: {r['reason'] or '-'} · requested {r['requested_at']}")
                note = st.text_input("Note (optional)", key=f"note{r['id']}")
                a, b, _ = st.columns([1, 1, 4])
                if a.button("✅ Approve", key=f"ap{r['id']}"):
                    st.toast(approvals.decide(r["id"], ss.user, True, note)["message"]); st.rerun()
                if b.button("🚫 Reject", key=f"rj{r['id']}"):
                    st.toast(approvals.decide(r["id"], ss.user, False, note)["message"]); st.rerun()
        st.markdown("**History**")
        hist = approvals.list_requests()
        st.dataframe(pd.DataFrame(hist).drop(columns=["trace_id"], errors="ignore"), hide_index=True) if hist else st.caption("No requests yet.")
    else:
        mine = approvals.list_requests(student_id=ss.user.user_id)
        st.dataframe(pd.DataFrame(mine).drop(columns=["trace_id"], errors="ignore"), hide_index=True) if mine else st.caption("You have no change requests.")
        st.caption("Only a registrar office staff member can approve a change. Log in as STF001 to try it.")

# ------------------------------------------------------------------ evaluation
with tab_eval:
    st.subheader("Evaluation: accuracy · tools · latency · tokens · evidence")
    st.caption("Each test runs in a fresh sandbox (clean Excel copy + empty DB) through the real agent and Groq API. "
               "Scoring is deterministic (tools called, decisions, answer keywords, DB state) - no LLM judge.")
    tests_all = runner.load_tests()
    c1, c2, c3 = st.columns([2, 2, 2])
    preset = c1.radio("Test set", ["Quick (core scenarios)", "Full suite", "Custom"], horizontal=True)
    modes = c2.multiselect("Modes", ["Assignment 1 baseline (controls OFF)", "Assignment 2 secure (controls ON)"],
                           default=["Assignment 1 baseline (controls OFF)", "Assignment 2 secure (controls ON)"])
    delay = c3.slider("Pause between tests (s) - avoids Groq rate limits", 0.0, 10.0, 2.0, 0.5)
    if preset == "Quick (core scenarios)":
        chosen = runner.load_tests(core_only=True)
    elif preset == "Full suite":
        chosen = tests_all
    else:
        ids = st.multiselect("Tests", [t["id"] for t in tests_all], default=[t["id"] for t in tests_all][:5])
        chosen = [t for t in tests_all if t["id"] in ids]
    with st.expander(f"Selected tests ({len(chosen)})"):
        st.dataframe(pd.DataFrame([{"id": t["id"], "category": t["category"], "student": t["student"], "question": " → ".join(t["turns"])} for t in chosen]), hide_index=True)

    if st.button("▶ Run evaluation", type="primary", disabled=not (chosen and modes)):
        if not api_key():
            st.error("Add your Groq API key first.")
        else:
            ss.eval = {}
            bar, label = st.progress(0.0), st.empty()
            for mi, mname in enumerate(modes):
                secure = "ON" in mname
                def cb(i, n, tid, md, mi=mi):
                    bar.progress(min(1.0, (mi + i / n) / len(modes)))
                    label.write(f"Running **{md or 'finished'}** · test `{tid}` ({i}/{n})")
                ss.eval["secure" if secure else "baseline"] = runner.run_suite(chosen, secure, ss.model, api_key(), delay, cb)
            bar.progress(1.0); label.success("Evaluation finished")

    if ss.eval:
        base, sec = ss.eval.get("baseline"), ss.eval.get("secure")
        if base and sec:
            st.markdown("### Assignment 1 vs Assignment 2")
            st.dataframe(report.comparison_df(base, sec), hide_index=True)
        for mode, res in ss.eval.items():
            st.markdown(f"### Summary - {'Assignment 2 (secure)' if mode == 'secure' else 'Assignment 1 (baseline)'}")
            st.dataframe(report.summary_df(res), hide_index=True)
        allres = [r for rs in ss.eval.values() for r in rs]
        st.markdown("### Per-test results")
        df = report.results_df(allres)
        st.dataframe(df.drop(columns=["answer", "question"]), hide_index=True)
        st.markdown("### Latency per test (seconds, LLM vs tools)")
        lat = report.latency_df(allres)
        lat["label"] = lat["id"] + " (" + lat["mode"] + ")"
        st.bar_chart(lat.set_index("label")[["llm_latency_s", "tool_latency_s"]])
        st.markdown("### Download reports")
        d1, d2, d3 = st.columns(3)
        d1.download_button("⬇ Latency report (CSV)", lat.drop(columns="label").to_csv(index=False).encode(), "latency_report.csv", "text/csv")
        d2.download_button("⬇ Full evaluation report (Excel)", report.build_excel(ss.eval), "evaluation_report.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
        d3.download_button("⬇ Raw traces + audit (JSON)", json.dumps([{k: r[k] for k in ("id", "mode", "traces", "audit")} for r in allres], indent=2, default=str).encode(),
                           "traces_and_audit.json", "application/json")
        st.markdown("### Inspect a test")
        pick = st.selectbox("Test", [f"{r['id']} · {r['mode']}" for r in allres])
        r = next(x for x in allres if f"{x['id']} · {x['mode']}" == pick)
        st.markdown(f"**Question:** {r['question']}  \n**Result:** {'✅ PASS' if r['passed'] else '❌ FAIL'} {r['failure_reasons']}")
        st.markdown(f"**Answer:** {r['answer']}")
        for t in r["traces"]:
            render_trace(t)
        if r["audit"]:
            st.markdown("**Audit records created by this test**")
            st.dataframe(pd.DataFrame(r["audit"]).drop(columns=["prev_hash", "hash"]), hide_index=True)

# ------------------------------------------------------------------ traces & audit
with tab_audit:
    st.subheader("Audit log (tamper-evident hash chain)")
    st.caption("Every tool call, denial, approval decision and login is recorded: who · what · allowed/approved? · result.")
    a, b, c, d = st.columns(4)
    if a.button("🔐 Verify audit chain"):
        ok, msg = audit.verify_chain()
        (st.success if ok else st.error)(msg)
    if b.button("🧨 Simulate tampering (demo)"):
        rows = audit.records(1)
        if rows:
            ss.tamper = (rows[0]["id"], rows[0]["decision"])
            db.execute("UPDATE audit_log SET decision='ALLOWED' WHERE id=?", (rows[0]["id"],))
            st.warning("Last audit row was edited behind the application's back - now click Verify.")
    if c.button("↩ Undo tampering") and ss.tamper:
        db.execute("UPDATE audit_log SET decision=? WHERE id=?", (ss.tamper[1], ss.tamper[0])); ss.tamper = None
        st.info("Restored.")
    rec = audit.records()
    adf = pd.DataFrame(rec)
    if not adf.empty:
        d.download_button("⬇ Audit log (CSV)", adf.to_csv(index=False).encode(), "audit_log.csv", "text/csv")
        st.dataframe(adf.drop(columns=["prev_hash"]), hide_index=True)
    else:
        st.caption("No audit records yet.")
    st.subheader("Recent chat traces")
    trs = recent_traces(30)
    if trs:
        st.dataframe(pd.DataFrame([{"trace_id": t["trace_id"], "time": t["ts"], "student": t["student_id"], "mode": t["mode"],
                                    "question": t["question"][:70], "tools": ", ".join(s["name"] for s in t["steps"] if s["type"] == "tool"),
                                    "latency_s": t["metrics"]["total_latency_s"], "in_tok": t["metrics"]["prompt_tokens"],
                                    "out_tok": t["metrics"]["completion_tokens"]} for t in trs]), hide_index=True)
        st.download_button("⬇ Traces (JSON)", json.dumps(trs, indent=2).encode(), "traces.json", "application/json")
    else:
        st.caption("Chat with the agent to see traces here.")
