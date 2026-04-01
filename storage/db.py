"""
storage/db.py
SQLite database layer — repos, drafts, version history, approvals.
Single source of truth for all persistent state in the system.
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "living_api_docs.db")


def get_connection():
    """Return a sqlite3 connection with row_factory for dict-like access."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Create all tables if they don't exist.
    Call this once at app startup.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # --- Repos table ---
    # Stores each GitHub repo that has been added for monitoring
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS repos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_url TEXT UNIQUE NOT NULL,
            framework TEXT,
            last_commit_sha TEXT,
            added_at TEXT DEFAULT (datetime('now')),
            last_checked_at TEXT
        )
    """)

    # --- Endpoints table ---
    # Stores every parsed API endpoint discovered from a repo
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS endpoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_url TEXT NOT NULL,
            method TEXT NOT NULL,
            route TEXT NOT NULL,
            params TEXT,         -- JSON string: list of param dicts
            return_type TEXT,
            auth_required INTEGER DEFAULT 0,
            raw_code TEXT,       -- the actual source snippet
            discovered_at TEXT DEFAULT (datetime('now')),
            UNIQUE(repo_url, method, route)
        )
    """)

    # --- Drafts table ---
    # Stores AI-generated documentation drafts awaiting review
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_url TEXT NOT NULL,
            method TEXT NOT NULL,
            route TEXT NOT NULL,
            generated_doc TEXT NOT NULL,   -- full markdown doc
            status TEXT DEFAULT 'pending', -- pending | approved | rejected
            edited_doc TEXT,               -- if dev edited before approving
            consistency_warnings TEXT,     -- JSON list of warnings
            created_at TEXT DEFAULT (datetime('now')),
            reviewed_at TEXT
        )
    """)

    # --- Version history table ---
    # Stores approved doc snapshots for every endpoint
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS version_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_url TEXT NOT NULL,
            method TEXT NOT NULL,
            route TEXT NOT NULL,
            version_number INTEGER NOT NULL,
            doc_content TEXT NOT NULL,     -- approved markdown content
            change_summary TEXT,           -- what changed vs previous version
            approved_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # --- Published docs table ---
    # Stores final published doc metadata per repo
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS published_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_url TEXT NOT NULL,
            published_url TEXT,            -- GitHub Pages URL
            markdown_path TEXT,            -- local file path
            swagger_path TEXT,             -- local swagger YAML path
            published_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Database initialised successfully.")


# ─────────────────────────────────────────────
# REPO OPERATIONS
# ─────────────────────────────────────────────

def add_repo(repo_url: str, framework: str = None) -> bool:
    """Add a new repo for monitoring. Returns True if added, False if already exists."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO repos (repo_url, framework) VALUES (?, ?)",
            (repo_url, framework)
        )
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def get_all_repos() -> list:
    """Return all monitored repos as list of dicts."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM repos ORDER BY added_at DESC").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_repo_commit(repo_url: str, commit_sha: str):
    """Update the last known commit SHA and check timestamp for a repo."""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE repos SET last_commit_sha = ?, last_checked_at = datetime('now')
               WHERE repo_url = ?""",
            (commit_sha, repo_url)
        )
        conn.commit()
    finally:
        conn.close()


def update_repo_framework(repo_url: str, framework: str):
    """Update detected framework for a repo."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE repos SET framework = ? WHERE repo_url = ?",
            (framework, repo_url)
        )
        conn.commit()
    finally:
        conn.close()


def get_repo(repo_url: str) -> dict:
    """Return a single repo record as dict, or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM repos WHERE repo_url = ?", (repo_url,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ─────────────────────────────────────────────
# ENDPOINT OPERATIONS
# ─────────────────────────────────────────────

def upsert_endpoint(repo_url: str, method: str, route: str,
                    params: list, return_type: str,
                    auth_required: bool, raw_code: str):
    """Insert or update an endpoint record."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO endpoints (repo_url, method, route, params, return_type, auth_required, raw_code)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(repo_url, method, route)
            DO UPDATE SET
                params = excluded.params,
                return_type = excluded.return_type,
                auth_required = excluded.auth_required,
                raw_code = excluded.raw_code,
                discovered_at = datetime('now')
        """, (
            repo_url, method.upper(), route,
            json.dumps(params), return_type,
            1 if auth_required else 0, raw_code
        ))
        conn.commit()
    finally:
        conn.close()


def get_endpoints(repo_url: str) -> list:
    """Return all endpoints for a repo."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM endpoints WHERE repo_url = ? ORDER BY route",
            (repo_url,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["params"] = json.loads(d["params"]) if d["params"] else []
            result.append(d)
        return result
    finally:
        conn.close()


# ─────────────────────────────────────────────
# DRAFT OPERATIONS
# ─────────────────────────────────────────────

def save_draft(repo_url: str, method: str, route: str,
               generated_doc: str, consistency_warnings: list = None):
    """Save a newly generated draft doc."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO drafts (repo_url, method, route, generated_doc, consistency_warnings)
            VALUES (?, ?, ?, ?, ?)
        """, (
            repo_url, method.upper(), route,
            generated_doc,
            json.dumps(consistency_warnings or [])
        ))
        conn.commit()
    finally:
        conn.close()


def get_pending_drafts(repo_url: str) -> list:
    """Return all pending drafts for a repo."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM drafts
            WHERE repo_url = ? AND status = 'pending'
            ORDER BY created_at DESC
        """, (repo_url,)).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["consistency_warnings"] = json.loads(d["consistency_warnings"] or "[]")
            result.append(d)
        return result
    finally:
        conn.close()


def get_all_drafts(repo_url: str) -> list:
    """Return all drafts (any status) for a repo."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM drafts WHERE repo_url = ?
            ORDER BY created_at DESC
        """, (repo_url,)).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["consistency_warnings"] = json.loads(d["consistency_warnings"] or "[]")
            result.append(d)
        return result
    finally:
        conn.close()


def approve_draft(draft_id: int, final_doc: str):
    """Mark a draft as approved and store the final (possibly edited) doc."""
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE drafts
            SET status = 'approved', edited_doc = ?, reviewed_at = datetime('now')
            WHERE id = ?
        """, (final_doc, draft_id))
        conn.commit()
    finally:
        conn.close()


