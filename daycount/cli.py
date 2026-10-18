"""Command-line interface: argparse subcommands with text or JSON output."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction

from . import __version__
from .calfile import load_calendar
from .core import (
    ADJUST_RULES,
    CONVENTIONS,
    Calendar,
    add_business_days,
    adjust,
    age,
    business_days_between,
    day_count,
    days_in_year,
    parse_frequency,
    schedule,
)

PLACES = Decimal("0.0000000001")


def _date(text):
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date {text!r} (use YYYY-MM-DD)")


def _decimal(value):
    """Format an exact Fraction as a 10-place decimal string."""
    return str((Decimal(value.numerator) / Decimal(value.denominator)).quantize(PLACES, ROUND_HALF_EVEN))


def _load(path):
    if path is None:
        return Calendar()
    calendar, issues = load_calendar(path)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        first = errors[0]
        raise ValueError(f"{first.render(path)} (run 'daycount lint {path}' for all issues)")
    return calendar


def _dump(data):
    print(json.dumps(data, indent=2))


def cmd_fraction(args):
    fraction = day_count(args.start, args.end, args.conv)
    print(f"Start:       {args.start.isoformat()}")
    print(f"End:         {args.end.isoformat()}")
    print(f"Convention:  {args.conv}")
    print(f"Days:        {(args.end - args.start).days}")
    print(f"Fraction:    {_decimal(fraction)}  ({fraction.numerator}/{fraction.denominator})")
    return 0


def cmd_table(args):
    rows = [
        {"convention": conv, "fraction": day_count(args.start, args.end, conv)}
        for conv in CONVENTIONS
    ]
    if args.json:
        _dump([
            {"convention": row["convention"], "fraction": _decimal(row["fraction"])}
            for row in rows
        ])
        return 0
    print(f"{args.start} to {args.end} ({(args.end - args.start).days} calendar days)")
    for row in rows:
        print(f"  {row['convention']:<9} {_decimal(row['fraction'])}")
    return 0


def cmd_bizdays(args):
    calendar = _load(args.calendar)
    count = business_days_between(args.start, args.end, calendar)
    print(f"Business days from {args.start} up to, not including, {args.end}: {count}")
    print(f"Calendar days: {(args.end - args.start).days}")
    return 0


def cmd_add(args):
    calendar = _load(args.calendar)
    result = add_business_days(args.start, args.n, calendar)
    print(f"{args.n} business day(s) after {args.start} is {result.isoformat()} ({result:%A})")
    return 0


def cmd_adjust(args):
    calendar = _load(args.calendar)
    result = adjust(args.date, calendar, args.rule)
    moved = (result - args.date).days
    print(f"{args.date.isoformat()} ({args.date:%A}) -> {result.isoformat()} ({result:%A})")
    print(f"Rule: {args.rule}; moved {moved} calendar day(s)")
    return 0


def cmd_schedule(args):
    calendar = _load(args.calendar)
    months = parse_frequency(args.every)
    periods = schedule(args.start, args.end, months, args.conv, calendar, args.adjust)
    total_days = sum(period.days for period in periods)
    total_fraction = sum((period.fraction for period in periods), Fraction(0))
    if args.json:
        _dump({
            "convention": args.conv,
            "periods": [
                {
                    "number": period.number,
                    "start": period.start.isoformat(),
                    "end": period.end.isoformat(),
                    "pay": period.pay.isoformat(),
                    "days": period.days,
                    "fraction": _decimal(period.fraction),
                }
                for period in periods
            ],
            "total_days": total_days,
            "total_fraction": _decimal(total_fraction),
        })
        return 0
    print(f"{'#':>3}  {'Start':<10}  {'End':<10}  {'Pay':<10}  {'Days':>5}  Fraction")
    for period in periods:
        print(
            f"{period.number:>3}  {period.start.isoformat():<10}  {period.end.isoformat():<10}  "
            f"{period.pay.isoformat():<10}  {period.days:>5}  {_decimal(period.fraction)}"
        )
    print(f"{'':>3}  {'Total':<10}  {'':<10}  {'':<10}  {total_days:>5}  {_decimal(total_fraction)}")
    return 0


def cmd_info(args):
    calendar = _load(args.calendar)
    iso_year, iso_week, iso_day = args.date.isocalendar()
    print(f"Date:        {args.date.isoformat()} ({args.date:%A})")
    print(f"ISO week:    {iso_year}-W{iso_week:02d}-{iso_day}")
    print(f"Day of year: {args.date.timetuple().tm_yday} of {days_in_year(args.date.year)}")
    if args.calendar is not None:
        if args.date in calendar.holidays:
            status = f"holiday ({calendar.holidays[args.date]})"
        elif args.date.weekday() in calendar.weekend:
            status = "weekend"
        else:
            status = "business day"
        print(f"Calendar:    {status}")
    return 0


def cmd_age(args):
    as_of = args.asof or date.today()
    years, months, days = age(args.birth, as_of)
    print(f"As of {as_of.isoformat()}: {years} years, {months} months, {days} days")
    print(f"Total days: {(as_of - args.birth).days}")
    return 0


def cmd_lint(args):
    calendar, issues = load_calendar(args.file)
    for issue in issues:
        print(issue.render(args.file))
    errors = sum(1 for issue in issues if issue.severity == "error")
    warnings = len(issues) - errors
    if not issues:
        print(f"{args.file}: OK ({len(calendar.holidays)} holiday(s))")
    else:
        print(f"{args.file}: {errors} error(s), {warnings} warning(s)")
    if errors or (args.strict and warnings):
        return 1
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="daycount",
        description="Offline day-count, business-day and payment-schedule calculator.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = sub.add_parser("fraction", help="year fraction between two dates under one convention")
    p.add_argument("start", type=_date)
    p.add_argument("end", type=_date)
    p.add_argument("--conv", choices=CONVENTIONS, default="ACT/365")
    p.set_defaults(handler=cmd_fraction)

    p = sub.add_parser("table", help="year fraction under every convention side by side")
    p.add_argument("start", type=_date)
    p.add_argument("end", type=_date)
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(handler=cmd_table)

    p = sub.add_parser("bizdays", help="count business days in [start, end)")
    p.add_argument("start", type=_date)
    p.add_argument("end", type=_date)
    p.add_argument("--calendar", metavar="FILE", help="holiday calendar file")
    p.set_defaults(handler=cmd_bizdays)

    p = sub.add_parser("add", help="step forward a number of business days")
    p.add_argument("start", type=_date)
    p.add_argument("n", type=int)
    p.add_argument("--calendar", metavar="FILE", help="holiday calendar file")
    p.set_defaults(handler=cmd_add)

    p = sub.add_parser("adjust", help="roll a date onto a business day")
    p.add_argument("date", type=_date)
    p.add_argument("--rule", choices=ADJUST_RULES, default="modified")
    p.add_argument("--calendar", metavar="FILE", help="holiday calendar file")
    p.set_defaults(handler=cmd_adjust)

    p = sub.add_parser("schedule", help="regular accrual periods with pay dates")
    p.add_argument("start", type=_date)
    p.add_argument("end", type=_date)
    p.add_argument("--every", default="quarterly",
                   help="monthly, quarterly, semiannual, annual or Nm (default quarterly)")
    p.add_argument("--conv", choices=CONVENTIONS, default="ACT/360")
    p.add_argument("--adjust", choices=ADJUST_RULES, default="modified")
    p.add_argument("--calendar", metavar="FILE", help="holiday calendar file")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(handler=cmd_schedule)

    p = sub.add_parser("info", help="ISO week, day of year and calendar status for a date")
    p.add_argument("date", type=_date)
    p.add_argument("--calendar", metavar="FILE", help="holiday calendar file")
    p.set_defaults(handler=cmd_info)

    p = sub.add_parser("age", help="exact years, months and days between two dates")
    p.add_argument("birth", type=_date)
    p.add_argument("--asof", type=_date, help="date to measure to (default: today)")
    p.set_defaults(handler=cmd_age)

    p = sub.add_parser("lint", help="check a holiday calendar file with line-numbered issues")
    p.add_argument("file")
    p.add_argument("--strict", action="store_true", help="treat warnings as failures")
    p.set_defaults(handler=cmd_lint)

    return parser


def main(argv=None):
    """Run the CLI. Returns 0 on success, 1 on lint failure, 2 on bad input."""
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except OSError as exc:
        print(f"daycount: error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"daycount: error: {exc}", file=sys.stderr)
        return 2
