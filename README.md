# EAMA — Excel Anomaly Monitoring & Alerting

EAMA is an automated pipeline that takes a CSV or Excel file, detects statistically
significant anomalies in your KPIs, consolidates them into business-readable alerts,
and produces stakeholder-ready reports (Excel + PDF), draft emails — and, if you
want, actually sends them. It runs from the command line, through a REST API, or
through a web page, with no dataset-specific setup required.

It was built and validated iteratively across several structurally different
datasets (retail sales, website traffic, marketing spend, and real estate listings)
and stress-tested against messy, real-world edge cases (currency-formatted numbers,
blank rows, multi-sheet Excel files, non-English headers, mixed date formats,
address/zip columns, categorical rating columns) to make sure it generalizes rather
than just happening to work on the data it was originally built with.

## What it does

1. **Ingests** any CSV/XLSX/XLS file.
2. **Auto-detects** the date column, numeric metrics, and categorical dimensions —
   or you can supply a hand-written config instead.
3. **Detects anomalies** using a rolling baseline and z-score threshold, aggregating
   each metric correctly (sums for totals like sales, averages for rates like bounce
   rate — detected automatically).
4. **Consolidates** related high-priority findings (same date, same segment) into a
   single business alert instead of a flood of disconnected KPI messages.
5. **Remembers** what's already been alerted on, so re-running EAMA on the same or
   overlapping data doesn't re-notify on things you've already seen.
6. **Reports** the results as a formatted Excel workbook and a stakeholder-ready PDF.
7. **Drafts** one email per new business alert, and can **send** them for real via
   Office 365 SMTP if you want.

## Requirements

- Python 3.10+
- A virtual environment (recommended)
- Dependencies are pinned in `requirements.txt` — install with the command below

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH = ".\src"
```

## Ways to run EAMA

### 1. Command line

Run on any file — no config needed. EAMA inspects the file, auto-generates a
config, saves it for review, and runs the full pipeline in one command:

```powershell
.\.venv\Scripts\python.exe -m eama.cli --input "data/raw/your_file.csv" --output data/outputs/anomalies.csv
```

With a hand-written config instead, for full control over column mapping,
metrics, dimensions, or thresholds:

```powershell
.\.venv\Scripts\python.exe -m eama.cli --input "data/raw/your_file.csv" --config config/your_config.json --output data/outputs/anomalies.csv
```

To actually send an email for each new alert (see **Email sending** below for setup):

```powershell
.\.venv\Scripts\python.exe -m eama.cli --input "data/raw/your_file.csv" --output data/outputs/anomalies.csv --send-emails
```

Just generate a config, without running detection — useful for reviewing or
hand-editing before a real run:

```powershell
.\.venv\Scripts\python.exe -m eama.generate_config --input "data/raw/your_file.csv" --output config/your_config.json
```

### 2. Web interface

Start the API server:

```powershell
.\.venv\Scripts\python.exe -m uvicorn eama.api:app --reload
```

Open `http://127.0.0.1:8000/` in a browser. Drag and drop a file, optionally check
"Send email for new alerts," and click Run — you'll see a live readout of what was
detected, summary stats, alert cards, and download links for every report.

### 3. REST API directly

- `POST /api/analyze` — upload a file (multipart form field `file`, optional form
  field `send_emails=true`), get back a JSON summary and report download URLs.
- `GET /api/download/{job_id}/{report_type}` — download a report
  (`report_type` is one of `excel`, `pdf`, `findings`, `alerts`).
- `GET /api/health` — health check.

Interactive API docs (auto-generated): `http://127.0.0.1:8000/docs`

## Email sending

To let EAMA actually send emails (instead of only writing `.txt` drafts to disk),
set these environment variables before running with `--send-emails` or
`send_emails=true`:

```powershell
$env:EAMA_SMTP_EMAIL = "your_email@yourcompany.com"
$env:EAMA_SMTP_PASSWORD = "your_password_or_app_password"
$env:EAMA_ALERT_RECIPIENT = "recipient@yourcompany.com"
```

These only last for the current terminal session — set them as permanent System
Environment Variables in Windows if you want them to persist. **Never commit
credentials to git.**

Sends go out via Outlook/Office 365 SMTP (`smtp.office365.com`). If you get an
authentication error, it's usually one of:
- Your account uses multi-factor authentication and needs an **app password**
  instead of your normal password.
- Your Microsoft 365 tenant has **SMTP AUTH disabled** for the mailbox (Microsoft
  disables this by default for many tenants) — an admin may need to enable it.

Without `--send-emails` / `send_emails=true`, EAMA never touches SMTP at all —
drafts are only written to disk, exactly as before.

## Config file format

```json
{
  "date_column": "Order Date",
  "column_mapping": {
    "Category": "category",
    "Region": "region",
    "Sales": "sales",
    "Profit": "profit"
  },
  "metrics": ["sales", "profit"],
  "dimensions": ["category", "region"],
  "analysis_frequency": "W-SUN",
  "rolling_window_days": 14,
  "minimum_history_days": 7,
  "z_score_threshold": 3.0,
  "minimum_relative_change": 0.3,
  "metric_aggregations": {
    "sales": "sum",
    "profit": "sum"
  }
}
```

