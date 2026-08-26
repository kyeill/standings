"""Check the back end actually does what it claims.

Most of this cannot be seen by looking at the page: the trend needs a week of
history to exist, the season test needs a preseason league to reject, and the
games-behind maths is only obviously right if you check it against ESPN's own
published column. So check it here.

    python selftest.py

Anything that needs the network is marked LIVE and will fail if ESPN is down;
everything else is arithmetic and runs offline.
"""

import datetime
import os
import shutil
import sys
import tempfile

import build
import chockey
import fetch
import history
import model
import odds
import season

PASS, FAIL = [], []


def check(name, got, want, note=""):
    ok = got == want
    (PASS if ok else FAIL).append(name)
    print("  %-4s %-52s %s" % ("ok" if ok else "FAIL", name,
                               "" if ok else "got %r, want %r %s" % (got, want, note)))


def near(name, got, want, tol=0.01):
    ok = got is not None and abs(got - want) <= tol
    (PASS if ok else FAIL).append(name)
    print("  %-4s %-52s %s" % ("ok" if ok else "FAIL", name,
                               "" if ok else "got %r, want %r" % (got, want)))


print("record parsing")
# College football publishes wins but NO losses -- the bug that silently
# collapsed every games-behind number until it was found.
check("cfb: losses come from the overall string",
      model.win_loss({"wins": "8", "overall": "8-3"}), (8.0, 3.0))
check("hockey: ignores the PTS suffix",
      model.win_loss({"overall": "41-31-10, 92 PTS"}), (41.0, 31.0))
check("conference basis reads vs. Conf.",
      model.win_loss({"wins": "30", "losses": "9", "vs. Conf.": "13-7"},
                     basis="conference"), (13.0, 7.0))
check("conference basis falls back when absent",
      model.win_loss({"wins": "30", "losses": "9"}, basis="conference"), (30.0, 9.0))

print("\ngames behind")
a = {"wins": "61", "losses": "70"}          # Tigers
b = {"wins": "68", "losses": "63"}          # White Sox, division leader
near("Tigers are 7 back of the White Sox", model.gap(a, b, model.GAMES), 7.0)
near("leader is 0 back of itself", model.gap(b, b, model.GAMES), 0.0)
near("ahead reads negative", model.gap(b, a, model.GAMES), -7.0)
near("points sports subtract points",
     model.gap({"points": "92"}, {"points": "113"}, model.POINTS), 21.0)

print("\nordering")
rows = [{"team": "Purdue", "stats": {"overall": "30-9", "vs. Conf.": "13-7"}},
        {"team": "Wisconsin", "stats": {"overall": "24-11", "vs. Conf.": "14-6"}}]
order = [r["team"] for r in model._order(rows, model.GAMES, "conference")]
check("conference table sorts on conference record", order, ["Wisconsin", "Purdue"])
order2 = [r["team"] for r in model._order(rows, model.GAMES, "overall")]
check("overall basis sorts the other way", order2, ["Purdue", "Wisconsin"])

print("\ntrend (the part that needs a week of history)")
real = history.HISTORY
tmp = tempfile.mkdtemp()
try:
    history.HISTORY = tmp
    today = datetime.date(2026, 9, 10)
    history.record("test", {"Detroit Lions": 55.0}, today - datetime.timedelta(days=7))
    history.record("test", {"Detroit Lions": 68.0}, today)
    prev, delta = history.trend("test", "Detroit Lions", 68.0, today)
    near("reading from 7 days ago is found", prev, 55.0)
    near("delta is the rise", delta, 13.0)
    check("a team with no history returns nothing",
          history.trend("test", "Nobody", 50.0, today), (None, None))
    # 20 days is outside the 5-10 day window and must not be used
    history.record("test", {"Old Team": 10.0}, today - datetime.timedelta(days=20))
    check("a reading far outside the window is ignored",
          history.previous("test", "Old Team", today), None)
    # recording twice in a day must not duplicate the row
    history.record("test", {"Detroit Lions": 99.0}, today)
    series = history.read("test")["Detroit Lions"]
    check("one row per team per day", len([d for d, _ in series if d == today]), 1)
finally:
    history.HISTORY = real
    shutil.rmtree(tmp, ignore_errors=True)

