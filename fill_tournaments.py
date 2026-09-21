"""Tournament seasons for the History rankings: cups, not leagues.

A tournament is read one day at a time -- ESPN stopped accepting date ranges
in September 2026 -- across the window it was played in, and each team is
credited with the DEEPEST stage it reached, named by ESPN's season slug
("group-stage", "round-of-16", "final"...). Each tab turns that stage into
its own points, the scale he used in the sheet.

    python fill_tournaments.py --check   the previous edition vs what he typed
    python fill_tournaments.py           write every finished edition missing

Every filler here was checked against his last typed edition first; the
results of that check are recorded in NOTES.md.
"""

import datetime
import re
import sys
import unicodedata

import fetch
import fill
import rankings

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/%s/scoreboard"


def days(start, end):
    d = start
    while d <= end:
        yield d
        d += datetime.timedelta(days=1)


def tournament(path, start, end):
    """{team id: {"name", "location", "stages": {slug: games}, "wins":
    {slug: wins}, "won_final": bool|None}} from every game in the window."""
    teams = {}
    for day in days(start, end):
        data = fetch.get(SCOREBOARD % path, {"dates": day.strftime("%Y%m%d"),
                                             "limit": 300},
                         key="tourn-%s-%s" % (path.replace("/", "-"),
                                              day.strftime("%Y%m%d")),
                         max_age_min=60 * 24 * 30)
        for event in (data or {}).get("events") or []:
            comp = (event.get("competitions") or [{}])[0]
            if not ((comp.get("status") or {}).get("type") or {}).get("completed"):
                continue
            slug = ((event.get("season") or {}).get("slug") or "").lower()
            for side in comp.get("competitors") or []:
                team = side.get("team") or {}
                tid = str(team.get("id"))
                t = teams.setdefault(tid, {
                    "name": team.get("displayName") or "",
                    "location": team.get("location") or team.get("displayName") or "",
                    "abbr": team.get("abbreviation") or "",
                    "stages": {}, "wins": {}, "won_final": None})
                t["stages"][slug] = t["stages"].get(slug, 0) + 1
                if side.get("winner"):
                    t["wins"][slug] = t["wins"].get(slug, 0) + 1
                if slug in FINALS:
                    t["won_final"] = bool(side.get("winner"))
    return teams


# The deciding game's slug in each competition. A best-of-three final (the
# College World Series) is decided by its last game, so later games overwrite.
FINALS = {"final", "championship-series"}


def deepest(t, order):
    best = None
    for slug in t["stages"]:
        if slug in order and (best is None or order.index(slug) > order.index(best)):
            best = slug
    return best


# ---- names ------------------------------------------------------------------------

def plain(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("-", " ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", text)).strip()


# ESPN's name (flattened) -> his, where no rule gets there.
ALIASES = {
    "america": "Club America", "club america": "Club America",
    "tigres uanl": "Tigres", "pumas unam": "Pumas", "fc juarez": "Juarez",
    "atletico de san luis": "San Luis", "lafc": "Los Angeles",
    "los angeles fc": "Los Angeles", "new york red bulls": "NY Red Bulls",
    "red bull new york": "NY Red Bulls", "la galaxy": "LA Galaxy",
    "atlanta united fc": "ATLANTA", "atlanta united": "ATLANTA",
    "dc united": "DC United", "d c united": "DC United",
    "cf montreal": "Montreal", "st louis city sc": "St. Louis",
    "mazatlan fc": "Mazatlan", "queretaro": "Queretaro",
    "united states": "UNITED STATES", "usa": "UNITED STATES",
    "st kitts and nevis": "Saint Kitts and Nevis",
    # His spellings, kept: "Ciabo", "Hamilton" for Forge, "Antigua".
    "forge fc": "Hamilton", "cibao fc": "Ciabo", "antigua gfc": "Antigua",
    "sporting kansas city": "Sporting KC", "uic": "Illinois Chicago",
    "club deportivo olimpia": "Olimpia",
    "tcu": "Texas Christian", "south carolina upstate": "USC Upstate",
    "lsu": "Louisiana State", "ole miss": "Ole Miss", "uconn": "Connecticut",
    "ucf": "Central Florida", "usc": "Southern California",
    "nc state": "North Carolina State", "miami": "Miami",
    "miami fl": "Miami", "miami oh": "Miami OH", "byu": "Brigham Young",
    "smu": "SMU", "unlv": "UNLV", "utsa": "UTSA",
}


