"""Playoff odds, from a different source for every sport.

    NFL   ESPN FPI          probmakeplayoffs        0-100
    NBA   ESPN BPI          probmakeplayoffs        0-100
    MLB   ESPN standings    playoffPercent          already a percent string
    NHL   Hockey-Reference  prob_playoffs           scraped, see below
    CFB   ESPN FPI          probmakeplayoffs        = CFP odds, in season only

Sports with no source at all: college basketball (the race is bracketology),
college hockey, and every soccer competition (no playoffs to have odds about,
except MLS, which nobody publishes odds for).

On the Hockey-Reference scrape: MoneyPuck, the obvious NHL source, explicitly
asks not to be scraped, so it stays out. Hockey-Reference's robots.txt was
checked on 2026-08-25 -- it disallows /hockey/, /play-index/*cgi, */gamelog/
and friends, but NOT /friv/playoff_prob.cgi -- and asks for Crawl-delay: 3.
One request a day, cached for half a day, is well inside that. If this ever
feels wrong it can be dropped: the NHL simply loses its odds column, which is
where it was before. (The .cgi address now 301s to the .fcgi one below.)

Hockey-Reference only starts a new season's table once every team has played
about ten games. Until then the page keeps serving LAST season's final table
-- every team's points_remain 0, the playoff teams at 100% -- under the same
address, and nothing on it says so. That leftover was recorded as the
2026-27 race from 2026-10-15 until 2026-10-18. So the page's points must match
the NHL standings we already fetched, or the odds are thrown away.
"""

import re
import time

import fetch

HOCKEY_REF = "https://www.hockey-reference.com/friv/playoff_prob.fcgi"
CACHE_MINUTES = 60 * 12

_last_hockey_ref = [0.0]


def _espn(path, key, field="probmakeplayoffs"):
    out = {}
    for name, proj in fetch.power_index(path, key).items():
        value = proj.get(field)
        if isinstance(value, (int, float)):
            out[name.lower()] = float(value)
    return out


def _hockey_reference(rows=None):
    """{team name lower: percent} from the NHL playoff probabilities page, or
    {} when the page is still showing a finished season (see the top).

    `rows` are the NHL standings rows from ESPN. Without them the only test
    left is that some points remain to be played somewhere.
    """
    since = time.time() - _last_hockey_ref[0]
    if since < 3:                      # honour the published crawl delay
        time.sleep(3 - since)
    _last_hockey_ref[0] = time.time()
    html = fetch.get_text(HOCKEY_REF, key="odds-nhl-hr", max_age_min=CACHE_MINUTES)
    if not html:
        return {}
    out, points, remain = {}, {}, []
    # One <tr> per team; pull the name cell and the probability cell together
    # so a team with a missing value cannot shift the whole column.
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S):
        name = re.search(r'data-stat="team_name"[^>]*>(?:<a[^>]*>)?([^<]+)', row)
        if not name:
            continue
        label = name.group(1).strip().lower()
        cur = re.search(r'data-stat="points_current"[^>]*>(\d+)<', row)
        left = re.search(r'data-stat="points_remain"[^>]*>(\d+)<', row)
        if cur:
            points[label] = int(cur.group(1))
        if left:
            remain.append(int(left.group(1)))
        prob = re.search(r'data-stat="prob_playoffs"[^>]*>([^<]*)<', row)
        if not prob:
            continue
        value = prob.group(1).strip().rstrip("%")
        try:
            out[label] = float(value)
        except ValueError:
            continue                   # the header row, which repeats the label
    if not _current(points, remain, rows):
        print("  ! Hockey-Reference is still showing last season -- no NHL odds")
        return {}
    return out


def _current(points, remain, rows):
    """Is the Hockey-Reference table this season's?

    With ESPN's standings to hand, three quarters of the teams must sit within
    two points of their ESPN total. Not exact, because Hockey-Reference may
    not have caught up with last night's games by the morning build; last
    season's final table misses by fifty points or more. Without standings,
    fall back to points still being left to play.
    """
    if rows:
        checked = agree = 0
        for r in rows:
            espn = r["stats"].get("points")
            page = lookup(points, r["team"])
            try:
                espn = int(float(espn))
            except (TypeError, ValueError):
                continue
            if page is None:
                continue
            checked += 1
            agree += abs(page - espn) <= 2
        if checked:
            return agree * 4 >= checked * 3
    return any(remain)


def _flat(text):
    return "".join(c for c in (text or "").lower() if c.isalnum())


def lookup(table, team):
    """Match a source's label against a config team name.

    Deliberately loose in both directions: sources disagree about how much of
    a name to give, so "Tigers" has to match "Detroit Tigers" and vice versa.
    """
    if not table:
        return None
    target = _flat(team)
    for label, pct in table.items():
        flat = _flat(label)
        if flat and (flat in target or target in flat):
            return pct
    return None


def for_league(key, rows=None):
    """{team label lower: percent} for one league key, or {}.

    `rows`, the league's standings, let the NHL scrape check it is reading
    this season's table."""
    try:
        if key == "nfl":
            return _espn("football/nfl", "nfl")
        if key == "nba":
            return _espn("basketball/nba", "nba")
        if key == "cfb":
            return _espn("football/college-football", "cfb")
        if key == "nhl":
            return _hockey_reference(rows)
    except Exception as exc:
        # A third party changing shape must never break the build.
        print("  ! odds unavailable for %s (%s)" % (key, exc))
        fetch.FAILURES.append("%s odds" % key)
    return {}
