"""
Phase 3, Module F — user + document + simulation persistence (repository layer).
Thin functions over db.database so routers never write raw SQL.
"""
import json
from typing import Optional

from auth import security
from db import database


def _is_admin_email(email: str) -> bool:
    from config import PRISM_ADMIN_EMAIL
    return bool(PRISM_ADMIN_EMAIL) and email.strip().lower() == PRISM_ADMIN_EMAIL.strip().lower()


def create_user(email: str, name: str, password: Optional[str], role: str = "user") -> dict:
    if get_user_by_email(email):
        raise ValueError("Email already registered")
    uid = security.new_user_id()
    api_key = security.new_api_key()
    pw_hash = security.hash_password(password) if password else None
    if _is_admin_email(email):
        role = "admin"  # bootstrap the admin account (PRISM_ADMIN_EMAIL)
    database.execute(
        "INSERT INTO users (id, email, name, password_hash, role, api_key) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (uid, email, name, pw_hash, role, api_key),
    )
    return get_user_by_id(uid)


def ensure_admin(user: dict) -> dict:
    """Promote an existing user to admin if their email matches
    PRISM_ADMIN_EMAIL (so the bootstrap works even for pre-existing accounts)."""
    if user.get("role") != "admin" and _is_admin_email(user.get("email", "")):
        database.execute("UPDATE users SET role = ? WHERE id = ?", ("admin", str(user["id"])))
        user["role"] = "admin"
    return user


def get_user_by_email(email: str) -> Optional[dict]:
    return database.fetchone("SELECT * FROM users WHERE email = ?", (email,))


def get_user_by_id(uid: str) -> Optional[dict]:
    return database.fetchone("SELECT * FROM users WHERE id = ?", (str(uid),))


def get_user_by_api_key(api_key: str) -> Optional[dict]:
    return database.fetchone("SELECT * FROM users WHERE api_key = ?", (api_key,))


def rotate_api_key(uid: str) -> str:
    key = security.new_api_key()
    database.execute("UPDATE users SET api_key = ? WHERE id = ?", (key, str(uid)))
    return key


def list_users() -> list[dict]:
    return database.fetchall(
        "SELECT u.id, u.email, u.name, u.role, u.created_at, "
        "(SELECT COUNT(*) FROM user_documents d WHERE d.user_id = u.id) AS doc_count, "
        "(SELECT COUNT(*) FROM api_usage a WHERE a.user_id = u.id) AS api_calls "
        "FROM users u ORDER BY u.created_at DESC"
    )


def public_user(user: dict) -> dict:
    """Strip secrets before returning a user to the client."""
    return {
        "id": user["id"], "email": user["email"], "name": user.get("name"),
        "role": user.get("role", "user"), "created_at": str(user.get("created_at", "")),
    }


# --- documents ---

def record_document(user_id: str, doc_id: str, doc_name: str, r2_key: str = "", status: str = "ready") -> None:
    import uuid
    database.execute(
        "INSERT INTO user_documents (id, user_id, doc_id, doc_name, r2_key, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), str(user_id), doc_id, doc_name, r2_key, status),
    )


def list_documents(user_id: str) -> list[dict]:
    return database.fetchall(
        "SELECT doc_id, doc_name, r2_key, status, created_at FROM user_documents "
        "WHERE user_id = ? ORDER BY created_at DESC",
        (str(user_id),),
    )


# --- simulations ---

def record_simulation(user_id: str, doc_id: str, config: dict, results: dict) -> None:
    import uuid
    database.execute(
        "INSERT INTO simulations (id, user_id, doc_id, config, results) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), str(user_id), doc_id,
         json.dumps(config), json.dumps(results)),
    )


def list_simulations(user_id: str) -> list[dict]:
    return database.fetchall(
        "SELECT doc_id, config, results, created_at FROM simulations "
        "WHERE user_id = ? ORDER BY created_at DESC",
        (str(user_id),),
    )


# --- usage metering ---

def log_usage(user_id: str, endpoint: str) -> None:
    database.execute("INSERT INTO api_usage (user_id, endpoint) VALUES (?, ?)", (str(user_id), endpoint))


def usage_count(user_id: str) -> int:
    return database.scalar("SELECT COUNT(*) FROM api_usage WHERE user_id = ?", (str(user_id),)) or 0
