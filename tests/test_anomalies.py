import sys
from pathlib import Path
import unittest

import pandas as pd

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src"),
)

from eama.anomalies import detect_anomalies
from eama.config import AnalysisConfig


class AnomalyTests(unittest.TestCase):
    def test_detects_large_spike_after_stable_history(self):
        frame = pd.DataFrame(
            {
                "date": pd.date_range(
                    "2026-01-01",
                    periods=15,
                ),
                "region": ["North"] * 15,
                "sales": [100.0] * 14 + [500.0],
            }
        )

        config = AnalysisConfig(
            date_column="Date",
            column_mapping={},
            metrics=["sales"],
            dimensions=["region"],
            rolling_window_days=14,
            minimum_history_days=7,
            z_score_threshold=3.0,
            minimum_relative_change=0.3,
        )

        findings = detect_anomalies(frame, config)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings.iloc[0]["severity"], "high")

    def test_ignores_normal_variation(self):
        frame = pd.DataFrame(
            {
                "date": pd.date_range(
                    "2026-01-01",
                    periods=15,
                ),
                "region": ["North"] * 15,
                "sales": [
                    100.0,
                    102.0,
                    99.0,
                    101.0,
                    98.0,
                ] * 3,
            }
        )

        config = AnalysisConfig(
            date_column="Date",
            column_mapping={},
            metrics=["sales"],
            dimensions=["region"],
            rolling_window_days=14,
            minimum_history_days=7,
            z_score_threshold=3.0,
            minimum_relative_change=0.3,
        )

        findings = detect_anomalies(frame, config)

        self.assertTrue(findings.empty)


if __name__ == "__main__":
    unittest.main()