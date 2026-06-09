# app/routes/drug_detail_export.py

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.core.auth import get_authenticated_user
from app.models import User
from app.services.drug_detail_export import build_drug_detail_pdf

router = APIRouter(tags=["drug-detail-export"])


@router.get("/{drug_detail_id}/export/pdf")
def export_drug_detail_pdf(
    drug_detail_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    try:
        pdf_buffer, filename = build_drug_detail_pdf(
            db=db,
            drug_detail_id=drug_detail_id,
        )

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
        )

    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate drug detail PDF: {exc}",
        ) from exc