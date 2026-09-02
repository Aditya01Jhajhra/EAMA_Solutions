from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .pipeline import run_pipeline

app = FastAPI(
    title="EAMA API",
    description=(
        "Upload a CSV or Excel file and get back anomaly detection "
        "results, consolidated business alerts, and downloadable "
        "Excel/PDF reports."
    ),
)

UPLOAD_DIR = Path("data/api_uploads")
OUTPUT_DIR = Path("data/api_outputs")
STATIC_DIR = Path("static")
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB
JOB_RETENTION_DAYS = 7


def _cleanup_old_jobs() -> None:
    """Delete upload/output folders older than JOB_RETENTION_DAYS.

    Runs opportunistically at the start of each /api/analyze call
    rather than on a schedule, since this is a lightweight personal
    API rather than a long-running service with a task scheduler.
    """
    cutoff = time.time() - (JOB_RETENTION_DAYS * 86400)
    for base_dir in (UPLOAD_DIR, OUTPUT_DIR):
        if not base_dir.exists():
            continue
        for job_dir in base_dir.iterdir():
            if job_dir.is_dir() and job_dir.stat().st_mtime < cutoff:
                shutil.rmtree(job_dir, ignore_errors=True)


@app.get("/")
async def frontend() -> FileResponse:
    """Serve the EAMA web interface."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend not found. Expected static/index.html.",
        )
    return FileResponse(index_path, media_type="text/html")


class AnalyzeResponse(BaseModel):
    job_id: str
    records_loaded: int
    anomalies_detected: int
    business_alerts_total: int
    business_alerts_new: int
    email_drafts_created: int
    new_alert_summaries: list[str]
    all_alert_summaries: list[str]

    emails_sent: int
    email_send_errors: list[str]

    used_auto_config: bool
    auto_detected_date_column: str | None
    auto_detected_metrics: list[str]
    auto_detected_dimensions: list[str]
    auto_config_warnings: list[str]

    excel_report_url: str
    pdf_report_url: str
    findings_csv_url: str
    business_alerts_csv_url: str


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(
    file: UploadFile = File(...),
    send_emails: bool = Form(False),
) -> AnalyzeResponse:
    """Upload a CSV/XLSX/XLS file and run the full EAMA pipeline on it.

    No config is required -- EAMA inspects the file and generates one
    automatically, the same way `eama.cli` behaves without --config.
    Set send_emails=true to actually email new alerts via Office 365
    SMTP (requires EAMA_SMTP_EMAIL, EAMA_SMTP_PASSWORD, and
    EAMA_ALERT_RECIPIENT to be set as environment variables).
    """
    original_suffix = Path(file.filename or "").suffix.lower()

    if original_suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{original_suffix}'. "
                f"EAMA accepts .csv, .xlsx, and .xls files."
            ),
        )

    _cleanup_old_jobs()

    job_id = uuid.uuid4().hex[:12]

    job_upload_dir = UPLOAD_DIR / job_id
    job_output_dir = OUTPUT_DIR / job_id
    job_upload_dir.mkdir(parents=True, exist_ok=True)
    job_output_dir.mkdir(parents=True, exist_ok=True)

    saved_input_path = job_upload_dir / f"input{original_suffix}"

    total_bytes = 0
    try:
        with saved_input_path.open("wb") as destination:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"File too large. Maximum upload size is "
                            f"{MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB."
                        ),
                    )
                destination.write(chunk)
    except HTTPException:
        shutil.rmtree(job_upload_dir, ignore_errors=True)
        shutil.rmtree(job_output_dir, ignore_errors=True)
        raise

    try:
        result = run_pipeline(
            input_path=saved_input_path,
            config_path=None,
            output_path=job_output_dir / "anomalies.csv",
            send_emails=send_emails,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return AnalyzeResponse(
        job_id=job_id,
        records_loaded=result.records_loaded,
        anomalies_detected=result.anomalies_detected,
        business_alerts_total=result.business_alerts_total,
        business_alerts_new=result.business_alerts_new,
        email_drafts_created=result.email_drafts_created,
        new_alert_summaries=result.new_alert_summaries,
        all_alert_summaries=result.all_alert_summaries,
        emails_sent=result.emails_sent,
        email_send_errors=result.email_send_errors,
        used_auto_config=result.used_auto_config,
        auto_detected_date_column=result.auto_detected_date_column,
        auto_detected_metrics=result.auto_detected_metrics,
        auto_detected_dimensions=result.auto_detected_dimensions,
        auto_config_warnings=result.auto_config_warnings,
        excel_report_url=f"/api/download/{job_id}/excel",
        pdf_report_url=f"/api/download/{job_id}/pdf",
        findings_csv_url=f"/api/download/{job_id}/findings",
        business_alerts_csv_url=f"/api/download/{job_id}/alerts",
    )


_DOWNLOAD_FILES = {
    "excel": ("EAMA_Weekly_Alert_Report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "pdf": ("EAMA_Weekly_Alert_Report.pdf", "application/pdf"),
    "findings": ("anomalies.csv", "text/csv"),
    "alerts": ("business_alerts.csv", "text/csv"),
}


@app.get("/api/download/{job_id}/{report_type}")
async def download(job_id: str, report_type: str) -> FileResponse:
    """Download a report generated by a previous /api/analyze call."""
    if report_type not in _DOWNLOAD_FILES:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown report type '{report_type}'. "
                f"Valid options: {', '.join(_DOWNLOAD_FILES)}."
            ),
        )

    filename, media_type = _DOWNLOAD_FILES[report_type]

    if not job_id.isalnum():
        raise HTTPException(status_code=400, detail="Invalid job_id.")

    file_path = OUTPUT_DIR / job_id / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Report not found. It may not have been generated for this job.",
        )

    return FileResponse(file_path, media_type=media_type, filename=filename)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}