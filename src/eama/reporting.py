from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd


def create_excel_report(
    findings: pd.DataFrame,
    business_alerts: pd.DataFrame,
    output_path: str | Path,
) -> Path:
    """Create an Excel report for EAMA anomaly findings."""
    report_path = Path(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    severity_counts = (
        findings["severity"]
        .value_counts()
        .reindex(["high", "medium", "low"], fill_value=0)
        .rename_axis("severity")
        .reset_index(name="count")
    )

    report_summary = pd.DataFrame(
        {
            "Metric": [
                "Report generated",
                "Total anomalies",
                "High-priority anomalies",
                "Consolidated business alerts",
            ],
            "Value": [
                date.today().isoformat(),
                len(findings),
                int((findings["severity"] == "high").sum()),
                len(business_alerts),
            ],
        }
    )

    with pd.ExcelWriter(
        report_path,
        engine="openpyxl",
    ) as writer:
        report_summary.to_excel(
            writer,
            sheet_name="Summary",
            index=False,
            startrow=1,
        )

        severity_counts.to_excel(
            writer,
            sheet_name="Summary",
            index=False,
            startrow=8,
        )

        business_alerts.to_excel(
            writer,
            sheet_name="Business Alerts",
            index=False,
        )

        findings.to_excel(
            writer,
            sheet_name="All Findings",
            index=False,
        )

        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]

            for column_cells in worksheet.columns:
                maximum_length = max(
                    len(str(cell.value))
                    if cell.value is not None
                    else 0
                    for cell in column_cells
                )

                column_letter = column_cells[0].column_letter

                worksheet.column_dimensions[
                    column_letter
                ].width = min(maximum_length + 2, 60)

    return report_path