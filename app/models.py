from pydantic import BaseModel, Field, field_validator
from typing import Literal
from datetime import date


VALID_STATUSES = {"pending", "validated", "rejected"}
VALID_TRIAL_PHASES = {"I", "II", "III", "IV"}


class RecordIn(BaseModel):
    site_id: str = Field(..., min_length=3, max_length=20, description="Trial site identifier")
    trial_phase: Literal["I", "II", "III", "IV"] = Field(..., description="Clinical trial phase")
    submission_date: date = Field(..., description="Date of submission (YYYY-MM-DD)")
    status: str = Field(..., description="Record status: pending, validated, or rejected")
    patient_count: int = Field(..., ge=1, le=10000, description="Number of patients in submission")
    notes: str = Field(default="", max_length=500)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v

    @field_validator("site_id")
    @classmethod
    def validate_site_id(cls, v: str) -> str:
        if not v.isalnum():
            raise ValueError("site_id must be alphanumeric")
        return v.upper()


class RecordOut(RecordIn):
    id: str = Field(..., description="Unique record identifier (UUID)")
