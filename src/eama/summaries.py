from __future__ import annotations

import pandas as pd


def format_business_summary(finding: pd.Series) -> str:
    """Turn one anomaly finding into a business-ready explanation."""
    direction = (
        "increased"
        if finding["relative_change"] > 0
        else "decreased"
    )

    percentage_change = abs(
        float(finding["relative_change"])
    ) * 100

    metric = str(finding["metric"]).replace("_", " ")

    return (
        f"{finding['severity'].title()}-priority anomaly: "
        f"{finding['dimension_value']} {metric} "
        f"{direction} {percentage_change:.1f}% in the week ending "
        f"{pd.Timestamp(finding['date']).date()}, compared with its "
        f"trailing baseline. Actual value: "
        f"{finding['actual_value']:,.2f}; baseline: "
        f"{finding['baseline_mean']:,.2f}. "
        f"Recommended next step: review recent promotions, large orders, "
        f"product availability, and operational changes affecting this area."
    )