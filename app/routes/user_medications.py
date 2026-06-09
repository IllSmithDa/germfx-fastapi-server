# app/routers/user_medications.py
import traceback
from app.core.auth import get_authenticated_user
from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, or_
from app.db import get_db
from app import models
from app.schemas.user_medication import UserMedicationList, UserMedicationListItem, UserMedicationCreate, UserMedicationOut, UserMedicationContainsOut
from app.schemas.user_medication import UserMedicationUpdate

router = APIRouter(tags=["user-medications"])  # ← removed prefix here

@router.get("", response_model=UserMedicationList)
def list_user_medications(
    active: bool | None = Query(None, description="Filter by active status"),
    q: str | None = Query(None, description="Search by drug name, normalized name, nickname"),
    sort: str = Query("latest", description="latest | oldest | alphabetical | reverse_alphabetical"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_authenticated_user),
):
    if not db.get(models.User, current_user.id):
        raise HTTPException(status_code=404, detail="User not found")

    sort = sort if sort in {
        "latest",
        "oldest",
        "alphabetical",
        "reverse_alphabetical",
    } else "latest"

    stmt = (
        select(models.UserMedication)
        .where(models.UserMedication.user_id == current_user.id)
        .options(selectinload(models.UserMedication.drug_detail))
    )

    if active is not None:
        stmt = stmt.where(models.UserMedication.is_active == active)

    if q:
        like = f"%{q}%"
        stmt = stmt.join(models.UserMedication.drug_detail).where(
            or_(
                models.DrugDetail.name.ilike(like),
                models.DrugDetail.normalized_name.ilike(like),
                models.UserMedication.name.ilike(like),
                models.UserMedication.nickname.ilike(like),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    if sort == "oldest":
        stmt = stmt.order_by(
            models.UserMedication.created_at.asc(),
            models.UserMedication.id.asc(),
        )
    elif sort == "alphabetical":
        stmt = stmt.order_by(
            func.lower(
                func.coalesce(
                    models.UserMedication.nickname,
                    models.UserMedication.name,
                    models.DrugDetail.name,
                )
            ).asc(),
            models.UserMedication.id.desc(),
        ).join(models.UserMedication.drug_detail, isouter=True)
    elif sort == "reverse_alphabetical":
        stmt = stmt.order_by(
            func.lower(
                func.coalesce(
                    models.UserMedication.nickname,
                    models.UserMedication.name,
                    models.DrugDetail.name,
                )
            ).desc(),
            models.UserMedication.id.desc(),
        ).join(models.UserMedication.drug_detail, isouter=True)
    else:
        stmt = stmt.order_by(
            models.UserMedication.created_at.desc(),
            models.UserMedication.id.desc(),
        )

    rows = db.execute(stmt.limit(limit).offset(offset)).unique().scalars().all()
    items = [UserMedicationListItem.model_validate(r, from_attributes=True) for r in rows]

    return UserMedicationList(items=items, total=total)

@router.post("", 
response_model=UserMedicationOut, status_code=status.HTTP_201_CREATED)
def create_user_medication(
    payload: UserMedicationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_authenticated_user),
):
    print(current_user.id)
    # ensure user exists
    user = db.get(models.User, current_user.id)
    if not user:
        raise HTTPException(status_code=422, detail="User not found")

    # ensure medication exists
    med_index = db.get(models.DrugIndex, payload.drug_index_id)
    if not med_index:
        raise HTTPException(status_code=422, detail="Drug Index not found")
                            
    med_detail = db.get(models.DrugDetail, payload.drug_detail_id)
    if not med_detail:
        raise HTTPException(status_code=422, detail="Drug Detail not found")
    

    # basic date sanity
    if payload.end_date and payload.start_date and payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="end_date cannot be before start_date")

    inst = models.UserMedication(
        user_id=current_user.id,
        drug_detail_id=payload.drug_detail_id,
        drug_index_id=payload.drug_index_id,
        name=payload.name,
        nickname=payload.nickname,
        dosage=payload.dosage,
        route=payload.route,
        frequency=payload.frequency,
        start_date=payload.start_date,
        end_date=payload.end_date,
        is_active=True if payload.is_active is None else payload.is_active,
        notes=payload.notes,
        tracking_purpose=payload.tracking_purpose,
    )
    db.add(inst)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # print("DB IntegrityError:", repr(exc))
        # print("Orig:", repr(getattr(exc, "orig", None)))
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"IntegrityError: {getattr(exc, 'orig', exc)}")
    except Exception as exc:
        db.rollback()
        # print("DB Exception:", repr(exc))
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"DB error: {exc}")
    
    db.refresh(inst)

    return UserMedicationOut(
        id=inst.id,
        user_id=inst.user_id,
        drug_detail_id=inst.drug_detail_id,
        drug_index_id=inst.drug_index_id,
        name=inst.name,
        dosage=inst.dosage,
        route=inst.route,
        frequency=inst.frequency,
        start_date=inst.start_date,
        end_date=inst.end_date,
        is_active=inst.is_active,
        notes=inst.notes,
        nickname=inst.nickname,
        created_at=inst.created_at,
        tracking_purpose=payload.tracking_purpose,
    )


