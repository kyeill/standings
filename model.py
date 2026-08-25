"""Turn ESPN standings into one uniform 'race card' per tracked team.

The shape every sport is squeezed into:

    {league, team, record,
     division: {name, rank, of, gap, rows},        place in the division table
     ladder:   {name, seed, of, spots, gap, rows}, the playoff cut line
     odds:     {label, pct} or None,
     state:    in / out / clinched / eliminated}

Sports that cannot fill a field leave it None rather than faking one -- the
whole point of the exercise is to see which sports come up empty.
"""

import fetch

GAMES, POINTS = "games", "points"

LEAGUES = [
    {"key": "mlb", "label": "MLB", "path": "baseball/mlb",
     "teams": ["Detroit Tigers"], "spots": 6, "unit": GAMES,
     "ladder_label": "American League", "spots_label": "wild card"},
    {"key": "nfl", "label": "NFL", "path": "football/nfl",
     "teams": ["Detroit Lions"], "spots": 7, "unit": GAMES,
     "ladder_label": "NFC", "spots_label": "wild card"},
    {"key": "nba", "label": "NBA", "path": "basketball/nba",
     "teams": ["Detroit Pistons", "Cleveland Cavaliers"], "spots": 10, "unit": GAMES,
     "ladder_label": "Eastern Conference", "spots_label": "play-in"},
    {"key": "nhl", "label": "NHL", "path": "hockey/nhl",
     "teams": ["Detroit Red Wings"], "spots": 8, "unit": POINTS,
     "ladder_label": "Eastern Conference", "spots_label": "wild card"},
    {"key": "cfb", "basis": "conference", "label": "College Football", "path": "football/college-football",
     "teams": ["Michigan Wolverines"], "spots": None, "unit": GAMES,
     "group": 80, "ladder_label": None, "spots_label": None},
    {"key": "cfb-fcs", "basis": "conference", "label": "College Football", "path": "football/college-football",
     "teams": ["Cornell Big Red"], "spots": None, "unit": GAMES,
     "group": 81, "ladder_label": None, "spots_label": None},
    {"key": "cbb", "basis": "conference", "label": "College Basketball",
     "path": "basketball/mens-college-basketball",
     "teams": ["Michigan Wolverines", "Cornell Big Red"], "spots": None,
     "unit": GAMES, "ladder_label": None, "spots_label": None},
    {"key": "chockey", "label": "College Hockey", "path": "hockey/mens-college-hockey",
     "teams": ["Michigan Wolverines", "Cornell Big Red"], "spots": None,
     "unit": GAMES, "ladder_label": None, "spots_label": None},
    {"key": "epl", "label": "Premier League", "path": "soccer/eng.1",
     "teams": ["Tottenham Hotspur"], "spots": 5, "unit": POINTS,
     "ladder_label": "Premier League", "spots_label": "Champions League"},
    {"key": "mls", "label": "MLS", "path": "soccer/usa.1",
     "teams": ["Atlanta United"], "spots": 9, "unit": POINTS,
     "ladder_label": "Eastern Conference", "spots_label": "playoff"},
]

ODDS = {
    "nfl": ("football/nfl", "probmakeplayoffs", "to make the playoffs"),
    "nba": ("basketball/nba", "probmakeplayoffs", "to make the playoffs"),
    "cfb": ("football/college-football", "probmakeplayoffs", "to make the CFP"),
}

CLINCH = {"z": "clinched", "y": "clinched", "x": "clinched", "*": "clinched",
          "xp": "in", "pb": "in", "e": "eliminated"}


def num(value):
    try:
        return float(str(value).replace("+", "").strip())
    except (TypeError, ValueError):
        return None


def _int(value):
    v = num(value)
    return int(v) if v is not None else None


def short(text):
    """Hockey reports '41-31-10, 92 PTS' and a last-ten of '7-2-1, 0 PTS';
    the points half of the last-ten figure is always zero. Keep the record."""
    return (text or "").split(",")[0].strip() or None


def matches(row, name):
    return name.lower() in (row["team"] or "").lower()


def _split(text):
    parts = [num(p) for p in (text or "").split(",")[0].split("-")]
    parts = [p for p in parts if p is not None]
    return (parts[0], parts[1]) if len(parts) >= 2 else (None, None)


