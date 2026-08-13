from __future__ import annotations

import pandas as pd


def create_business_alerts(findings: pd.DataFrame) -> pd.DataFrame:
    """Combine high-priority KPI findings into one business alert."""
    high_priority = findings[
        findings["severity"] == "high"
    ].copy()

    if high_priority.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "dimension",
                "dimension_value",
                "metrics_affected",
                "summary",
            ]
        )

    alerts: list[dict[str, str]] = []

    grouped = high_priority.groupby(
        ["date", "dimension", "dimension_value"],
        sort=True,
    )

    for (date, dimension, dimension_value), group in grouped:
        metric_changes = []

        for _, finding in group.iterrows():
            metric = str(finding["metric"]).replace("_", " ")
            change = abs(float(finding["relative_change"])) * 100
            direction = (
                "increased"
                if finding["relative_change"] > 0
                else "decreased"
            )

            metric_changes.append(
                f"{metric} {direction} {change:.1f}%"
            )

        metrics_text = ", ".join(metric_changes)

        summary = (
            f"High-priority {dimension_value} "
            f"{dimension} performance change for the week ending "
            f"{pd.Timestamp(date).date()}: {metrics_text} "
            f"versus the trailing baseline. Recommended next step: "
            f"review promotions, bulk orders, inventory availability, "
            f"and operational changes."
        )

        alerts.append(
            {
                "date": pd.Timestamp(date).date().isoformat(),
                "dimension": dimension,
                "dimension_value": dimension_value,
                "metrics_affected": ", ".join(
                    group["metric"].tolist()
                ),
                "summary": summary,
            }
        )

    return pd.DataFrame(alerts)