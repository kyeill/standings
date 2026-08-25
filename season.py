"""Is a competition actively going on right now?

Kyle's rule: exclude anything not actively ongoing. That cannot be answered
from the standings payload, because an out-of-season league does not come back
empty -- it comes back either as last season's FINAL table (NBA, NHL today,
complete with clinch flags) or as an all-zero table for a season that has not
started (college football today). The two failure modes look nothing alike, so
emptiness is not a usable test.

Asking the scoreboard whether games exist in a window around today is a direct
answer, and it also catches the case that made this necessary: the NFL is in
PRESEASON right now, so its standings show 1-1 and 2-0 records that mean
nothing. Preseason counts as not ongoing.
"""

import datetime

import fetch

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/%s/scoreboard"
WINDOW_DAYS = 10
CACHE_MINUTES = 60 * 6


def is_live(league_path, today=None, window=WINDOW_DAYS, params=None):
    """True when real (non-preseason) games fall within +/- window days."""
    today = today or datetime.date.today()
    lo = (today - datetime.timedelta(days=window)).strftime("%Y%m%d")
    hi = (today + datetime.timedelta(days=window)).strftime("%Y%m%d")
    query = {"dates": "%s-%s" % (lo, hi), "limit": 400}
    if params:
        query.update(params)
    data = fetch.get(SCOREBOARD % league_path, query,
                     key="season-%s-%s" % (league_path.replace("/", "-"), lo),
                     max_age_min=CACHE_MINUTES)
    if data is None:
        # College basketball 404s on a wide date range where every other
        # league accepts one. Fall back to sampling single days across the
        # same window rather than reading the error as "out of season".
        # The range attempt is expected to fail here, so it must not be
        # reported to the user as a data outage.
        key = "season-%s-%s" % (league_path.replace("/", "-"), lo)
        if key in fetch.FAILURES:
            fetch.FAILURES.remove(key)
        data = {"events": []}
        for offset in (0, -7, 7, -3, 3):
            day = (today + datetime.timedelta(days=offset)).strftime("%Y%m%d")
            single = fetch.get(SCOREBOARD % league_path,
                               dict(query, dates=day),
                               key="season1-%s-%s" % (
                                   league_path.replace("/", "-"), day),
                               max_age_min=CACHE_MINUTES)
            if single and (single.get("events") or []):
                data = single
                break
    for event in data.get("events") or []:
        season = event.get("season") or {}
        slug = (season.get("slug") or "").lower()
        if season.get("type") == 1 or "preseason" in slug:
            continue
        if "friendly" in slug or "all-star" in slug:
            continue
        return True
    return False


def describe(league_path, today=None):
    """(live, note) -- the note explains a no, for the page to show."""
    live = is_live(league_path, today)
    return live, "" if live else "no games within %d days" % WINDOW_DAYS


def current_phase(league_path, today=None, window=WINDOW_DAYS):
    """The set of season slugs with games around today.

    A European competition only HAS a table during its league phase; once the
    knockout rounds start there is nothing to stand in a table, so the tab has
    to drop it rather than keep showing a frozen final table.
    """
    today = today or datetime.date.today()
    lo = (today - datetime.timedelta(days=window)).strftime("%Y%m%d")
    hi = (today + datetime.timedelta(days=window)).strftime("%Y%m%d")
    data = fetch.get(SCOREBOARD % league_path,
                     {"dates": "%s-%s" % (lo, hi), "limit": 400},
                     key="season-%s-%s" % (league_path.replace("/", "-"), lo),
                     max_age_min=CACHE_MINUTES)
    slugs = set()
    for event in (data or {}).get("events") or []:
        slug = ((event.get("season") or {}).get("slug") or "").lower()
        if slug:
            slugs.add(slug)
    return slugs
