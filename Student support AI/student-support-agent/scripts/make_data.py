"""Generates data/university_data.xlsx (seed data for the Student Support Agent).
Run:  python scripts/make_data.py
Demo passwords: students -> Pass@<last 4 digits of ID> (e.g. S1001 -> Pass@1001), staff -> Staff@123
(These are fake demo credentials for fake demo users.)"""
import hashlib
import sys
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill

OUT = Path(__file__).resolve().parents[1] / "data" / "university_data.xlsx"


def hash_pw(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()


BDA = "PGDM (Big Data Analytics)"
AIDS = "PGDM (AI & Data Science)"

students = [
    ("S1001", "Aarav Mehta", BDA, "2025-27", "aarav.mehta@example.edu", "9810011001"),
    ("S1002", "Priya Nair", AIDS, "2025-27", "priya.nair@example.edu", "9810011002"),
    ("S1003", "Rohan Iyer", BDA, "2025-27", "rohan.iyer@example.edu", "9810011003"),
    ("S1004", "Sneha Kapoor", AIDS, "2025-27", "sneha.kapoor@example.edu", "9810011004"),
    ("S1005", "Karan Shah", BDA, "2025-27", "karan.shah@example.edu", "9810011005"),
]
rows = []
for sid, name, prog, batch, email, phone in students:
    salt = f"salt-{sid}"
    rows.append(dict(student_id=sid, name=name, programme=prog, batch=batch, email=email,
                     phone=phone, salt=salt, password_hash=hash_pw(f"Pass@{sid[-4:]}", salt)))
df_students = pd.DataFrame(rows)

df_fees = pd.DataFrame([
    ("S1001", "Term 3", 185000, 140000, 45000, "2026-11-15", "Partially Paid", "2026-08-12"),
    ("S1002", "Term 3", 185000, 167000, 18000, "2026-11-02", "Partially Paid", "2026-09-01"),
    ("S1003", "Term 3", 185000, 185000, 0, "2026-11-15", "Paid", "2026-08-20"),
    ("S1004", "Term 3", 185000, 92500, 92500, "2026-10-20", "Overdue", "2026-07-30"),
    ("S1005", "Term 3", 185000, 120000, 65000, "2026-12-01", "Partially Paid", "2026-09-15"),
], columns=["student_id", "term", "total_fee", "amount_paid", "due_amount", "due_date",
            "status", "last_payment_date"])

df_schol = pd.DataFrame([
    ("S1001", "Merit Scholarship", 50000, "Approved", "Renewal needs CGPA >= 3.0 at end of Term 3"),
    ("S1002", "Women in Data Science Grant", 75000, "Approved", "Credited against Term 4 fee"),
    ("S1003", "Need-Based Aid", 40000, "Under Review", "Income documents received; committee meets in November"),
    ("S1004", "None", 0, "Not Applied", "Applications for this term are closed"),
    ("S1005", "Merit Scholarship", 0, "Rejected", "CGPA below the cut-off for this cycle"),
], columns=["student_id", "scheme", "amount", "status", "remarks"])

df_staff = pd.DataFrame([
    ("STF001", "Dr. Meera Rao", "Registrar Office", "staff", "salt-STF001", hash_pw("Staff@123", "salt-STF001")),
], columns=["staff_id", "name", "department", "role", "salt", "password_hash"])

df_readme = pd.DataFrame({"sheet": ["Students", "Fees", "Scholarships", "Staff"],
                          "purpose": ["Private student records + login hashes (PBKDF2)",
                                      "Fee status per student (private)",
                                      "Scholarship status per student (private)",
                                      "Staff accounts allowed to approve sensitive changes"]})

OUT.parent.mkdir(exist_ok=True)
with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
    df_students.to_excel(xw, sheet_name="Students", index=False)
    df_fees.to_excel(xw, sheet_name="Fees", index=False)
    df_schol.to_excel(xw, sheet_name="Scholarships", index=False)
    df_staff.to_excel(xw, sheet_name="Staff", index=False)
    df_readme.to_excel(xw, sheet_name="ReadMe", index=False)

wb = load_workbook(OUT)
for ws in wb.worksheets:
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F4E78")
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(48, max(len(str(c.value or "")) for c in col) + 2)
wb.save(OUT)
print(f"Created {OUT}")
