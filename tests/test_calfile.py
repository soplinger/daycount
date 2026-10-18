import unittest
from datetime import date

from daycount.calfile import parse_calendar


class CalendarParseTests(unittest.TestCase):
    def test_clean_calendar_has_no_issues(self):
        text = "weekend sat sun\n2026-01-01 New Year's Day\n# comment\n\n2026-07-03 Observed\n"
        calendar, issues = parse_calendar(text)
        self.assertEqual(issues, [])
        self.assertEqual(calendar.holidays[date(2026, 1, 1)], "New Year's Day")
        self.assertEqual(calendar.holidays[date(2026, 7, 3)], "Observed")

    def test_errors_carry_line_numbers(self):
        text = (
            "weekend sat sun\n"          # line 1
            "2026-02-30 Not a date\n"    # line 2
            "2026-03-1 Bad shape\n"      # line 3
            "2026-04-06 Fine\n"          # line 4
            "2026-04-06 Duplicate\n"     # line 5
            "weekend funday\n"           # line 6
        )
        _, issues = parse_calendar(text)
        by_line = {issue.line: issue for issue in issues if issue.severity == "error"}
        self.assertIn(2, by_line)
        self.assertIn("not a real calendar date", by_line[2].message)
        self.assertIn(3, by_line)
        self.assertIn("YYYY-MM-DD", by_line[3].message)
        self.assertIn(5, by_line)
        self.assertIn("line 4", by_line[5].message)
        self.assertIn(6, by_line)
        self.assertIn("unknown weekday", by_line[6].message)

    def test_holiday_on_weekend_is_a_warning(self):
        # 2026-01-03 is a Saturday.
        _, issues = parse_calendar("2026-01-03 Saturday thing\n")
        self.assertEqual([(i.line, i.severity) for i in issues], [(1, "warning")])

    def test_weekend_none_makes_every_day_a_business_day(self):
        calendar, issues = parse_calendar("weekend none\n")
        self.assertEqual(issues, [])
        self.assertTrue(calendar.is_business_day(date(2026, 1, 3)))

    def test_issues_render_as_path_line_severity(self):
        _, issues = parse_calendar("nonsense\n")
        self.assertEqual(
            issues[0].render("cal.txt"),
            "cal.txt:1: error: expected YYYY-MM-DD or 'weekend', got 'nonsense'",
        )


if __name__ == "__main__":
    unittest.main()
