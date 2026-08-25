"""Daily odds history, so the page can show which way a race is moving.

Kyle wants the trend expressed as "and here is where it was 7 days ago". That
cannot be backfilled from anywhere -- ESPN and Hockey-Reference both publish
only today's number -- so the value of this file starts accruing the first day
it runs and not before.

One CSV per league, one row per team per day:

    date,team,pct

Appended only when the run is for today, so rebuilding an old page cannot
stamp it with current numbers. Same rule, and same reason, as the games-back
history in sports-daily.
"""

import csv
import datetime
import os

HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY = os.path.join(HERE, "output", "history")
LOOKBACK_DAYS = 7
# A run can be missed (the season pauses, a build fails), so accept the
# nearest reading in a window around the target rather than that exact date.
WINDOW = (5, 10)


def _path(league):
    return os.path.join(HISTORY, "odds-%s.csv" % league)


def record(league, values, today=None):
    """values: {team: percent}. Writes one row per team, once per day."""
    if not values:
        return
    today = today or datetime.date.today()
    stamp = today.isoformat()
    os.makedirs(HISTORY, exist_ok=True)
    path = _path(league)
    seen = set()
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row.get("date") == stamp:
                    seen.add(row.get("team"))
    new = [(team, pct) for team, pct in sorted(values.items()) if team not in seen]
    if not new:
        return
    fresh = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if fresh:
            writer.writerow(["date", "team", "pct"])
        for team, pct in new:
            writer.writerow([stamp, team, "%.1f" % pct])


def read(league):
    """{team: [(date, pct)]} sorted oldest first."""
    path = _path(league)
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                date = datetime.date.fromisoformat(row["date"])
                pct = float(row["pct"])
            except (KeyError, ValueError, TypeError):
                continue
            out.setdefault(row["team"], []).append((date, pct))
    for team in out:
        out[team].sort()
    return out


def previous(league, team, today=None):
    """The reading closest to a week ago, or None if we have not run long enough."""
    today = today or datetime.date.today()
    series = read(league).get(team) or []
    best, best_off = None, None
    for date, pct in series:
        age = (today - date).days
        if WINDOW[0] <= age <= WINDOW[1]:
            off = abs(age - LOOKBACK_DAYS)
            if best_off is None or off < best_off:
                best, best_off = pct, off
    return best


def trend(league, team, current, today=None):
    """(previous, delta) or (None, None) when there is not enough history."""
    prev = previous(league, team, today)
    if prev is None or current is None:
        return None, None
    return prev, current - prev
