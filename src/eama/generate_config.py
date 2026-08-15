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
    print(
        "\nReview this file before using it — check that the metrics "
        "and dimensions look right, and adjust minimum_relative_change "
        "or z_score_threshold if needed."
    )


if __name__ == "__main__":
    main()