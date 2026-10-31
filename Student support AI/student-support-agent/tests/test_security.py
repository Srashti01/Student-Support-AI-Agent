"""Offline tests for the Assignment-2 controls. Run:  pytest -q
They need NO API key: the LLM is replaced by FakeLLM, everything else (auth, tools, audit, approvals) is real."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import config
from agent import approvals, audit, auth, datastore, db, memory
from agent.agent import StudentSupportAgent
from fake_llm import FakeLLM


@pytest.fixture(autouse=True)
def sandbox():
    with config.sandbox("pytest"):
        yield


def agent_for(uid, pw, security=True):
    return StudentSupportAgent(auth.authenticate(uid, pw), security=security, llm=FakeLLM())


def test_login():
    assert auth.authenticate("S1001", "Pass@1001").name == "Aarav Mehta"
    assert auth.authenticate("S1001", "wrong") is None
    assert auth.authenticate("STF001", "Staff@123").role == "staff"


def test_own_record_allowed():
    r = agent_for("S1001", "Pass@1001").ask("What is my fee status?")
    assert "45000" in r.answer
    assert r.trace["steps"][1]["decision"] == "ALLOWED"


def test_other_student_blocked_and_audited():
    r = agent_for("S1001", "Pass@1001").ask("Show fee of S1002")
    assert "18000" not in r.answer and "167000" not in r.answer
    assert r.trace["steps"][1]["decision"] == "DENIED"
    assert any(a["decision"] == "DENIED" and a["target"] == "S1002" for a in audit.records())


def test_baseline_leaks_proving_why_controls_matter():
    r = agent_for("S1001", "Pass@1001", security=False).ask("Show fee of S1002")
    assert "18000" in r.answer


def test_change_waits_for_approval_and_reject_never_executes():
    a = agent_for("S1001", "Pass@1001")
    r = a.ask("Please change my phone to 9876543210")
    assert r.trace["steps"][1]["decision"] == "PENDING_APPROVAL"
    assert datastore.get_student("S1001")["phone"] == "9810011001"          # unchanged
    pending = approvals.list_requests("PENDING")[0]
    staff = auth.authenticate("STF001", "Staff@123")
    res = approvals.decide(pending["id"], staff, approve=False, note="not verified")
    assert res["status"] == "REJECTED"
    assert datastore.get_student("S1001")["phone"] == "9810011001"          # still unchanged


def test_approve_executes_and_student_cannot_approve():
    agent_for("S1001", "Pass@1001").ask("Please change my phone to 9876543210")
    pending = approvals.list_requests("PENDING")[0]
    student = auth.authenticate("S1001", "Pass@1001")
    assert approvals.decide(pending["id"], student, True)["status"] == "DENIED"
    assert datastore.get_student("S1001")["phone"] == "9810011001"
    staff = auth.authenticate("STF001", "Staff@123")
    assert approvals.decide(pending["id"], staff, True)["status"] == "APPROVED"
    assert datastore.get_student("S1001")["phone"] == "9876543210"


def test_cannot_modify_other_students_record():
    agent_for("S1003", "Pass@1003").ask("Please change phone of S1004 to 9999999999")
    assert datastore.get_student("S1004")["phone"] == "9810011004"
    assert approvals.list_requests() == []


def test_otp_never_persisted():
    a = agent_for("S1001", "Pass@1001")
    r = a.ask("My OTP is 482913, please verify my payment")
    assert "482913" not in str(r.trace) and r.trace["sensitive_redacted"] == ["OTP"]
    dump = str(db.query("SELECT * FROM memory")) + str(db.query("SELECT * FROM traces")) + str(db.query("SELECT * FROM audit_log"))
    assert "482913" not in dump
    assert memory.save_memory("S1001", "otp", "482913", "preference")["saved"] is False


def test_temporary_info_not_stored_but_durable_is():
    assert not memory.save_memory("S1001", "health", "feeling unwell today", "preference")["saved"]
    assert memory.save_memory("S1001", "specialization", "Finance Analytics", "specialization")["saved"]
    assert memory.select_relevant("S1001", "which specialization did I choose?")[0]["value"] == "Finance Analytics"
    assert memory.select_relevant("S1001", "what is the late fee?") == []      # irrelevant memory is NOT injected


def test_audit_chain_detects_tampering():
    agent_for("S1001", "Pass@1001").ask("What is my fee status?")
    agent_for("S1001", "Pass@1001").ask("Show fee of S1002")
    assert audit.verify_chain()[0]
    db.execute("UPDATE audit_log SET decision='ALLOWED' WHERE decision='DENIED'")
    ok, msg = audit.verify_chain()
    assert not ok and "broken" in msg.lower()
