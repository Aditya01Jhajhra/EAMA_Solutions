from __future__ import annotations

import argparse
from pathlib import Path

from .auto_config import infer_config, save_inferred_config
from .ingestion import read_tabular_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect a CSV/XLSX file and generate a starting "
            "EAMA config JSON for it."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to a CSV, XLSX, or XLS source file.",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Path to write the generated config JSON.",
    )

    args = parser.parse_args()

    raw_data = read_tabular_file(args.input)

    config = infer_config(raw_data)

    config_path = save_inferred_config(config, args.output)

    print(f"Inspected {len(raw_data):,} rows from: {args.input}")
    print(f"Detected date column: {config['date_column']}")
    print(f"Detected metrics: {', '.join(config['metrics']) or '(none found)'}")
    print(
        f"Detected dimensions: "
        f"{', '.join(config['dimensions']) or '(none found)'}"
    )
    print(f"\nSaved generated config to: {config_path}")

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
            "manually to the generated config, for example by setting "
            "'dimensions' and 'column_mapping' for a suitable column."
        )

    minimum_rows_needed = (
        config["rolling_window_days"] + config["minimum_history_days"]
    )
    if len(raw_data) < minimum_rows_needed:
        warnings.append(
            f"This file has {len(raw_data):,} rows, but detecting "
            f"anomalies needs roughly {minimum_rows_needed:,} rows of "
            f"history per group to build a baseline. With less data "
            f"than that, EAMA may find few or no anomalies until more "
            f"data accumulates."
        )

    if warnings:
        print("\n⚠ Review before using this config:")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print(
            "\nReview this file before using it — check that the "
            "metrics and dimensions look right, and adjust "
            "minimum_relative_change or z_score_threshold if needed."
        )


if __name__ == "__main__":
    main()