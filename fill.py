"""Fill finished seasons into the History rankings, from ESPN.

rankings/inputs/ is the sheet as imported and never changes (it is what the
proof runs against). Every season finished SINCE lands in an overlay,
rankings/seasons/<tab>.csv, three columns:

    season,name,value
    2026,Detroit,1              a team's value that season
    2026,Super Bowl,SEA         a footer row, found by its label
    2026,Super Bowl+1,NE        the unlabelled row beneath it
    2025,#row2,Gold             a row with no label, by its row number

rankings.Tab lays the overlay in front of the sheet's own seasons, newest
first, so the formulas cannot tell the two apart.

    python fill.py            fill every season that is finished and missing
    python fill.py --check    re-derive the sheet's LATEST season from ESPN and
                              diff it against what he typed -- the proof that
                              a filler reads ESPN the way he did

A season is only written once it is over: a filler that is asked about a
season still being played returns nothing. Each filler is checked against
the last season he typed before it is trusted with a new one.
"""

import csv
import datetime
import os
import re
import sys

import fetch
import rankings

OVERLAY = os.path.join(rankings.HERE, "rankings", "seasons")
SITE = "https://site.api.espn.com/apis/site/v2/sports/%s"


# ---- names --------------------------------------------------------------------

_SHORT = {"ny": "new york", "la": "los angeles"}
# Where his name is not the city ESPN uses now.
_ALIAS = {"oakland": "athletics", "southern california": "usc",
          "louisiana state": "lsu", "central florida": "ucf",
          "brigham young": "byu", "texas christian": "tcu"}


def _flat(text):
    return re.sub(r"[^a-z0-9 ]", "", str(text or "").lower()).strip()


def matcher(his_names, espn_teams):
    """{espn team id: his name}. His sheet writes a club by city ("Dallas"),
    by city and a nickname fragment where a city has two ("NY Giants",
    "Chicago Sox", "LA Dodgers"), and his own teams in capitals. Match on
    the city first, then the nickname to break a tie."""
    out = {}
    for his in his_names:
        words = _flat(his).split()
        city = _ALIAS.get(_flat(his), " ".join(_SHORT.get(w, w) for w in words))

        def loc(t):
            # ESPN itself now writes "LA Clippers": expand it the same way.
            return " ".join(_SHORT.get(w, w) for w in _flat(t["location"]).split())

        cands = [t for t in espn_teams
                 if loc(t) == city or _flat(t["displayName"]) == city
                 or _flat(t["displayName"]) == _flat(his)]
        if not cands and len(words) > 1:
            first = _SHORT.get(words[0], words[0])
            cands = [t for t in espn_teams
                     if loc(t).startswith(first)
                     and words[-1] in _flat(t["displayName"])]
        if not cands:
            cands = [t for t in espn_teams if loc(t).startswith(city)]
        if len(cands) == 1:
            out[cands[0]["id"]] = his
    return out


# ---- the overlay ----------------------------------------------------------------

def overlay_path(tab):
    return os.path.join(OVERLAY, tab.replace("+", "plus") + ".csv")


def read_overlay(tab):
    path = overlay_path(tab)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [(r["season"], r["name"], r["value"]) for r in csv.DictReader(f)]


def write_season(tab, season, values):
    """Replace one season of one tab's overlay. values = {name: value}."""
    rows = [r for r in read_overlay(tab) if r[0] != season]
    rows += [(season, name, value) for name, value in values.items()
             if value not in (None, "")]
    os.makedirs(OVERLAY, exist_ok=True)
    with open(overlay_path(tab), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["season", "name", "value"])
        for r in sorted(rows, key=lambda r: (r[0], r[1]), reverse=True):
            w.writerow(r)


def has_season(tab, season):
    old = rankings.SHEET_COMPAT
    rankings.SHEET_COMPAT = False
    try:
        return season in rankings.Tab(tab).seasons()
    finally:
        rankings.SHEET_COMPAT = old


# ---- ESPN ---------------------------------------------------------------------

