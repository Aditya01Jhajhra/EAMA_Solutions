from __future__ import annotations

from pathlib import Path

import pandas as pd

ALERT_HISTORY_COLUMNS = [
    "date",
    "dimension",
    "dimension_value",
    "metrics_affected",
    "summary",
    "first_seen",
]


def load_alert_history(path: str | Path) -> pd.DataFrame:
    """Load previously-surfaced alerts, or an empty history if none exists."""
    history_path = Path(path)
    if not history_path.exists():
        return pd.DataFrame(columns=ALERT_HISTORY_COLUMNS)
    return pd.read_csv(history_path)


def filter_new_alerts(
    business_alerts: pd.DataFrame,
    history: pd.DataFrame,
) -> pd.DataFrame:
    """Return only the alerts that are not already present in history.

    An alert is considered a repeat if it matches a prior entry on
    (date, dimension, dimension_value) -- the same key business_alerts.py
    already groups by, so "Office category, week ending 2022-05-15"
    will only ever be surfaced once, even across repeated runs.
    """
    if business_alerts.empty:
        return business_alerts.copy()

    key_columns = ["date", "dimension", "dimension_value"]

    if history.empty:
        return business_alerts.copy()

    merged = business_alerts.merge(
        history[key_columns].drop_duplicates(),
        on=key_columns,
        how="left",
        indicator=True,
    )

    new_alerts = merged[merged["_merge"] == "left_only"].drop(
        columns=["_merge"]
    )

    return new_alerts.reset_index(drop=True)


def append_to_history(
    new_alerts: pd.DataFrame,
    history: pd.DataFrame,
    path: str | Path,
) -> Path:
    """Record newly-surfaced alerts into history and save it to disk."""
    history_path = Path(path)
    history_path.parent.mkdir(parents=True, exist_ok=True)

    if new_alerts.empty:
        if not history_path.exists():
            history.to_csv(history_path, index=False)
        return history_path

    stamped_alerts = new_alerts.copy()
    stamped_alerts["first_seen"] = pd.Timestamp.now().date().isoformat()

    updated_history = pd.concat(
        [history, stamped_alerts], ignore_index=True
    )
    updated_history.to_csv(history_path, index=False)

    return history_path