print("\nseason detection  [LIVE]")
today = datetime.date.today()
check("MLB is in season", season.is_live("baseball/mlb", today), True)
# The NFL is playing exhibition games right now. If this ever returns True the
# preseason guard has broken and the app will show meaningless 1-1 records.
check("NFL preseason does NOT count as in season",
      season.is_live("football/nfl", today), False)
check("NBA is out of season", season.is_live("basketball/nba", today), False)

print("\ncollege hockey derivation  [LIVE]")
rows = chockey.standings(datetime.date(2026, 4, 20))
check("all D1 teams present", len(rows), 63)
ecac = [r for r in rows if "East Coast" in r["conference"]]
b1g = [r for r in rows if r["conference"].startswith("Big Ten")]
check("ECAC has 12 teams", len(ecac), 12)
check("Big Ten has 7 teams", len(b1g), 7)
cornell = next((r for r in rows if "Cornell" in r["team"]), None)
check("Cornell is found", bool(cornell), True)
if cornell:
    check("Cornell conference record", cornell["stats"]["vs. Conf."], "14-6-2")
check("every team matched an NPI rank",
      sum(1 for r in rows if r.get("npi")), 63)
mich = next((r for r in rows if r["team"] == "Michigan Wolverines"), None)
mstate = next((r for r in rows if "Michigan State" in r["team"]), None)
check("Michigan is NPI 1", mich and mich["npi"], 1)
# The trap: a substring match would give Michigan State Michigan's rank.
check("Michigan State has its own rank, not Michigan's",
      mstate and mstate["npi"], 3)

print("\nodds sources  [LIVE]")
nfl = odds.for_league("nfl")
nba = odds.for_league("nba")
nhl = odds.for_league("nhl")
check("NFL odds available", len(nfl) >= 30, True)
check("NBA odds available", len(nba) >= 30, True)
check("NHL odds available (Hockey-Reference)", len(nhl) > 0, True)
check("lookup matches a full name against a short label",
      odds.lookup({"tigers": 3.2}, "Detroit Tigers"), 3.2)
check("lookup matches the other direction",
      odds.lookup({"detroit lions": 68.0}, "Lions"), 68.0)
check("lookup returns nothing for an unknown team",
      odds.lookup({"tigers": 3.2}, "Arsenal"), None)

print("\ntab order")
import leagues
check("tabs are in the order he asked for",
      [t["label"] for t in leagues.TABS],
      ["CFB", "CBB", "HKY", "EPL", "NFL", "MLB", "NBA", "NHL", "MLS"])
check("college splits by sport, both schools on each tab",
      [g["label"] for g in leagues.TABS[0]["groups"]], ["Big Ten", "Ivy League"])
check("HKY is COLLEGE hockey, and derived",
      all(g.get("derived") for g in leagues.TABS[2]["groups"]), True)
check("Europe sits on the EPL tab",
      [g["key"] for g in leagues.TABS[3]["groups"]],
      ["epl", "ucl", "uel", "uecl"])

print("\nper-team columns  [LIVE]")
for key, label in (("cfb", "CFP"), ("cbb", "Seed"), ("hky", "NPI")):
    tab = next(t for t in leagues.TABS if t["key"] == key)
    built = build.table(tab["groups"][0], datetime.date.today())
    check("%s carries a %s column" % (key.upper(), label),
          built["column"]["label"], label)
    check("%s column has values" % key.upper(),
          sum(1 for r in built["rows"] if r["extra"] is not None) > 0, True)
# The BPI ranks only 50 teams nationally, so most of a conference is
# legitimately blank -- that must not be mistaken for a failure.
cbb = build.table(next(t for t in leagues.TABS if t["key"] == "cbb")["groups"][0],
                  datetime.date.today())
check("a team outside the BPI top 50 is blank, not zero",
      any(r["extra"] is None for r in cbb["rows"]), True)

print("\nodds beside my team's name")
mlbg = next(t for t in leagues.TABS if t["key"] == "mlb")["groups"][0]
tc = build.tracker(mlbg, datetime.date.today(), record=False)[0]
noted = [(sec["kind"], r["team"]) for sec in tc["sections"]
         for r in sec["rows"] if r.get("odds_note") is not None]
check("the figure appears exactly once", len(noted), 1)
check("the Tigers are not leading, so it sits in the wild-card race",
      noted and noted[0][0], "wildcard")