def name_for(t, his_names):
    """His name for an ESPN team, or None. Tries the alias list, then the
    full name, then the place name, then the place name without a trailing
    'FC'/'SC'."""
    his = {plain(n): n for n in his_names}
    for candidate in (t["name"], t["location"]):
        key = plain(candidate)
        if key in ALIASES and plain(ALIASES[key]) in his:
            return his[plain(ALIASES[key])]
        if key in his:
            return his[key]
        stripped = re.sub(r"\b(fc|sc|cf)\b", "", key).strip()
        if stripped in his:
            return his[stripped]
    # A club he names by its city alone: "Seattle" for Seattle Sounders FC,
    # "Santos Laguna" for ESPN's "Santos". A prefix either way, if unique.
    key = plain(t["name"])
    hits = [n for k, n in his.items()
            if len(k) > 3 and (key.startswith(k + " ") or k.startswith(key + " "))]
    return hits[0] if len(hits) == 1 else None


# ---- the competitions ---------------------------------------------------------------

def _run(slug_points):
    """points(team) for a stage -> points map, with the final split 30/15."""
    def points(t, order):
        stage = deepest(t, order)
        if stage is None:
            return None
        if stage in FINALS:
            return 30 if t["won_final"] else 15
        return slug_points.get(stage)
    return points


COMPETITIONS = {
    # Gold Cup: groups 1, quarters 3, semis 5, final 15/30. The sheet also
    # carries Copa America years; row 2 of the tab names the event.
    "Concacaf_GC": {
        "path": "soccer/concacaf.gold", "label": str,
        "window": lambda y: (datetime.date(y, 6, 1), datetime.date(y, 7, 20)),
        "years": lambda y: y % 2 == 1, "event": "Gold", "guests": False,
        "order": ["group-stage", "quarterfinals", "semifinals", "final"],
        "points": {"group-stage": 1, "quarterfinals": 3, "semifinals": 5},
        "footer": "Gold Cup"},
    # World Cup: groups 2, round of 16 5, quarters 8, semis (and the third-
    # place match) 10, final 15/30. 2026 added a round of 32, which the
    # sheet has no number for: 3, between the group and the round of 16.
    "Concacaf_WC": {
        "path": "soccer/fifa.world", "label": str,
        # Qatar 2022 was played in November and December.
        "window": lambda y: ((datetime.date(y, 11, 18), datetime.date(y, 12, 20))
                             if y == 2022 else
                             (datetime.date(y, 6, 8), datetime.date(y, 7, 22))),
        "years": lambda y: y % 4 == 2, "guests": False,
        "order": ["group-stage", "round-of-32", "round-of-16", "quarterfinals",
                  "semifinals", "3rd-place-match", "final"],
        "points": {"group-stage": 2, "round-of-32": 3, "round-of-16": 5,
                   "quarterfinals": 8, "semifinals": 10, "3rd-place-match": 10},
        "footer": "World Cup", "footer_names": "abbr",
        # Reaching the final qualifying round -- the Octagonal in 2022, the
        # third round for 2026 -- is worth 0.5 ("wcq" on the page).
        "qualifying": {"path": "soccer/fifa.worldq.concacaf",
                       "slug": "third-round", "points": 0.5,
                       "window": lambda y: (datetime.date(y - 1, 9, 1),
                                            datetime.date(y, 3, 31))}},
    "MLS_CCC": {
        "path": "soccer/concacaf.champions", "label": str,
        "window": lambda y: (datetime.date(y, 2, 1), datetime.date(y, 6, 10)),
        "years": lambda y: True,
        "order": ["round-one", "round-of-16", "quarterfinals", "semifinals", "final"],
        "points": {"round-one": 0.5, "round-of-16": 1, "quarterfinals": 3,
                   "semifinals": 5}},
    "MLS_LC": {
        "path": "soccer/concacaf.leagues.cup", "label": str,
        "window": lambda y: (datetime.date(y, 7, 20), datetime.date(y, 9, 12)),
        "years": lambda y: y >= 2019,
        "order": ["league-phase", "group-stage", "round-of-32", "round-of-16",
                  "quarterfinals", "semifinals", "3rd-place-match", "final"],
        # 2025's league phase earned nothing in his sheet; the old group
        # stage and round of 32 earned 0.5.
        "points": {"league-phase": None, "group-stage": 0.5, "round-of-32": 0.5,
                   "round-of-16": 1, "quarterfinals": 3, "semifinals": 5,
                   "3rd-place-match": 5}},
    # College World Series. Regional 0.5, super regional 1; in Omaha, 0-2 is
    # 3, one win 5, a bracket final lost 10; the finals 15/30.
    "NCAAB_CWS": {
        "path": "baseball/college-baseball", "label": str,
        "window": lambda y: (datetime.date(y, 5, 28), datetime.date(y, 6, 25)),
        "years": lambda y: True,
        "order": ["regionals", "super-regionals", "world-series",
                  "championship-series"],
        "points": {"regionals": 0.5, "super-regionals": 1},
        "omaha": True},
}


