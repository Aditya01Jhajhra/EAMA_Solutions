from __future__ import annotations

from pathlib import Path

import pandas as pd


def _build_subject(alert: pd.Series) -> str:
    return (
        f"High-Priority Alert: {alert['dimension_value']} "
        f"({alert['dimension']}) — week ending {alert['date']}"
    )


def _build_body(alert: pd.Series, excel_report_name: str) -> str:
    return (
        "Hi team,\n\n"
        "EAMA flagged a high-priority performance change that needs review.\n\n"
        f"Summary:\n{alert['summary']}\n\n"
        f"Metrics affected: {alert['metrics_affected']}\n\n"
        f"Full details are attached in {excel_report_name} "
        "(see the 'Business Alerts' and 'All Findings' sheets).\n\n"
        "Best,\nEAMA Reporting\n"
    )


def create_email_drafts(
    business_alerts: pd.DataFrame,
    excel_report_path: str | Path,
) -> pd.DataFrame:
    """Create one email draft per consolidated business alert."""
    excel_report_name = Path(excel_report_path).name

    if business_alerts.empty:
        return pd.DataFrame(columns=["alert_id", "subject", "body"])

    drafts = pd.DataFrame(
        {
            "alert_id": range(1, len(business_alerts) + 1),
            "subject": [
                _build_subject(alert)
                for _, alert in business_alerts.iterrows()
            ],
            "body": [
                _build_body(alert, excel_report_name)
                for _, alert in business_alerts.iterrows()
            ],
        }
    )

    return drafts


def save_email_drafts(drafts: pd.DataFrame, output_dir: str | Path) -> Path:
    """Save each draft as its own .txt file, plus an index CSV."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for _, draft in drafts.iterrows():
        draft_path = output_dir / f"alert_{draft['alert_id']:02d}.txt"
        draft_path.write_text(
            f"Subject: {draft['subject']}\n\n{draft['body']}",
            encoding="utf-8",
        )

    index_path = output_dir / "email_drafts_index.csv"
    drafts.to_csv(index_path, index=False)

    return output_dir