check("it is my team that carries it", noted and noted[0][1], "Detroit Tigers")
# ESPN writes a near certainty as ">99.9%", which does not parse as a number
# and silently blanked the strongest teams.
nfl = next(t for t in leagues.TABS if t["key"] == "nfl")["groups"][0]
lions = build.tracker(nfl, datetime.date.today(), record=False)[0]
lead_noted = [sec["kind"] for sec in lions["sections"]
              for r in sec["rows"] if r.get("odds_note") is not None]
check("a division leader carries it on the division table",
      lead_noted, ["division"])
check("no tracker table has an odds column any more",
      all(sec.get("column") is None for sec in tc["sections"]), True)
check("the wild-card label is capitalised",
      tc["sections"][1]["label"], "Wild Card Race")
# The Cavaliers share the Pistons' conference table, so their card is never
# drawn -- their odds have to be moved onto the table that is.
nbag = next(t for t in leagues.TABS if t["key"] == "nba")["groups"][0]
nba_cards = build.tracker(nbag, datetime.date.today(), record=False)
drawn = next(c for c in nba_cards if c["show_table"])
teams_noted = {r["team"] for sec in drawn["sections"] for r in sec["rows"]
               if r.get("odds_note") is not None}
check("both tracked NBA teams show odds on the one table",
      teams_noted, {"Detroit Pistons", "Cleveland Cavaliers"})

print("\nindex column")
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("sitebuild", "site.py")
sitebuild = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(sitebuild)
idx_rows = [{"gb": 0.0}, {"gb": 4.0}, {"gb": 4.0}, {"gb": 4.0}, {"gb": 5.0}]
check("ties share a position and leave the rest blank",
      sitebuild.index_cells(idx_rows), ["1", "2", "", "", "5"])
check("soccer blanks clubs level on points too",
      sitebuild.index_cells([{"gb": 0.0}, {"gb": 0.0}, {"gb": 1.0}]),
      ["1", "", "3"])
check("a missing gap does not crash the index",
      sitebuild.index_cells([{"gb": None}, {"gb": None}]), ["1", ""])
check("a points sport prints no unit in the cell",
      sitebuild.record_of({"points": 113, "record": "53-22-7"}, leagues.POINTS),
      "113")

print("\ngap formatting")
# Games behind always carries one decimal so the column lines up; points
# behind stays whole, because hockey deals in whole points.
check("a whole number of games gains a decimal",
      sitebuild.fmt(7.0, leagues.GAMES), "7.0")
check("a half game keeps its decimal", sitebuild.fmt(2.5, leagues.GAMES), "2.5")
check("points behind stays whole", sitebuild.fmt(13.0, leagues.POINTS), "13")
check("ahead of the cut line reads with a plus and a decimal",
      "+9.0" in sitebuild.behind(-9.0, leagues.GAMES), True)
check("level still reads as a dash",
      "-" in sitebuild.behind(0.0, leagues.GAMES), True)

print("\nteam names")
check("a trailing FC is dropped", sitebuild.club_name("Atlanta United FC"),
      "Atlanta United")
# Only FC and AFC come off. CF and SC stay, so these keep theirs.
check("a trailing CF stays", sitebuild.club_name("Inter Miami CF"),
      "Inter Miami CF")
check("a trailing SC stays", sitebuild.club_name("Nashville SC"),
      "Nashville SC")
check("AFC Bournemouth is just Bournemouth",
      sitebuild.club_name("AFC Bournemouth"), "Bournemouth")
# A LEADING FC is part of the name, unlike a trailing one.
check("FC Dallas keeps its FC", sitebuild.club_name("FC Dallas"), "FC Dallas")
# Stripping must never leave a bare city name.
check("Charlotte FC keeps its FC", sitebuild.club_name("Charlotte FC"),
      "Charlotte FC")
check("Toronto FC keeps its FC", sitebuild.club_name("Toronto FC"),
      "Toronto FC")
check("three words can afford to lose the FC",
      sitebuild.club_name("San Diego FC"), "San Diego")
# Two clubs the suffix rule cannot get right, named explicitly.
check("Orlando loses its SC by name",
      sitebuild.club_name("Orlando City SC"), "Orlando City")
check("but Nashville keeps its SC, or it is a bare city",
      sitebuild.club_name("Nashville SC"), "Nashville SC")
