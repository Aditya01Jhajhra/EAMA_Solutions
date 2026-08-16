from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_HEADER_BLUE = colors.HexColor("#1F4E78")
_LIGHT_GREY = colors.HexColor("#F2F2F2")
_BORDER_GREY = colors.HexColor("#BFBFBF")
_HIGH_RED = colors.HexColor("#C00000")


def _build_styles() -> dict:
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "EAMATitle",
            parent=base["Title"],
            fontSize=20,
            textColor=_HEADER_BLUE,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "EAMASubtitle",
            parent=base["Normal"],
            fontSize=11,
            textColor=colors.grey,
            spaceAfter=18,
        ),
        "section": ParagraphStyle(
            "EAMASection",
            parent=base["Heading2"],
            fontSize=14,
            textColor=_HEADER_BLUE,
            spaceBefore=18,
            spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "EAMABody",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
        ),
        "alert_summary": ParagraphStyle(
            "EAMAAlertSummary",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            spaceAfter=4,
        ),
        "cell": ParagraphStyle(
            "EAMACell",
            parent=base["Normal"],
            fontSize=8.5,
            leading=11,
        ),
    }
    return styles


def _summary_table(
    findings: pd.DataFrame,
    business_alerts: pd.DataFrame,
    styles: dict,
) -> Table:
    severity_counts = (
        findings["severity"]
        .value_counts()
        .reindex(["high", "medium", "low"], fill_value=0)
    )

    rows = [
        [
            Paragraph("<b>Metric</b>", styles["cell"]),
            Paragraph("<b>Value</b>", styles["cell"]),
        ],
        ["Report generated", date.today().isoformat()],
        ["Total anomalies detected", f"{len(findings):,}"],
        ["High-priority anomalies", f"{int(severity_counts['high']):,}"],
        ["Medium-priority anomalies", f"{int(severity_counts['medium']):,}"],
        ["Low-priority anomalies", f"{int(severity_counts['low']):,}"],
        [
            "Consolidated business alerts",
            f"{len(business_alerts):,}",
        ],
    ]

    table = Table(rows, colWidths=[3.2 * inch, 3.2 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_GREY]),
                ("GRID", (0, 0), (-1, -1), 0.5, _BORDER_GREY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _business_alert_blocks(
    business_alerts: pd.DataFrame, styles: dict
) -> list:
    if business_alerts.empty:
        return [
            Paragraph(
                "No high-priority business alerts were found in this "
                "reporting period.",
                styles["body"],
            )
        ]

    blocks: list = []
    for position, alert in enumerate(business_alerts.itertuples(), start=1):
        header = Paragraph(
            f"<b>Alert {position}: {alert.dimension_value} "
            f"({alert.dimension}) — week ending {alert.date}</b>",
            styles["alert_summary"],
        )
        body = Paragraph(alert.summary, styles["body"])
        spacer = Spacer(1, 10)
        blocks.extend([header, body, spacer])
    return blocks


def _findings_table(findings: pd.DataFrame, styles: dict) -> Table:
    display_columns = [
        "date",
        "dimension_value",
        "metric",
        "relative_change",
        "severity",
    ]

    header_row = [
        Paragraph("<b>Date</b>", styles["cell"]),
        Paragraph("<b>Segment</b>", styles["cell"]),
        Paragraph("<b>Metric</b>", styles["cell"]),
        Paragraph("<b>Change</b>", styles["cell"]),
        Paragraph("<b>Severity</b>", styles["cell"]),
    ]

    rows = [header_row]

    sorted_findings = findings.sort_values(
        "severity",
        key=lambda column: column.map({"high": 0, "medium": 1, "low": 2}),
    )

    for finding in sorted_findings[display_columns].itertuples(index=False):
        change_pct = f"{finding.relative_change * 100:+.1f}%"
        severity_style = ParagraphStyle(
            "sev",
            parent=styles["cell"],
            textColor=_HIGH_RED if finding.severity == "high" else colors.black,
            fontName="Helvetica-Bold" if finding.severity == "high" else "Helvetica",
        )
        rows.append(
            [
                Paragraph(str(finding.date)[:10], styles["cell"]),
                Paragraph(str(finding.dimension_value), styles["cell"]),
                Paragraph(str(finding.metric).replace("_", " "), styles["cell"]),
                Paragraph(change_pct, styles["cell"]),
                Paragraph(finding.severity, severity_style),
            ]
        )

    table = Table(
        rows,
        colWidths=[0.95 * inch, 1.5 * inch, 1.55 * inch, 0.9 * inch, 0.9 * inch],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_GREY]),
                ("GRID", (0, 0), (-1, -1), 0.5, _BORDER_GREY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def create_pdf_report(
    findings: pd.DataFrame,
    business_alerts: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    """Create a stakeholder-ready PDF report for EAMA anomaly findings."""
    report_path = Path(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    styles = _build_styles()

    doc = SimpleDocTemplate(
        str(report_path),
        pagesize=letter,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
    )

    story: list = []

    story.append(Paragraph("EAMA Weekly Alert Report", styles["title"]))
    story.append(
        Paragraph(
            f"Automated anomaly monitoring summary — "
            f"generated {date.today().strftime('%d %B %Y')}",
            styles["subtitle"],
        )
    )

    story.append(Paragraph("Summary", styles["section"]))
    story.append(_summary_table(findings, business_alerts, styles))

    story.append(Paragraph("Business Alerts", styles["section"]))
    story.extend(_business_alert_blocks(business_alerts, styles))

    story.append(PageBreak())
    story.append(Paragraph("All Findings", styles["section"]))
    if findings.empty:
        story.append(Paragraph("No anomalies were detected.", styles["body"]))
    else:
        story.append(_findings_table(findings, styles))

    doc.build(story)

    return report_path