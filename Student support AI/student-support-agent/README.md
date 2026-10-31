# 🎓 Intelligent & Safe Student Support Agent
**Agentic AI Engineering – Assignment 1 (agent, tools, memory, retrieval, tracing) + Assignment 2 (privacy, approval, audit)**
One project, one Streamlit app. A toggle in the sidebar switches the Assignment-2 controls OFF so you can measure *Assignment 1 vs Assignment 2* on the same test set.

---
## 1. What it does
A chat agent (Groq LLM + tool calling) for students: fee status, scholarships, policy questions, support tickets and record-change requests.

| Requirement | Where it lives |
|---|---|
| Agent loop (decide → tool → read result → answer) | `agent/agent.py` |
| ≥ 2 tools (7 implemented) | `agent/tools.py` |
| Persistent memory + never store sensitive/temporary data | `agent/memory.py` (SQLite) |
| Retrieval from ONE handbook, only relevant chunks | `agent/retrieval.py`, `agent/textsearch.py` (BM25), `data/student_handbook.md` |
| Context selection (question + needed info only) | `agent/agent.py` (last 6 msgs, top-3 memories, top-3 chunks via tool) |
| Missing info / tool errors / unanswerable | tools return structured errors; prompt + `search_policy` returns "no relevant policy" |
| Tracing: tools, latency, tokens, evidence | `agent/tracing.py`, 🔎 Trace expander in chat |
| Student identity | `agent/auth.py` (PBKDF2 password hashes, login form) |
| Privacy / authorization **in code** | `agent/auth.py` + checks inside every tool in `agent/tools.py` |
| Human approval for sensitive actions | `agent/approvals.py` + ✅ Approvals tab (staff) |
| Audit records | `agent/audit.py` (SQLite, hash-chained) |
| Evaluation + downloadable reports | `eval/runner.py`, `eval/report.py`, 🧪 Evaluation tab |
| Offline unit tests (no API key) | `tests/` |

### Things that make it more than the minimum
1. **Tamper-evident audit log** – every record contains `hash(prev_hash + record)`. The UI has a *Verify chain* button and a *Simulate tampering* demo.
2. **A1 vs A2 comparison in one click** – same tests run with controls OFF (baseline) and ON (secure); table shows accuracy, privacy-block rate, approval-gate rate, latency overhead and token overhead.
3. **Sensitive data is redacted *before* the LLM** – OTP / password / PIN / CVV / card / Aadhaar / PAN never reach the model, traces, audit log or memory.
4. **Maker-checker** – only staff can approve; a requester can never approve their own request; reject = nothing executes.
5. **Deterministic scoring** – no "LLM judge"; checks look at tools called, authorization decisions, DB/Excel state and answer keywords.
6. **Latency split** – LLM time vs tool time per test; downloadable **CSV latency report** and **Excel evaluation workbook** (Summary, A1_vs_A2, Test_Results, Latency_Report, Tool_Trace, Audit_Records).

---
## 2. Architecture
```
 Streamlit UI (app.py)
 ├─ Chat tab ─────────────┐         ┌── Approvals tab (staff) ──► approvals.decide()  ─► Excel updated ONLY here
 ├─ Evaluation tab ───────┤         │
 └─ Traces & Audit tab    ▼         │
                  StudentSupportAgent  (agent/agent.py)
        redact() ──► select memories ──► build context ──► Groq LLM ◄──┐
                                                            │ tool calls │ tool results
                                                            ▼            │
                                                     run_tool()  ────────┘
        ┌───────────────────────────┬───────────────────────────┬──────────────────┐
        │ auth.can_access_student() │ approvals.create_request() │ audit.log()      │  ← enforced in Python
        └───────────────────────────┴───────────────────────────┴──────────────────┘
   Data: data/university_data.xlsx (Students, Fees, Scholarships, Staff) · data/student_handbook.md
   State: runtime/agent.db (memory, audit_log, approvals, tickets, traces)
```
**Per-question flow:** redact sensitive text → pick relevant memories → send *system prompt + memories + last 6 messages + question* → model may call tools (max 5 steps) → every tool call is authorized, executed, audited and traced → final answer + trace.

### Tools
| Tool | Purpose | Control |
|---|---|---|
| `get_student_profile`, `get_fee_status`, `get_scholarship_status` | read private records | own record only |
| `search_policy` | BM25 retrieval of top handbook chunks | public |
| `create_support_request` | creates ticket `SR-000x` | audited |
| `request_record_change` | email / phone / programme | **needs staff approval** |
| `save_memory` | durable facts only | whitelist + sensitive/temporary filters |