def standings(path, season, level=3):
    """[(division, [team dicts in finishing order])] for a finished season."""
    data = fetch.get("https://site.api.espn.com/apis/v2/sports/%s/standings" % path,
                     {"level": level, "season": season},
                     key="hist-standings-%s-%s-l%s" % (path.replace("/", "-"), season, level),
                     max_age_min=60 * 24 * 7)
    out = []

    def walk(node):
        entries = (node.get("standings") or {}).get("entries") or []
        if entries:
            out.append((node.get("name"), [dict(e["team"], stats={
                s["name"]: s.get("value") for s in e.get("stats") or []})
                for e in entries]))
        for child in node.get("children") or []:
            walk(child)

    walk(data or {})
    return out


ROUNDS = ["PLAYIN", "RD16", "QTR", "SEMI", "FINAL"]


def round_of(comp):
    """A postseason game's round, from ESPN's type code where it has one and
    from the note where it does not (the NFL's codes are all "STD")."""
    code = (comp.get("type") or {}).get("abbreviation") or ""
    note = " ".join(n.get("headline") or "" for n in comp.get("notes") or []).lower()
    if "play-in" in note or "play in" in note:
        return "PLAYIN"
    if code in ROUNDS:
        return code
    if "super bowl" in note or "world series" in note or "stanley cup final" in note \
            or "nba finals" in note:
        return "FINAL"
    if "championship" in note or "lcs" in note or "conference finals" in note:
        return "SEMI"
    if "divisional" in note or "lds" in note or "semifinal" in note:
        return "QTR"
    if "wild card" in note or "1st round" in note or "first round" in note:
        return "RD16"
    return None


PLAYOFF_POINTS = {"PLAYIN": 0.5, "RD16": 1, "QTR": 3, "SEMI": 5}


def playoff_run(path, team_id, season):
    """(points, won_title) from a team's own postseason schedule. The deepest
    round reached decides: 30 for the title, 15 for losing the final, 5, 3,
    1 for the rounds before, 0.5 for a play-in."""
    events = []
    # The NBA files its play-in as a season type of its own (5).
    for kind in ((3, 5) if path.endswith("/nba") else (3,)):
        data = fetch.get(SITE % path + "/teams/%s/schedule" % team_id,
                         {"season": season, "seasontype": kind},
                         key="hist-post-%s-%s-%s-t%s" % (path.replace("/", "-"),
                                                         season, team_id, kind),
                         max_age_min=60 * 24 * 7)
        events += (data or {}).get("events") or []
    deepest, final_games = None, []
    for event in events:
        comp = (event.get("competitions") or [{}])[0]
        if not ((comp.get("status") or {}).get("type") or {}).get("completed"):
            continue
        rnd = round_of(comp)
        if rnd is None:
            continue
        if deepest is None or ROUNDS.index(rnd) > ROUNDS.index(deepest):
            deepest = rnd
        if rnd == "FINAL":
            me = next((c for c in comp.get("competitors") or []
                       if str((c.get("team") or {}).get("id")) == str(team_id)), {})
            final_games.append((event.get("date") or "", bool(me.get("winner"))))
    if deepest is None:
        return None, False
    if deepest == "FINAL":
        won = sorted(final_games)[-1][1]
        return (30 if won else 15), won
    return PLAYOFF_POINTS[deepest], False


# ---- the Big 4 ------------------------------------------------------------------

PRO = {
    "NFL": {"path": "football/nfl", "label": lambda y: "%d-%s" % (y, str(y + 1)[2:]),
            "espn_season": lambda y: y, "final": "Super Bowl",
            "over": lambda y: datetime.date(y + 1, 2, 20)},
    "MLB": {"path": "baseball/mlb", "label": str, "espn_season": lambda y: y,
            "final": "World Series", "over": lambda y: datetime.date(y, 11, 10)},
    "NBA": {"path": "basketball/nba", "label": lambda y: "%d-%s" % (y, str(y + 1)[2:]),
            "espn_season": lambda y: y + 1, "final": "Finals",
            "over": lambda y: datetime.date(y + 1, 6, 30)},
    "NHL": {"path": "hockey/nhl", "label": lambda y: "%d-%s" % (y, str(y + 1)[2:]),
            "espn_season": lambda y: y + 1, "final": "Stanley Cup",
            "over": lambda y: datetime.date(y + 1, 6, 30)},
}