| Field | Description |
|---|---|
| `date_column` | Source column name containing the date. |
| `column_mapping` | Maps source column names to the internal names used everywhere else. |
| `metrics` | Numeric KPI columns to monitor for anomalies. |
| `dimensions` | Categorical columns to group by (e.g. region, category). |
| `analysis_frequency` | Pandas offset alias for the aggregation window. `"W-SUN"` for weekly, `"D"` for daily. Daily catches single-day spikes; weekly is quieter but smooths them out. |
| `rolling_window_days` | How many prior periods form the baseline. |
| `minimum_history_days` | Minimum history required before a baseline is trusted. |
| `z_score_threshold` | How many standard deviations from baseline counts as anomalous. |
| `minimum_relative_change` | Minimum % change required to flag a flat/zero-variance baseline. |
| `metric_aggregations` | `"sum"` or `"mean"` per metric. Rate-like metrics (percentages) should be averaged, not summed. Auto-detected when using `generate_config`. |

## Project structure

```
src/eama/
├── ingestion.py         # Reads files, cleans/validates data, parses currency & percent formats
├── auto_config.py       # Inspects a file and infers a config automatically
├── generate_config.py   # Standalone script to generate + review a config
├── config.py            # Config schema, validation, loading
├── anomalies.py         # Rolling-baseline z-score anomaly detection
├── business_alerts.py   # Consolidates related findings into one alert per event
├── alert_history.py     # Tracks previously-surfaced alerts to prevent repeat notifications
├── reporting.py          # Excel report generation
├── pdf_report.py          # PDF report generation
├── email_drafts.py        # Drafts one email per new business alert
├── email_sender.py        # Sends drafted emails via Office 365 SMTP
├── pipeline.py             # Shared run_pipeline() used by both cli.py and api.py
├── cli.py                  # Command-line entry point
└── api.py                  # FastAPI REST API + serves the web frontend

static/
└── index.html             # Web interface (served at the API's root URL)

scripts/
└── health_check.py        # Verifies every module imports and the pipeline runs end to end
```

## Output files

Each run produces, alongside your `--output` path:

- **`<name>.csv`** — every anomaly detected, unfiltered.
- **`business_alerts.csv`** — consolidated alerts for this run (full picture).
- **`EAMA_Weekly_Alert_Report.xlsx`** — Summary, Business Alerts, and All Findings sheets.
- **`EAMA_Weekly_Alert_Report.pdf`** — stakeholder-ready version of the same report.
- **`email_drafts/`** — one `.txt` draft per *new* alert (already de-duplicated against history), plus an index CSV.
- **`<filename>_auto_config.json`** — saved whenever a config was auto-generated, for review or reuse.
- **`data/state/alert_history.csv`** — running record of every alert ever surfaced, used for de-duplication across runs.

For API uploads specifically, files live under `data/api_uploads/<job_id>/` and
`data/api_outputs/<job_id>/`. Jobs older than 7 days are cleaned up automatically
the next time `/api/analyze` runs.

## Verifying the project after making changes

Run the health check any time after editing code:

```powershell
.\.venv\Scripts\python.exe scripts\health_check.py
```

This imports every module and runs the full pipeline end to end on a small
built-in synthetic dataset, catching broken imports, syntax errors, or pipeline
regressions in seconds — before you go looking for them by hand.

## Current status

The core pipeline (ingestion → detection → consolidation → reporting → email
drafting/sending) is complete, runs through three different interfaces (CLI, API,
web page), and has been stress-tested against messy, real-world-shaped data across
several unrelated domains.

**Not yet built:**
- Per-user alert history — all users/uploads currently share one global
  de-duplication history, which is fine for a single person but would need
  rework if this is ever used by more than one person.
- AI-generated business summaries — alert text is currently template-based, not
  model-generated.
- Further edge-case coverage — every new real-world dataset tested so far has
  surfaced at least one genuine detection bug; this is treated as an ongoing
  process rather than something that is ever fully "finished."

## Known design trade-offs

- **Weekly vs. daily analysis**: weekly aggregation (the default) smooths single-day
  spikes, which can under-report sharp one-day events. Daily analysis catches them
  but produces more noise. Choose `analysis_frequency` accordingly.
- **Auto-detected configs are a starting point, not a guarantee.** Always review a
  freshly generated config — especially the warnings EAMA prints — before trusting
  its output on an unfamiliar dataset.
- **Categorical vs. measurement columns are distinguished by name, not just shape.**
  A low-cardinality numeric column (e.g. a 1–5 rating) and a genuine small-range
  count metric (e.g. order quantity, often also 1–10) can look statistically
  identical. EAMA uses column-name keywords to tell them apart; an unusually named
  column of either kind may still need a manual config override.