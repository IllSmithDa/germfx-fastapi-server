# app/routers/symptom_logs.py
from typing import Optional, List
from datetime import date
from app.models import User
from fastapi import APIRouter, Depends, HTTPException, Query, status, Body
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from app.core.auth import get_authenticated_user
from app.db import get_db
from app.models import SymptomLog, UserMedication, Symptom
from app.schemas.symptoms import SymptomLogCreate, SymptomLogOut, SymptomLogList, SymptomLogUpdate

router = APIRouter(tags=["symptom-logs"])  # ← removed prefix here

@router.post("", response_model=SymptomLogOut, status_code=status.HTTP_201_CREATED)
def create_symptom_log(
    payload: SymptomLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    user = db.get(User, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.user_medication_id is not None and not db.get(UserMedication, payload.user_medication_id):
        raise HTTPException(status_code=404, detail="User Medication not found")

    if payload.symptom_id is not None and not db.get(Symptom, payload.symptom_id):
        raise HTTPException(status_code=404, detail="Symptom term not found")

    row = SymptomLog(
        user_id=current_user.id,
        user_medication_id=payload.user_medication_id,
        symptom_id=payload.symptom_id,
        symptom_text=payload.symptom_text,
        date=payload.date,
        details=payload.details,
        severity=payload.severity,
        possible_trigger=payload.possible_trigger,
        management_strategy=payload.management_strategy,
    )
    db.add(row)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not save symptom log") from exc

    row = db.execute(
        select(SymptomLog)
        .where(SymptomLog.id == row.id)
        .options(
            selectinload(SymptomLog.user_medication),
            selectinload(SymptomLog.symptom),
        )
    ).unique().scalar_one()
    return row


@router.get("", response_model=SymptomLogList)
def list_symptom_logs(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    q: Optional[str] = Query(None, description="Search symptom_text or details"),
    min_severity: Optional[int] = Query(None, ge=1, le=10),
    user_medication_id: Optional[int] = Query(None, ge=1),
    symptom_id: Optional[int] = Query(None, ge=1),
    sort: str = Query("latest", description="latest | oldest | severity_low | severity_high"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    if not db.get(User, current_user.id):
        raise HTTPException(status_code=404, detail="User not found")

    sort = sort if sort in {
        "latest",
        "oldest",
        "severity_low",
        "severity_high",
    } else "latest"

    stmt = (
        select(SymptomLog)
        .where(SymptomLog.user_id == current_user.id)
        .options(
            selectinload(SymptomLog.user_medication),
            selectinload(SymptomLog.symptom),
        )
    )

    if date_from:
        stmt = stmt.where(SymptomLog.date >= date_from)
    if date_to:
        stmt = stmt.where(SymptomLog.date <= date_to)
    if min_severity is not None:
        stmt = stmt.where(SymptomLog.severity >= min_severity)
    if user_medication_id is not None:
        stmt = stmt.where(SymptomLog.user_medication_id == user_medication_id)
    if symptom_id is not None:
        stmt = stmt.where(SymptomLog.symptom_id == symptom_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                SymptomLog.symptom_text.ilike(like),
                SymptomLog.details.ilike(like),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    if sort == "oldest":
        stmt = stmt.order_by(
            SymptomLog.date.asc(),
            SymptomLog.created_at.asc(),
            SymptomLog.id.asc(),
        )
    elif sort == "severity_low":
        stmt = stmt.order_by(
            SymptomLog.severity.asc().nullslast(),
            SymptomLog.date.desc(),
            SymptomLog.created_at.desc(),
            SymptomLog.id.desc(),
        )
    elif sort == "severity_high":
        stmt = stmt.order_by(
            SymptomLog.severity.desc().nullslast(),
            SymptomLog.date.desc(),
            SymptomLog.created_at.desc(),
            SymptomLog.id.desc(),
        )
    else:
        stmt = stmt.order_by(
            SymptomLog.date.desc(),
            SymptomLog.created_at.desc(),
            SymptomLog.id.desc(),
        )

    rows: List[SymptomLog] = db.execute(
        stmt.limit(limit).offset(offset)
    ).unique().scalars().all()

    return {
        "items": rows,
        "total": total,
    }
    

@router.post(
    "/bulk",
    response_model=SymptomLogList,
    status_code=status.HTTP_201_CREATED,
)
def create_symptom_logs_bulk(
    payloads: List[SymptomLogCreate] = Body(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    print("Bulk symptom logs received:", payloads)

    # Ensure user exists once
    user = db.get(User, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Optional: validate referenced IDs in batch (faster than per-row db.get)
    med_ids = {p.user_medication_id for p in payloads if p.user_medication_id is not None}
    sym_ids = {p.symptom_id for p in payloads if p.symptom_id is not None}

    if med_ids:
        found = set(db.execute(select(UserMedication.id).where(UserMedication.id.in_(med_ids))).scalars().all())
        missing = sorted(med_ids - found)
        if missing:
            raise HTTPException(status_code=404, detail=f"Medication not found: {missing}")

    if sym_ids:
        found = set(db.execute(select(Symptom.id).where(Symptom.id.in_(sym_ids))).scalars().all())
        missing = sorted(sym_ids - found)
        if missing:
            raise HTTPException(status_code=404, detail=f"Symptom term not found: {missing}")

    rows: List[SymptomLog] = []
    for p in payloads:
        rows.append(
            SymptomLog(
                user_id=current_user.id,
                user_medication_id=p.user_medication_id,
                symptom_id=p.symptom_id,
                symptom_text=p.symptom_text,
                date=p.date,
                details=p.details,
                severity=p.severity,
                possible_trigger=p.possible_trigger,
                management_strategy=p.management_strategy,
            )
        )

    db.add_all(rows)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not save symptom logs") from exc

    # Re-fetch with relationships loaded (matches your single-create behavior)
    ids = [r.id for r in rows]
    saved = (
        db.execute(
            select(SymptomLog)
            .where(SymptomLog.id.in_(ids))
            .options(
                selectinload(SymptomLog.user_medication),
                selectinload(SymptomLog.symptom),
            )
            .order_by(SymptomLog.date.desc(), SymptomLog.id.desc())
        )
        .unique()
        .scalars()
        .all()
    )

    return {"items": saved, "total": len(saved)}


@router.patch(
    "/update-symptom/{symptom_log_id}",
    response_model=SymptomLogOut,
    status_code=status.HTTP_200_OK,
)
def update_symptom_log(
    symptom_log_id: int,
    payload: SymptomLogUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):

    # Ensure user exists
    user = db.get(User, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Ensure log exists and belongs to user
    inst = db.get(SymptomLog, symptom_log_id)

    if not inst or inst.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Symptom log not found")

    # Convert payload -> dict
    data = payload.model_dump(exclude_unset=True)

    # Apply updates dynamically
    for k, v in data.items():
        setattr(inst, k, v)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"IntegrityError: {getattr(exc, 'orig', exc)}",
        )

    db.refresh(inst)

    return inst

@router.delete(
    "/delete-symptom/{symptom_log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_symptom_log(
    symptom_log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    # Ensure user exists
    user = db.get(User, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Ensure symptom log exists and belongs to this user
    inst = db.get(SymptomLog, symptom_log_id)
    if not inst or inst.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Symptom log not found")

    db.delete(inst)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not delete symptom log") from exc

    return

@router.get(
    "/recent-names",
    response_model=List[str],
)
def list_recent_symptom_names(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
     current_user: User = Depends(get_authenticated_user),
):
    # Ensure user exists
    user = db.get(User, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Pull newest symptom logs first
    rows = db.execute(
        select(SymptomLog.symptom_text)
        .where(SymptomLog.user_id == current_user.id)
        .order_by(SymptomLog.date.desc(), SymptomLog.id.desc())
    ).scalars().all()

    # Keep last distinct names only
    seen = set()
    result: List[str] = []

    for raw_name in rows:
        name = (raw_name or "").strip()
        if not name:
            continue

        key = name.lower()
        if key in seen:
            continue

        seen.add(key)
        result.append(name)

        if len(result) >= limit:
            break

    return result

@router.get("/last-medication-id")
def get_last_used_medication_id(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    if current_user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    row = (
        db.query(SymptomLog.user_medication_id)
        .filter(
            SymptomLog.user_id == current_user.id,
            SymptomLog.user_medication_id.isnot(None),
        )
        .order_by(
            SymptomLog.date.desc(),
            SymptomLog.created_at.desc(),
            SymptomLog.id.desc(),
        )
        .first()
    )

    return {
        "user_medication_id": row[0] if row else None,
    }