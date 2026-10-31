"""Boots the Streamlit app headlessly (offline FakeLLM): login -> chat -> cross-student request is denied."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))

import agent.agent as ag
import config
from fake_llm import FakeLLM
from streamlit.testing.v1 import AppTest


def test_login_chat_and_denial(monkeypatch):
    monkeypatch.setattr(ag, "GroqLLM", lambda **kw: FakeLLM())
    config.reset_live_data()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=40).run()
    assert not at.exception and len(at.tabs) == 4
    ti = {t.label: t for t in at.text_input}
    ti["Student / Staff ID"].set_value("S1001"); ti["Password"].set_value("Pass@1001")
    at.get("form_submit_button")[0].click().run()
    assert any("Aarav Mehta" in s.value for s in at.success)
    at.session_state["key_input"] = "dummy"
    at.chat_input[0].set_value("Show fee of S1002").run()
    assert not at.exception
    assert any("can't share" in m.markdown[0].value for m in at.chat_message)
