"""
Phase 3, Module F — database layer.

Dual-backend by design: if DATABASE_URL is set it uses Neon/Postgres (psycopg);
otherwise it falls back to a local SQLite file (data/prism.db) so the whole auth
+ dashboard stack runs with zero cloud setup. The two share one SQL surface via
a tiny param-style shim (`?` for SQLite, `%s` for Postgres).

Tables: users, user_documents, simulations (see migrations/001_init.sql).
"""
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Optional

from config import BASE_DIR, DATABASE_URL

_SQLITE_PATH = BASE_DIR / "data" / "prism.db"
_lock = threading.Lock()
_initialized = False

IS_POSTGRES = bool(DATABASE_URL)


def _q(sql: str) -> str:
    """Translate `?` placeholders to `%s` for Postgres; leave SQLite as-is."""
    return sql.replace("?", "%s") if IS_POSTGRES else sql


@contextmanager
def get_conn():
    if IS_POSTGRES:
        import psycopg
        conn = psycopg.connect(DATABASE_URL)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        _SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_SQLITE_PATH))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


_SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    password_hash TEXT,
    role TEXT DEFAULT 'user',
    api_key TEXT UNIQUE NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS user_documents (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    doc_name TEXT,
    r2_key TEXT,
    status TEXT DEFAULT 'ready',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS simulations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    doc_id TEXT,
    config TEXT,
    results TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    endpoint TEXT,
    ts TEXT DEFAULT (datetime('now'))
);
"""

_POSTGRES_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    password_hash TEXT,
    role TEXT DEFAULT 'user',
    api_key TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS user_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    doc_id TEXT NOT NULL,
    doc_name TEXT,
    r2_key TEXT,
    status TEXT DEFAULT 'ready',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS simulations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    doc_id TEXT,
    config JSONB,
    results JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS api_usage (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID,
    endpoint TEXT,
    ts TIMESTAMPTZ DEFAULT NOW()
);
"""


def init_db() -> str:
    """Create tables if absent. Idempotent; safe to call at startup."""
    global _initialized
    with _lock:
        if _initialized:
            return "postgres" if IS_POSTGRES else "sqlite"
        ddl = _POSTGRES_DDL if IS_POSTGRES else _SQLITE_DDL
        with get_conn() as conn:
            cur = conn.cursor()
            if IS_POSTGRES:
                cur.execute(ddl)
            else:
                cur.executescript(ddl)
        _initialized = True
        return "postgres" if IS_POSTGRES else "sqlite"


def execute(sql: str, params: tuple = ()) -> None:
    with get_conn() as conn:
        conn.cursor().execute(_q(sql), params)


def fetchone(sql: str, params: tuple = ()) -> Optional[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(_q(sql), params)
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row)) if IS_POSTGRES else dict(row)


def fetchall(sql: str, params: tuple = ()) -> list[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(_q(sql), params)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        if IS_POSTGRES:
            return [dict(zip(cols, r)) for r in rows]
        return [dict(r) for r in rows]


def scalar(sql: str, params: tuple = ()) -> Any:
    row = fetchone(sql, params)
    if not row:
        return None
    return next(iter(row.values()))
