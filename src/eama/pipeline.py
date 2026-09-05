from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .alert_history import append_to_history, filter_new_alerts, load_alert_history
from .anomalies import detect_anomalies
from .auto_config import config_warnings, infer_config, save_inferred_config
from .business_alerts import create_business_alerts
from .config import load_config
from .email_drafts import create_email_drafts, save_email_drafts
from .email_sender import send_alert_emails
from .ingestion import prepare_dataset, read_tabular_file
from .pdf_report import create_pdf_report
from .reporting import create_excel_report


@dataclass
class PipelineResult:
    """Structured summary of a single EAMA run, for callers (CLI, API,
    or anything else) to present however they like without needing to
    re-run or re-parse anything.
    """

    records_loaded: int
    anomalies_detected: int
    business_alerts_total: int
    business_alerts_new: int
    email_drafts_created: int

    findings_path: Path
    business_alerts_path: Path
    excel_report_path: Path
    pdf_report_path: Path
    email_drafts_dir: Path

    new_alert_summaries: list[str] = field(default_factory=list)
    all_alert_summaries: list[str] = field(default_factory=list)

    emails_sent: int = 0
    email_send_errors: list[str] = field(default_factory=list)

    used_auto_config: bool = False
    auto_config_path: Path | None = None
    auto_detected_date_column: str | None = None
    auto_detected_metrics: list[str] = field(default_factory=list)
    auto_detected_dimensions: list[str] = field(default_factory=list)
    auto_config_warnings: list[str] = field(default_factory=list)


def run_pipeline(
    input_path: str | Path,
    config_path: str | Path | None = None,
    output_path: str | Path = "data/outputs/anomalies.csv",
    history_path: str | Path | None = None,
    user_id: str = "default",
    send_emails: bool = False,
) -> PipelineResult:
    """Run the full EAMA pipeline and return a structured result.

    This is the single source of truth for what "running EAMA" means:
    ingest -> (auto-)configure -> detect -> consolidate -> de-duplicate
    against history -> report (Excel + PDF) -> draft emails -> (optionally)
    send emails. Both cli.py and api.py call this directly rather than
    duplicating any of this logic.

    user_id scopes alert history so different users/teams uploading the
    same or overlapping data don't suppress each other's "new" alerts.
    The default user's history file keeps its original filename
    (data/state/alert_history.csv) for backward compatibility; any
    other user gets their own alert_history_<user_id>.csv.
    """
    raw_data = read_tabular_file(input_path)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    used_auto_config = False
    auto_config_path: Path | None = None
    auto_detected_date_column: str | None = None
    auto_detected_metrics: list[str] = []
    auto_detected_dimensions: list[str] = []
    auto_warnings: list[str] = []

    if config_path:
        config = load_config(config_path)
    else:
        used_auto_config = True

        inferred = infer_config(raw_data)

        auto_config_path = output_path.with_name(
            f"{Path(input_path).stem}_auto_config.json"
        )

        save_inferred_config(inferred, auto_config_path)

        auto_detected_date_column = inferred["date_column"]
        auto_detected_metrics = inferred["metrics"]
        auto_detected_dimensions = inferred["dimensions"]
        auto_warnings = config_warnings(inferred, len(raw_data))

        config = load_config(auto_config_path)

    prepared_data = prepare_dataset(raw_data, config)

    findings = detect_anomalies(prepared_data, config)

    findings.to_csv(output_path, index=False)

    business_alerts = create_business_alerts(findings)

    safe_user_id = (
        "".join(ch for ch in user_id if ch.isalnum() or ch in ("-", "_"))
        or "default"
    )

    if history_path is None:
        if safe_user_id == "default":
            # Preserve the original filename for the default user so
            # existing history from before per-user support isn't
            # orphaned and re-treated as "new".
            history_path = Path("data/state/alert_history.csv")
        else:
            history_path = (
                Path("data/state") / f"alert_history_{safe_user_id}.csv"
            )
    else:
        history_path = Path(history_path)

    alert_history = load_alert_history(history_path)

    new_business_alerts = filter_new_alerts(business_alerts, alert_history)

    append_to_history(new_business_alerts, alert_history, history_path)

    alerts_output_path = output_path.with_name("business_alerts.csv")

    business_alerts.to_csv(alerts_output_path, index=False)

    excel_report_path = output_path.with_name(
        "EAMA_Weekly_Alert_Report.xlsx"
    )

    create_excel_report(findings, business_alerts, excel_report_path)

    pdf_report_path = output_path.with_name("EAMA_Weekly_Alert_Report.pdf")

    create_pdf_report(findings, business_alerts, pdf_report_path)

    email_drafts = create_email_drafts(
        new_business_alerts,
        excel_report_path,
    )

    email_drafts_dir = output_path.parent / "email_drafts"

    save_email_drafts(email_drafts, email_drafts_dir)

    emails_sent = 0
    email_send_errors: list[str] = []

    if send_emails:
        emails_sent, email_send_errors = send_alert_emails(email_drafts)

    new_alert_summaries = (
        []
        if new_business_alerts.empty
        else new_business_alerts["summary"].tolist()
    )

    all_alert_summaries = (
        []
        if business_alerts.empty
        else business_alerts["summary"].tolist()
    )

    return PipelineResult(
        records_loaded=len(prepared_data),
        anomalies_detected=len(findings),
        business_alerts_total=len(business_alerts),
        business_alerts_new=len(new_business_alerts),
        email_drafts_created=len(email_drafts),
        findings_path=output_path,
        business_alerts_path=alerts_output_path,
        excel_report_path=excel_report_path,
        pdf_report_path=pdf_report_path,
        email_drafts_dir=email_drafts_dir,
        new_alert_summaries=new_alert_summaries,
        all_alert_summaries=all_alert_summaries,
        emails_sent=emails_sent,
        email_send_errors=email_send_errors,
        used_auto_config=used_auto_config,
        auto_config_path=auto_config_path,
        auto_detected_date_column=auto_detected_date_column,
        auto_detected_metrics=auto_detected_metrics,
        auto_detected_dimensions=auto_detected_dimensions,
        auto_config_warnings=auto_warnings,
    )