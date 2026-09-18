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
import re

import fetch

CORE = ("https://sports.core.api.espn.com/v2/sports/hockey/leagues/"
        "mens-college-hockey/seasons/%s/types/2/groups")
# Each team's own schedule, NOT the scoreboard. The scoreboard used to be read
# a month at a time with a date range; in September 2026 ESPN stopped accepting
# ranges at all (400 "Failed to get events endpoint"), and a whole season one
# day at a time would be ~200 calls. Team schedules are one call each.
SCHEDULE = ("https://site.api.espn.com/apis/site/v2/sports/hockey/"
            "mens-college-hockey/teams/%s/schedule")
MONTH_CACHE = 60 * 24 * 7      # a finished month never changes

# A conference TOURNAMENT game, told apart by its note. ESPN files these under
# the REGULAR SEASON -- seasontype 2 -- so the season type cannot exclude them:
# Cornell's 2025-26 schedule carries four "ECAC - Quarterfinal" and
# "ECAC - Semifinal" games at type 2, which turned a verified 14-6-2
# conference record into 16-8-2. Conference standings are the regular
# season's table; the tournament is played after it is settled.
# "round" covers every way ESPN numbers one -- "ECAC - 1st Round" slipped past a
# pattern that only knew "first round" and added a playoff game to half the
# ECAC's regular-season records.
TOURNAMENT = re.compile(r"quarterfinal|semifinal|final|championship|"
                        r"\bround\b|play-?in|tournament", re.I)

# KNOWN LIMIT, inherited rather than introduced: ESPN marks nothing that tells
# a NON-conference game between two conference members from a conference one
# -- no conferenceId on the scoreboard, no conferenceCompetition flag on the
# team schedule. So such a game is counted. In 2025-26 that left several ECAC
# teams one game over their 22 (Yale met Dartmouth three times, once before
# conference play began). Cornell played none, which is why its row verifies
# exactly; the Big Ten had none at all, and every team lands on 24.
LIVE_CACHE = 60 * 3


NPI = "https://ncaa-api.henrygd.me/rankings/icehockey-men/d1"

# The NCAA writes school names its own way ("Michigan St.", "Alas. Fairbanks").
# Expanding the common abbreviations gets 55 of 63 teams; the rest need saying
# out loud. Matching is EXACT after normalising -- a substring match would give
# Michigan State and Michigan Tech both Michigan's ranking.
_ABBR = {"st": "state", "mich": "michigan", "minn": "minnesota",
         "neb": "nebraska", "conn": "connecticut", "mass": "massachusetts",
         "colo": "colorado", "wis": "wisconsin", "ill": "illinois",
         "ind": "indiana", "fla": "florida", "ala": "alabama",
         "ariz": "arizona", "calif": "california", "penn": "pennsylvania",
         "n": "north", "s": "south", "w": "west", "e": "east"}

_ALIASES = {
    "army": "army west point",
    "augustana university": "augustana",
    "saint thomas minnesota": "saint thomas",
    "boston university": "boston u",
    "alaska anchorage": "alas anchorage",
    "alaska": "alas fairbanks",
    "long island university": "liu",
    "colorado college": "colorado col",
}


def _norm(text):
    """Fold a school name to a comparable form.

    "St." is Saint when it leads and State when it does not, which is why
    St. Lawrence and Minnesota St. cannot share one rule.
    """
    import re
    lowered = re.sub(r"\(.*?\)", " ", (text or "").lower())
    words, out = re.split(r"[\s.]+", lowered), []
    for i, word in enumerate(words):
        word = re.sub(r"[^a-z]", "", word)
        if not word:
            continue
        if word == "st":
            out.append("saint" if i == 0 else "state")
        else:
            out.append(_ABBR.get(word, word))
    key = " ".join(out)
    return _ALIASES.get(key, key)


def npi_ranks():
    """{normalised school: rank} from the NCAA's NPI, or {}.

    NPI is what actually decides at-large selection for the NCAA tournament,
    so it is the closest thing college hockey has to a playoff-odds number.
    Served by a community mirror of ncaa.com rather than a first-party feed --
    if it disappears the tables simply lose their rank column.
    """
    data = fetch.get(NPI, key="npi-icehockey", max_age_min=60 * 12)
    out = {}
    for row in (data or {}).get("data") or []:
        try:
            out[_norm(row.get("School"))] = int(row.get("Rank"))
        except (TypeError, ValueError):
            continue
    return out


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


def _score(side):
    """A competitor's score as an int, whichever shape ESPN sent it in.

    The scoreboard sends "3"; the team SCHEDULE sends {"value": 3.0,
    "displayValue": "3"}. int() on the dict raises TypeError, which the loop
    below catches and skips -- so without this every game of the season would
    be silently discarded and every record would read 0-0-0.
    """
    score = side.get("score")
    if isinstance(score, dict):
        score = score.get("value", score.get("displayValue"))
    return int(float(score))


def _season_events(year, team_ids, today=None):
    """Every game of the season involving any of these teams, each ONCE.

    A game between two tracked teams appears in both teams' schedules, so it is
    kept by event id -- counting it twice would give both sides a double result.

    The season YEAR is named here, unlike the K Money Teams tab where naming it
    was a trap. This module computes one specific season's table (the one
    season_year() picked, and the one conference_map() was built for), so the
    year is the question being asked, not a fallback.

    Regular season only: conference standings are a regular-season table, and
    the conference tournament is not part of it.
    """
    today = today or datetime.date.today()
    finished = today > datetime.date(year + 1, 4, 30)
    events = {}
    for tid in team_ids:
        data = fetch.get(SCHEDULE % tid, {"season": year + 1, "seasontype": 2},
                         key="chockey-sched-%s-%s" % (year, tid),
                         max_age_min=MONTH_CACHE if finished else LIVE_CACHE)
        for event in (data or {}).get("events") or []:
            if event.get("id"):
                events.setdefault(event["id"], event)
    return list(events.values())


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
    for event in _season_events(year, list(conf_of), today):
        comp = (event.get("competitions") or [{}])[0]
        sides = comp.get("competitors") or []
        if len(sides) != 2:
            continue
        if not (comp.get("status") or {}).get("type", {}).get("completed"):
            continue
        # Skipped entirely rather than just kept out of the conference column.
        # The only record either hockey table SHOWS is the conference one --
        # both groups set drop_overall in leagues.py -- so this keeps the
        # overall figure a regular-season number too rather than a mixture.
        if any(TOURNAMENT.search(note.get("headline") or "")
               for note in comp.get("notes") or []):
            continue
        ids = [str((s.get("team") or {}).get("id")) for s in sides]
        same = conf_of.get(ids[0]) and conf_of.get(ids[0]) == conf_of.get(ids[1])
        for side, other in ((sides[0], sides[1]), (sides[1], sides[0])):
            team = side.get("team") or {}
            tid = str(team.get("id"))
            meta.setdefault(tid, team)
            try:
                mine, theirs = _score(side), _score(other)
            except (TypeError, ValueError):
                continue
            slot = 0 if mine > theirs else 1 if mine < theirs else 2
            all_rec[tid][slot] += 1
            if same:
                conf_rec[tid][slot] += 1

    ranks = npi_ranks()
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
            "location": team.get("location") or "",
            "npi": ranks.get(_norm(team.get("location") or team.get("displayName"))),
            "stats": {
                "vs. Conf.": "%d-%d-%d" % tuple(c),
                "overall": "%d-%d-%d" % tuple(a),
                "wins": c[0], "losses": c[1], "ties": c[2],
                "derived": "1",
            },
        })
    return rows
