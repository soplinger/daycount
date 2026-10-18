import unittest
from datetime import date
from fractions import Fraction

from daycount.core import (
    Calendar,
    add_business_days,
    add_months,
    adjust,
    age,
    business_days_between,
    day_count,
    parse_frequency,
    schedule,
)


class DayCountTests(unittest.TestCase):
    def test_act_360_and_act_365_use_calendar_days(self):
        start, end = date(2026, 1, 15), date(2026, 7, 15)
        self.assertEqual(day_count(start, end, "ACT/360"), Fraction(181, 360))
        self.assertEqual(day_count(start, end, "ACT/365"), Fraction(181, 365))

    def test_30_360_us_treats_month_end_as_30(self):
        self.assertEqual(day_count(date(2026, 1, 31), date(2026, 3, 31), "30/360"), Fraction(60, 360))

    def test_30e_360_differs_from_us_rule_at_february_end(self):
        start, end = date(2026, 2, 28), date(2026, 3, 31)
        self.assertEqual(day_count(start, end, "30/360"), Fraction(30, 360))
        self.assertEqual(day_count(start, end, "30E/360"), Fraction(32, 360))

    def test_act_act_isda_full_year_across_year_boundary_is_one(self):
        self.assertEqual(day_count(date(2025, 7, 1), date(2026, 7, 1), "ACT/ACT"), 1)

    def test_act_act_isda_leap_year_uses_366_day_basis(self):
        self.assertEqual(day_count(date(2024, 1, 1), date(2024, 12, 31), "ACT/ACT"), Fraction(365, 366))

    def test_reversed_dates_are_rejected(self):
        with self.assertRaises(ValueError):
            day_count(date(2026, 2, 1), date(2026, 1, 1), "ACT/365")

    def test_unknown_convention_is_rejected(self):
        with self.assertRaises(ValueError):
            day_count(date(2026, 1, 1), date(2026, 2, 1), "ACT/42")


class MonthAndFrequencyTests(unittest.TestCase):
    def test_add_months_clamps_to_month_end(self):
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(add_months(date(2024, 1, 31), 1), date(2024, 2, 29))

    def test_parse_frequency_accepts_names_and_counts(self):
        self.assertEqual(parse_frequency("quarterly"), 3)
        self.assertEqual(parse_frequency("Semiannual"), 6)
        self.assertEqual(parse_frequency("2m"), 2)
        with self.assertRaises(ValueError):
            parse_frequency("0m")
        with self.assertRaises(ValueError):
            parse_frequency("fortnightly")


class BusinessDayTests(unittest.TestCase):
    def test_business_days_count_is_start_inclusive_end_exclusive(self):
        # Mon 2026-01-05 up to Mon 2026-01-12 is Mon..Fri = 5 business days.
        self.assertEqual(
            business_days_between(date(2026, 1, 5), date(2026, 1, 12), Calendar()), 5
        )

    def test_holiday_removes_a_business_day(self):
        cal = Calendar(holidays={date(2026, 1, 7): "Test holiday"})
        self.assertEqual(business_days_between(date(2026, 1, 5), date(2026, 1, 12), cal), 4)

    def test_add_business_days_skips_weekend_and_holiday(self):
        # Fri 2026-01-02 + 1 business day is Mon 2026-01-05.
        self.assertEqual(add_business_days(date(2026, 1, 2), 1, Calendar()), date(2026, 1, 5))
        cal = Calendar(holidays={date(2026, 1, 5): "Test holiday"})
        self.assertEqual(add_business_days(date(2026, 1, 2), 1, cal), date(2026, 1, 6))

    def test_modified_following_moves_back_when_crossing_month_end(self):
        # Sat 2026-01-31: following would land in February, so modified goes back to Fri 30th.
        self.assertEqual(adjust(date(2026, 1, 31), Calendar(), "modified"), date(2026, 1, 30))
        # Sat 2026-01-03 has no month crossing, so it rolls forward to Mon 5th.
        self.assertEqual(adjust(date(2026, 1, 3), Calendar(), "modified"), date(2026, 1, 5))


class ScheduleTests(unittest.TestCase):
    def test_quarterly_schedule_covers_a_year_exactly(self):
        periods = schedule(date(2026, 1, 15), date(2027, 1, 15), 3, "ACT/365", Calendar(), "none")
        self.assertEqual(len(periods), 4)
        self.assertEqual(sum(p.days for p in periods), 365)
        self.assertEqual(sum((p.fraction for p in periods), Fraction(0)), 1)
        self.assertEqual(periods[-1].end, date(2027, 1, 15))

    def test_pay_date_is_adjusted_but_accrual_uses_unadjusted_dates(self):
        # 2026-03-14 is a Saturday, so modified-following pays on Mon 2026-03-16 (no month cross).
        periods = schedule(date(2026, 1, 14), date(2026, 3, 14), 2, "ACT/360", Calendar(), "modified")
        self.assertEqual(periods[-1].end, date(2026, 3, 14))
        self.assertEqual(periods[-1].pay, date(2026, 3, 16))

    def test_schedule_rejects_empty_span(self):
        with self.assertRaises(ValueError):
            schedule(date(2026, 1, 1), date(2026, 1, 1), 1, "ACT/365", Calendar(), "none")


class AgeTests(unittest.TestCase):
    def test_age_in_years_months_and_days(self):
        self.assertEqual(age(date(1990, 6, 15), date(2026, 10, 18)), (36, 4, 3))

    def test_age_handles_month_end_birthdays(self):
        self.assertEqual(age(date(2000, 1, 31), date(2000, 2, 29)), (0, 1, 0))

    def test_age_rejects_future_birth(self):
        with self.assertRaises(ValueError):
            age(date(2030, 1, 1), date(2026, 1, 1))


if __name__ == "__main__":
    unittest.main()
