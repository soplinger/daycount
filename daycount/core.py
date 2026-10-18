"""Exact date arithmetic for finance and scheduling.

Day-count fractions are returned as fractions.Fraction, so nothing is rounded
until the output layer formats them.
"""

from __future__ import annotations

import calendar as pycal
from dataclasses import dataclass, field
from datetime import date, timedelta
from fractions import Fraction

CONVENTIONS = ("ACT/360", "ACT/365", "ACT/ACT", "30/360", "30E/360")
ADJUST_RULES = ("following", "modified", "preceding", "none")
FREQUENCIES = {"monthly": 1, "quarterly": 3, "semiannual": 6, "annual": 12}
WEEKDAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
MAX_SEARCH_DAYS = 366


def days_in_month(year, month):
    return pycal.monthrange(year, month)[1]


def days_in_year(year):
    return 366 if pycal.isleap(year) else 365


def add_months(d, months):
    """Shift d by whole months, clamping the day to the end of the target month."""
    year, month_index = divmod(d.year * 12 + (d.month - 1) + months, 12)
    month = month_index + 1
    return date(year, month, min(d.day, days_in_month(year, month)))


def parse_frequency(text):
    """Turn 'quarterly', 'semiannual' or 'Nm' into a number of months."""
    key = text.lower()
    if key in FREQUENCIES:
        return FREQUENCIES[key]
    if key.endswith("m") and key[:-1].isdigit() and int(key[:-1]) > 0:
        return int(key[:-1])
    raise ValueError(
        f"unknown frequency {text!r} (use monthly, quarterly, semiannual, annual or Nm)"
    )


def _is_last_feb(d):
    return d.month == 2 and d.day == days_in_month(d.year, 2)


def _thirty_360_days(start, end, us_rule):
    """Day count under the 30/360 US or 30E/360 (Eurobond) rules."""
    d1, d2 = start.day, end.day
    if us_rule:
        if _is_last_feb(start) and _is_last_feb(end):
            d2 = 30
        if _is_last_feb(start):
            d1 = 30
        if d2 == 31 and d1 >= 30:
            d2 = 30
    elif d2 == 31:
        d2 = 30
    if d1 == 31:
        d1 = 30
    return 360 * (end.year - start.year) + 30 * (end.month - start.month) + (d2 - d1)


def _act_act_isda(start, end):
    """ACT/ACT (ISDA): each calendar year is weighted by its own length."""
    if start.year == end.year:
        return Fraction((end - start).days, days_in_year(start.year))
    total = Fraction((date(start.year + 1, 1, 1) - start).days, days_in_year(start.year))
    total += Fraction((end - date(end.year, 1, 1)).days, days_in_year(end.year))
    total += end.year - start.year - 1
    return total


def day_count(start, end, convention):
    """Year fraction from start to end under a convention, as an exact Fraction."""
    if end < start:
        raise ValueError("end date is before start date")
    if convention == "ACT/360":
        return Fraction((end - start).days, 360)
    if convention == "ACT/365":
        return Fraction((end - start).days, 365)
    if convention == "ACT/ACT":
        return _act_act_isda(start, end)
    if convention == "30/360":
        return Fraction(_thirty_360_days(start, end, us_rule=True), 360)
    if convention == "30E/360":
        return Fraction(_thirty_360_days(start, end, us_rule=False), 360)
    raise ValueError(f"unknown day-count convention {convention!r}")


@dataclass
class Calendar:
    """Business-day rules: a weekend mask plus a dict of holiday dates to names."""

    holidays: dict = field(default_factory=dict)
    weekend: frozenset = frozenset({5, 6})

    def is_business_day(self, d):
        return d.weekday() not in self.weekend and d not in self.holidays


def _search(d, calendar, step):
    """Walk from d (exclusive) by step days until a business day is found."""
    cur = d
    for _ in range(MAX_SEARCH_DAYS):
        cur += timedelta(days=step)
        if calendar.is_business_day(cur):
            return cur
    raise ValueError("no business day found within a year; check the calendar")


def adjust(d, calendar, rule):
    """Roll a non-business day to a business day using a convention rule."""
    if rule not in ADJUST_RULES:
        raise ValueError(f"unknown adjustment rule {rule!r}")
    if rule == "none" or calendar.is_business_day(d):
        return d
    if rule == "following":
        return _search(d, calendar, 1)
    if rule == "preceding":
        return _search(d, calendar, -1)
    forward = _search(d, calendar, 1)
    if forward.month != d.month:
        return _search(d, calendar, -1)
    return forward


def add_business_days(d, n, calendar):
    """The nth business day strictly after d (n=0 returns d unchanged)."""
    if n < 0:
        raise ValueError("business-day offset must be zero or positive")
    cur = d
    for _ in range(n):
        cur = _search(cur, calendar, 1)
    return cur


def business_days_between(start, end, calendar):
    """Business days in [start, end): start counts, end does not."""
    if end < start:
        raise ValueError("end date is before start date")
    count = 0
    cur = start
    while cur < end:
        if calendar.is_business_day(cur):
            count += 1
        cur += timedelta(days=1)
    return count


def age(birth, asof):
    """Whole years, months and days from birth to asof."""
    if asof < birth:
        raise ValueError("as-of date is before birth date")
    months = (asof.year - birth.year) * 12 + asof.month - birth.month
    if add_months(birth, months) > asof:
        months -= 1
    anchor = add_months(birth, months)
    return months // 12, months % 12, (asof - anchor).days


@dataclass(frozen=True)
class Period:
    number: int
    start: date
    end: date
    pay: date
    days: int
    fraction: Fraction


def schedule(start, end, months, convention, calendar, rule):
    """Split start..end into regular periods, anchored on the start day-of-month.

    Accrual uses the unadjusted period dates; the pay date is the adjusted end.
    The final period is cut at end even when the cadence does not land on it.
    """
    if end <= start:
        raise ValueError("schedule end must be after its start")
    if months <= 0:
        raise ValueError("schedule frequency must be at least one month")
    boundaries = [start]
    step = 1
    while True:
        boundary = add_months(start, months * step)
        if boundary >= end:
            break
        boundaries.append(boundary)
        step += 1
    boundaries.append(end)
    periods = []
    for number, (a, b) in enumerate(zip(boundaries, boundaries[1:]), start=1):
        periods.append(
            Period(
                number=number,
                start=a,
                end=b,
                pay=adjust(b, calendar, rule),
                days=(b - a).days,
                fraction=day_count(a, b, convention),
            )
        )
    return periods
