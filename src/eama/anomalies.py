from __future__ import annotations

import pandas as pd

from .config import AnalysisConfig


FINDING_COLUMNS = [
    "date",
    "dimension",
    "dimension_value",
    "metric",
    "actual_value",
    "baseline_mean",
    "relative_change",
    "z_score",
    "severity",
]


def get_severity(z_score: float) -> str:
    """Assign a business priority based on anomaly strength."""
    if abs(z_score) >= 5:
        return "high"

    if abs(z_score) >= 4:
        return "medium"

    return "low"


def detect_anomalies(
    frame: pd.DataFrame,
    config: AnalysisConfig,
) -> pd.DataFrame:
    """Detect unusual daily KPI values against a prior rolling baseline."""
    findings: list[dict[str, object]] = []

    for dimension in config.dimensions:
        for metric in config.metrics:
            daily = (
                frame.groupby([dimension, "date"], as_index=False)[metric]
                .sum()
                .sort_values([dimension, "date"])
            )

            for dimension_value, group in daily.groupby(
                dimension,
                sort=False,
            ):
                values = group[metric].astype(float).reset_index(drop=True)

                baseline = values.shift(1).rolling(
                    window=config.rolling_window_days,
                    min_periods=config.minimum_history_days,
                )

                baseline_mean = baseline.mean()
                baseline_std = baseline.std(ddof=0)

                relative_change = (
                    (values - baseline_mean)
                    / baseline_mean.abs().replace(0, pd.NA)
                )

                z_score = (
                    (values - baseline_mean)
                    / baseline_std.replace(0, pd.NA)
                )

                flat_baseline_change = (
                    baseline_std.eq(0)
                    & relative_change.abs().ge(
                        config.minimum_relative_change
                    )
                )

                z_score = z_score.mask(
                    flat_baseline_change,
                    float("inf"),
                )

                flagged = z_score.abs().ge(
                    config.z_score_threshold
                ).fillna(False)

                for position in z_score.index[flagged]:
                    findings.append(
                        {
                            "date": group.iloc[position]["date"],
                            "dimension": dimension,
                            "dimension_value": dimension_value,
                            "metric": metric,
                            "actual_value": values.iloc[position],
                            "baseline_mean": baseline_mean.iloc[position],
                            "relative_change": relative_change.iloc[position],
                            "z_score": z_score.iloc[position],
                            "severity": get_severity(
                                float(z_score.iloc[position])
                            ),
                        }
                    )

    if not findings:
        return pd.DataFrame(columns=FINDING_COLUMNS)

    return pd.DataFrame(findings)