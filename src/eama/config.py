from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AnalysisConfig:
    date_column: str
    column_mapping: dict[str, str]
    metrics: list[str]
    dimensions: list[str]
    rolling_window_days: int = 14
    minimum_history_days: int = 7
    z_score_threshold: float = 3.0
    minimum_relative_change: float = 0.30
    analysis_frequency: str = "D"
    metric_aggregations: dict[str, str] = field(default_factory=dict)

    def aggregation_for(self, metric: str) -> str:
        """Return 'sum' or 'mean' for a given metric, defaulting to 'sum'."""
        return self.metric_aggregations.get(metric, "sum")


def load_config(path: str | Path) -> AnalysisConfig:
    with Path(path).open(encoding="utf-8") as file:
        config = AnalysisConfig(**json.load(file))

    if config.minimum_history_days < 2:
        raise ValueError("minimum_history_days must be at least 2")

    if config.rolling_window_days < config.minimum_history_days:
        raise ValueError(
            "rolling_window_days must be at least minimum_history_days"
        )

    invalid_aggregations = {
        metric: aggregation
        for metric, aggregation in config.metric_aggregations.items()
        if aggregation not in {"sum", "mean"}
    }
    if invalid_aggregations:
        raise ValueError(
            f"metric_aggregations values must be 'sum' or 'mean': "
            f"{invalid_aggregations}"
        )

    return config