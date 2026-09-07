# EAMA — Excel Anomaly Monitoring & Alerting

EAMA is an automated pipeline that takes a CSV or Excel file, detects statistically
significant anomalies in your KPIs, consolidates them into business-readable alerts,
and produces stakeholder-ready reports (Excel + PDF), draft emails — and, if you
want, actually sends them, with AI-generated summaries in place of template text.
It runs from the command line, through a REST API, or through a web page, with no
dataset-specific setup required.

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
5. **Remembers** what's already been alerted on, per user, so re-running EAMA on
   the same or overlapping data doesn't re-notify on things already seen.
6. **Reports** the results as a formatted Excel workbook and a stakeholder-ready PDF.
7. **Writes AI-generated summaries** for each alert, in plain business language,
   instead of template text — with automatic fallback to the template if the AI
   call fails.
8. **Drafts** one email per new business alert, and can **send** them for real via
   Office 365 or Gmail SMTP if you want.

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

To use AI-generated alert summaries instead of template text (see **AI-generated
summaries** below for setup):

```powershell
.\.venv\Scripts\python.exe -m eama.cli --input "data/raw/your_file.csv" --output data/outputs/anomalies.csv --ai-summaries
```

To scope alert history to a specific user (see **Per-user alert history** below):

```powershell
.\.venv\Scripts\python.exe -m eama.cli --input "data/raw/your_file.csv" --output data/outputs/anomalies.csv --user alice
```

All flags can be combined, e.g. `--ai-summaries --send-emails --user alice`.

Just generate a config, without running detection — useful for reviewing or
hand-editing before a real run:

```powershell
.\.venv\Scripts\python.exe -m eama.generate_config --input "data/raw/your_file.csv" --output config/your_config.json
```

### 2. Web interface

Start the API server:

```powershell
$env:PYTHONPATH = ".\src"
.\.venv\Scripts\python.exe -m uvicorn eama.api:app --reload
```

Wait for `Application startup complete`, then open in a browser:


Drag and drop a file (or click to choose one), optionally enter your name, check
"Send email for new alerts" and/or "Use AI-generated summaries," and click Run —
you'll see a live readout of what was detected, summary stats, alert cards, and
download links for every report.

Press `Ctrl+C` in the terminal to stop the server.

### 3. REST API directly

- `POST /api/analyze` — upload a file (multipart form field `file`, optional form
  fields `send_emails=true`, `use_ai_summaries=true`, and `user_id=alice`), get
  back a JSON summary and report download URLs.
- `GET /api/download/{job_id}/{report_type}` — download a report
  (`report_type` is one of `excel`, `pdf`, `findings`, `alerts`).
- `GET /api/health` — health check.

Interactive API docs (auto-generated): `http://127.0.0.1:8000/docs`

## AI-generated summaries

EAMA can replace its template alert text ("sales increased X%...") with natural,
plain-English summaries generated by Google's Gemini API, which has a free tier
with no credit card required.

**Setup:**
1. Get a free API key at **aistudio.google.com/apikey**.
2. Set it as an environment variable:
```powershell
$env:GEMINI_API_KEY = "your_key_here"
```
3. Use `--ai-summaries` (CLI) or check "Use AI-generated summaries" (web interface),
   or send `use_ai_summaries=true` (API).

**Behavior and limits:**
- If a summary fails to generate for any reason (missing key, network issue, rate
  limit, model unavailable), that specific alert falls back to its original
  template text automatically — one failure never breaks the run.
- Network timeouts and "503 server overloaded" responses are retried once
  automatically before falling back.
- Requests are spaced a few seconds apart to avoid tripping the free tier's
  per-minute rate limit on runs with several alerts.
- The default model is set in `EAMA_GEMINI_MODEL` (falls back to a built-in
  default if unset). Google's free-tier model names change over time; if you get
  a 404 error, the error message will name the current model to use — set it with:
```powershell
$env:EAMA_GEMINI_MODEL = "model-name-from-the-error-message"
```

## Per-user alert history

By default, everyone shares one alert history file (`data/state/alert_history.csv`),
so re-running EAMA on the same data won't re-notify on alerts already seen. If more
than one person is using EAMA against overlapping data, scope each person's history
separately so they don't suppress each other's "new" alerts:

- **Command line**: `--user alice`
- **Web interface**: type a name into the "Your name (optional)" field before running
- **API**: include a `user_id` form field with the `/api/analyze` request

Each named user gets their own `data/state/alert_history_<user_id>.csv`. The
default user keeps the original `alert_history.csv` filename, so nothing changes
for existing single-user setups.

## Email sending