def pro_season(sport, year):
    """{"div": {his name: place}, "playoffs": {his name: points},
    "footer": (champion abbr, runner-up abbr)} for the season STARTING in
    `year`, or None if it is not over."""
    cfg = PRO[sport]
    if datetime.date.today() < cfg["over"](year):
        return None
    season = cfg["espn_season"](year)
    divisions = standings(cfg["path"], season)
    if not divisions:
        return None
    teams = [t for _d, ts in divisions for t in ts]
    div_tab, po_tab = rankings.Tab(sport + "_div"), rankings.Tab(sport + "_playoffs")
    names = matcher([n for _r, n in div_tab.teams()], teams)
    po_names = matcher([n for _r, n in po_tab.teams()], teams)
    div, po, champ, runner = {}, {}, None, None
    for _name, ts in divisions:
        # ESPN lists a division in its own order, not the finishing order --
        # the 2025 AL East came back Yankees first, Blue Jays last. The
        # conference seed carries every tiebreaker, and within one division
        # it ranks the teams exactly as they finished.
        ts = sorted(ts, key=lambda t: (t["stats"].get("playoffSeed") or 99,
                                       -(t["stats"].get("winPercent") or 0)))
        # But a TIE shares the place, as he types it: two 9-8 teams are both
        # third, and the next is fifth. Tied means the same record (the same
        # points in the NHL), whatever the tiebreaker then decided -- EXCEPT
        # for first: the division title is won outright, so the champion is
        # 1 and a team level with it is 2 (2025: Toronto 1, Yankees 2).
        key = "points" if sport == "NHL" else "winPercent"
        for i, t in enumerate(ts):
            if t["id"] in names:
                mine = t["stats"].get(key) or 0
                better = sum(1 for u in ts if (u["stats"].get(key) or 0) > mine + 1e-9)
                div[names[t["id"]]] = 1 if i == 0 else max(2, 1 + better)
    for t in teams:
        pts, won = playoff_run(cfg["path"], t["id"], season)
        if pts and t["id"] in po_names:
            po[po_names[t["id"]]] = pts
        if pts == 30:
            champ = t.get("abbreviation")
        elif pts == 15:
            runner = t.get("abbreviation")
    return {"div": div, "playoffs": po, "footer": (champ, runner),
            "unmatched": [t["displayName"] for t in teams
                          if t["id"] not in names or t["id"] not in po_names]}


def fill_pro(sport, year):
    cfg = PRO[sport]
    label = cfg["label"](year)
    if has_season(sport + "_div", label):
        return "%s %s: already there" % (sport, label)
    got = pro_season(sport, year)
    if not got:
        return "%s %s: not finished" % (sport, label)
    footer_label = _footer_label(rankings.Tab(sport + "_playoffs"))
    write_season(sport + "_div", label, got["div"])
    po = dict(got["playoffs"])
    if footer_label:
        po[footer_label], po[footer_label + "+1"] = got["footer"]
    write_season(sport + "_playoffs", label, po)
    return "%s %s: filled (%d places, %d playoff teams)%s" % (
        sport, label, len(got["div"]), len(got["playoffs"]),
        "; UNMATCHED %s" % got["unmatched"] if got["unmatched"] else "")


def _footer_label(tab):
    last = tab.teams()[-1][0]
    for r in range(last + 1, len(tab.grid) + 1):
        if tab.cell(r, 1):
            return tab.cell(r, 1)
    return None


def check_pro(sport):
    """Re-derive the latest season he typed and list every difference."""
    div_tab, po_tab = rankings.Tab(sport + "_div"), rankings.Tab(sport + "_playoffs")
    label = div_tab.seasons()[0]
    year = int(label[:4])
    got = pro_season(sport, year)
    diffs = []
    for name, place in got["div"].items():
        typed = rankings._cell_by(div_tab, name, label)
        if typed != place:
            diffs.append("%s place: typed %s, ESPN %s" % (name, typed, place))
    for _r, name in po_tab.teams():
        typed = rankings._cell_by(po_tab, name, label)
        mine = got["playoffs"].get(name)
        if (typed or None) != (mine or None):
            diffs.append("%s playoffs: typed %s, ESPN %s" % (name, typed, mine))
    return label, diffs, got["unmatched"], got["footer"]


