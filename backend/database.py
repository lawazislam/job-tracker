"""Database connection and schema setup.

Design decisions:
- sqlite3 from the standard library instead of an ORM: for a project this
  size an ORM hides the SQL, and being able to talk through the actual SQL
  (foreign keys, cascade deletes, triggers) is worth more in an interview.
- Row factory set to sqlite3.Row so query results behave like dicts.
- PRAGMA foreign_keys=ON per connection: SQLite ships with FK enforcement
  off by default; without this, cascade delete silently does nothing.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "tracker.db"

ALLOWED_STATUSES = (
    "saved", "applied", "screening", "interview",
    "offer", "rejected", "withdrawn", "ghosted",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'applied'
        CHECK (status IN ('saved','applied','screening','interview',
                          'offer','rejected','withdrawn','ghosted')),
    date_applied TEXT,
    follow_up_date TEXT,
    resume_version TEXT,
    job_url TEXT,
    location TEXT,
    source TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL
        REFERENCES applications(id) ON DELETE CASCADE,
    old_status TEXT,
    new_status TEXT NOT NULL,
    changed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_history_app
    ON status_history(application_id);

-- Keep updated_at accurate without relying on app code to remember it.
CREATE TRIGGER IF NOT EXISTS trg_applications_updated
AFTER UPDATE ON applications
BEGIN
    UPDATE applications SET updated_at = datetime('now')
    WHERE id = NEW.id;
END;
"""


def init_db(db_path: Path | None = None) -> None:
    with sqlite3.connect(db_path or DB_PATH) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn(db_path: Path | None = None):
    """db_path resolves at call time (not definition time), so tests can
    point DB_PATH at a temporary database. A default of `db_path=DB_PATH`
    would freeze the path the moment this module is imported."""
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
