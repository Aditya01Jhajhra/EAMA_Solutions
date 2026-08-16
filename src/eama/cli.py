from __future__ import annotations

import argparse
from pathlib import Path

from .alert_history import append_to_history, filter_new_alerts, load_alert_history
from .anomalies import detect_anomalies
from .auto_config import config_warnings, infer_config, save_inferred_config
from .business_alerts import create_business_alerts
from .config import load_config
from .email_drafts import create_email_drafts, save_email_drafts
from .ingestion import prepare_dataset, read_tabular_file
from .pdf_report import create_pdf_report
from .reporting import create_excel_report


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

    raw_data = read_tabular_file(args.input)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.config:
        config = load_config(args.config)
    else:
        print(
            "No --config provided. Inspecting the input file and "
            "generating a config automatically...\n"
        )

        inferred = infer_config(raw_data)

        auto_config_path = output_path.with_name(
            f"{Path(args.input).stem}_auto_config.json"
        )

        save_inferred_config(inferred, auto_config_path)

        print(f"Detected date column: {inferred['date_column']}")
        print(
            f"Detected metrics: "
            f"{', '.join(inferred['metrics']) or '(none found)'}"
        )
        print(
            f"Detected dimensions: "
            f"{', '.join(inferred['dimensions']) or '(none found)'}"
        )
        print(f"Saved auto-generated config to: {auto_config_path}\n")

        warnings = config_warnings(inferred, len(raw_data))
        if warnings:
            print("⚠ Review the auto-generated config before trusting results:")
            for warning in warnings:
                print(f"  - {warning}")
            print()

        config = load_config(auto_config_path)

    prepared_data = prepare_dataset(raw_data, config)

    findings = detect_anomalies(prepared_data, config)

    findings.to_csv(output_path, index=False)

    business_alerts = create_business_alerts(findings)

    history_path = Path("data/state/alert_history.csv")

    alert_history = load_alert_history(history_path)

    new_business_alerts = filter_new_alerts(business_alerts, alert_history)

    append_to_history(new_business_alerts, alert_history, history_path)

    alerts_output_path = output_path.with_name(
        "business_alerts.csv"
    )

    business_alerts.to_csv(alerts_output_path, index=False)

    excel_report_path = output_path.with_name(
        "EAMA_Weekly_Alert_Report.xlsx"
    )

    create_excel_report(
        findings,
        business_alerts,
        excel_report_path,
    )

    pdf_report_path = output_path.with_name(
        "EAMA_Weekly_Alert_Report.pdf"
    )

    create_pdf_report(
        findings,
        business_alerts,
        pdf_report_path,
    )

    email_drafts = create_email_drafts(
        new_business_alerts,
        excel_report_path,
    )

    email_drafts_dir = output_path.parent / "email_drafts"

    save_email_drafts(email_drafts, email_drafts_dir)

    print(f"Loaded {len(prepared_data):,} records.")
    print(f"Detected {len(findings):,} anomalies.")
    print(f"Saved anomaly report to: {output_path}")
    print(
        f"Created {len(business_alerts):,} consolidated "
        f"high-priority business alerts this run."
    )
    print(
        f"{len(new_business_alerts):,} of those are new "
        f"(not previously seen)."
    )
    print(f"Saved business alerts to: {alerts_output_path}")
    print(f"Saved Excel report to: {excel_report_path}")
    print(f"Saved PDF report to: {pdf_report_path}")
    print(
        f"Created {len(email_drafts):,} email drafts in: "
        f"{email_drafts_dir}"
    )

    if new_business_alerts.empty:
        print("\nNo new high-priority business alerts found.")
    else:
        print("\nNew business alerts:")

        for _, alert in new_business_alerts.iterrows():
            print(f"\n- {alert['summary']}")


if __name__ == "__main__":
    main()