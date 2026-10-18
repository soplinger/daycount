"""Plain-text holiday calendar: parsing and line-numbered lint.

Format, one entry per line; blank lines and lines starting with '#' are ignored.
Inline comments are not supported. Use 'weekend none' for a calendar with no weekend:

    weekend sat sun
    2026-01-01 New Year's Day
    2026-07-03 Independence Day (observed)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .core import WEEKDAY_NAMES, Calendar

DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
DEFAULT_WEEKEND = frozenset({5, 6})


@dataclass(frozen=True)
class Issue:
    line: int
    severity: str
    message: str

    def render(self, path):
        return f"{path}:{self.line}: {self.severity}: {self.message}"


def parse_calendar(text):
    """Parse calendar text into (Calendar, issues). Bad lines are skipped, not fatal."""
    issues = []
    holidays = {}
    first_seen = {}
    weekend = DEFAULT_WEEKEND
    weekend_line = None
    entries = []

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        words = line.split()
        head = words[0]

        if head.lower() == "weekend":
            if weekend_line is not None:
                issues.append(
                    Issue(number, "warning",
                          f"weekend already set on line {weekend_line}; this line overrides it")
                )
            names = [word.lower() for word in words[1:]]
            if not names:
                issues.append(Issue(number, "error", "weekend needs day names (mon..sun) or 'none'"))
                continue
            if names == ["none"]:
                weekend = frozenset()
            else:
                unknown = [name for name in names if name not in WEEKDAY_NAMES]
                if unknown:
                    issues.append(Issue(number, "error", f"unknown weekday {unknown[0]!r} (use mon..sun)"))
                    continue
                weekend = frozenset(WEEKDAY_NAMES.index(name) for name in names)
            weekend_line = number
            continue

        if not DATE_PATTERN.fullmatch(head):
            issues.append(Issue(number, "error", f"expected YYYY-MM-DD or 'weekend', got {head!r}"))
            continue
        try:
            day = date.fromisoformat(head)
        except ValueError:
            issues.append(Issue(number, "error", f"{head} is not a real calendar date"))
            continue
        if day in first_seen:
            issues.append(
                Issue(number, "error", f"duplicate date {head} (first listed on line {first_seen[day]})")
            )
            continue
        first_seen[day] = number
        holidays[day] = " ".join(words[1:]) or "holiday"
        entries.append((number, day))

    for number, day in entries:
        if day.weekday() in weekend:
            issues.append(
                Issue(number, "warning", f"{day.isoformat()} already falls on a weekend")
            )

    issues.sort(key=lambda issue: issue.line)
    return Calendar(holidays=holidays, weekend=weekend), issues


def load_calendar(path):
    with open(path, encoding="utf-8") as handle:
        return parse_calendar(handle.read())
