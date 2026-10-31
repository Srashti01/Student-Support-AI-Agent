"""Run inside the student-support-agent folder:  python apply_model_fix.py
Groq shut down llama-3.3-70b-versatile / llama-3.1-8b-instant on 16 Aug 2026. This switches the project to openai/gpt-oss-120b."""
from pathlib import Path

def sub(path, pairs):
    p = Path(path)
    if not p.exists():
        print("skip (not found):", path); return
    s = p.read_text(encoding="utf-8")
    for a, b in pairs:
        s = s.replace(a, b)
    p.write_text(s, encoding="utf-8"); print("patched:", path)

sub("config.py", [
    ('DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")', 'DEFAULT_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")'),
    ('MODEL_CHOICES = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]', 'MODEL_CHOICES = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b"]'),
])
sub("agent/llm.py", [
    ('kwargs = dict(model=self.model, messages=messages, temperature=0, max_tokens=700)\n',
     'kwargs = dict(model=self.model, messages=messages, temperature=0, max_tokens=2000)\n'
     '                if "gpt-oss" in self.model:   # reasoning models: keep thinking short\n'
     '                    kwargs["extra_body"] = {"reasoning_effort": "low"}\n'),
])
sub(".env.example", [("llama-3.3-70b-versatile", "openai/gpt-oss-120b")])
sub(".env", [("llama-3.3-70b-versatile", "openai/gpt-oss-120b"), ("llama-3.1-8b-instant", "openai/gpt-oss-20b")])
sub("README.md", [("llama-3.1-8b-instant", "openai/gpt-oss-20b"), ("llama-3.3-70b-versatile", "openai/gpt-oss-120b")])
print("Done. Restart the app: streamlit run app.py")
