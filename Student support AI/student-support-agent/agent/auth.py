"""Identity + authorization. These checks run in normal Python code - NOT in the prompt - so the LLM
cannot talk its way around them."""
import hashlib
import hmac
from dataclasses import dataclass

from agent import datastore


@dataclass
class User:
    user_id: str
    name: str
    role: str        # "student" | "staff"


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()


def authenticate(user_id: str, password: str):
    user_id = (user_id or "").strip().upper()
    if not user_id or not password:
        return None
    rec, role = datastore.get_student(user_id), "student"
    if rec is None:
        rec, role = datastore.get_staff(user_id), "staff"
    if rec is None:
        return None
    if not hmac.compare_digest(hash_password(password, str(rec["salt"])), str(rec["password_hash"])):
        return None
    return User(user_id=user_id, name=rec["name"], role=role)


def can_access_student(user: User, target_id: str):
    """Rule: a student may touch ONLY their own private record. Staff do not get blanket access either
    (least privilege) - they only see the approval queue."""
    target_id = (target_id or "").strip().upper()
    if user.role == "student" and user.user_id == target_id:
        return True, "own record"
    return False, f"{user.user_id} is not authorised to access the private record of {target_id}"


def can_decide_approval(user: User, requester_id: str):
    if user.role != "staff":
        return False, "only staff can approve or reject sensitive changes"
    if user.user_id == requester_id:
        return False, "maker-checker rule: you cannot approve your own request"
    return True, "staff approver"