def edition(tab, year):
    """({his name: points}, [ESPN names he has no row for], teams) or None."""
    cfg = COMPETITIONS[tab]
    start, end = cfg["window"](year)
    if datetime.date.today() <= end + datetime.timedelta(days=2):
        return None
    teams = tournament(cfg["path"], start, end)
    if not teams:
        return None
    his_names = [n for _r, n in rankings.Tab(tab).teams()]
    points = _run(cfg["points"])
    out, unknown = {}, []
    for t in teams.values():
        pts = points(t, cfg["order"])
        if cfg.get("omaha") and deepest(t, cfg["order"]) == "world-series":
            wins = t["wins"].get("world-series", 0)
            pts = 3 if wins == 0 else 5 if wins == 1 else 10
        if pts is None:
            continue
        name = name_for(t, his_names)
        if name is None:
            unknown.append(t["name"])
            if cfg.get("guests") is False:
                continue        # an invited team from outside Concacaf, or a
                                # World Cup team from elsewhere: not his list
            name = t["location"]            # a new row, under ESPN's name
        out[name] = max(pts, out.get(name) or 0)
    q = cfg.get("qualifying")
    if q:
        qs, qe = q["window"](year)
        for t in tournament(q["path"], qs, qe).values():
            name = name_for(t, his_names)
            if name and q["slug"] in t["stages"]:
                out[name] = max(q["points"], out.get(name) or 0)
    return out, unknown, teams


def check(tab):
    """The latest edition he typed, re-derived: every difference."""
    old = rankings.SHEET_COMPAT
    rankings.SHEET_COMPAT = True
    try:
        t = rankings.Tab(tab)
        label = next(s for s in t.seasons()
                     if COMPETITIONS[tab]["years"](int(s[:4]))
                     and (not COMPETITIONS[tab].get("event")
                          or _event_of(t, s) == COMPETITIONS[tab]["event"]))
        typed = {n: rankings._coerce(rankings._cell_by(t, n, label))
                 for _r, n in t.teams()}
    finally:
        rankings.SHEET_COMPAT = old
    got, unknown, teams = edition(tab, int(label[:4]))
    diffs = []
    for name in sorted(set(typed) | set(got), key=str):
        a = typed.get(name) if rankings.is_num(typed.get(name)) else None
        b = got.get(name)
        if (a or None) != (b or None):
            diffs.append("%s: typed %s, ESPN %s" % (name, a, b))
    slugs = sorted({s for t in teams.values() for s in t["stages"]})
    return label, diffs, unknown, slugs


def _event_of(tab, season):
    """Concacaf_GC's row 2 names the event each season -- Gold or Copa."""
    try:
        return tab.cell(2, tab.col_of(season))
    except KeyError:
        return None


def fill_edition(tab, year):
    cfg = COMPETITIONS[tab]
    label = cfg["label"](year)
    if not cfg["years"](year):
        return None
    if fill.has_season(tab, label):
        return "%s %s: already there" % (tab, label)
    got = edition(tab, year)
    if not got:
        return "%s %s: not finished" % (tab, label)
    values, unknown, teams = got
    if cfg.get("event"):
        values["#row2"] = cfg["event"]      # the tab's row naming each event
    if cfg.get("footer"):
        final = [t for t in teams.values() if deepest(t, cfg["order"]) in FINALS]
        final.sort(key=lambda t: not t["won_final"])
        attr = "abbr" if cfg.get("footer_names") == "abbr" else "abbr"
        if len(final) == 2:
            values[cfg["footer"]] = final[0][attr]
            values["Runner-Up"] = final[1][attr]
    fill.write_season(tab, label, values)
    return "%s %s: filled %d teams%s" % (
        tab, label, len(values), "; NEW ROWS %s" % unknown if unknown else "")


def main():
    if "--check" in sys.argv:
        for tab in COMPETITIONS:
            label, diffs, unknown, slugs = check(tab)
            print("%s %s: %d differences; stages %s%s" % (
                tab, label, len(diffs), slugs,
                "; not in his tab: %s" % unknown if unknown else ""))
            for d in diffs:
                print("    " + d)
        return
    today = datetime.date.today()
    for tab in COMPETITIONS:
        for year in range(today.year - 2, today.year + 1):
            msg = fill_edition(tab, year)
            if msg:
                print(msg)


if __name__ == "__main__":
    main()
