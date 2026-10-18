import contextlib
import io
import json
import os
import tempfile
import unittest

from daycount.cli import main

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "examples", "us-federal-2026.txt")


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def write_calendar(self, directory, text):
        path = os.path.join(directory, "cal.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_fraction_prints_days_and_fraction(self):
        code, out, _ = run(["fraction", "2026-01-15", "2026-07-15", "--conv", "ACT/365"])
        self.assertEqual(code, 0)
        self.assertIn("Days:        181", out)
        self.assertIn("Fraction:    0.4958904110", out)

    def test_table_json_lists_every_convention(self):
        code, out, _ = run(["table", "2026-01-15", "2026-07-15", "--json"])
        self.assertEqual(code, 0)
        rows = json.loads(out)
        self.assertEqual([row["convention"] for row in rows],
                         ["ACT/360", "ACT/365", "ACT/ACT", "30/360", "30E/360"])

    def test_schedule_json_totals_match_periods(self):
        code, out, _ = run(["schedule", "2026-01-15", "2027-01-15", "--every", "quarterly",
                            "--conv", "ACT/365", "--adjust", "none", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(len(data["periods"]), 4)
        self.assertEqual(data["total_days"], 365)
        self.assertEqual(data["total_fraction"], "1.0000000000")

    def test_bizdays_uses_the_example_calendar(self):
        # Jan 1-30 2026 has 22 weekdays; New Year's Day (Thu 1st) and MLK Day (Mon 19th) remove two.
        code, out, _ = run(["bizdays", "2026-01-01", "2026-01-31", "--calendar", SAMPLE])
        self.assertEqual(code, 0)
        self.assertIn("Business days from 2026-01-01 up to, not including, 2026-01-31: 20", out)

    def test_adjust_reports_the_moved_date(self):
        code, out, _ = run(["adjust", "2026-01-31", "--rule", "modified"])
        self.assertEqual(code, 0)
        self.assertIn("-> 2026-01-30 (Friday)", out)

    def test_info_reports_holiday_status(self):
        code, out, _ = run(["info", "2026-12-25", "--calendar", SAMPLE])
        self.assertEqual(code, 0)
        self.assertIn("holiday (Christmas Day)", out)

    def test_lint_fails_with_exit_1_and_prints_line_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_calendar(directory, "2026-02-30 Broken\n")
            code, out, _ = run(["lint", path])
        self.assertEqual(code, 1)
        self.assertIn(f"{path}:1: error:", out)

    def test_lint_passes_the_example_calendar(self):
        code, out, _ = run(["lint", SAMPLE])
        self.assertEqual(code, 0)
        self.assertIn("OK (11 holiday(s))", out)

    def test_bad_calendar_for_bizdays_exits_2(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_calendar(directory, "2026-02-30 Broken\n")
            code, _, err = run(["bizdays", "2026-01-01", "2026-02-01", "--calendar", path])
        self.assertEqual(code, 2)
        self.assertIn(":1: error:", err)

    def test_reversed_dates_exit_2_with_message(self):
        code, _, err = run(["fraction", "2026-02-01", "2026-01-01"])
        self.assertEqual(code, 2)
        self.assertIn("end date is before start date", err)


if __name__ == "__main__":
    unittest.main()
