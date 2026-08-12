from __future__ import annotations

import argparse
from pathlib import Path

from .anomalies import detect_anomalies
from .config import load_config
from .ingestion import prepare_dataset, read_tabular_file
from .summaries import format_business_summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run EAMA anomaly detection."
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to a CSV, XLSX, or XLS source file.",
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Path to the EAMA JSON configuration file.",
    )

    parser.add_argument(
        "--output",
        default="data/outputs/anomalies.csv",
        help="Path for the generated anomaly report.",
    )

    args = parser.parse_args()

    config = load_config(args.config)

    raw_data = read_tabular_file(args.input)

    prepared_data = prepare_dataset(raw_data, config)

    findings = detect_anomalies(prepared_data, config)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    findings.to_csv(output_path, index=False)

    print(f"Loaded {len(prepared_data):,} records.")
    print(f"Detected {len(findings):,} anomalies.")
    print(f"Saved report to: {output_path}")

    high_priority = findings[
        findings["severity"] == "high"
    ]

    if high_priority.empty:
        print("\nNo high-priority anomalies found.")
    else:
        print(
            f"\nHigh-priority business summaries "
            f"({len(high_priority)}):"
        )

        for _, finding in high_priority.iterrows():
            print(f"\n- {format_business_summary(finding)}")


if __name__ == "__main__":
    main()