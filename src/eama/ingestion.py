from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import AnalysisConfig


def read_tabular_file(
    path: str | Path,
    sheet_name: str | int = 0,
) -> pd.DataFrame:
    """Read a CSV or Excel file.

    For Excel files with more than one sheet, only one sheet is read
    (the first, by default). A warning is printed naming every sheet
    and which one was used, so multi-sheet data is never silently
    dropped without the user knowing. Pass sheet_name to read a
    different sheet.
    """
    source = Path(path)

    if not source.exists():
        raise FileNotFoundError(f"Input file was not found: {source}")

    file_type = source.suffix.lower()

    if file_type == ".csv":
        return pd.read_csv(source)

    if file_type in {".xlsx", ".xls"}:
        excel_file = pd.ExcelFile(source)
        sheet_names = excel_file.sheet_names

        if len(sheet_names) > 1:
            selected_name = (
                sheet_names[sheet_name]
                if isinstance(sheet_name, int)
                else sheet_name
            )
            print(
                f"⚠ '{source.name}' contains {len(sheet_names)} sheets: "
                f"{', '.join(sheet_names)}. Only reading '{selected_name}'. "
                f"Pass a different sheet_name to read_tabular_file if "
                f"that isn't the sheet you want."
            )

        return pd.read_excel(source, sheet_name=sheet_name)

    raise ValueError("EAMA accepts .csv, .xlsx, and .xls files")


def clean_numeric_series(series: pd.Series) -> pd.Series:
    """Coerce a column to numbers, tolerating common spreadsheet formatting.

    Handles: currency symbols ($, €, £, ¥), thousands separators (,),
    percent signs (%), and accounting-style negatives in parentheses,
    e.g. "(1,234.56)" -> -1234.56. Already-numeric columns pass through.
    """
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    cleaned = series.astype(str).str.strip()
    cleaned = cleaned.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    cleaned = cleaned.str.replace(r"[\$€£¥]", "", regex=True)
    cleaned = cleaned.str.replace(",", "", regex=False)
    cleaned = cleaned.str.replace("%", "", regex=False)
    cleaned = cleaned.str.strip()

    return pd.to_numeric(cleaned, errors="coerce")


def prepare_dataset(
    frame: pd.DataFrame,
    config: AnalysisConfig,
) -> pd.DataFrame:
    """Map source columns to EAMA fields and validate their values."""
    # Drop fully-blank rows (common artifact of Excel exports) before
    # validating, rather than letting them fail date/metric parsing.
    working_frame = frame.dropna(how="all").reset_index(drop=True)

    required_columns = {config.date_column, *config.column_mapping}
    missing_columns = sorted(required_columns - set(working_frame.columns))

    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Input is missing configured columns: {missing}")

    prepared = working_frame.rename(
        columns={
            config.date_column: "date",
            **config.column_mapping,
        }
    ).copy()

    prepared["date"] = pd.to_datetime(
        prepared["date"], errors="coerce", format="mixed"
    )

    if prepared["date"].isna().any():
        invalid_count = int(prepared["date"].isna().sum())
        raise ValueError(
            f"Input contains {invalid_count} row(s) with invalid or "
            f"missing date values in column '{config.date_column}'."
        )

    for metric in config.metrics:
        prepared[metric] = clean_numeric_series(prepared[metric])
        if prepared[metric].isna().any():
            invalid_count = int(prepared[metric].isna().sum())
            raise ValueError(
                f"Metric '{metric}' contains {invalid_count} row(s) "
                f"with non-numeric values that could not be parsed."
            )

    for dimension in config.dimensions:
        prepared[dimension] = (
            prepared[dimension]
            .fillna("Unknown")
            .astype(str)
        )

    prepared["date"] = prepared["date"].dt.normalize()

    return prepared