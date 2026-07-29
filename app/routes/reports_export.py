# app/routes/reports_export.py

from app import models
from app.core.auth import get_authenticated_user
from app.db import get_db
from app.services.reports_export import build_user_report_pdf
from app.services.usage_limits import enforce_and_increment_usage_counter
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/{user_id}/export/pdf")
def export_report_pdf(
    user_id: int,
    days: int = Query(30, ge=1, le=365),
    top_symptom_limit: int = Query(5, ge=1, le=15),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_authenticated_user),
):
    """
    Generate and download the authenticated user's PDF report.

    Free users are limited through the counter-based ``pdf_downloads``
    usage feature. Admin and Plus users are treated as unlimited by the
    shared usage-limit service.
    """

    user = db.get(models.User, current_user.id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "You are not allowed to export another user's report.",
                "code": "REPORT_EXPORT_FORBIDDEN",
            },
        )

    try:
        # Build the report first so a failed PDF generation does not consume
        # one of the user's allowed downloads.
        pdf_buffer, filename = build_user_report_pdf(
            db=db,
            user_id=user.id,
            days=days,
            top_symptom_limit=top_symptom_limit,
        )

        # Counter-based features do not naturally create a database row.
        # This enforces the configured free limit and increments the counter
        # only for limited/free users.
        usage = enforce_and_increment_usage_counter(
            db=db,
            user=user,
            feature_key="pdf_downloads",
            increment_by=1,
            label="PDF downloads",
        )

        db.commit()

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Usage-Feature": "pdf_downloads",
            "X-Usage-Unlimited": str(bool(usage["unlimited"])).lower(),
        }

        if not usage["unlimited"]:
            headers.update(
                {
                    "X-Usage-Count": str(usage["current_count"]),
                    "X-Usage-Limit": str(usage["limit"]),
                    "X-Usage-Remaining": str(usage["remaining"]),
                }
            )

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers=headers,
        )

    except HTTPException:
        # Preserve structured 403 usage-limit responses and any other
        # intentional HTTP errors raised inside the route.
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF: {exc}",
        ) from exc