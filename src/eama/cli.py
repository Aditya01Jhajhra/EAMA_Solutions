from __future__ import annotations

import argparse

from .pipeline import run_pipeline


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
        required=False,
        default=None,
        help=(
            "Path to an EAMA JSON configuration file. If omitted, "
            "EAMA will inspect the input file and generate a config "
            "automatically."
        ),
    )

    parser.add_argument(
        "--output",
        default="data/outputs/anomalies.csv",
        help="Path for the generated anomaly report.",
    )

    args = parser.parse_args()

    if not args.config:
        print(
            "No --config provided. Inspecting the input file and "
            "generating a config automatically...\n"
        )

    result = run_pipeline(
        input_path=args.input,
        config_path=args.config,
        output_path=args.output,
    )

    if result.used_auto_config:
        print(f"Detected date column: {result.auto_detected_date_column}")
        print(
            f"Detected metrics: "
            f"{', '.join(result.auto_detected_metrics) or '(none found)'}"
        )
        print(
            f"Detected dimensions: "
            f"{', '.join(result.auto_detected_dimensions) or '(none found)'}"
        )
        print(f"Saved auto-generated config to: {result.auto_config_path}\n")

        if result.auto_config_warnings:
            print("⚠ Review the auto-generated config before trusting results:")
            for warning in result.auto_config_warnings:
                print(f"  - {warning}")
            print()

    print(f"Loaded {result.records_loaded:,} records.")
    print(f"Detected {result.anomalies_detected:,} anomalies.")
    print(f"Saved anomaly report to: {result.findings_path}")
    print(
        f"Created {result.business_alerts_total:,} consolidated "
        f"high-priority business alerts this run."
    )
    print(
        f"{result.business_alerts_new:,} of those are new "
        f"(not previously seen)."
    )
    print(f"Saved business alerts to: {result.business_alerts_path}")
    print(f"Saved Excel report to: {result.excel_report_path}")
    print(f"Saved PDF report to: {result.pdf_report_path}")
    print(
        f"Created {result.email_drafts_created:,} email drafts in: "
        f"{result.email_drafts_dir}"
    )

    if not result.new_alert_summaries:
        print("\nNo new high-priority business alerts found.")
    else:
        print("\nNew business alerts:")

        for summary in result.new_alert_summaries:
            print(f"\n- {summary}")


if __name__ == "__main__":
    main()