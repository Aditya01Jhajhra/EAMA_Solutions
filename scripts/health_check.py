"""
EAMA project health check.

Run this any time after making code changes to confirm every module
still imports correctly and the full pipeline still runs end to end
on a small built-in synthetic dataset. This does not replace real
testing on your actual data, but it catches broken imports, syntax
errors, and pipeline regressions in seconds, before you go looking
for them by hand.

Usage:
    $env:PYTHONPATH = ".\\src"
    .\\.venv\\Scripts\\python.exe scripts\\health_check.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

CHECK_MARK = "✓"
CROSS_MARK = "✗"

results: list[tuple[str, bool, str]] = []


def check(label: str):
    def decorator(func):
        try:
            func()
            results.append((label, True, ""))
        except Exception as error:  # noqa: BLE001
            results.append((label, False, f"{type(error).__name__}: {error}"))
        return func
    return decorator


MODULES = [
    "eama.config",
    "eama.ingestion",
    "eama.auto_config",
    "eama.generate_config",
    "eama.anomalies",
    "eama.business_alerts",
    "eama.alert_history",
    "eama.reporting",
    "eama.pdf_report",
    "eama.email_drafts",
    "eama.email_sender",
    "eama.pipeline",
    "eama.cli",
    "eama.api",
]

for module_name in MODULES:
    @check(f"import {module_name}")
    def _run(module_name=module_name):
        __import__(module_name)


@check("full pipeline runs end to end")
def _run():
    import pandas as pd
    import numpy as np

    from eama.pipeline import run_pipeline

    np.random.seed(1)
    dates = pd.date_range("2023-01-01", "2023-12-31", freq="D")
    categories = ["A", "B", "C"]

    rows = []
    for d in dates:
        for c in categories:
            rows.append(
                {
                    "Date": d.strftime("%Y-%m-%d"),
                    "Category": c,
                    "Sales": int(np.random.randint(100, 1000)),
                }
            )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_csv = tmp_path / "health_check_input.csv"
        pd.DataFrame(rows).to_csv(input_csv, index=False)

        result = run_pipeline(
            input_path=input_csv,
            config_path=None,
            output_path=tmp_path / "outputs" / "anomalies.csv",
            history_path=tmp_path / "state" / "alert_history.csv",
        )

        assert result.records_loaded == len(rows), "record count mismatch"
        assert result.excel_report_path.exists(), "Excel report was not created"
        assert result.pdf_report_path.exists(), "PDF report was not created"
        assert result.findings_path.exists(), "findings CSV was not created"


@check("FastAPI app loads and responds")
def _run():
    from fastapi.testclient import TestClient
    from eama.api import app

    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200, f"unexpected status {response.status_code}"
    assert response.json().get("status") == "ok", "unexpected health response"


print("=" * 60)
print("EAMA HEALTH CHECK")
print("=" * 60)

failed = 0
for label, passed, error in results:
    mark = CHECK_MARK if passed else CROSS_MARK
    print(f"  {mark} {label}")
    if not passed:
        failed += 1
        print(f"      -> {error}")

print("=" * 60)
print(f"{len(results) - failed}/{len(results)} checks passed")

if failed:
    print(f"\n{failed} check(s) FAILED. See details above.")
    sys.exit(1)
else:
    print("\nAll checks passed.")
    sys.exit(0)