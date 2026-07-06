"""Seed script: loads realistic demo data so the app isn't empty on first run."""
from .database import init_db, get_conn
from . import crud

DEMO = [
    dict(company="Maple Analytics", role="Junior Data Analyst", status="interview",
         date_applied="2026-06-08", follow_up_date="2026-07-08",
         resume_version="IT-Data", location="Toronto, ON", source="LinkedIn",
         notes="Second-round interview scheduled. Prep SQL joins and Power BI case study."),
    dict(company="Great Lakes Utilities", role="IT Support Analyst", status="screening",
         date_applied="2026-06-15", resume_version="IT-Data",
         location="Windsor, ON", source="Indeed",
         notes="Phone screen done, waiting on next steps."),
    dict(company="Northfield Manufacturing", role="Engineering Technician", status="applied",
         date_applied="2026-06-22", resume_version="Engineering",
         location="London, ON", source="Company site"),
    dict(company="Bytown Systems", role="IT Project Coordinator", status="rejected",
         date_applied="2026-05-30", resume_version="IT-Data",
         location="Ottawa, ON", source="Indeed",
         notes="Went with internal candidate. Recruiter said to reapply in fall."),
    dict(company="Huron Health Network", role="Reporting Analyst", status="applied",
         date_applied="2026-06-28", follow_up_date="2026-07-12",
         resume_version="IT-Data", location="Remote", source="LinkedIn"),
    dict(company="Lakeshore Robotics", role="Automation Technician", status="saved",
         resume_version="Engineering", location="Windsor, ON", source="Referral",
         notes="Posting closes July 20. Tailor cover letter to PLC cert."),
]

def run():
    init_db()
    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM applications").fetchone()["n"]
    if n:
        print(f"Database already has {n} applications, skipping seed.")
        return
    for item in DEMO:
        crud.create_application({**item,
            "status": item.get("status", "applied"),
            "date_applied": item.get("date_applied"),
            "follow_up_date": item.get("follow_up_date"),
            "resume_version": item.get("resume_version"),
            "job_url": item.get("job_url"),
            "location": item.get("location"),
            "source": item.get("source"),
            "notes": item.get("notes")})
    print(f"Seeded {len(DEMO)} applications.")

if __name__ == "__main__":
    run()