# --- NEW: check if user has a medication by drug_detail_id ---+
@router.get(
    "/contains",
    response_model=UserMedicationContainsOut,
    status_code=status.HTTP_200_OK,
)
def contains_user_medication(
    drug_index_id: int = Query(..., description="drug index id to check"),
    only_active: bool = Query(False, description="If true, only match active meds"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_authenticated_user),
):
    
    # print(f"contains_user_medication called with user_id={user_id}, drug_index_id={drug_index_id}, only_active={only_active}")
    # Ensure user exists (optional but nice)
    user = db.get(models.User, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    stmt = select(models.UserMedication).where(
        models.UserMedication.user_id == current_user.id,
        models.UserMedication.drug_index_id == drug_index_id,
    )

    if only_active:
        stmt = stmt.where(models.UserMedication.is_active == True)  # noqa: E712

    inst = db.execute(stmt).scalars().first()

    

    return UserMedicationContainsOut(
        added=inst is not None,
        user_medication_id=inst.id if inst else None,
    )


@router.delete(
    "/{user_medication_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_user_medication(
    user_medication_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_authenticated_user),
):
    # Ensure user exists
    user = db.get(models.User, current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Ensure the user-medication instance exists AND belongs to this user
    inst = db.get(models.UserMedication, user_medication_id)
    if not inst or inst.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="User medication not found")

    db.delete(inst)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not delete user medication") from exc

    # 204 No Content => return nothing
    return

# --- NEW: delete by drug_detail_id and user Id ---
@router.delete(
    "/by-detail/{drug_detail_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_user_medication_by_detail(
    drug_detail_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_authenticated_user),
):
    # print(f"delete_user_medication_by_detail called with user_id={user_id}, drug_detail_id={drug_detail_id}")
    inst = (
        db.query(models.UserMedication)
        .filter(
            models.UserMedication.user_id == current_user.id,
            models.UserMedication.drug_detail_id == drug_detail_id,
        )
        .first()
    )

    if not inst:
        raise HTTPException(status_code=422, detail="Medication not found")

    db.delete(inst)
    db.commit()


@router.patch(
    "/{user_medication_id}",
    response_model=UserMedicationOut,
    status_code=status.HTTP_200_OK,
)
def update_user_medication(
    user_medication_id: int,
    payload: UserMedicationUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_authenticated_user),
):
    print(f"check frequency: {payload.frequency}")

    # Ensure user exists
    user = db.get(models.User, current_user.id)
    if not user:    
        raise HTTPException(status_code=404, detail="User not found")

    # Ensure the row exists and belongs to user
    inst = db.get(models.UserMedication, user_medication_id)
    if not inst or inst.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="User medication not found")

    # Apply partial updates
    data = payload.model_dump(exclude_unset=True)

    # Basic date sanity if either date is being updated
    new_start = data.get("start_date", inst.start_date)
    new_end = data.get("end_date", inst.end_date)
    if new_end and new_start and new_end < new_start:
        raise HTTPException(status_code=422, detail="end_date cannot be before start_date")

    for k, v in data.items():
        setattr(inst, k, v)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"IntegrityError: {getattr(exc, 'orig', exc)}")

    db.refresh(inst)

    print(f"returning updated medication with frequency: {inst.frequency}")

    return UserMedicationOut(
        id=inst.id,
        user_id=inst.user_id,
        drug_detail_id=inst.drug_detail_id,
        drug_index_id=inst.drug_index_id,
        name=inst.name,
        dosage=inst.dosage,
        route=inst.route,
        frequency=inst.frequency,
        start_date=inst.start_date,
        end_date=inst.end_date,
        is_active=inst.is_active,
        notes=inst.notes,
        nickname=inst.nickname,
        created_at=inst.created_at,
        tracking_purpose=payload.tracking_purpose,
    )