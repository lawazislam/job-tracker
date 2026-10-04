# Job Application Tracker

A personal job-application tracker I built to manage my own job search: every
application, its current pipeline stage, and a full history of how it moved
through the stages.

**Live demo:** deployed on Render (free tier: first load after idle takes
~30-60 seconds to wake up, and demo data resets on restart by design).

## What it does

- Track applications with company, role, dates, resume version used, source, and notes
- Move applications through a pipeline (saved, applied, screening, interview, offer, rejected, withdrawn, ghosted) with one click
- Every status change is recorded in an audit trail (`status_history` table)
- Live stats: totals by stage and applications per week
- Filter by stage, search by company
- Duplicate protection: warns before double-submitting the same active company + role, while deliberately allowing reapplication after a rejection

## Tech stack

- **Backend:** Python, FastAPI, SQLite (raw `sqlite3`, no ORM)
- **Frontend:** plain HTML/CSS/JS, no frameworks, served by FastAPI
- **Tests:** pytest, 7 end-to-end API tests against an isolated temporary database

## Run it locally

```bash
pip install -r requirements.txt
python -m uvicorn backend.main:app
# open http://localhost:8000
```

Run tests:

```bash
python -m pytest tests/ -v
```

## A technical challenge worth mentioning

My first test run failed in a way that exposed a real bug: the connection
helper was defined as `get_conn(db_path=DB_PATH)`, and Python evaluates
default arguments once, at function definition time. That froze the database
path the moment the module was imported, so when the tests tried to point at
a temporary database, they silently hit the real seeded one instead. The fix
was resolving the path at call time (`db_path=None`, falling back to the
module-level path inside the function). Small change, but it is the
difference between a test suite that isolates data and one that quietly
corrupts your real database.

## Design decisions

- Status changes go through a dedicated `PATCH /status` endpoint, never
  through general updates, so the audit trail can never miss a change.
- `PRAGMA foreign_keys=ON` per connection: SQLite ships with foreign-key
  enforcement off, and without it, deleting an application would silently
  orphan its history rows.
- Validation rejects logically impossible data (follow-up date before the
  application date) and unknown filter values, with error messages that say
  what is wrong instead of generic 500s.