def win_loss(stats, basis="overall"):
    """(wins, losses) for any sport.

    College football publishes NO `losses` stat -- only `wins` and an `overall`
    string like "8-3" -- so a plain stats.get("losses") reads None and every
    games-behind calculation silently collapses. Parse `overall` as the
    fallback. Hockey's overall is "41-31-10, 92 PTS", so split on the comma
    first and take only the first two numbers.

    A college CONFERENCE table is ordered by conference record, not overall
    record, so games-behind there has to be computed on the same basis the
    table is sorted by -- otherwise the column contradicts the order it sits
    in (Purdue 30-9 appearing below Wisconsin 24-11 with a smaller number).
    """
    if basis == "conference":
        w, l = _split(stats.get("vs. Conf.") or stats.get("vs. Conf"))
        if w is not None:
            return w, l
    w, l = num(stats.get("wins")), num(stats.get("losses"))
    if w is not None and l is not None:
        return w, l
    return _split(stats.get("overall"))


def gap(a, b, unit, basis="overall"):
    """How far a is behind b. Negative means a is ahead."""
    if unit == POINTS:
        pa, pb = num(a.get("points")), num(b.get("points"))
        if pa is None or pb is None:
            return None
        return pb - pa
    aw, al = win_loss(a, basis)
    bw, bl = win_loss(b, basis)
    if None in (aw, al, bw, bl):
        return None
    return ((bw - aw) + (al - bl)) / 2


def _order(rows, unit, basis="overall"):
    """Sort a group the way the sport ranks it.

    ESPN's own order is unreliable: college basketball comes back worst-first
    and the college football conference table is not sorted at all. Never
    trust the payload order.
    """
    def key(r):
        s = r["stats"]
        # ESPN's playoffSeed encodes the league's real tiebreakers (the NHL
        # orders on points but breaks ties on regulation wins), so prefer it
        # where the sport has one. College seeds are absent or meaningless.
        seed = _int(s.get("playoffSeed"))
        if seed and basis != "conference":
            return (seed, 0.0)
        if unit == POINTS:
            rank = _int(s.get("rank"))
            if rank:
                return (rank, 0.0)
            return (-(num(s.get("points")) or 0),
                    -(num(s.get("pointDifferential")) or 0))
        w, l = win_loss(s, basis)
        w, l = w or 0, l or 0
        pct = w / (w + l) if (w + l) else 0
        return (-pct, -w)
    return sorted(rows, key=key)


def _row(r, me, unit, basis="overall", leader=None):
    s = r["stats"]
    return {
        "team": r["team"], "abbr": r["abbr"], "logo": r["logo"],
        "id": r.get("id"),
        "mine": r["team"] == me["team"],
        "record": s.get("overall") or "%s-%s" % (s.get("wins"), s.get("losses")),
        "conf_record": s.get("vs. Conf.") or s.get("vs. Conf") or "",
        "wins": _int(win_loss(s, basis)[0]), "losses": _int(win_loss(s, basis)[1]),
        "points": _int(s.get("points")), "gp": _int(s.get("gamesPlayed")),
        "diff": s.get("pointDifferential") or s.get("differential"),
        # two different questions: how far behind the leader (the conventional
        # standings column) and how far from MY team (the only one that
        # matters when the table is there to explain my race)
        "gb": gap(s, leader["stats"], unit, basis) if leader else None,
        "vs_me": gap(s, me["stats"], unit, basis),
        "streak": s.get("streak"), "last10": s.get("Last Ten Games"),
        "clincher": (s.get("clincher") or "").strip().lower(),
        "seed": _int(s.get("playoffSeed")),
    }


