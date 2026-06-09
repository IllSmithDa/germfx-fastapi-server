# Restyled Drug Detail PDF Export Service

from __future__ import annotations

from io import BytesIO
from typing import Iterable
from urllib.parse import unquote

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from sqlalchemy.orm import Session

from app.models import DrugDetail
from app.util.side_effects_parser import classify_side_effects


def _clean_text(value: str | None) -> str:
    if not value:
        return ""

    return " ".join(str(value).replace("\n", " ").split())


def _clean_name(value: str | None) -> str:
    if not value:
        return "Drug Detail"

    return unquote(str(value)).strip() or "Drug Detail"


def _as_list(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []

    return [
        _clean_text(value)
        for value in values
        if _clean_text(value)
    ]


def _add_metadata_card(story, metadata_lines, card_style):
    if not metadata_lines:
        return

    card_content = "<br/>".join(metadata_lines)

    table = Table(
        [[Paragraph(card_content, card_style)]],
        colWidths=[6.1 * inch],
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    story.append(table)
    story.append(Spacer(1, 0.22 * inch))


def _add_bullet_section(story, title, values, heading_style, body_style):
    if not values:
        return

    story.append(Paragraph(title, heading_style))
    story.append(Spacer(1, 0.08 * inch))

    for value in values:
        story.append(Paragraph(f"• {value}", body_style))
        story.append(Spacer(1, 0.05 * inch))

    story.append(Spacer(1, 0.2 * inch))


def _make_chip(label: str, chip_style):
    clean_label = label.replace("_", " ").title()

    return Paragraph(clean_label, chip_style)


def _add_side_effect_chips(
    story,
    *,
    title: str,
    values: list[str],
    heading_style,
    chip_style,
    background_color: str,
    border_color: str,
    text_color: str,
):
    if not values:
        return

    story.append(Paragraph(title, heading_style))
    story.append(Spacer(1, 0.06 * inch))

    chips = [
        _make_chip(value, chip_style)
        for value in values
    ]

    rows = []
    per_row = 3

    for i in range(0, len(chips), per_row):
        row = chips[i : i + per_row]

        while len(row) < per_row:
            row.append("")

        rows.append(row)

    table = Table(
        rows,
        colWidths=[1.95 * inch, 1.95 * inch, 1.95 * inch],
        hAlign="LEFT",
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(background_color)),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor(text_color)),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(border_color)),
        ("INNERGRID", (0, 0), (-1, -1), 5, colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(table)
    story.append(Spacer(1, 0.18 * inch))



def _add_warning_cards(
    story,
    values,
    heading_style,
    warning_style,
):
    if not values:
        return

    story.append(Paragraph("Safety Warnings", heading_style))
    story.append(Spacer(1, 0.08 * inch))

    for value in values:
        warning_table = Table(
            [[Paragraph(value, warning_style)]],
            colWidths=[6.1 * inch],
        )

        warning_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF2F2")),
            ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#FCA5A5")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))

        story.append(warning_table)
        story.append(Spacer(1, 0.08 * inch))

    story.append(Spacer(1, 0.18 * inch))



def build_drug_detail_pdf(
    db: Session,
    drug_detail_id: int,
) -> tuple[BytesIO, str]:
    detail = db.get(DrugDetail, drug_detail_id)

    if not detail:
        raise ValueError("Drug detail not found")

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.7 * inch,
        leftMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DrugTitle",
        parent=styles["Title"],
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#0F172A"),
        alignment=TA_CENTER,
    )

    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=0,
    )

    body_style = ParagraphStyle(
        "DrugBody",
        parent=styles["BodyText"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1E293B"),
    )

    muted_style = ParagraphStyle(
        "Muted",
        parent=body_style,
        textColor=colors.HexColor("#64748B"),
        fontSize=8,
        leading=11,
        alignment=TA_CENTER,
    )

    metadata_style = ParagraphStyle(
        "Metadata",
        parent=body_style,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#334155"),
    )

    chip_style = ParagraphStyle(
        "Chip",
        parent=body_style,
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0F172A"),
    )

    warning_style = ParagraphStyle(
        "WarningBody",
        parent=body_style,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#7F1D1D"),
    )

    name = _clean_name(detail.name)

    indications = _as_list(detail.purpose_or_indications)
    dosage = _as_list(detail.dosage_and_administration)

    adverse_reactions = _as_list(detail.adverse_reactions)

    boxed_warnings = _as_list(detail.boxed_warning)
    warnings_raw = _as_list(detail.warnings_raw)
    warnings_simple = _as_list(detail.warnings_simple)
    stop_using_warnings = _as_list(detail.stop_using_warnings)

    classified_effects = classify_side_effects(
        adverse_reactions=detail.adverse_reactions,
        warnings_raw=detail.warnings_raw,
        boxed_warning=detail.boxed_warning,
    )

    common_effects = classified_effects.get("common_or_likely", [])
    possible_effects = classified_effects.get("possible", [])
    serious_effects = classified_effects.get("serious", [])

    story = []

    story.append(Paragraph(name, title_style))
    story.append(Spacer(1, 0.08 * inch))

    story.append(
        Paragraph(
            "Drug detail summary generated from FDA/OpenFDA label information.",
            muted_style,
        )
    )

    story.append(Spacer(1, 0.24 * inch))

    metadata_lines = []

    if detail.brand_names:
        metadata_lines.append(
            f"<b>Brand names:</b> {', '.join(detail.brand_names[:8])}"
        )

    if detail.generic_names:
        metadata_lines.append(
            f"<b>Generic names:</b> {', '.join(detail.generic_names[:8])}"
        )

    if detail.manufacturer_names:
        metadata_lines.append(
            f"<b>Manufacturer:</b> {', '.join(detail.manufacturer_names[:5])}"
        )

    if detail.route:
        metadata_lines.append(
            f"<b>Route:</b> {', '.join(detail.route[:8])}"
        )

    if detail.effective_time:
        metadata_lines.append(
            f"<b>Label effective date:</b> {detail.effective_time.isoformat()}"
        )

    _add_metadata_card(
        story,
        metadata_lines,
        metadata_style,
    )

    _add_bullet_section(
        story,
        "Indications / Usage",
        indications,
        heading_style,
        body_style,
    )

    _add_bullet_section(
        story,
        "Dosage and Administration",
        dosage,
        heading_style,
        body_style,
    )

    if common_effects or possible_effects or serious_effects:
        story.append(
            Paragraph(
                "Reported Side Effects",
                heading_style,
            )
        )

        story.append(Spacer(1, 0.08 * inch))

        story.append(
            Paragraph(
                "Side effects are categorized using adverse reactions and warning sections from the FDA label.",
                muted_style,
            )
        )

        story.append(Spacer(1, 0.16 * inch))

        _add_side_effect_chips(
            story,
            title="Common or Likely",
            values=common_effects,
            heading_style=heading_style,
            chip_style=chip_style,
            background_color="#DBEAFE",
            border_color="#93C5FD",
            text_color="#1D4ED8",
        )

        _add_side_effect_chips(
            story,
            title="Possible",
            values=possible_effects,
            heading_style=heading_style,
            chip_style=chip_style,
            background_color="#FEF3C7",
            border_color="#FCD34D",
            text_color="#B45309",
        )

        _add_side_effect_chips(
            story,
            title="Serious",
            values=serious_effects,
            heading_style=heading_style,
            chip_style=chip_style,
            background_color="#FEE2E2",
            border_color="#FCA5A5",
            text_color="#B91C1C",
        )

    safety_values = []

    safety_values.extend(boxed_warnings)
    safety_values.extend(warnings_simple)
    safety_values.extend(stop_using_warnings)
    safety_values.extend(warnings_raw)

    deduped_safety_values = []
    seen = set()

    for value in safety_values:
        normalized = value.lower().strip()

        if normalized in seen:
            continue

        seen.add(normalized)
        deduped_safety_values.append(value)

    _add_warning_cards(
        story,
        deduped_safety_values,
        heading_style,
        warning_style,
    )

    if adverse_reactions:
        story.append(Paragraph("Original Adverse Reaction Text", heading_style))
        story.append(Spacer(1, 0.08 * inch))

        for value in adverse_reactions[:8]:
            story.append(Paragraph(value, body_style))
            story.append(Spacer(1, 0.06 * inch))

        story.append(Spacer(1, 0.16 * inch))

    story.append(
        Paragraph(
            "This PDF is intended for educational tracking and informational purposes only and should not replace professional medical advice.",
            muted_style,
        )
    )

    doc.build(story)

    buffer.seek(0)

    filename_safe_name = (
        name.lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace("\\", "-")
    )

    filename = (
        f"sidefx-drug-detail-{drug_detail_id}-{filename_safe_name[:40]}.pdf"
    )

    return buffer, filename


