from app.schemas.recalls import SymptomContextReportItem
from sqlalchemy import func, desc
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.schemas.reports import ActivitySummary, MedicationSummary, MedicationUsageReportItem, ReportsSummaryResponse, SymptomFrequencyReportItem, SymptomSummary
from app.db import get_db
from app.models import User, SymptomLog, UserMedication
from app.core.auth import get_authenticated_user
from typing import Optional, Tuple
from datetime import date, timedelta
from pydantic import BaseModel
from app.db import get_db


router = APIRouter()

def resolve_report_date_range(
    range: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Tuple[Optional[date], Optional[date]]:
    today = date.today()

    if start_date or end_date:
        return start_date, end_date

    if not range or range == "all":
        return None, None

    days_map = {
        "7d": 7,
        "30d": 30,
        "90d": 90,
    }

    days = days_map.get(range)
    if not days:
        raise HTTPException(status_code=400, detail="Invalid report range")

    return today - timedelta(days=days - 1), today

    
def calculate_total_days_used(
    start_date: Optional[date],
    end_date: Optional[date],
    is_active: bool,
) -> Optional[int]:
    if not start_date:
        return None

    effective_end = end_date or (date.today() if is_active else None)
    if not effective_end:
        return None

    delta = (effective_end - start_date).days + 1
    return max(delta, 0)


@router.get(
    "/symptom-frequency",
    response_model=list[SymptomFrequencyReportItem],
)
def get_symptom_frequency_report(
    limit: int = Query(10, ge=1, le=50),
    range: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    user_id = current_user.id

    resolved_start, resolved_end = resolve_report_date_range(
        range=range,
        start_date=start_date,
        end_date=end_date,
    )

    normalized_symptom = func.lower(func.trim(SymptomLog.symptom_text))

    query = (
        db.query(
            normalized_symptom.label("symptom_text"),
            func.count(SymptomLog.id).label("count"),
            func.avg(SymptomLog.severity).label("avg_severity"),
        )
        .filter(
            SymptomLog.user_id == user_id,
            SymptomLog.symptom_text.isnot(None),
            func.trim(SymptomLog.symptom_text) != "",
        )
    )

    if resolved_start:
        query = query.filter(SymptomLog.date >= resolved_start)

    if resolved_end:
        query = query.filter(SymptomLog.date <= resolved_end)

    results = (
        query.group_by(normalized_symptom)
        .order_by(desc("count"), normalized_symptom.asc())
        .limit(limit)
        .all()
    )

    return [
        SymptomFrequencyReportItem(
            symptom_text=row.symptom_text.title(),
            count=row.count,
            avg_severity=round(float(row.avg_severity), 1)
            if row.avg_severity is not None
            else None,
        )
        for row in results
    ]

@router.get(
    "/medication-usage",
    response_model=list[MedicationUsageReportItem],
)
def get_medication_usage_report(
    range: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    user_id = current_user.id

    resolved_start, resolved_end = resolve_report_date_range(
        range=range,
        start_date=start_date,
        end_date=end_date,
    )

    query = db.query(UserMedication).filter(UserMedication.user_id == user_id)

    if resolved_start:
        query = query.filter(
            (UserMedication.end_date.is_(None)) |
            (UserMedication.end_date >= resolved_start)
        )

    if resolved_end:
        query = query.filter(
            (UserMedication.start_date.is_(None)) |
            (UserMedication.start_date <= resolved_end)
        )

    medications = (
        query.order_by(
            UserMedication.is_active.desc(),
            UserMedication.start_date.desc().nullslast(),
            UserMedication.id.desc(),
        )
        .all()
    )

    results: list[MedicationUsageReportItem] = []

    for med in medications:
        raw_name = (
            med.name
            or getattr(getattr(med, "drug_index", None), "name", None)
            or "Unknown medication"
        )

        results.append(
            MedicationUsageReportItem(
                user_medication_id=med.id,
                drug_index_id=getattr(med, "drug_index_id", None),
                name=raw_name,
                nickname=getattr(med, "nickname", None),
                start_date=getattr(med, "start_date", None),
                end_date=getattr(med, "end_date", None),
                is_active=bool(getattr(med, "is_active", False)),
                total_days_used=calculate_total_days_used(
                    start_date=getattr(med, "start_date", None),
                    end_date=getattr(med, "end_date", None),
                    is_active=bool(getattr(med, "is_active", False)),
                ),
            )
        )

    return results
@router.get(
    "/summary",
    response_model=ReportsSummaryResponse,
)
def get_reports_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    user_id = current_user.id
    today = date.today()
    seven_days_ago = today - timedelta(days=6)
    previous_period_start = seven_days_ago - timedelta(days=7)
    previous_period_end = seven_days_ago - timedelta(days=1)

    # -------------------------
    # Symptoms: last 7 days
    # -------------------------
    recent_logs_count = (
        db.query(func.count(SymptomLog.id))
        .filter(
            SymptomLog.user_id == user_id,
            SymptomLog.date >= seven_days_ago,
            SymptomLog.date <= today,
        )
        .scalar()
        or 0
    )

    previous_logs_count = (
        db.query(func.count(SymptomLog.id))
        .filter(
            SymptomLog.user_id == user_id,
            SymptomLog.date >= previous_period_start,
            SymptomLog.date <= previous_period_end,
        )
        .scalar()
        or 0
    )

    change_vs_previous_7_days = recent_logs_count - previous_logs_count

    top_symptom_row = (
        db.query(
            func.lower(func.trim(SymptomLog.symptom_text)).label("symptom_name"),
            func.count(SymptomLog.id).label("count"),
        )
        .filter(
            SymptomLog.user_id == user_id,
            SymptomLog.date >= seven_days_ago,
            SymptomLog.date <= today,
            SymptomLog.symptom_text.isnot(None),
            func.trim(SymptomLog.symptom_text) != "",
        )
        .group_by(func.lower(func.trim(SymptomLog.symptom_text)))
        .order_by(desc("count"))
        .first()
    )

    avg_severity_recent = (
        db.query(func.avg(SymptomLog.severity))
        .filter(
            SymptomLog.user_id == user_id,
            SymptomLog.date >= seven_days_ago,
            SymptomLog.date <= today,
            SymptomLog.severity.isnot(None),
        )
        .scalar()
    )

    # -------------------------
    # Medications
    # -------------------------
    user_meds = (
        db.query(UserMedication)
        .filter(UserMedication.user_id == user_id)
        .all()
    )

    total_tracked = len(user_meds)
    active_count = sum(1 for med in user_meds if med.is_active)

    most_recent_started = None
    meds_with_start = [med for med in user_meds if med.start_date is not None]
    if meds_with_start:
        most_recent_started = max(meds_with_start, key=lambda med: med.start_date)

    longest_active = None
    longest_active_days = None

    meds_with_duration = []
    for med in user_meds:
        total_days = calculate_total_days_used(
            med.start_date,
            med.end_date,
            bool(med.is_active),
        )
        if total_days is not None:
            meds_with_duration.append((med, total_days))

    if meds_with_duration:
        longest_active, longest_active_days = max(
            meds_with_duration,
            key=lambda item: item[1],
        )

    # -------------------------
    # Activity
    # -------------------------
    last_symptom_log_date = (
        db.query(func.max(SymptomLog.date))
        .filter(SymptomLog.user_id == user_id)
        .scalar()
    )

    last_medication_start_date = (
        db.query(func.max(UserMedication.start_date))
        .filter(UserMedication.user_id == user_id)
        .scalar()
    )

    def get_med_name(med) -> str | None:
        if med is None:
            return None
        if getattr(med, "nickname", None):
            return med.nickname
        if getattr(med, "name", None):
            return med.name
        if getattr(med, "drug_index", None) and getattr(med.drug_index, "name", None):
            return med.drug_index.name
        if getattr(med, "drug_detail", None) and getattr(med.drug_detail, "name", None):
            return med.drug_detail.name
        return "Unknown medication"

    return ReportsSummaryResponse(
        symptoms=SymptomSummary(
            total_logs_last_7_days=recent_logs_count,
            top_symptom_name=top_symptom_row.symptom_name.title() if top_symptom_row else None,
            top_symptom_count=top_symptom_row.count if top_symptom_row else 0,
            avg_severity_last_7_days=round(float(avg_severity_recent), 1)
            if avg_severity_recent is not None
            else None,
            change_vs_previous_7_days=change_vs_previous_7_days,
        ),
        medications=MedicationSummary(
            total_tracked=total_tracked,
            active_count=active_count,
            longest_active_name=get_med_name(longest_active),
            longest_active_days=longest_active_days,
            most_recent_started_name=get_med_name(most_recent_started),
        ),
        activity=ActivitySummary(
            last_symptom_log_date=last_symptom_log_date,
            last_medication_start_date=last_medication_start_date,
        ),
    )

@router.get(
    "/symptom-context",
    response_model=list[SymptomContextReportItem],
)
def get_symptom_context_report( 
    limit: int = Query(10, ge=1, le=50),
    context_limit: int = Query(3, ge=1, le=10),
    range: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    user_id = current_user.id

    resolved_start, resolved_end = resolve_report_date_range(
        range=range,
        start_date=start_date,
        end_date=end_date,
    )

    normalized_symptom = func.lower(func.trim(SymptomLog.symptom_text))

    top_query = (
        db.query(
            normalized_symptom.label("normalized_symptom"),
            func.count(SymptomLog.id).label("count"),
        )
        .filter(
            SymptomLog.user_id == user_id,
            SymptomLog.symptom_text.isnot(None),
            func.trim(SymptomLog.symptom_text) != "",
        )
    )

    if resolved_start:
        top_query = top_query.filter(SymptomLog.date >= resolved_start)

    if resolved_end:
        top_query = top_query.filter(SymptomLog.date <= resolved_end)

    top_symptoms = (
        top_query
        .group_by(normalized_symptom)
        .order_by(desc("count"), normalized_symptom.asc())
        .limit(limit)
        .all()
    )

    results: list[SymptomContextReportItem] = []

    for row in top_symptoms:
        logs_query = (
            db.query(SymptomLog)
            .filter(
                SymptomLog.user_id == user_id,
                normalized_symptom == row.normalized_symptom,
            )
        )

        if resolved_start:
            logs_query = logs_query.filter(SymptomLog.date >= resolved_start)

        if resolved_end:
            logs_query = logs_query.filter(SymptomLog.date <= resolved_end)

        logs = (
            logs_query
            .order_by(
                SymptomLog.date.desc().nullslast(),
                SymptomLog.id.desc(),
            )
            .all()
        )

        triggers: list[str] = []
        trigger_seen: set[str] = set()

        strategies: list[str] = []
        strategy_seen: set[str] = set()

        for log in logs:
            trigger = (getattr(log, "possible_trigger", None) or "").strip()
            if trigger:
                key = trigger.lower()
                if key not in trigger_seen:
                    trigger_seen.add(key)
                    triggers.append(trigger)

            strategy = (getattr(log, "management_strategy", None) or "").strip()
            if strategy:
                key = strategy.lower()
                if key not in strategy_seen:
                    strategy_seen.add(key)
                    strategies.append(strategy)

            if len(triggers) >= context_limit and len(strategies) >= context_limit:
                break

        if triggers or strategies:
            results.append(
                SymptomContextReportItem(
                    symptom_text=row.normalized_symptom.title(),
                    possible_triggers=triggers[:context_limit],
                    management_strategies=strategies[:context_limit],
                )
            )

    return results