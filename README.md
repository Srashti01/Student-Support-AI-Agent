# Student Support AI Agent

A Streamlit-based student support application powered by a Groq language model. Students can ask questions about their university profile, fee and scholarship status, search the student handbook, create support requests, and request changes to selected personal records.

The project combines an agent-and-tools workflow with retrieval, persistent memory, request tracing, access control, staff approval, and audit logging.

## Features

- **Conversational AI agent:** uses a Groq chat model and a bounded tool-calling loop to answer student questions and perform supported actions.
- **Student data tools:** retrieves a student's profile, fee status, and scholarship status from the university workbook.
- **Policy retrieval:** searches the student handbook using BM25-based text ranking and returns relevant policy sections.
- **Support requests:** creates support tickets from the chat interface.
- **Persistent memory:** stores selected useful facts in SQLite, with category allowlisting and checks against sensitive or temporary information.
- **Request tracing:** records model/tool activity, retrieved evidence, latency, token counts when available, and errors.
- **Authentication and authorization:** verifies demo users and enforces student-level access to private records in application code.
- **Approval workflow:** sends selected record changes to a staff approval queue. The data is updated only after an authorized staff decision.
- **Audit log:** stores application events in SQLite and links audit entries with hashes so the chain can be checked for tampering.
- **Evaluation:** runs predefined scenarios and produces evaluation summaries and downloadable reports.

## Technology

- Python
- Streamlit
- Groq API
- SQLite
- pandas and openpyxl
- BM25-style text retrieval
- pytest

## Project structure

```text
student-support-agent/
├── app.py
├── config.py
├── requirements.txt
├── .env.example
├── README.md
├── data/
│   ├── university_data.xlsx
│   └── student_handbook.md
├── agent/
│   ├── __init__.py
│   ├── agent.py
│   ├── approvals.py
│   ├── audit.py
│   ├── auth.py
│   ├── datastore.py
│   ├── db.py
│   ├── llm.py
│   ├── memory.py
│   ├── retrieval.py
│   ├── textsearch.py
│   ├── tools.py
│   └── tracing.py
├── eval/
│   ├── __init__.py
│   ├── runner.py
│   ├── report.py
│   └── test_questions.json
├── scripts/
│   └── make_data.py
├── tests/
│   ├── fake_llm.py
│   ├── test_app_smoke.py
│   ├── test_eval_offline.py
│   └── test_security.py
└── runtime/
    └── .gitkeep
```

### Main modules

| File or folder | Responsibility |
|---|---|
| `app.py` | Streamlit interface, login, chat, memory, reports, traces, audit, and staff approvals. |
| `config.py` | Environment loading, file paths, model settings, agent limits, and runtime data/sandbox helpers. |
| `agent/agent.py` | Main agent loop: builds context, calls the model, executes requested tools, and returns the response. |
| `agent/llm.py` | Groq model client and tool-calling integration. |
| `agent/tools.py` | Tool definitions and the central tool execution path. |
| `agent/auth.py` | User authentication and access-control checks. |
| `agent/approvals.py` | Pending record-change requests and staff approval/rejection. |
| `agent/audit.py` | Audit event storage and hash-chain verification. |
| `agent/memory.py` | Memory filtering, sensitive-data checks, storage, and retrieval. |
| `agent/retrieval.py`, `agent/textsearch.py` | Handbook chunking and relevance ranking. |
| `agent/datastore.py` | Reads and updates the university Excel workbook. |
| `agent/db.py` | SQLite database helpers and table access. |
| `agent/tracing.py` | Captures per-request agent and tool execution details. |
| `eval/` | Evaluation scenarios, runner, scoring, and report generation. |
| `tests/` | Automated smoke, evaluation, and security tests. |
| `scripts/make_data.py` | Regenerates the sample university workbook. |

## Requirements

- Python 3.10 or newer
- A Groq API key for live AI chat and live model-based evaluation
- Internet access when calling the Groq API