def build(league):
    """[race card] for every tracked team in one league."""
    unit = league["unit"]
    group = league.get("group")
    div_rows = fetch.rows(league["path"], level=3, group=group)
    lad_rows = fetch.rows(league["path"], level=2, group=group)
    if not div_rows and not lad_rows:
        return [{"league": league["label"], "key": league["key"], "team": t,
                 "missing": "ESPN publishes no standings for this sport"}
                for t in league["teams"]]

    odds_table = {}
    if league["key"] in ODDS:
        path, field, _label = ODDS[league["key"]]
        for name, proj in fetch.power_index(path, league["key"]).items():
            value = proj.get(field)
            if isinstance(value, (int, float)):
                odds_table[name.lower()] = float(value)

    cards = []
    for name in league["teams"]:
        me = next((r for r in div_rows if matches(r, name)), None)
        if me is None:
            me = next((r for r in lad_rows if matches(r, name)), None)
        if me is None:
            cards.append({"league": league["label"], "key": league["key"],
                          "team": name,
                          "missing": "not in this season's standings"})
            continue
        st = me["stats"]
        card = {
            "league": league["label"], "key": league["key"],
            "team": me["team"], "abbr": me["abbr"], "logo": me["logo"],
            "record": st.get("overall") or "%s-%s" % (st.get("wins"), st.get("losses")),
            "streak": st.get("streak"), "last10": st.get("Last Ten Games"),
            "points": _int(st.get("points")), "gp": _int(st.get("gamesPlayed")),
            "unit": unit, "missing": None, "odds_extra": None,
        }

        basis = league.get("basis", "overall")
        card["basis"] = basis
        peers = _order([r for r in div_rows if r["division"] == me["division"]],
                       unit, basis)
        if peers:
            rank = [p["team"] for p in peers].index(me["team"]) + 1
            behind = gap(st, peers[0]["stats"], unit, basis)
            if rank == 1 and len(peers) > 1:
                behind = -abs(gap(peers[1]["stats"], st, unit, basis) or 0)
            card["division"] = {"name": me["division"], "rank": rank,
                                "of": len(peers), "gap": behind,
                                "rows": [_row(p, me, unit, basis, peers[0])
                                         for p in peers]}
        else:
            card["division"] = None

        conf = me["conference"] or (lad_rows[0]["conference"] if lad_rows else "")
        pool = _order([r for r in lad_rows if r["conference"] == conf] or lad_rows,
                      unit, basis)
        spots = league["spots"]
        if pool and spots:
            names = [p["team"] for p in pool]
            seed = names.index(me["team"]) + 1 if me["team"] in names else None
            cut = None
            if seed and len(pool) > spots:
                if seed <= spots:
                    cut = -abs(gap(pool[spots]["stats"], st, unit, basis) or 0)
                else:
                    cut = gap(st, pool[spots - 1]["stats"], unit, basis)
            card["ladder"] = {"name": league["ladder_label"] or conf, "seed": seed,
                              "of": len(pool), "spots": spots, "gap": cut,
                              "spots_label": league["spots_label"],
                              "rows": [_row(p, me, unit, basis, pool[0])
                                       for p in pool]}
        else:
            card["ladder"] = None

        card["odds"] = None
        if league["key"] in ODDS:
            for label, value in odds_table.items():
                if name.lower() in label or label in name.lower():
                    card["odds"] = {"pct": value, "label": ODDS[league["key"]][2],
                                    "source": "ESPN FPI/BPI"}
                    break
        if league["key"] == "mlb":
            raw = num((st.get("playoffPercent") or "").replace("%", ""))
            if raw is not None:
                card["odds"] = {"pct": raw, "label": "to make the playoffs",
                                "source": "ESPN"}
                card["odds_extra"] = {
                    "wildcard": num((st.get("wildCardPercent") or "").replace("%", "")),
                    "magic_div": st.get("magicNumberDivision"),
                    "magic_wc": st.get("magicNumberWildcard")}

        clinch = (st.get("clincher") or "").strip().lower()
        card["state"] = CLINCH.get(clinch)
        if card["state"] is None and card["ladder"] and card["ladder"]["seed"]:
            card["state"] = "in" if card["ladder"]["seed"] <= (spots or 0) else "out"
        cards.append(card)
    return cards


def all_cards():
    out = []
    for league in LEAGUES:
        out.extend(build(league))
    return out


if __name__ == "__main__":
    for c in all_cards():
        if c.get("missing"):
            print("%-20s %-24s -- %s" % (c["league"], c["team"], c["missing"]))
            continue
        d, l = c.get("division"), c.get("ladder")
        print("%-20s %-24s %-18s div %-12s ladder %-12s odds %s" % (
            c["league"], c["team"], c["record"],
            "%s/%s %+.1f" % (d["rank"], d["of"], d["gap"])
            if d and d["gap"] is not None else "-",
            "%s of %s %+.1f" % (l["seed"], l["spots"], l["gap"])
            if l and l["gap"] is not None else "-",
            "%.0f%%" % c["odds"]["pct"] if c.get("odds") else "-"))