To let EAMA actually send emails (instead of only writing `.txt` drafts to disk),
set these environment variables before running with `--send-emails` or
`send_emails=true`:

```powershell
$env:EAMA_SMTP_EMAIL = "your_email@example.com"
$env:EAMA_SMTP_PASSWORD = "your_password_or_app_password"
$env:EAMA_ALERT_RECIPIENT = "recipient@example.com"
```

These default to Office 365 (`smtp.office365.com`, port 587). For Gmail or another
provider, also set:

```powershell
$env:EAMA_SMTP_SERVER = "smtp.gmail.com"
$env:EAMA_SMTP_PORT = "587"
```

**To avoid re-setting these every terminal session**, set them as permanent Windows
environment variables instead: search "Edit the system environment variables" in
the Start menu → Environment Variables → New (under "User variables") for each one.
Close and reopen your terminal afterward for the change to take effect.

**Never commit credentials to git.**

If you get an authentication error, it's usually one of:
- **Gmail**: you need a Google **App Password** (myaccount.google.com/apppasswords,
  requires 2-Step Verification to be turned on) — Gmail will not accept your normal
  password.
- **Office 365**: multi-factor accounts need an app password too, and your
  organization's SMTP AUTH may be disabled by default — this is especially common
  on student/education tenants, which usually can't be re-enabled by the student
  themselves.

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

src/eama/
├── ingestion.py # Reads files, cleans/validates data, parses currency & percent formats
├── auto_config.py # Inspects a file and infers a config automatically
├── generate_config.py # Standalone script to generate + review a config
├── config.py # Config schema, validation, loading
├── anomalies.py # Rolling-baseline z-score anomaly detection
├── business_alerts.py # Consolidates related findings into one alert per event
├── alert_history.py # Tracks previously-surfaced alerts to prevent repeat notifications
├── ai_summary.py # Generates AI-written alert summaries via Gemini, with fallback
├── reporting.py # Excel report generation
├── pdf_report.py # PDF report generation
├── email_drafts.py # Drafts one email per new business alert
├── email_sender.py # Sends drafted emails via SMTP (Office 365 or Gmail)
├── pipeline.py # Shared run_pipeline() used by both cli.py and api.py
├── cli.py # Command-line entry point
└── api.py # FastAPI REST API + serves the web frontend

static/
└── index.html # Web interface (served at the API's root URL)

scripts/
└── health_check.py # Verifies every module imports and the pipeline runs end to end


## Output files

Each run produces, alongside your `--output` path:

- **`<name>.csv`** — every anomaly detected, unfiltered.
- **`business_alerts.csv`** — consolidated alerts for this run (full picture).
- **`EAMA_Weekly_Alert_Report.xlsx`** — Summary, Business Alerts, and All Findings sheets.
- **`EAMA_Weekly_Alert_Report.pdf`** — stakeholder-ready version of the same report.
- **`email_drafts/`** — one `.txt` draft per *new* alert (already de-duplicated against history), plus an index CSV.
- **`<filename>_auto_config.json`** — saved whenever a config was auto-generated, for review or reuse.
- **`data/state/alert_history.csv`** (or `alert_history_<user_id>.csv`) — running record of every alert ever surfaced for that user, used for de-duplication across runs.

For API uploads specifically, files live under `data/api_uploads/<job_id>/` and
`data/api_outputs/<job_id>/`. Jobs older than 7 days are cleaned up automatically
the next time `/api/analyze` runs.

## Verifying the project after making changes

Run the health check any time after editing code:

```powershell
$env:PYTHONPATH = ".\src"
.\.venv\Scripts\python.exe scripts\health_check.py
```

This imports every module and runs the full pipeline end to end on a small
built-in synthetic dataset, catching broken imports, syntax errors, or pipeline
regressions in seconds — before you go looking for them by hand.

## Current status

The core pipeline (ingestion → detection → consolidation → AI/template reporting →
email drafting/sending) is complete, runs through three different interfaces (CLI,
API, web page), supports multiple users without cross-suppressing alerts, and has
been stress-tested against messy, real-world-shaped data across several unrelated
domains. Email sending has been confirmed working with real Office 365 and Gmail
accounts; AI summaries have been confirmed working with real Gemini API responses.

**Not yet built:**
- Deployment beyond localhost — EAMA currently only runs on your own machine
  (`127.0.0.1`); making it reachable elsewhere (a shared server, cloud hosting)
  hasn't been set up.
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
- **AI summaries depend on a free, rate-limited external service.** Even with
  retry logic and request spacing, occasional summaries may fall back to template
  text during high demand on Google's end — this is expected, not a bug.

  