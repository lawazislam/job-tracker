"""FastAPI app: routes and HTTP concerns.

Design decisions:
- Routes are thin: validate with Pydantic, call crud, map None -> 404.
- job_url arrives as HttpUrl; converted to str before storage.
- Frontend served from FastAPI via StaticFiles so the whole thing deploys
  as one unit. API lives under /api/* so static routes never collide.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .database import init_db, ALLOWED_STATUSES
from . import crud
from .models import (
    ApplicationCreate, ApplicationUpdate, StatusChange,
    ApplicationOut, ApplicationDetailOut,
)

app = FastAPI(title="Job Application Tracker", version="1.0.0")

init_db()

# On a fresh database (e.g. Render's ephemeral filesystem after a restart),
# load demo data so the deployed demo is never an empty table.
from . import seed as _seed
_seed.run()

SORT_FIELDS = ("created_at", "updated_at", "date_applied", "company", "status", "follow_up_date")


@app.exception_handler(sqlite3.Error)
def sqlite_error_handler(request: Request, exc: sqlite3.Error):
    """Unexpected database errors return a clean 500 without leaking SQL
    internals, instead of an unhandled stack trace."""
    return JSONResponse(status_code=500, content={
        "detail": "A database error occurred. The operation was rolled back."
    })


def _serialize(data: dict) -> dict:
    if data.get("job_url") is not None:
        data["job_url"] = str(data["job_url"])
    for k in ("date_applied", "follow_up_date"):
        if data.get(k) is not None:
            data[k] = data[k].isoformat()
    return data


@app.post("/api/applications", response_model=ApplicationOut, status_code=201)
def create_application(payload: ApplicationCreate, allow_duplicate: bool = Query(default=False)):
    dup = crud.find_active_duplicate(payload.company, payload.role)
    if dup and not allow_duplicate:
        raise HTTPException(
            status_code=409,
            detail=(
                f"An active application for '{payload.role}' at '{payload.company}' "
                f"already exists (id={dup['id']}, status={dup['status']}). "
                "Pass ?allow_duplicate=true to create it anyway."
            ),
        )
    return crud.create_application(_serialize(payload.model_dump()))


@app.get("/api/applications", response_model=list[ApplicationOut])
def list_applications(
    status: Optional[str] = Query(default=None),
    company: Optional[str] = Query(default=None),
    sort: str = Query(default="created_at"),
):
    if status is not None and status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status filter '{status}'. Valid values: {', '.join(ALLOWED_STATUSES)}",
        )
    if sort not in SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid sort field '{sort}'. Valid values: {', '.join(SORT_FIELDS)}",
        )
    return crud.list_applications(status=status, company=company, sort=sort)


@app.get("/api/applications/{app_id}", response_model=ApplicationDetailOut)
def get_application(app_id: int):
    result = crud.get_application(app_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id} not found")
    return result


@app.put("/api/applications/{app_id}", response_model=ApplicationDetailOut)
def update_application(app_id: int, payload: ApplicationUpdate):
    fields = _serialize(payload.model_dump(exclude_unset=True))
    result = crud.update_application(app_id, fields)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id} not found")
    return result


@app.patch("/api/applications/{app_id}/status", response_model=ApplicationDetailOut)
def change_status(app_id: int, payload: StatusChange):
    result = crud.change_status(app_id, payload.status)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Application {app_id} not found")
    return result


@app.delete("/api/applications/{app_id}", status_code=204)
def delete_application(app_id: int):
    if not crud.delete_application(app_id):
        raise HTTPException(status_code=404, detail=f"Application {app_id} not found")


@app.get("/api/stats")
def stats():
    return crud.get_stats()


# Mounted last so /api/* wins; html=True serves index.html at /
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
