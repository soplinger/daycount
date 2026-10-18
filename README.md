# Daycount

**Exact day-count fractions, business-day arithmetic and payment schedules, offline, from one plain-text holiday file.**

Daycount answers the questions that finance paperwork keeps asking: how many
years is this period under ACT/360 versus 30/360, which day does a payment roll
to when it lands on a holiday, how many business days are left until a deadline,
and what do the accrual periods of a quarterly coupon look like. Every answer is
computed with exact rational arithmetic, so nothing is rounded until the final
decimal is printed.

It is a single standard-library Python package. No network access, no accounts,
no API keys, no runtime dependencies.

## Features

- **Five day-count conventions**: `ACT/360`, `ACT/365`, `ACT/ACT` (ISDA),
  `30/360` (US) and `30E/360` (Eurobond).
- **Exact arithmetic**: year fractions are `fractions.Fraction` internally and
  printed to ten decimal places with round-half-even.
- **Side-by-side comparison**: `table` shows every convention for one span, so
  you can see how much the basis matters.
- **Business-day counting** over a `[start, end)` span, with weekends and
  holidays from a plain-text calendar.
- **Business-day arithmetic**: step forward *n* business days, skipping weekends
  and holidays.
- **Adjustment rules**: `following`, `modified following`, `preceding` and `none`
  for rolling a date onto a business day.
- **Payment schedules**: monthly, quarterly, semiannual, annual or any `Nm`
  cadence, anchored on the start day-of-month, with accrual days, fractions and
  adjusted pay dates per period, and a totals row.
- **Schedule JSON output** for pipelines (`--json` on `table` and `schedule`).
- **Date facts**: ISO week date, day of year and whether a date is a holiday,
  weekend or business day.
- **Exact age**: years, months and days between two dates, with month-end
  birthdays handled.
- **Holiday calendar lint**: a plain-text calendar with `file:line: severity:`
  messages for bad dates, unknown weekdays, duplicates and holidays on weekends.
- **CI-friendly exit codes**: `0` success, `1` lint failure (or warnings with
  `--strict`), `2` bad input.

## Quick start

Clone or copy the folder, then run from the project root:

```sh
python3 -m daycount fraction 2026-01-15 2026-07-15
```

```
Start:       2026-01-15
End:         2026-07-15
Convention:  ACT/365
Days:        181
Fraction:    0.4958904110  (181/365)
```

Compare conventions for the same span:

```sh
python3 -m daycount table 2026-01-15 2026-07-15
```

```
2026-01-15 to 2026-07-15 (181 calendar days)
  ACT/360   0.5027777778
  ACT/365   0.4958904110
  ACT/ACT   0.4958904110
  30/360    0.5000000000
  30E/360   0.5000000000
```

Count business days with the included US federal calendar:

```sh
python3 -m daycount bizdays 2026-01-01 2026-01-31 --calendar examples/us-federal-2026.txt
```

```
Business days from 2026-01-01 up to, not including, 2026-01-31: 20
Calendar days: 30
```

Roll a payment that lands on a Saturday at a month end:

```sh
python3 -m daycount adjust 2026-01-31 --rule modified
```

```
2026-01-31 (Saturday) -> 2026-01-30 (Friday)
Rule: modified; moved -1 calendar day(s)
```

Lint your own holiday calendar (exit code 1 if it has errors):

```sh
python3 -m daycount lint examples/us-federal-2026.txt
```

```
examples/us-federal-2026.txt: OK (11 holiday(s))
```

## How to run

Requires Python 3.9 or newer. Run every command from the project root, using
`python3 -m daycount COMMAND ...`.

| Command | What it does |
| --- | --- |
| `fraction START END [--conv CONV]` | One year fraction, with the day count shown |
| `table START END [--json]` | Every convention side by side |
| `bizdays START END [--calendar FILE]` | Business days in `[START, END)` |
| `add START N [--calendar FILE]` | The Nth business day after START |
| `adjust DATE [--rule RULE] [--calendar FILE]` | Roll DATE onto a business day |
| `schedule START END [--every FREQ] [--conv CONV] [--adjust RULE] [--calendar FILE] [--json]` | Accrual periods with pay dates |
| `info DATE [--calendar FILE]` | ISO week, day of year, calendar status |
| `age BIRTH [--asof DATE]` | Exact years, months and days |
| `lint FILE [--strict]` | Check a holiday calendar file |

Dates are `YYYY-MM-DD`. Conventions are `ACT/360`, `ACT/365`, `ACT/ACT`,
`30/360` and `30E/360`. Schedule frequencies are `monthly`, `quarterly`,
`semiannual`, `annual` or `Nm`. Adjustment rules are `following`, `modified`,
`preceding` and `none`.

### Holiday calendar file

Plain text, one entry per line. Blank lines and lines starting with `#` are ignored.

```
# Use "weekend none" instead of the line below for a calendar with no weekend.
weekend sat sun
2026-01-01 New Year's Day
2026-07-03 Independence Day (observed)
```

Only whole lines can be comments. Inline `#` comments are not supported, so
anything after a date becomes part of the holiday name.

Lint messages look like this:

```
holidays.txt:2: error: 2026-02-30 is not a real calendar date
holidays.txt:5: error: duplicate date 2026-04-06 (first listed on line 4)
holidays.txt:7: warning: 2026-01-03 already falls on a weekend
```

The file in `examples/us-federal-2026.txt` is an example. Check it against an
official source before relying on it for real payments.

## Notes on the conventions

- `ACT/360` and `ACT/365` divide the calendar days between the two dates by 360 or 365.
- `30/360` (US) treats 31st days and February month-ends as 30. `30E/360` only
  clamps 31st days.
- `ACT/ACT` (ISDA) weights each calendar year touched by the span by that year's length.
- In `schedule`, accrual uses the unadjusted period dates and the pay date is the
  adjusted end date. Periods are anchored on the start day-of-month, so a
  monthly schedule from the 31st clamps to month ends without drifting.

## How to test

```sh
python3 -m unittest discover -s tests -t .
```

The suite also runs under pytest:

```sh
python3 -m pytest tests
```

The tests cover the day-count formulas, month-end and leap-year edge cases,
business-day and adjustment logic, schedule totals, age calculation, calendar
parsing with line-numbered errors, and the CLI's output and exit codes.

## Project layout

```
daycount/
  core.py      day-count, calendar, adjustment, schedule and age functions
  calfile.py   holiday calendar parser and line-numbered lint
  cli.py       argparse subcommands, text and JSON output
  __main__.py  python3 -m daycount entry point
examples/
  us-federal-2026.txt   example holiday calendar
tests/
  test_core.py  test_calfile.py  test_cli.py
```

## Limitations

- Holidays are supplied by you. Daycount ships an example calendar, not an
  authoritative holiday database.
- Dates only: there are no times, time zones or stub-period rules (front or back
  stubs). Schedules run forward from the start date and cut the last period at the end date.
- Business-day searches look at most one year ahead, so a calendar that closes
  every day raises an error instead of looping.
