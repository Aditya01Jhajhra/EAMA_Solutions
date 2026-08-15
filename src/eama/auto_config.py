from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def _looks_like_date_column(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    sample = series.dropna().head(50)
    if sample.empty:
        return False
    parsed = pd.to_datetime(sample, errors="coerce")
    return parsed.notna().mean() > 0.9


def _looks_like_metric_column(series: pd.Series) -> bool:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.notna().mean() > 0.9


def _looks_like_identifier_column(column_name: str) -> bool:
    normalized = column_name.strip().lower()
    excluded_keywords = ("name", "id", "sku", "code", "description")
    return any(keyword in normalized for keyword in excluded_keywords)


def _looks_like_dimension_column(
    series: pd.Series,
    max_unique_ratio: float = 0.1,
    max_unique_values: int = 20,
) -> bool:
    non_null = series.dropna()
    if non_null.empty:
        return False
    unique_count = non_null.nunique()
    return (
        unique_count <= max_unique_values
        and (unique_count / len(non_null)) <= max_unique_ratio
    )


def _looks_like_rate_metric(column_name: str, series: pd.Series) -> bool:
    """Guess whether a metric should be averaged rather than summed."""
    normalized = column_name.strip().lower()
    rate_keywords = (
        "rate",
        "percent",
        "pct",
        "ratio",
        "average",
        "avg",
        "score",
        "margin",
    )
    if any(keyword in normalized for keyword in rate_keywords):
        return True

    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return False

    within_percent_range = numeric.between(0, 100).mean() > 0.95
    has_decimals = (numeric % 1 != 0).mean() > 0.3
    return bool(within_percent_range and has_decimals)


def infer_config(
    frame: pd.DataFrame,
    analysis_frequency: str = "W-SUN",
    rolling_window_days: int = 14,
    minimum_history_days: int = 7,
    z_score_threshold: float = 3.0,
    minimum_relative_change: float = 0.30,
) -> dict:
    """Inspect a DataFrame and propose an EAMA config."""
    date_column = None
    for column in frame.columns:
        if _looks_like_date_column(frame[column]):
            date_column = column
            break

    if date_column is None:
        raise ValueError(
            "Could not find a date-like column. Please specify "
            "'date_column' manually in the generated config."
        )

    remaining_columns = [
        column for column in frame.columns if column != date_column
    ]

    metrics: list[str] = []
    dimensions: list[str] = []
    column_mapping: dict[str, str] = {}
    metric_aggregations: dict[str, str] = {}

    for column in remaining_columns:
        if _looks_like_metric_column(frame[column]):
            metrics.append(column)
        elif _looks_like_identifier_column(column):
            continue
        elif _looks_like_dimension_column(frame[column]):
            dimensions.append(column)

    for column in metrics:
        column_mapping[column] = column.strip().lower().replace(" ", "_")

    for column in dimensions:
        column_mapping[column] = column.strip().lower().replace(" ", "_")

    for column in metrics:
        mapped_name = column_mapping[column]
        if _looks_like_rate_metric(column, frame[column]):
            metric_aggregations[mapped_name] = "mean"
        else:
            metric_aggregations[mapped_name] = "sum"

    config = {
        "date_column": date_column,
        "column_mapping": column_mapping,
        "metrics": [column_mapping[column] for column in metrics],
        "dimensions": [column_mapping[column] for column in dimensions],
        "analysis_frequency": analysis_frequency,
        "rolling_window_days": rolling_window_days,
        "minimum_history_days": minimum_history_days,
        "z_score_threshold": z_score_threshold,
        "minimum_relative_change": minimum_relative_change,
        "metric_aggregations": metric_aggregations,
    }

    return config


def save_inferred_config(config: dict, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(config, file, indent=2)
    return output_path