### Privacy & approval rules
* A student may read/modify **only their own** record. The LLM may *ask* for `S1002`'s data, but `auth.can_access_student()` denies it in code → `DENIED` + audit row.
* Staff can't browse student records through the agent (least privilege); they only decide approvals.
* `request_record_change` never edits data: it creates a `PENDING` approval. Only `approvals.decide()` (staff) writes to Excel.
* Passwords/OTP/CVV/card/Aadhaar/PAN → redacted, never stored. Memory accepts only categories `programme, specialization, preference, interest, goal, language, contact_preference`, rejects "today/tomorrow/right now…" facts.

---
## 3. Project structure
```
student-support-agent/
├── app.py                      # Streamlit UI (chat, approvals, evaluation, audit)
├── config.py                   # paths, model list, limits, sandbox helper
├── requirements.txt  .env.example  .gitignore  README.md
├── data/
│   ├── university_data.xlsx    # sample data (generated)
│   └── student_handbook.md     # the ONE policy document
├── agent/
│   ├── agent.py  llm.py  tools.py  memory.py  retrieval.py  textsearch.py
│   ├── auth.py  approvals.py  audit.py  tracing.py  datastore.py  db.py
├── eval/
│   ├── test_questions.json     # 20 tests (core = 10 quick ones)
│   ├── runner.py  report.py
├── scripts/make_data.py        # regenerates the Excel file
└── tests/                      # offline pytest suite (no API key needed)
```

---
## 4. Run it in VS Code (Windows / macOS / Linux)
1. Install **Python 3.10+** and **VS Code** (+ the *Python* extension).
2. `File ▸ Open Folder…` → `student-support-agent`.
3. Open the terminal: `` Ctrl+` ``.
4. Create & activate a virtual environment
   * Windows PowerShell: `python -m venv .venv` then `.venv\Scripts\Activate.ps1`
     (if blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`)
   * macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate`
   * VS Code: `Ctrl+Shift+P ▸ Python: Select Interpreter ▸ .venv`
5. `pip install -r requirements.txt`
6. Get a free key at <https://console.groq.com/keys>, then copy `.env.example` → `.env` and paste it:
   `GROQ_API_KEY=gsk_...` (the `.env` file is git-ignored – never commit it).
7. *(optional)* `python scripts/make_data.py` regenerates the Excel file.
8. `pytest -q` → 12 offline tests should pass (proves auth, approval, audit, redaction work without any API).
9. `streamlit run app.py` → opens <http://localhost:8501>.

**Demo logins:** students `S1001…S1005` / `Pass@1001…Pass@1005` · staff approver `STF001` / `Staff@123` (fake demo accounts).

> Close `runtime/live_data.xlsx` in Excel while the app runs (Excel locks the file and approved changes can't be written).
> Groq free tier has token-per-minute limits: use *Quick* test set or raise the pause slider; the client auto-retries on 429.

---
## 5. Demo script for the video (≈ 8–10 min)
1. **Architecture** – walk through the diagram above and the folder structure (1 min).
2. **A1 scenarios** (S1001): *What is my current fee status?* → open 🔎 Trace (tool, latency, tokens). *The payment portal failed. Can I pay on the next working day?* → show retrieved chunk `POL-FEE-03` (only 1 chunk). *What are the hostel fees…?* → "I don't have that information".
3. **Memory** – say *"I'm specializing in Finance Analytics and I prefer email"* → 🧠 memory panel → *New session* → *Which specialization did I tell you about?* → memory used shown in trace. Then *"My OTP is 482913"* → warning chip, memory unchanged.
4. **A2 controls** – *Show fee of S1002* → ⛔ DENIED; open Traces & Audit → record. *Change my phone to 9876543210* → ⏳ pending → sign in as `STF001` → Reject (nothing changes) → repeat → Approve (Excel value changes).
5. **Audit** – *Verify chain* ✔ → *Simulate tampering* → *Verify* ✖ → *Undo*.
6. **Evaluation** – run Quick set in both modes → show A1 vs A2 table, latency chart, download the CSV and Excel reports; open the Excel.
7. **Code walk-through** (2 min): `agent.py` loop, `tools.py` `_check()`/`run_tool()`, `approvals.decide()`, `audit.py` hash chain, `memory.redact()`.

---
## 6. Sample evaluation (fill from your own run)
After running the Evaluation tab, paste the **A1 vs A2** table here (Download ▸ Excel ▸ sheet `A1_vs_A2`). Expected pattern: normal-task accuracy similar in both modes; privacy and unsafe-action tests fail in the baseline and pass in the secure mode; secure mode adds only a few ms of tool/audit time (the LLM dominates latency).

## 7. Notes on safety of the repo
No credentials are committed. `.env`, `runtime/` (live DB + Excel copy) are git-ignored. Passwords in the Excel file are PBKDF2 hashes of fake demo passwords.
