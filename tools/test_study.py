"""Focused checks for evidence gating and exact cumulative PDI plots."""

# SPDX-License-Identifier: EPL-2.0
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cbc_pdi
import numpy as np
import report
from report import cumulative_curve
from run_study import measure


class StudyTest(unittest.TestCase):
    def test_incomplete_study_writes_failure_report(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "manifest.json").write_text(
                '{"tasks":[{"arm":"off","seed":6401,"instance":"missing"}]}'
            )
            with patch("sys.argv", ["report.py", "--out", directory]):
                self.assertEqual(report.main(), 1)
            self.assertIn("INCOMPLETE", (folder / "REPORT.md").read_text())

    def test_cumulative_plot_matches_exact_integral(self):
        tr = cbc_pdi.Trace()
        tr.add_primal(2, 10)
        tr.add_dual(4, 5)
        tr.final_primal = 10
        tr.end_time = 8
        tr.status = "optimal"
        tr.dual.append((8, 10))
        grid = np.array([0.0, 2.0, 4.0, 8.0, 10.0])
        got = cumulative_curve(tr, 10, grid)
        np.testing.assert_allclose(got, [0, 0.4, 0.6, 0.8, 0.8])
        self.assertAlmostEqual(got[-1], cbc_pdi.integrate(tr, 10)["pdi"])

    def test_missing_and_out_of_order_final_events_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            log, progress = folder / "test.log", folder / "test.progress.csv"
            log.write_text("Result - Stopped on time limit\n")
            header = "time,primal,dual,source\n"
            reference = {"sense": "min", "objective": "10", "status": "best_known"}
            progress.write_text(header + "1,10,-1e50,solution\n")
            with self.assertRaisesRegex(ValueError, "Missing final"):
                measure(log, progress, reference, 10)
            progress.write_text(header + "2,10,5,solution\n1,10,5,final\n")
            with self.assertRaisesRegex(ValueError, "non-monotonic"):
                measure(log, progress, reference, 10)

    def test_late_proof_does_not_count_as_within_horizon(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            log, progress = folder / "test.log", folder / "test.progress.csv"
            log.write_text("Result - Optimal solution found\nObjective value: 10\n")
            progress.write_text(
                "time,primal,dual,source\n2,10,5,solution\n12,10,10,final\n"
            )
            metrics = measure(
                log,
                progress,
                {"sense": "min", "objective": "10", "status": "optimal"},
                10,
            )
            self.assertFalse(metrics["optimal_within_horizon"])
            self.assertAlmostEqual(metrics["final_gap"], 0.5)
            self.assertAlmostEqual(metrics["pdi"], 0.8)


if __name__ == "__main__":
    unittest.main()
