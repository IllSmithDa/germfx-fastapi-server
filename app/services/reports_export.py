# app/services/report_export.py
from __future__ import annotations

from io import BytesIO
from datetime import datetime, timedelta, timezone
from collections import Counter
from typing import Tuple
from urllib.parse import unquote

from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.models import UserMedication, SymptomLog


UPPERCASE_TOKENS = {"hcl", "er", "xr", "sr", "mg", "ml", "otc", "ndc", "usp"}
def _recent_unique_context_for_symptom(
    logs: list[SymptomLog],
    symptom_name: str,
    *,
    limit: int = 3,
) -> tuple[list[str], list[str]]:
    normalized = symptom_name.strip().lower()

    matching_logs = [
        log
        for log in logs
        if (log.symptom_text or "").strip().lower() == normalized
    ]

    triggers: list[str] = []
    trigger_seen: set[str] = set()

    strategies: list[str] = []
    strategy_seen: set[str] = set()

    for log in matching_logs:
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

        if len(triggers) >= limit and len(strategies) >= limit:
            break

    return triggers[:limit], strategies[:limit]

def format_pdf_drug_name(value: str | None) -> str:
    """
    Make drug names more readable in the PDF:
    - decode URL-encoded strings like %20
    - normalize whitespace
    - capitalize first letter of each word
    - preserve common abbreviations like HCL / ER / MG
    """
    if not value:
        return "Unknown"

    decoded = unquote(str(value)).strip()
    if not decoded:
        return "Unknown"

    words = decoded.split()
    out: list[str] = []

    for word in words:
        lower = word.lower()

        if lower in UPPERCASE_TOKENS:
            out.append(lower.upper())
            continue

        # preserve slash-separated terms a bit more cleanly
        if "/" in word:
            slash_parts = []
            for part in word.split("/"):
                p = part.strip()
                if not p:
                    slash_parts.append(p)
                elif p.lower() in UPPERCASE_TOKENS:
                    slash_parts.append(p.upper())
                else:
                    slash_parts.append(p[:1].upper() + p[1:].lower())
            out.append("/".join(slash_parts))
            continue

        out.append(lower[:1].upper() + lower[1:])

    return " ".join(out)


