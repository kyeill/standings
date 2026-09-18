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


def _around(league_path, today, window, params=None):
    """Events from single days, walking OUTWARD from today: 0, -1, +1, -2, +2...

    This was one ranged call across the whole window. In September 2026 ESPN
    stopped accepting date RANGES on the scoreboard at all -- any league, any
    length, a single week included -- answering

        400 {"code":400,"message":"Failed to get events endpoint."}

    A single day still works. So each day is its own call, nearest first, and
    the caller stops the moment it has an answer: an in-season league usually
    settles on day 0 or 1. Each day is cached separately and is_live() and
    current_phase() share the cache, so asking both costs nothing extra.

    EVERY day, not a sample. The old fallback sampled today and +/-3 and +/-7,
    which misses any competition that plays one fixed weekday: from a Friday,
    the Europa League's Thursdays sit at -1 and +6, and neither was checked.
    """
    extra = "".join("-%s%s" % (k, v) for k, v in sorted((params or {}).items()))
    base = league_path.replace("/", "-")
    for dist in range(window + 1):
        for offset in ((0,) if dist == 0 else (-dist, dist)):
            day = (today + datetime.timedelta(days=offset)).strftime("%Y%m%d")
            query = {"dates": day, "limit": 400}
            query.update(params or {})
            data = fetch.get(SCOREBOARD % league_path, query,
                             key="day-%s-%s%s" % (base, day, extra),
                             max_age_min=CACHE_MINUTES)
            for event in (data or {}).get("events") or []:
                yield event


def _real(event):
    """A game that counts: not preseason, not a friendly, not an all-star."""
    season = event.get("season") or {}
    slug = (season.get("slug") or "").lower()
    if season.get("type") == 1 or "preseason" in slug:
        return False
    return not ("friendly" in slug or "all-star" in slug)


def is_live(league_path, today=None, window=WINDOW_DAYS, params=None):
    """True when real (non-preseason) games fall within +/- window days."""
    today = today or datetime.date.today()
    return any(_real(e) for e in _around(league_path, today, window, params))


def current_phase(league_path, today=None, window=WINDOW_DAYS):
    """The season slugs of the games NEAREST today.

    A European competition only HAS a table during its league phase; once the
    knockout rounds start there is nothing to stand in a table, so the tab has
    to drop it rather than keep showing a frozen final table.

    Nearest-first is the right reading of "current": at the turn from league
    phase to knockouts, the games closest to today are the phase that is
    actually under way. It also stops early, where a whole-window scan would
    cost twenty-one calls per competition.

    This had NO fallback when the ranged call began failing, so it returned an
    empty set -- and every European table was dropped as "not in its league
    phase" while the Champions League and Europa League were both mid-phase.
    """
    today = today or datetime.date.today()
    slugs, nearest = set(), None
    for dist in range(window + 1):
        for offset in ((0,) if dist == 0 else (-dist, dist)):
            day = today + datetime.timedelta(days=offset)
            for event in _around(league_path, day, 0):
                slug = ((event.get("season") or {}).get("slug") or "").lower()
                if slug:
                    slugs.add(slug)
                    nearest = dist
        if nearest is not None:
            return slugs
    return slugs
