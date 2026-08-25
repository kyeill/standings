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
where it was before.
"""

import re
import time

import fetch

HOCKEY_REF = "https://www.hockey-reference.com/friv/playoff_prob.cgi"
CACHE_MINUTES = 60 * 12

_last_hockey_ref = [0.0]


def _espn(path, key, field="probmakeplayoffs"):
    out = {}
    for name, proj in fetch.power_index(path, key).items():
        value = proj.get(field)
        if isinstance(value, (int, float)):
            out[name.lower()] = float(value)
    return out


def _hockey_reference():
    """{team name lower: percent} from the NHL playoff probabilities page."""
    since = time.time() - _last_hockey_ref[0]
    if since < 3:                      # honour the published crawl delay
        time.sleep(3 - since)
    _last_hockey_ref[0] = time.time()
    html = fetch.get_text(HOCKEY_REF, key="odds-nhl-hr", max_age_min=CACHE_MINUTES)
    if not html:
        return {}
    out = {}
    # One <tr> per team; pull the name cell and the probability cell together
    # so a team with a missing value cannot shift the whole column.
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S):
        name = re.search(r'data-stat="team_name"[^>]*>(?:<a[^>]*>)?([^<]+)', row)
        prob = re.search(r'data-stat="prob_playoffs"[^>]*>([^<]*)<', row)
        if not name or not prob:
            continue
        value = prob.group(1).strip().rstrip("%")
        try:
            out[name.group(1).strip().lower()] = float(value)
        except ValueError:
            continue                   # the header row, which repeats the label
    return out


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


def for_league(key):
    """{team label lower: percent} for one league key, or {}."""
    try:
        if key == "nfl":
            return _espn("football/nfl", "nfl")
        if key == "nba":
            return _espn("basketball/nba", "nba")
        if key == "cfb":
            return _espn("football/college-football", "cfb")
        if key == "nhl":
            return _hockey_reference()
    except Exception as exc:
        # A third party changing shape must never break the build.
        print("  ! odds unavailable for %s (%s)" % (key, exc))
        fetch.FAILURES.append("%s odds" % key)
    return {}
