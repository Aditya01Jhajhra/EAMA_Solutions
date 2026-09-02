from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .ingestion import clean_numeric_series


def _looks_like_date_column(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True

    if pd.api.types.is_numeric_dtype(series):
        return False

    sample = series.dropna().head(50)
    if sample.empty:
        return False

    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    valid = parsed.dropna()
    if valid.empty:
        return False

    in_range = valid.dt.year.between(1990, 2100)

    return bool(parsed.notna().mean() > 0.9 and in_range.mean() > 0.9)


def _looks_like_metric_column(series: pd.Series) -> bool:
    numeric = clean_numeric_series(series)
    return numeric.notna().mean() > 0.9


def _looks_like_identifier_column(column_name: str) -> bool:
    normalized = column_name.strip().lower()
    excluded_keywords = (
        "name", "id", "sku", "code", "description",
        "nombre", "código", "codigo", "descripción", "descripcion",
        "nom", "identifiant",
        "kennung", "beschreibung",
        "nome", "descrição", "descricao",
        "codice", "descrizione",
        # Geographic / location identifiers -- these describe *where*
        # a record is, not a business category to group and monitor
        # trends by (e.g. grouping anomalies by individual street
        # address is close to meaningless).
        "street", "address", "zip", "postal", "latitude", "longitude",
        "lat", "lng",
    )
    return any(keyword in normalized for keyword in excluded_keywords)


def _looks_like_categorical_code(
    column_name: str,
    series: pd.Series,
    max_unique_values: int = 6,
) -> bool:
    """Flag numeric columns that are really categorical codes or
    flags (e.g. a 0/1 waterfront flag, a 1-5 condition rating) rather
    than a continuous KPI worth monitoring for anomalies.

    Cardinality alone can't tell a rating scale (1-5) apart from a
    genuine small-range count like order quantity (also often 1-10),
    so this requires either a name that clearly suggests a flag/rating,
    or a truly binary (0/1 style) range, not low cardinality alone.
    """
    normalized = column_name.strip().lower()

    measurement_keywords = (
        "quantity", "qty", "count", "units", "amount", "volume",
        "num", "number", "sales", "revenue", "profit", "price",
        "cost", "total", "sessions", "clicks", "impressions",
    )
    if any(keyword in normalized for keyword in measurement_keywords):
        return False

    numeric = clean_numeric_series(series).dropna()
    if numeric.empty:
        return False

    all_whole_numbers = (numeric % 1 == 0).all()
    unique_count = numeric.nunique()

    if not (all_whole_numbers and unique_count <= max_unique_values):
        return False

    flag_keywords = (
        "flag", "waterfront", "condition", "rating", "grade", "tier",
        "level", "status", "stars", "view", "is_", "has_",
    )
    name_suggests_flag = any(keyword in normalized for keyword in flag_keywords)
    is_binary = unique_count <= 2

    return bool(name_suggests_flag or is_binary)


def _looks_like_dimension_column(
    series: pd.Series,
    max_unique_ratio: float = 0.1,
    max_unique_values: int = 20,
    small_sample_threshold: int = 50,
) -> bool:
    non_null = series.dropna()
    if non_null.empty:
        return False

    unique_count = non_null.nunique()
    if unique_count > max_unique_values:
        return False

    if len(non_null) < small_sample_threshold:
        return True

    return (unique_count / len(non_null)) <= max_unique_ratio


def _looks_like_rate_metric(column_name: str, series: pd.Series) -> bool:
    """Guess whether a metric should be averaged rather than summed."""
    normalized = column_name.strip().lower()
    rate_keywords = (
        "rate", "percent", "pct", "ratio", "average", "avg", "score", "margin",
    )
    if any(keyword in normalized for keyword in rate_keywords):
        return True

    numeric = clean_numeric_series(series).dropna()
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
        if _looks_like_metric_column(frame[column]) and not (
            _looks_like_categorical_code(column, frame[column])
        ):
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


def config_warnings(config: dict, row_count: int) -> list[str]:
    """Flag risky auto-detected configs instead of failing silently."""
    warnings: list[str] = []

    if not config["metrics"]:
        warnings.append(
            "No numeric metric columns were detected. EAMA will not "
            "be able to find anomalies without at least one metric. "
            "Check that your KPI columns contain numeric values."
        )

    if not config["dimensions"]:
        warnings.append(
            "No grouping dimension was detected. This usually means "
            "every categorical column either looks like an identifier "
            "(e.g. a name or ID) or has too many unique values to be "
            "a useful business category. EAMA will not produce any "
            "findings without at least one dimension. You can add one "
            "manually to the saved config, for example by setting "
            "'dimensions' and 'column_mapping' for a suitable column."
        )

    minimum_rows_needed = (
        config["rolling_window_days"] + config["minimum_history_days"]
    )
    if row_count < minimum_rows_needed:
        warnings.append(
            f"This file has {row_count:,} rows, but detecting "
            f"anomalies needs roughly {minimum_rows_needed:,} rows of "
            f"history per group to build a baseline. With less data "
            f"than that, EAMA may find few or no anomalies until more "
            f"data accumulates."
        )

    return warnings