def build_user_report_pdf(
    db: Session,
    user_id: int,
    days: int = 30,
    top_symptom_limit: int = 5,
) -> Tuple[BytesIO, str]:
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.7 * inch,
        leftMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
    )

    top_symptom_limit = max(1, min(int(top_symptom_limit or 5), 15))
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    heading_style = styles["Heading2"]
    body_style = ParagraphStyle(
        "BodySmall",
        parent=styles["BodyText"],
        fontSize=9,
        leading=12,
        spaceAfter=0,
    )
    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=body_style,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1F2937"),
    )
    muted_style = ParagraphStyle(
        "Muted",
        parent=body_style,
        textColor=colors.HexColor("#6B7280"),
        fontSize=9,
        leading=12,
    )

    story = []

    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days)

    medications = (
        db.query(UserMedication)
        .filter(UserMedication.user_id == user_id)
        .order_by(UserMedication.created_at.desc())
        .all()
    )

    logs = (
        db.query(SymptomLog)
        .filter(
            SymptomLog.user_id == user_id,
            SymptomLog.date >= start_date,
        )
        .order_by(SymptomLog.date.desc())
        .all()
    )

    severity_values = [log.severity for log in logs if log.severity is not None]
    avg_severity = (
        round(sum(severity_values) / len(severity_values), 1)
        if severity_values
        else None
    )

    symptom_counter = Counter(
        (log.symptom_text or "").strip()
        for log in logs
        if (log.symptom_text or "").strip()
    )
    top_symptoms = symptom_counter.most_common(top_symptom_limit)

    # Header
    story.append(Paragraph("SideFX Health Report", title_style))
    story.append(
        Paragraph(
            f"Generated on {today.strftime('%B %d, %Y')} - covering the last {days} days",
            muted_style,
        )
    )
    story.append(Spacer(1, 0.25 * inch))

    # Medication Summary
    story.append(Paragraph("Medication Summary", heading_style))
    story.append(Spacer(1, 0.1 * inch))

    med_rows = [[
        Paragraph("Medication", table_header_style),
        Paragraph("Dosage", table_header_style),
        Paragraph("Frequency", table_header_style),
        Paragraph("Status", table_header_style),
    ]]

    if medications:
        for med in medications[:15]:
            med_display_name = format_pdf_drug_name(med.nickname or med.name)

            med_rows.append([
                Paragraph(med_display_name, body_style),
                Paragraph(med.dosage or "-", body_style),
                Paragraph(med.frequency or "-", body_style),
                Paragraph("Active" if med.is_active else "Inactive", body_style),
            ])
    else:
        med_rows.append([
            Paragraph("No medications found", body_style),
            Paragraph("-", body_style),
            Paragraph("-", body_style),
            Paragraph("-", body_style),
        ])

    med_table = Table(
        med_rows,
        colWidths=[3.0 * inch, 1.0 * inch, 1.2 * inch, 0.8 * inch],
        repeatRows=1,
    )
    med_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF2FF")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(med_table)
    story.append(Spacer(1, 0.3 * inch))

    # Symptom Summary
    story.append(Paragraph("Symptom Summary", heading_style))
    story.append(Spacer(1, 0.1 * inch))

    summary_lines = [
        f"Total symptom logs: {len(logs)}",
        f"Average severity: {avg_severity if avg_severity is not None else '-'}",
    ]

    if top_symptoms:
        summary_lines.append(
            f"Top {top_symptom_limit} symptoms: " + ", ".join(
                f"{name} ({count})" for name, count in top_symptoms
            )
        )

    for line in summary_lines:
        story.append(Paragraph(line, body_style))
        story.append(Spacer(1, 0.05 * inch))

    story.append(Spacer(1, 0.2 * inch))


    # Symptoms Context Sectionc
    context_rows = [[
        Paragraph("Symptom", table_header_style),
        Paragraph("Possible Triggers", table_header_style),
        Paragraph("Management Strategies", table_header_style),
    ]]
    
    for symptom_name, _count in top_symptoms:
        triggers, strategies = _recent_unique_context_for_symptom(
            logs,
            symptom_name,
            limit=3,
        )
    
        if not triggers and not strategies:
            continue
        
        context_rows.append([
            Paragraph(symptom_name, body_style),
            Paragraph("<br/>".join(triggers) if triggers else "-", body_style),
            Paragraph("<br/>".join(strategies) if strategies else "-", body_style),
        ])
    
    if len(context_rows) > 1:
        story.append(Paragraph("Recent Symptom Context", heading_style))
        story.append(Spacer(1, 0.1 * inch))
        story.append(
            Paragraph(
                "Recent possible triggers and management strategies for your top logged symptoms.",
                muted_style,
            )
        )
        story.append(Spacer(1, 0.1 * inch))
    
        context_table = Table(
            context_rows,
            colWidths=[1.6 * inch, 2.2 * inch, 2.2 * inch],
            repeatRows=1,
        )
        context_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
    
        story.append(context_table)
        story.append(Spacer(1, 0.3 * inch))

    # Recent Symptom Logs
    story.append(Paragraph("Recent Symptom Logs", heading_style))
    story.append(Spacer(1, 0.1 * inch))

    log_rows = [[
        Paragraph("Date", table_header_style),
        Paragraph("Symptom", table_header_style),
        Paragraph("Severity", table_header_style),
        Paragraph("Medication", table_header_style),
    ]]

    if logs:
        for log in logs[:40]:
            raw_medication_name = "-"
            if getattr(log, "user_medication", None):
                raw_medication_name = (
                    getattr(log.user_medication, "nickname", None)
                    or getattr(log.user_medication, "name", None)
                    or "-"
                )

            medication_name = format_pdf_drug_name(raw_medication_name)

            log_rows.append([
                Paragraph(log.date.strftime("%Y-%m-%d") if log.date else "-", body_style),
                Paragraph(log.symptom_text or "-", body_style),
                Paragraph(str(log.severity) if log.severity is not None else "-", body_style),
                Paragraph(medication_name, body_style),
            ])
    else:
        log_rows.append([
            Paragraph("-", body_style),
            Paragraph("No symptom logs found", body_style),
            Paragraph("-", body_style),
            Paragraph("-", body_style),
        ])

    log_table = Table(
        log_rows,
        colWidths=[1.1 * inch, 2.0 * inch, 0.7 * inch, 2.2 * inch],
        repeatRows=1,
    )
    log_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(log_table)
    story.append(Spacer(1, 0.3 * inch))

    # Footer note
    story.append(
        Paragraph(
            "This report is intended for personal tracking only and is not a substitute for medical advice.",
            muted_style,
        )
    )

    doc.build(story)
    buffer.seek(0)

    filename = f"sidefx-report-user-{user_id}-{today.isoformat()}.pdf"
    return buffer, filename