def main():
    if "--check" in sys.argv:
        for sport in PRO:
            label, diffs, unmatched, footer = check_pro(sport)
            print("%s %s: %d differences, footer %s%s" % (
                sport, label, len(diffs), footer,
                "; UNMATCHED %s" % unmatched if unmatched else ""))
            for d in diffs:
                print("    " + d)
        return
    today = datetime.date.today()
    for sport in PRO:
        for year in (today.year - 2, today.year - 1, today.year):
            print(fill_pro(sport, year))
    for year in (today.year - 1, today.year):
        print(fill_b1g_baseball(year))
    import fill_tournaments                 # it imports this module
    fill_tournaments.main()



# ---- Big Ten baseball (the NCAA tab's CWS column) -------------------------------

B1G_BASEBALL = 48       # ESPN's group id for the Big Ten in college baseball


def b1g_baseball(year):
    """{his name: conference place, "Outright Champion": ..., "B1G Tournament":
    ...} for a finished spring, or None. Places are by conference win
    percentage and a tie SHARES the place -- first included, so in 2025 UCLA
    and Oregon were both 1 and nobody was outright champion."""
    if datetime.date.today() < datetime.date(year, 6, 1):
        return None
    tab = rankings.Tab("NCAAB_B1G")
    conf = next((ts for name, ts in standings("baseball/college-baseball", year)
                 if "big 10" in (name or "").lower()), None)
    if not conf:
        return None
    names = matcher([n for _r, n in tab.teams()], conf)
    pct = {t["id"]: t["stats"].get("leagueWinPercent") or 0 for t in conf}
    out = {}
    for t in conf:
        place = 1 + sum(1 for u in conf if pct[u["id"]] > pct[t["id"]] + 1e-9)
        out[names.get(t["id"], t["location"])] = place
    firsts = [n for n, p in out.items() if p == 1]
    if len(firsts) == 1:
        out["Outright Champion"] = firsts[0]
    # The conference tournament's final, found on the days around it.
    for day in range(18, 32):
        data = fetch.get(SITE % "baseball/college-baseball" + "/scoreboard",
                         {"dates": "%d05%02d" % (year, day), "groups": B1G_BASEBALL,
                          "limit": 300},
                         key="b1g-bb-%d05%02d" % (year, day), max_age_min=60 * 24 * 30)
        for event in (data or {}).get("events") or []:
            comp = (event.get("competitions") or [{}])[0]
            note = " ".join(n.get("headline") or "" for n in comp.get("notes") or [])
            if "Big Ten Tournament - Championship" in note:
                for side in comp.get("competitors") or []:
                    if side.get("winner"):
                        team = side.get("team") or {}
                        byid = {t["id"]: out and names.get(t["id"], t["location"])
                                for t in conf}
                        out["B1G Tournament"] = byid.get(team.get("id"),
                                                         team.get("location"))
    return out


def fill_b1g_baseball(year):
    label = str(year)
    if has_season("NCAAB_B1G", label):
        return "NCAAB_B1G %s: already there" % label
    got = b1g_baseball(year)
    if not got:
        return "NCAAB_B1G %s: not finished" % label
    write_season("NCAAB_B1G", label, got)
    return "NCAAB_B1G %s: filled %d" % (label, len(got))


def check_b1g_baseball():
    tab = rankings.Tab("NCAAB_B1G")
    label = tab.seasons()[0]
    got = b1g_baseball(int(label))
    diffs = []
    for _r, name in tab.teams():
        typed = rankings._cell_by(tab, name, label)
        if typed != got.get(name):
            diffs.append("%s: typed %s, ESPN %s" % (name, typed, got.get(name)))
    for label_ in ("Outright Champion", "B1G Tournament"):
        typed = tab.footer(label_).get(label)
        if (typed or None) != (got.get(label_) or None):
            diffs.append("%s: typed %s, ESPN %s" % (label_, typed, got.get(label_)))
    return label, diffs


if __name__ == "__main__":
    main()
