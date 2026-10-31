"""Reads/writes the Excel workbook (the 'student information system')."""
from openpyxl import load_workbook
import pandas as pd

import config


def _py(v):
    if hasattr(v, "item"):
        return v.item()
    return None if pd.isna(v) else v


def _sheet(name):
    df = pd.read_excel(config.DATA_FILE, sheet_name=name, dtype={"student_id": str, "staff_id": str,
                                                                "phone": str, "salt": str})
    return [{k: _py(v) for k, v in row.items()} for row in df.to_dict("records")]


def _find(sheet, key, value):
    for r in _sheet(sheet):
        if str(r.get(key, "")).upper() == str(value).upper():
            return r
    return None


def get_student(student_id):
    return _find("Students", "student_id", student_id)


def get_fee(student_id):
    return _find("Fees", "student_id", student_id)


def get_scholarship(student_id):
    return _find("Scholarships", "student_id", student_id)


def get_staff(staff_id):
    return _find("Staff", "staff_id", staff_id)


def update_student_field(student_id, field, value):
    wb = load_workbook(config.DATA_FILE)
    ws = wb["Students"]
    headers = {c.value: c.column for c in ws[1]}
    if field not in headers:
        raise ValueError(f"Unknown field {field}")
    for row in ws.iter_rows(min_row=2):
        if str(row[headers["student_id"] - 1].value).upper() == student_id.upper():
            row[headers[field] - 1].value = value
            wb.save(config.DATA_FILE)
            return True
    raise ValueError(f"Student {student_id} not found")
