# EAMA — Excel Anomaly Monitoring & Alerting

EAMA is an automated pipeline that takes a CSV or Excel file, detects statistically
significant anomalies in your KPIs, consolidates them into business-readable alerts,
and produces stakeholder-ready reports (Excel + PDF) and draft emails — all from a
single command, with no dataset-specific setup required.

It was built and validated iteratively: first against a retail e-commerce dataset,
then deliberately stress-tested against a structurally different dataset (website
traffic) and a battery of messy edge cases (currency-formatted numbers, blank rows,
tiny files, ambiguous date columns) to make sure it generalizes rather than just
happening to work on the data it was built with.

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
7. **Drafts** one email per new business alert, ready to review and send.

## Requirements

- Python 3.10+
- A virtual environment (recommended)
- Dependencies: `pandas`, `openpyxl`, `reportlab`

## Setup

```powershell
# From the project root
python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install pandas openpyxl reportlab

# Set this at the start of every terminal session
$env:PYTHONPATH = ".\src"
```

## Usage

### Run EAMA on any file — no config needed

EAMA will inspect the file, auto-generate a config, save it for review, and run the
full pipeline in one command:

```powershell
.\.venv\Scripts\python.exe -m eama.cli --input "data/raw/your_file.csv" --output data/outputs/anomalies.csv
```

If the auto-detected config looks risky (no metrics found, no dimension found, or
too little history to build a baseline), EAMA prints an explicit warning rather than
failing silently.

### Run EAMA with a hand-written config

If you want full control over column mapping, metrics, dimensions, or thresholds,
write a config JSON (see format below) and pass it explicitly:

```powershell
.\.venv\Scripts\python.exe -m eama.cli --input "data/raw/your_file.csv" --config config/your_config.json --output data/outputs/anomalies.csv
```

### Just generate a config, without running detection

Useful for reviewing or hand-editing before a real run:

```powershell
.\.venv\Scripts\python.exe -m eama.generate_config --input "data/raw/your_file.csv" --output config/your_config.json
```

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
| `metric_aggregations` | `"sum"` or `"mean"` per metric. Rate-like metrics (percentages) should be averaged, not summed, or totals become meaningless. Auto-detected when using `generate_config`. |

## Project structure
