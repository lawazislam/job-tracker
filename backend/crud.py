"""Database operations, kept out of the route handlers.

Design decision: routes handle HTTP concerns (status codes, validation),
this module handles SQL. That separation keeps main.py readable and makes
these functions directly testable without spinning up the API.
"""

from typing import Optional

from .database import get_conn

SORTABLE = {"date_applied", "company", "status", "created_at", "updated_at", "follow_up_date"}


def find_active_duplicate(company: str, role: str) -> Optional[dict]:
    """An 'active' duplicate is the same company+role (case-insensitive)
    that isn't already closed out. Reapplying after a rejection is
    legitimate, so closed statuses don't count as duplicates."""
    closed = ("rejected", "withdrawn", "ghosted")
    with get_conn() as conn:
        row = conn.execute(
            """SELECT * FROM applications
               WHERE LOWER(company)=LOWER(?) AND LOWER(role)=LOWER(?)
                 AND status NOT IN (?,?,?)""",
            (company, role, *closed),
        ).fetchone()
        return dict(row) if row else None


def create_application(data: dict) -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO applications
               (company, role, status, date_applied, follow_up_date,
                resume_version, job_url, location, source, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                data["company"], data["role"], data["status"],
                data.get("date_applied"), data.get("follow_up_date"),
                data.get("resume_version"), data.get("job_url"),
                data.get("location"), data.get("source"), data.get("notes"),
            ),
        )
        app_id = cur.lastrowid
        # Record the initial status so history is complete from day one.
        conn.execute(
            "INSERT INTO status_history (application_id, old_status, new_status) VALUES (?,?,?)",
            (app_id, None, data["status"]),
        )
        row = conn.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
        return dict(row)


def list_applications(status: Optional[str] = None,
                      company: Optional[str] = None,
                      sort: str = "created_at") -> list[dict]:
    if sort not in SORTABLE:
        sort = "created_at"
    query = "SELECT * FROM applications"
    clauses, params = [], []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if company:
        clauses.append("LOWER(company) LIKE ?")
        params.append(f"%{company.lower()}%")
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    # sort is whitelisted above, safe to interpolate
    query += f" ORDER BY {sort} DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_application(app_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
        if row is None:
            return None
        app = dict(row)
        history = conn.execute(
            """SELECT old_status, new_status, changed_at
               FROM status_history WHERE application_id=?
               ORDER BY changed_at ASC, id ASC""",
            (app_id,),
        ).fetchall()
        app["history"] = [dict(h) for h in history]
        return app


def update_application(app_id: int, fields: dict) -> Optional[dict]:
    if not fields:
        return get_application(app_id)
    sets = ", ".join(f"{k} = ?" for k in fields)
    params = list(fields.values()) + [app_id]
    with get_conn() as conn:
        cur = conn.execute(f"UPDATE applications SET {sets} WHERE id=?", params)
        if cur.rowcount == 0:
            return None
    return get_application(app_id)


def change_status(app_id: int, new_status: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT status FROM applications WHERE id=?", (app_id,)).fetchone()
        if row is None:
            return None
        old_status = row["status"]
        if old_status != new_status:
            conn.execute("UPDATE applications SET status=? WHERE id=?", (new_status, app_id))
            conn.execute(
                "INSERT INTO status_history (application_id, old_status, new_status) VALUES (?,?,?)",
                (app_id, old_status, new_status),
            )
    return get_application(app_id)


def delete_application(app_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM applications WHERE id=?", (app_id,))
        return cur.rowcount > 0


def get_stats() -> dict:
    with get_conn() as conn:
        by_status = {
            r["status"]: r["n"]
            for r in conn.execute(
                "SELECT status, COUNT(*) AS n FROM applications GROUP BY status"
            ).fetchall()
        }
        per_week = [
            {"week": r["week"], "count": r["n"]}
            for r in conn.execute(
                """SELECT strftime('%Y-W%W', date_applied) AS week, COUNT(*) AS n
                   FROM applications
                   WHERE date_applied IS NOT NULL
                   GROUP BY week ORDER BY week"""
            ).fetchall()
        ]
        total = conn.execute("SELECT COUNT(*) AS n FROM applications").fetchone()["n"]
    return {"total": total, "by_status": by_status, "applications_per_week": per_week}
