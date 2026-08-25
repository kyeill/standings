"""Which tabs the app has, and what each one shows.

Two display modes, per Kyle's call on 2026-08-25:

  tracker  the Big 4 American sports. A playoff race: the cut line, the gap to
           it, the odds and how they have moved. Rows not adjacent to a
           decision are collapsed.
  table    everything else -- college and soccer. A straight standings table,
           because those sports either have no cut line (college: the race is
           a poll or a bracket) or their table IS the competition (soccer).

A tab may hold several tables. College combines Michigan and Cornell across
three sports; the Tottenham tab combines the Premier League with whichever
European competition is running.
"""

GAMES, POINTS = "games", "points"

TABS = [
    {
        "key": "nfl", "label": "NFL", "mode": "tracker",
        "groups": [{
            "key": "nfl", "path": "football/nfl", "label": "NFC",
            "teams": ["Detroit Lions"], "spots": 7, "unit": GAMES,
            "spots_label": "wild card", "odds": "nfl",
        }],
    },
    {
        "key": "mlb", "label": "MLB", "mode": "tracker",
        "groups": [{
            "key": "mlb", "path": "baseball/mlb", "label": "American League",
            "teams": ["Detroit Tigers"], "spots": 6, "unit": GAMES,
            "spots_label": "wild card", "odds": "mlb",
        }],
    },
    {
        "key": "nba", "label": "NBA", "mode": "tracker",
        "groups": [{
            "key": "nba", "path": "basketball/nba", "label": "Eastern Conference",
            "teams": ["Detroit Pistons", "Cleveland Cavaliers"], "spots": 10,
            "unit": GAMES, "spots_label": "play-in", "odds": "nba",
        }],
    },
    {
        "key": "nhl", "label": "NHL", "mode": "tracker",
        "groups": [{
            "key": "nhl", "path": "hockey/nhl", "label": "Eastern Conference",
            "teams": ["Detroit Red Wings"], "spots": 8, "unit": POINTS,
            "spots_label": "wild card", "odds": "nhl",
        }],
    },
    {
        "key": "college", "label": "College", "mode": "table",
        "groups": [
            {"key": "cfb", "path": "football/college-football", "group": 80,
             "label": "Football -- Big Ten", "teams": ["Michigan Wolverines"],
             "basis": "conference", "unit": GAMES, "poll": "ap"},
            {"key": "cfb-fcs", "path": "football/college-football", "group": 81,
             "label": "Football -- Ivy League", "teams": ["Cornell Big Red"],
             "basis": "conference", "unit": GAMES, "poll": "fcs"},
            {"key": "cbb", "path": "basketball/mens-college-basketball",
             "label": "Basketball -- Big Ten", "teams": ["Michigan Wolverines"],
             "basis": "conference", "unit": GAMES, "poll": "ap"},
            {"key": "cbb-ivy", "path": "basketball/mens-college-basketball",
             "label": "Basketball -- Ivy League", "teams": ["Cornell Big Red"],
             "basis": "conference", "unit": GAMES, "poll": "ap"},
            # ESPN publishes no college hockey standings at any level, so
            # chockey.py derives them from game results. Michigan and Cornell
            # are in different conferences, hence two groups.
            {"key": "chockey-b10", "path": "hockey/mens-college-hockey",
             "label": "Hockey -- Big Ten", "teams": ["Michigan Wolverines"],
             "basis": "conference", "unit": GAMES, "derived": True},
            {"key": "chockey-ecac", "path": "hockey/mens-college-hockey",
             "label": "Hockey -- ECAC", "teams": ["Cornell Big Red"],
             "basis": "conference", "unit": GAMES, "derived": True},
        ],
    },
    {
        "key": "spurs", "label": "Tottenham", "mode": "table",
        "groups": [
            {"key": "epl", "path": "soccer/eng.1", "label": "Premier League",
             "teams": ["Tottenham Hotspur"], "unit": POINTS,
             "line": 4, "line_label": "Champions League"},
            {"key": "ucl", "path": "soccer/uefa.champions",
             "label": "Champions League -- league phase",
             "teams": ["Tottenham Hotspur"], "unit": POINTS,
             "line": 8, "line_label": "last 16", "optional": True,
             "require_phase": "league-phase"},
            {"key": "uel", "path": "soccer/uefa.europa",
             "label": "Europa League -- league phase",
             "teams": ["Tottenham Hotspur"], "unit": POINTS,
             "line": 8, "line_label": "last 16", "optional": True,
             "require_phase": "league-phase"},
            {"key": "uecl", "path": "soccer/uefa.europa.conf",
             "label": "Conference League -- league phase",
             "teams": ["Tottenham Hotspur"], "unit": POINTS,
             "line": 8, "line_label": "last 16", "optional": True,
             "require_phase": "league-phase"},
        ],
    },
    {
        "key": "mls", "label": "Atlanta", "mode": "table",
        "groups": [{
            "key": "mls", "path": "soccer/usa.1", "label": "Eastern Conference",
            "teams": ["Atlanta United"], "unit": POINTS,
            "line": 9, "line_label": "playoff",
        }],
    },
]


def all_groups():
    for tab in TABS:
        for group in tab["groups"]:
            yield tab, group
