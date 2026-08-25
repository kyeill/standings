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
nba = next(t for t in leagues.TABS if t["key"] == "nba")
check("NBA is configured for one conference table",
      nba["groups"][0]["sections"], ["conference"])

print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
if FAIL:
    print("failed: %s" % ", ".join(FAIL))
sys.exit(1 if FAIL else 0)
