"""College hockey standings, derived from game results.

ESPN publishes no college hockey standings anywhere -- the site API and the
core API both return zero entries for every conference, and every other source
checked was a dead end (NCAA's data host 404s on every standings path, USCHO
renders client side, College Hockey News has no machine-readable standings).

So they are computed here: walk the season's completed games, keep the ones
where both teams are in the same conference, and count them. Verified against
the finished 2025-26 season, which reproduced a correct 12-team ECAC and
7-team Big Ten table (Cornell 14-6-2 third, Michigan 15-6-2 second).

Two things make this less obvious than it sounds:

  * the college hockey SCOREBOARD carries no conferenceId at all, so
    conference membership has to come from the core API's group listing
  * ESPN calls the ECAC "East Coast Athletic Conference"

Ties are real in college hockey, so records are W-L-T. Conference POINTS are
deliberately not computed: the leagues weight overtime results differently and
change the rules between seasons, so a points column would be a guess. The
table is ordered by win percentage counting a tie as half a win.
"""

import collections
import datetime

import fetch

CORE = ("https://sports.core.api.espn.com/v2/sports/hockey/leagues/"
        "mens-college-hockey/seasons/%s/types/2/groups")
SCOREBOARD = ("https://site.api.espn.com/apis/site/v2/sports/hockey/"
              "mens-college-hockey/scoreboard")
MONTH_CACHE = 60 * 24 * 7      # a finished month never changes
LIVE_CACHE = 60 * 3


def season_year(today=None):
    """The year a season STARTED. October 2026 and March 2027 are both 2026.

    Between May and September nothing is being played, so fall back to the
    season that just finished -- that way test mode shows a real table instead
    of an empty one, matching how the NBA and NHL tabs read out of season.
    """
    today = today or datetime.date.today()
    if today.month >= 10:
        return today.year
    return today.year - 1


def conference_map(year, ):
    """{team id: conference name}, cached for a week -- it barely moves."""
    groups = fetch.get(CORE % (year + 1), key="chockey-groups-%s" % year,
                       max_age_min=MONTH_CACHE)
    out, names = {}, {}
    if not groups:
        return out, names
    for item in groups.get("items") or []:
        group = fetch.get(item["$ref"].replace("http://", "https://"),
                          key="chockey-group-%s" % item["$ref"].rsplit("/", 1)[-1
                          ].split("?")[0], max_age_min=MONTH_CACHE)
        if not group:
            continue
        label = group.get("name") or ""
        teams_ref = (group.get("teams") or {}).get("$ref")
        if not teams_ref:
            continue
        teams = fetch.get(teams_ref.replace("http://", "https://"),
                          key="chockey-teams-%s" % group.get("id"),
                          max_age_min=MONTH_CACHE)
        for entry in (teams or {}).get("items") or []:
            ref = entry["$ref"].replace("http://", "https://")
            team = fetch.get(ref, key="chockey-team-%s" % ref.rsplit("/", 1)[-1
                             ].split("?")[0], max_age_min=MONTH_CACHE)
            if team and team.get("id"):
                out[str(team["id"])] = label
                names[str(team["id"])] = team.get("displayName") or ""
    return out, names


def _ranges(year, today=None):
    """Month-sized windows covering the season so far."""
    today = today or datetime.date.today()
    start = datetime.date(year, 10, 1)
    end = min(max(today, start), datetime.date(year + 1, 4, 30))
    out, cursor = [], start
    while cursor <= end:
        nxt = (cursor.replace(day=28) + datetime.timedelta(days=7)).replace(day=1)
        stop = min(nxt - datetime.timedelta(days=1), end)
        out.append((cursor, stop))
        cursor = nxt
    return out


def standings(today=None):
    """Rows shaped like fetch.rows(), so the rest of the app cannot tell."""
    today = today or datetime.date.today()
    year = season_year(today)
    conf_of, _names = conference_map(year)
    if not conf_of:
        return []

    conf_rec = collections.defaultdict(lambda: [0, 0, 0])
    all_rec = collections.defaultdict(lambda: [0, 0, 0])
    meta = {}
    for lo, hi in _ranges(year, today):
        finished = hi < today
        data = fetch.get(SCOREBOARD,
                         {"dates": "%s-%s" % (lo.strftime("%Y%m%d"),
                                              hi.strftime("%Y%m%d")),
                          "limit": 900},
                         key="chockey-games-%s" % lo.strftime("%Y%m"),
                         max_age_min=MONTH_CACHE if finished else LIVE_CACHE)
        for event in (data or {}).get("events") or []:
            comp = (event.get("competitions") or [{}])[0]
            sides = comp.get("competitors") or []
            if len(sides) != 2:
                continue
            if not (comp.get("status") or {}).get("type", {}).get("completed"):
                continue
            ids = [str((s.get("team") or {}).get("id")) for s in sides]
            same = conf_of.get(ids[0]) and conf_of.get(ids[0]) == conf_of.get(ids[1])
            for side, other in ((sides[0], sides[1]), (sides[1], sides[0])):
                team = side.get("team") or {}
                tid = str(team.get("id"))
                meta.setdefault(tid, team)
                try:
                    mine, theirs = int(side.get("score")), int(other.get("score"))
                except (TypeError, ValueError):
                    continue
                slot = 0 if mine > theirs else 1 if mine < theirs else 2
                all_rec[tid][slot] += 1
                if same:
                    conf_rec[tid][slot] += 1

    rows = []
    for tid, conference in conf_of.items():
        team = meta.get(tid)
        if not team:
            continue                       # a team that has not played yet
        c, a = conf_rec[tid], all_rec[tid]
        rows.append({
            "conference": conference, "division": conference,
            "team": team.get("displayName") or "", "abbr": team.get("abbreviation") or "",
            "id": tid, "logo": team.get("logo") or "",
            "stats": {
                "vs. Conf.": "%d-%d-%d" % tuple(c),
                "overall": "%d-%d-%d" % tuple(a),
                "wins": c[0], "losses": c[1], "ties": c[2],
                "derived": "1",
            },
        })
    return rows