check("the Red Bulls are not filed by sponsor",
      sitebuild.club_name("Red Bull New York"), "New York Red Bulls")
check("accents are stripped", sitebuild.plain_text("Montréal"), "Montreal")
check("college splits into school and nickname",
      sitebuild.college_parts({"team": "Michigan Wolverines",
                               "location": "Michigan"}),
      ("Michigan", " Wolverines"))
check("a team whose name is just the school has no nickname",
      sitebuild.college_parts({"team": "Michigan", "location": "Michigan"}),
      ("Michigan", ""))

print("\ncolumn counts")
# The Ivy tables have no metric of their own -- FCS has no FPI odds and the
# BPI ranks only 50 teams -- so they came out a column narrower than the Big
# Ten table above them, and the numbers shifted halfway down the page.
_data = build.build_all(include_offseason=True)
for _tab in _data["tabs"]:
    if len(_tab["tables"]) > 1:
        check("%s tables all carry the same columns" % _tab["label"],
              len({bool(t.get("column")) for t in _tab["tables"]}), 1)

print("\ncrest variants")
import json as _json
try:
    with open("logo-overrides.json", encoding="utf-8") as fh:
        overrides = _json.load(fh)
except OSError:
    overrides = {}
check("the measured override list exists", len(overrides) > 0, True)
# ESPN's -dark crest is a flat white silhouette for these, so they keep the
# default variant. Regenerate with `python logos.py --write`.
check("the Tigers keep their default crest",
      "/500-dark/" in overrides.get("Detroit Tigers", "/500-dark/"), False)
check("a team whose dark crest has colour is not overridden",
      "Cleveland Guardians" in overrides, False)
check("crest() honours an override",
      "/500-dark/" in sitebuild.crest({"team": "Detroit Tigers",
                                       "logo": "https://x/500/det.png"}), False)
check("crest() uses the dark variant otherwise",
      "/500-dark/" in sitebuild.crest({"team": "Nobody",
                                       "logo": "https://x/500/nob.png"}), True)

print("\nend to end  [LIVE]")
data = build.build_all(include_offseason=False)
live = sorted(t["label"] for t in data["tabs"] if t["live"])
check("only in-season tabs are live", live, ["CFB", "EPL", "MLB", "MLS"])
shown = [t for t in data["tabs"] if t["cards"] or t["tables"]]
check("out-of-season tabs carry no content",
      all(not t["cards"] and not t["tables"]
          for t in data["tabs"] if not t["live"]), True)
mlb = next(t for t in data["tabs"] if t["key"] == "mlb")
card = mlb["cards"][0]
check("MLB card is the Tigers", card["team"], "Detroit Tigers")
check("MLB card has odds", card["odds"] is not None, True)
check("MLB card knows its cut-line gap", card["cut"] is not None, True)

print("\nsections")
kinds = [s["kind"] for s in card["sections"]]
check("MLB shows division then wild card", kinds, ["division", "wildcard"])
div = card["sections"][0]
wc = card["sections"][1]
check("division holds only the division", len(div["rows"]), 5)
check("division has no cut line", div["cut"], None)
check("wild card is cut after three", wc["cut"], 3)
# A division leader holds an automatic berth and is not chasing a wild card,
# so it must not appear in the wild-card field.
leaders = {r["team"] for r in div["rows"]}
top = div["rows"][0]["team"]
check("the division leader is absent from the wild-card race",
      top in {r["team"] for r in wc["rows"]}, False)
check("the wild-card field is smaller than the league",
      len(wc["rows"]) < 15, True)
# The wild-card column is measured from the LAST spot, so the team holding it
# reads zero and everyone above it is negative.
check("the team on the cut line is the reference",
      abs(wc["rows"][wc["cut"] - 1]["gb"] or 0) < 0.01, True)
check("teams above the line are ahead of it", wc["rows"][0]["gb"] < 0, True)
check("teams below the line are behind it", wc["rows"][wc["cut"]]["gb"] > 0, True)
nba = next(t for t in leagues.TABS if t["key"] == "nba")
check("NBA is configured for one conference table",
      nba["groups"][0]["sections"], ["conference"])

print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
if FAIL:
    print("failed: %s" % ", ".join(FAIL))
sys.exit(1 if FAIL else 0)
