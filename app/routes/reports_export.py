# app/routes/reports_export.py
from app.services.reports_export import build_user_report_pdf
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db

router = APIRouter()

@router.get("/{user_id}/export/pdf")
def export_report_pdf(
    user_id: int,
    days: int = Query(30, ge=1, le=365),
    top_symptom_limit: int = Query(5, ge=1, le=15),
    db: Session = Depends(get_db),
):
    try:
        pdf_buffer, filename = build_user_report_pdf(
            db=db,
            user_id=user_id,
            days=days,
            top_symptom_limit=top_symptom_limit,
        )

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF: {e}",
        )