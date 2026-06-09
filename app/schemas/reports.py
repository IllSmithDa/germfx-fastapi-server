from pydantic import BaseModel
from typing import Optional
from datetime import date

class SymptomFrequencyReportItem(BaseModel):
    symptom_text: str
    count: int
    avg_severity: float | None

class MedicationUsageReportItem(BaseModel):
    user_medication_id: int
    drug_index_id: Optional[int] = None
    name: str
    nickname: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: bool
    total_days_used: Optional[int] = None

class SymptomSummary(BaseModel):
    total_logs_last_7_days: int
    top_symptom_name: str | None = None
    top_symptom_count: int = 0
    avg_severity_last_7_days: float | None = None
    change_vs_previous_7_days: int | None = None


class MedicationSummary(BaseModel):
    total_tracked: int
    active_count: int
    longest_active_name: str | None = None
    longest_active_days: int | None = None
    most_recent_started_name: str | None = None


class ActivitySummary(BaseModel):
    last_symptom_log_date: date | None = None
    last_medication_start_date: date | None = None


class ReportsSummaryResponse(BaseModel):
    symptoms: SymptomSummary
    medications: MedicationSummary
    activity: ActivitySummary