# EAMA — Excel Anomaly Monitoring & Alerting

EAMA is an automated pipeline that takes a CSV or Excel file, detects statistically significant anomalies in your KPIs, consolidates them into business-readable alerts, and produces stakeholder-ready reports (Excel + PDF) and draft emails — all from a single command, with no dataset-specific setup required.

It was built and validated iteratively: first against a retail e-commerce dataset, then deliberately stress-tested against a structurally different dataset (website traffic) and a battery of messy edge cases (currency-formatted numbers, blank rows, tiny files, ambiguous date columns) to make sure it generalizes rather than just happening to work on the data it was built with.

## What it does

1. **Ingests** any CSV/XLSX/XLS file.
2. **Auto-detects** the date column, numeric metrics, and categorical dimensions — or you can supply a hand-written config instead.
3. **Detects anomalies** using a rolling baseline and z-score threshold, aggregating each metric correctly (sums for totals like sales, averages for rates like bounce rate — detected automatically).
4. **Consolidates** related high-priority findings (same date, same segment) into a single business alert instead of a flood of disconnected KPI messages.
5. **Remembers** what's already been alerted on, so re-running EAMA on the same or overlapping data doesn't re-notify on things you've already seen.
6. **Reports** the results as a formatted Excel workbook and a stakeholder-ready PDF.
7. **Drafts** one email per new business alert, ready to review and send.

## Requirements

- Python 3.10+
- A virtual environment (recommended)
- Dependencies: `pandas`, `openpyxl`, `reportlab`

## Setup

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install pandas openpyxl reportlab
    $env:PYTHONPATH = ".\src"

## Usage

**Run EAMA on any file — no config needed.** EAMA inspects the file, auto-generates a config, saves it for review, and runs the full pipeline in one command. If the auto-detected config looks risky (no metrics found, no dimension found, or too little history to build a baseline), EAMA prints an explicit warning rather than failing silently.

    .\.venv\Scripts\python.exe -m eama.cli --input "data/raw/your_file.csv" --output data/outputs/anomalies.csv

**Run EAMA with a hand-written config**, for full control over column mapping, metrics, dimensions, or thresholds:

    .\.venv\Scripts\python.exe -m eama.cli --input "data/raw/your_file.csv" --config config/your_config.json --output data/outputs/anomalies.csv

**Just generate a config, without running detection** — useful for reviewing or hand-editing before a real run:

    .\.venv\Scripts\python.exe -m eama.generate_config --input "data/raw/your_file.csv" --output config/your_config.json

## Config file format

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
| `metric_aggregations` | `"sum"` or `"mean"` per metric. Rate-like metrics (percentages) should be averaged, not summed, or totals become meaningless. Auto-detected when using `generate_config`. |

## Project structure

    src/eama/
    ├── ingestion.py         # Reads files, cleans/validates data, parses currency & percent formats
    ├── auto_config.py       # Inspects a file and infers a config automatically
    ├── generate_config.py   # Standalone script to generate + review a config
    ├── config.py            # Config schema, validation, loading
    ├── anomalies.py         # Rolling-baseline z-score anomaly detection
    ├── business_alerts.py   # Consolidates related findings into one alert per event
    ├── alert_history.py     # Tracks previously-surfaced alerts to prevent repeat notifications
    ├── reporting.py         # Excel report generation
    ├── pdf_report.py        # PDF report generation
    ├── email_drafts.py      # Drafts one email per new business alert
    └── cli.py               # Single entry point that runs the full pipeline

## Output files

Each run produces, alongside your `--output` path:

- **`<name>.csv`** — every anomaly detected, unfiltered.
- **`business_alerts.csv`** — consolidated alerts for this run (full picture).
- **`EAMA_Weekly_Alert_Report.xlsx`** — Summary, Business Alerts, and All Findings sheets.
- **`EAMA_Weekly_Alert_Report.pdf`** — stakeholder-ready version of the same report.
- **`email_drafts/`** — one `.txt` draft per *new* alert (already de-duplicated against history), plus an index CSV.
- **`<filename>_auto_config.json`** — saved whenever a config was auto-generated, for review or reuse.
- **`data/state/alert_history.csv`** — running record of every alert ever surfaced, used for de-duplication across runs.

## Current status

The core pipeline (ingestion → detection → consolidation → reporting → email drafting) is complete and has been stress-tested against messy, real-world-shaped data, not just the dataset it was originally built with.

**Not yet built:**
- A frontend or API layer — EAMA currently runs from the command line only.
- Actual email sending — drafts are written to disk for manual review, not sent automatically.
- Coverage for a few remaining edge cases: multi-sheet Excel files, non-English column headers, and inconsistent date formats within a single column.
- AI-generated business summaries — alert text is currently template-based, not model-generated.

## Known design trade-offs

- **Weekly vs. daily analysis**: weekly aggregation (the default) smooths single-day spikes, which can under-report sharp one-day events. Daily analysis catches them but produces more noise. Choose `analysis_frequency` accordingly.
- **Auto-detected configs are a starting point, not a guarantee.** Always review a freshly generated config — especially the warnings EAMA prints — before trusting its output on an unfamiliar dataset.
