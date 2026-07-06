"""Pydantic models: request validation and response shapes.

Design decisions:
- Separate Create / Update / StatusChange models instead of one model with
  everything optional: this makes "which fields can change through which
  endpoint" explicit. Status can NOT be changed through PUT; it must go
  through PATCH /status so the history table always stays consistent.
- Dates are typed as `date`, so FastAPI rejects malformed dates for free
  (e.g. "2026-13-45") with a clear 422 error instead of storing junk.
- Strings are stripped and length-limited to keep garbage out of the DB.
"""

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

Status = Literal[
    "saved", "applied", "screening", "interview",
    "offer", "rejected", "withdrawn", "ghosted",
]


class ApplicationCreate(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    status: Status = "applied"
    date_applied: Optional[date] = None
    follow_up_date: Optional[date] = None
    resume_version: Optional[str] = Field(default=None, max_length=100)
    job_url: Optional[HttpUrl] = None
    location: Optional[str] = Field(default=None, max_length=200)
    source: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=5000)

    @field_validator("company", "role", "resume_version", "location", "source", mode="before")
    @classmethod
    def strip_strings(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

    @model_validator(mode="after")
    def follow_up_not_before_applied(self):
        if self.date_applied and self.follow_up_date and self.follow_up_date < self.date_applied:
            raise ValueError("follow_up_date cannot be earlier than date_applied")
        return self


class ApplicationUpdate(BaseModel):
    """PUT payload. Status intentionally absent, use PATCH /status."""
    company: Optional[str] = Field(default=None, min_length=1, max_length=200)
    role: Optional[str] = Field(default=None, min_length=1, max_length=200)
    date_applied: Optional[date] = None
    follow_up_date: Optional[date] = None
    resume_version: Optional[str] = Field(default=None, max_length=100)
    job_url: Optional[HttpUrl] = None
    location: Optional[str] = Field(default=None, max_length=200)
    source: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=5000)

    @field_validator("company", "role", "resume_version", "location", "source", mode="before")
    @classmethod
    def strip_strings(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


class StatusChange(BaseModel):
    status: Status


class StatusHistoryOut(BaseModel):
    old_status: Optional[str]
    new_status: str
    changed_at: datetime


class ApplicationOut(BaseModel):
    id: int
    company: str
    role: str
    status: str
    date_applied: Optional[date]
    follow_up_date: Optional[date]
    resume_version: Optional[str]
    job_url: Optional[str]
    location: Optional[str]
    source: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class ApplicationDetailOut(ApplicationOut):
    history: list[StatusHistoryOut]
