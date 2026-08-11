from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import AnalysisConfig


def read_tabular_file(path: str | Path) -> pd.DataFrame:
    """Read a CSV or Excel file."""
    source = Path(path)

    if not source.exists():
        raise FileNotFoundError(f"Input file was not found: {source}")

    file_type = source.suffix.lower()

    if file_type == ".csv":
        return pd.read_csv(source)

    if file_type in {".xlsx", ".xls"}:
        return pd.read_excel(source)

    raise ValueError("EAMA accepts .csv, .xlsx, and .xls files")


def prepare_dataset(
    frame: pd.DataFrame,
    config: AnalysisConfig,
) -> pd.DataFrame:
    """Map source columns to EAMA fields and validate their values."""
    required_columns = {config.date_column, *config.column_mapping}
    missing_columns = sorted(required_columns - set(frame.columns))

    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Input is missing configured columns: {missing}")

    prepared = frame.rename(
        columns={
            config.date_column: "date",
            **config.column_mapping,
        }
    ).copy()

    prepared["date"] = pd.to_datetime(prepared["date"], errors="coerce")

    if prepared["date"].isna().any():
        raise ValueError("Input contains invalid date values")

    for metric in config.metrics:
        prepared[metric] = pd.to_numeric(
            prepared[metric],
            errors="coerce",
        )

        if prepared[metric].isna().any():
            raise ValueError(
                f"Metric '{metric}' contains non-numeric values"
            )

    for dimension in config.dimensions:
        prepared[dimension] = (
            prepared[dimension]
            .fillna("Unknown")
            .astype(str)
        )

    prepared["date"] = prepared["date"].dt.normalize()

    return prepared