def reject_draft(draft_id: int):
    """Mark a draft as rejected."""
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE drafts
            SET status = 'rejected', reviewed_at = datetime('now')
            WHERE id = ?
        """, (draft_id,))
        conn.commit()
    finally:
        conn.close()


# ─────────────────────────────────────────────
# VERSION HISTORY OPERATIONS
# ─────────────────────────────────────────────

def save_version(repo_url: str, method: str, route: str,
                 doc_content: str, change_summary: str = None):
    """Save an approved doc as a new version. Auto-increments version number."""
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT MAX(version_number) as max_v FROM version_history
            WHERE repo_url = ? AND method = ? AND route = ?
        """, (repo_url, method.upper(), route)).fetchone()

        next_version = (row["max_v"] or 0) + 1

        conn.execute("""
            INSERT INTO version_history
            (repo_url, method, route, version_number, doc_content, change_summary)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (repo_url, method.upper(), route, next_version, doc_content, change_summary))
        conn.commit()
        return next_version
    finally:
        conn.close()


def get_version_history(repo_url: str, method: str = None, route: str = None) -> list:
    """Return version history. Filter by endpoint if method+route provided."""
    conn = get_connection()
    try:
        if method and route:
            rows = conn.execute("""
                SELECT * FROM version_history
                WHERE repo_url = ? AND method = ? AND route = ?
                ORDER BY version_number DESC
            """, (repo_url, method.upper(), route)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM version_history
                WHERE repo_url = ?
                ORDER BY approved_at DESC
            """, (repo_url,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_latest_approved_doc(repo_url: str, method: str, route: str) -> str:
    """Return the most recently approved doc content for an endpoint, or None."""
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT doc_content FROM version_history
            WHERE repo_url = ? AND method = ? AND route = ?
            ORDER BY version_number DESC LIMIT 1
        """, (repo_url, method.upper(), route)).fetchone()
        return row["doc_content"] if row else None
    finally:
        conn.close()


# ─────────────────────────────────────────────
# PUBLISHED DOCS OPERATIONS
# ─────────────────────────────────────────────

def save_published_doc(repo_url: str, published_url: str = None,
                       markdown_path: str = None, swagger_path: str = None):
    """Record a publish event for a repo."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO published_docs (repo_url, published_url, markdown_path, swagger_path)
            VALUES (?, ?, ?, ?)
        """, (repo_url, published_url, markdown_path, swagger_path))
        conn.commit()
    finally:
        conn.close()


def get_latest_published(repo_url: str) -> dict:
    """Return the most recent publish record for a repo."""
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT * FROM published_docs WHERE repo_url = ?
            ORDER BY published_at DESC LIMIT 1
        """, (repo_url,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ─────────────────────────────────────────────
# USER AUTH OPERATIONS
# ─────────────────────────────────────────────

def create_or_get_user(email: str) -> dict:
    """Create user if not exists, return user dict."""
    import secrets
    conn = get_connection()
    try:
        token = secrets.token_urlsafe(32)
        conn.execute("""
            INSERT INTO users (email, token) VALUES (?, ?)
            ON CONFLICT(email) DO UPDATE SET
                token = excluded.token,
                last_login = datetime('now')
        """, (email, token))
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_token(token: str) -> dict:
    """Return user dict for a given token, or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE token = ?", (token,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_email(email: str) -> dict:
    """Return user dict for a given email, or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def add_repo_for_user(repo_url: str, user_email: str, framework: str = None) -> bool:
    """Add repo linked to a user email."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO repos (repo_url, framework, user_email)
            VALUES (?, ?, ?)
        """, (repo_url, framework, user_email))
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def get_repos_for_user(user_email: str) -> list:
    """Return repos belonging to a specific user."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM repos WHERE user_email = ? ORDER BY added_at DESC",
            (user_email,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def ensure_users_table():
    """Add users table if upgrading from older DB without it."""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                token TEXT UNIQUE,
                created_at TEXT DEFAULT (datetime('now')),
                last_login TEXT
            )
        """)
        # Add user_email column to repos if missing
        try:
            conn.execute("ALTER TABLE repos ADD COLUMN user_email TEXT")
        except Exception:
            pass  # Column already exists
        conn.commit()
    finally:
        conn.close()


def has_pending_draft(repo_url: str, method: str, route: str) -> bool:
    """Check if a pending draft already exists for this endpoint."""
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT id FROM drafts
            WHERE repo_url = ? AND method = ? AND route = ? AND status = 'pending'
            LIMIT 1
        """, (repo_url, method.upper(), route)).fetchone()
        return row is not None
    finally:
        conn.close()


def has_approved_doc(repo_url: str, method: str, route: str) -> bool:
    """Check if an approved doc already exists for this endpoint."""
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT id FROM version_history
            WHERE repo_url = ? AND method = ? AND route = ?
            LIMIT 1
        """, (repo_url, method.upper(), route)).fetchone()
        return row is not None
    finally:
        conn.close()
