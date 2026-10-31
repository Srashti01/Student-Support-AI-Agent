"""Smoke test: the whole evaluation + report pipeline works end-to-end with the offline FakeLLM."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))

from eval import report, runner
from fake_llm import FakeLLM


def test_pipeline_and_excel():
    tests = [t for t in runner.load_tests() if t["id"] in ("N1", "P1", "A1", "A2", "A3")]
    sec = runner.run_suite(tests, True, llm=FakeLLM(), delay=0)
    base = runner.run_suite(tests, False, llm=FakeLLM(), delay=0)
    by = {r["id"]: r for r in sec}
    assert by["N1"]["passed"] and by["P1"]["passed"] and by["A1"]["passed"] and by["A2"]["passed"] and by["A3"]["passed"]
    assert not {r["id"]: r for r in base}["P1"]["passed"]          # baseline leaks -> test fails (as it should)
    assert not {r["id"]: r for r in base}["A1"]["passed"]
    xlsx = report.build_excel({"baseline": base, "secure": sec})
    assert xlsx[:2] == b"PK" and len(xlsx) > 5000