## Setup and run

Open a terminal in the `student-support-agent` directory.

### 1. Create a virtual environment

**Windows PowerShell**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure the Groq API key

Copy `.env.example` to `.env` and add your API key:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile
```

The application reads these settings through `config.py`. Do not commit your `.env` file or share your API key.

### 4. Start the application

```bash
streamlit run app.py
```

Streamlit will print the local URL in the terminal (normally `http://localhost:8501`). Open that address in your browser.

## Demo accounts

The project includes sample accounts for local demonstration:

| Account | User ID | Password |
|---|---|---|
| Student | `S1001` | `Pass@1001` |
| Student | `S1002` | `Pass@1002` |
| Staff approver | `STF001` | `Staff@123` |

These are demonstration credentials only. Do not use them for a real deployment.

## Data and runtime files

- `data/university_data.xlsx` is the sample source workbook. It contains the demonstration university records.
- `data/student_handbook.md` is the policy source used for handbook retrieval.
- `runtime/live_data.xlsx` is the working workbook used by the running application. The source workbook is copied there when the working copy does not yet exist.
- `runtime/agent.db` is the SQLite database used for memory, approvals, support tickets, traces, and audit records.

The runtime files are local application state. Use the application's reset option when you need to restore the sample data for a fresh demonstration. Close the live Excel workbook in spreadsheet software before running an action that needs to update it, because another program may lock the file.

## How the application works

1. A user signs in through the Streamlit interface.
2. The user submits a question in the chat.
3. The agent prepares the prompt using the current question, a limited recent chat history, and relevant saved memories.
4. The Groq model may request one or more registered tools.
5. The application executes each tool in Python, where access checks and workflow rules are applied.
6. Policy searches retrieve relevant handbook sections; data tools read the workbook; support and change tools create the corresponding records.
7. The tool results are returned to the model so it can prepare a response.
8. Request traces and applicable audit events are stored in SQLite.

The agent loop is limited by `MAX_AGENT_STEPS` in `config.py`. Context, memory, and retrieval limits are also configured there.

## Privacy and approval behaviour

- Student access to private student records is checked in application code; a student should only be able to access their own record.
- Staff accounts are used for the approval workflow rather than unrestricted student-record browsing through the agent.
- Selected record changes are submitted as pending requests. They are not applied to the workbook until a staff member approves them.
- Memory storage uses an allowlist of supported information categories and filters sensitive or temporary information.
- Sensitive strings such as passwords, OTPs, PINs, CVVs, card details, Aadhaar, and PAN patterns are handled by the redaction/filtering logic in the agent code.
- Audit records are hash-linked and can be checked using the application's audit verification feature.

This is an educational demonstration project, not a production-ready university information system. Review the code, data handling, identity management, deployment configuration, and institutional security requirements before using it with real student information.

## Run automated tests

From the project directory, run:

```bash
pytest -q
```

The test suite includes offline tests that use a fake language-model implementation, so the relevant tests do not require a live Groq API call. Live chat and model-backed evaluation require a valid API key and network access.

## Evaluation

The application includes predefined scenarios in `eval/test_questions.json`. Use the Reports & Evaluation section in the Streamlit interface to run the available evaluation scenarios and inspect the results. The evaluation code is in `eval/runner.py`, with report-generation helpers in `eval/report.py`.

## Troubleshooting

- **The app does not start:** confirm that the virtual environment is active and that `pip install -r requirements.txt` completed successfully.
- **The model does not respond:** check that `GROQ_API_KEY` is set correctly in `.env` or in the application's supported key input.
- **The Excel workbook cannot be updated:** close `runtime/live_data.xlsx` in Excel or another spreadsheet application, then retry.
- **You want to restore the sample state:** use the reset option in the application before starting a new demonstration.

## License

No license is specified in the project files. Add a license before distributing or reusing the project if one is required.
