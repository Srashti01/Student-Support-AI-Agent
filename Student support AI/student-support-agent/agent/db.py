"""SQLite helper. One small DB file holds: long-term memory, audit log, approvals, tickets, traces."""
import sqlite3
from contextlib import contextmanager

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS memory(
  id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, key TEXT NOT NULL,
  value TEXT NOT NULL, category TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(student_id, key));
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, actor TEXT NOT NULL, role TEXT NOT NULL,
  action TEXT NOT NULL, target TEXT, details TEXT, decision TEXT NOT NULL, result TEXT,
  trace_id TEXT, prev_hash TEXT NOT NULL, hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS approvals(
  id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, field TEXT NOT NULL,
  old_value TEXT, new_value TEXT NOT NULL, reason TEXT, status TEXT NOT NULL DEFAULT 'PENDING',
  requested_at TEXT NOT NULL, decided_by TEXT, decided_at TEXT, decision_note TEXT, trace_id TEXT);
CREATE TABLE IF NOT EXISTS tickets(
  id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, category TEXT, summary TEXT,
  status TEXT NOT NULL DEFAULT 'OPEN', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS traces(
  trace_id TEXT PRIMARY KEY, ts TEXT NOT NULL, student_id TEXT, mode TEXT, payload TEXT NOT NULL);
"""


@contextmanager
def conn():
    c = sqlite3.connect(config.DB_FILE, timeout=15)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    try:
        yield c
        c.commit()
    finally:
        c.close()


def query(sql, params=()):
    with conn() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def execute(sql, params=()):
    with conn() as c:
        cur = c.execute(sql, params)
        return cur.lastrowid
