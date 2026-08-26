"""Which tabs the app has, and what each one shows.

Two display modes, per Kyle's call on 2026-08-25:

  tracker  the Big 4 American sports. A playoff race: the cut line, the gap to
           it, the odds and how they have moved. Rows not adjacent to a
           decision are collapsed.
  table    everything else -- college and soccer. A straight standings table,
           because those sports either have no cut line (college: the race is
           a poll or a bracket) or their table IS the competition (soccer).

Tab order and headings are his, given 2026-08-25: CFB CBB HKY EPL NFL MLB NBA
NHL MLS. College is split by SPORT rather than by school, so Michigan and
Cornell appear together on each of the three college tabs. HKY is COLLEGE
hockey; the NHL has its own tab. Tottenham's European competitions sit on the
EPL tab alongside the domestic table.
"""

GAMES, POINTS = "games", "points"

MICHIGAN, CORNELL = "Michigan Wolverines", "Cornell Big Red"
SPURS = "Tottenham Hotspur"

TABS = [
    {
        "key": "cfb", "label": "CFB", "mode": "table",
        "groups": [
            {"key": "cfb", "path": "football/college-football", "group": 80,
             "label": "Big Ten", "teams": [MICHIGAN],
             "basis": "conference", "unit": GAMES, "poll": "ap",
             # ESPN's FPI carries probmakeplayoffs for college football, which
             # there means the CFP.
             "odds": "cfb", "odds_label": "to make the CFP",
             "column": {"source": "powerindex", "path": "football/college-football",
                        "key": "cfb", "field": "probmakeplayoffs",
                        "label": "CFP", "fmt": "pct"}},
            # Cornell is Ivy, which is FCS -- a different feed entirely.
            {"key": "cfb-fcs", "path": "football/college-football", "group": 81,
             "label": "Ivy League", "teams": [CORNELL],
             "basis": "conference", "unit": GAMES, "poll": "fcs"},
        ],
    },
    {
        "key": "cbb", "label": "CBB", "mode": "table",
        "groups": [
            {"key": "cbb", "path": "basketball/mens-college-basketball",
             "label": "Big Ten", "teams": [MICHIGAN],
             "basis": "conference", "unit": GAMES, "poll": "ap",
             # BPI has no "chance to make the tournament", but it does project
             # a seed, which is the bracketology answer.
             "column": {"source": "powerindex",
                        "path": "basketball/mens-college-basketball", "key": "cbb",
                        "field": "projectedtournamentseed",
                        "label": "Seed", "fmt": "int"}},
            {"key": "cbb-ivy", "path": "basketball/mens-college-basketball",
             "label": "Ivy League", "teams": [CORNELL],
             "basis": "conference", "unit": GAMES, "poll": "ap"},
        ],
    },
    {
        # College hockey. ESPN publishes no standings at any level, so these
        # are derived from game results in chockey.py.
        "key": "hky", "label": "HKY", "mode": "table",
        "groups": [
            {"key": "chockey-b10", "path": "hockey/mens-college-hockey",
             "label": "Big Ten", "teams": [MICHIGAN],
             "basis": "conference", "unit": GAMES, "derived": True,
             "column": {"source": "npi", "label": "NPI", "fmt": "int"}},
            {"key": "chockey-ecac", "path": "hockey/mens-college-hockey",
             "label": "ECAC", "teams": [CORNELL],
             "basis": "conference", "unit": GAMES, "derived": True,
             "column": {"source": "npi", "label": "NPI", "fmt": "int"}},
        ],
    },
    {
        "key": "epl", "label": "EPL", "mode": "table",
        "groups": [
            {"key": "epl", "path": "soccer/eng.1", "label": "Premier League",
             "teams": [SPURS], "unit": POINTS,
             "line": 4, "line_label": "Champions League"},
            # A European competition only has a table during its league phase;
            # once the knockouts start there is nothing to stand in one.
            {"key": "ucl", "path": "soccer/uefa.champions",
             "label": "Champions League", "teams": [SPURS], "unit": POINTS,
             "line": 8, "line_label": "last 16", "optional": True,
             "require_phase": "league-phase"},
            {"key": "uel", "path": "soccer/uefa.europa",
             "label": "Europa League", "teams": [SPURS], "unit": POINTS,
             "line": 8, "line_label": "last 16", "optional": True,
             "require_phase": "league-phase"},
            {"key": "uecl", "path": "soccer/uefa.europa.conf",
             "label": "Conference League", "teams": [SPURS], "unit": POINTS,
             "line": 8, "line_label": "last 16", "optional": True,
             "require_phase": "league-phase"},
        ],
    },
    {
        "key": "nfl", "label": "NFL", "mode": "tracker",
        "groups": [{
            "key": "nfl", "path": "football/nfl", "label": "NFC",
            "teams": ["Detroit Lions"], "spots": 7, "unit": GAMES,
            "spots_label": "wild card", "odds": "nfl",
            # Division table, then the wild-card race among the teams that are
            # not leading one. Three wild cards per conference.
            "sections": ["division", "wildcard"], "wildcards": 3,
        }],
    },
    {
        "key": "mlb", "label": "MLB", "mode": "tracker",
        "groups": [{
            "key": "mlb", "path": "baseball/mlb", "label": "American League",
            "teams": ["Detroit Tigers"], "spots": 6, "unit": GAMES,
            "spots_label": "wild card", "odds": "mlb",
            "sections": ["division", "wildcard"], "wildcards": 3,
        }],
    },
    {
        "key": "nba", "label": "NBA", "mode": "tracker",
        "groups": [{
            "key": "nba", "path": "basketball/nba", "label": "Eastern Conference",
            "teams": ["Detroit Pistons", "Cleveland Cavaliers"], "spots": 10,
            "unit": GAMES, "spots_label": "play-in", "odds": "nba",
            "sections": ["conference"],
        }],
    },
    {
        "key": "nhl", "label": "NHL", "mode": "tracker",
        "groups": [{
            "key": "nhl", "path": "hockey/nhl", "label": "Eastern Conference",
            "teams": ["Detroit Red Wings"], "spots": 8, "unit": POINTS,
            "spots_label": "wild card", "odds": "nhl",
            "sections": ["conference"],
        }],
    },
    {
        "key": "mls", "label": "MLS", "mode": "table",
        "groups": [{
            "key": "mls", "path": "soccer/usa.1", "label": "Eastern Conference",
            "teams": ["Atlanta United"], "unit": POINTS,
            "line": 9, "line_label": "playoff",
        }],
    },
]

