"""Central configuration. All paths are read at call time (config.DB_FILE etc.)
so the evaluation harness can swap in a throw-away sandbox."""
import os
import shutil
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
RUNTIME_DIR = BASE_DIR / "runtime"
RUNTIME_DIR.mkdir(exist_ok=True)

SOURCE_DATA_FILE = DATA_DIR / "university_data.xlsx"   # pristine seed data (never modified)
HANDBOOK_FILE = DATA_DIR / "student_handbook.md"

# Live (what the Streamlit chat uses)
DATA_FILE = RUNTIME_DIR / "live_data.xlsx"
DB_FILE = RUNTIME_DIR / "agent.db"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
MODEL_CHOICES = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b"]

MAX_AGENT_STEPS = 5      # hard stop for the agent loop
HISTORY_WINDOW = 6       # only the last N chat messages are sent to the model
TOP_K_CHUNKS = 3         # policy chunks returned per search
TOP_K_MEMORIES = 3       # remembered facts injected per question


def ensure_live_data():
    """Create the working copy of the Excel file the first time the app runs."""
    if not DATA_FILE.exists():
        shutil.copy(SOURCE_DATA_FILE, DATA_FILE)


def reset_live_data():
    """Restore the seed data + wipe the database (handy before recording the video)."""
    shutil.copy(SOURCE_DATA_FILE, DATA_FILE)
    if DB_FILE.exists():
        DB_FILE.unlink()


def fresh_sandbox(tag="eval"):
    """Point config at a clean copy of the data + empty DB (used per evaluation test)."""
    global DATA_FILE, DB_FILE
    DATA_FILE = RUNTIME_DIR / f"{tag}_data.xlsx"
    DB_FILE = RUNTIME_DIR / f"{tag}.db"
    shutil.copy(SOURCE_DATA_FILE, DATA_FILE)
    if DB_FILE.exists():
        DB_FILE.unlink()


@contextmanager
def sandbox(tag="eval"):
    """Temporarily run against a sandbox; the live data/DB are restored afterwards."""
    global DATA_FILE, DB_FILE
    old = (DATA_FILE, DB_FILE)
    try:
        fresh_sandbox(tag)
        yield
    finally:
        DATA_FILE, DB_FILE = old
