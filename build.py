"""Assemble every tab's data: trackers for the Big 4, tables for the rest."""

import datetime
import os

import chockey
import fetch
import history
import leagues
import model
import odds as odds_src
import season

POINTS = leagues.POINTS


def _find(rows, name):
    return next((r for r in rows if name.lower() in (r["team"] or "").lower()), None)


def _odds_for(group, rows):
    """{team display name: percent} for every team in the group, so the whole
    column can be recorded to history, not just my own team's number."""
    key = group.get("odds")
    if not key:
        return {}
    if key == "mlb":
        out = {}
        for r in rows:
            # ESPN writes a near-certainty as ">99.9%" and a long shot as
            # "<0.1%", so the comparison character has to come off before the
            # number will parse -- otherwise the best teams show no odds.
            raw = (r["stats"].get("playoffPercent") or "")
            raw = raw.replace("%", "").replace(">", "").replace("<", "").strip()
            value = model.num(raw)
            if value is not None:
                out[r["team"]] = value
        return out
    table = odds_src.for_league(key)
    out = {}
    for r in rows:
        value = odds_src.lookup(table, r["team"])
        if value is not None:
            out[r["team"]] = value
    return out


def tracker(group, today, record=True):
    """The Big 4 view: where my team sits against the playoff cut line."""
    unit = group["unit"]
    div_rows = fetch.rows(group["path"], level=3)
    lad_rows = fetch.rows(group["path"], level=2)
    if not lad_rows:
        return []
    odds_table = _odds_for(group, lad_rows)
    # Only a league that is actually being played gets written to history.
    # Without this guard a --all test run banks preseason and finished-season
    # numbers, which then surface as the "a week ago" baseline once the real
    # season starts.
    if odds_table and record:
        history.record(group["key"], odds_table, today)

    cards = []
    for name in group["teams"]:
        me = _find(div_rows, name) or _find(lad_rows, name)
        if not me:
            cards.append({"team": name, "missing": "not in this season's standings"})
            continue
        st = me["stats"]
        conf = me["conference"] or (lad_rows[0]["conference"] if lad_rows else "")
        pool = model._order([r for r in lad_rows if r["conference"] == conf] or lad_rows,
                            unit)
        names = [p["team"] for p in pool]
        seed = names.index(me["team"]) + 1 if me["team"] in names else None
        spots = group["spots"]
        cut = None
        if seed and len(pool) > spots:
            other = pool[spots] if seed <= spots else pool[spots - 1]
            cut = (-abs(model.gap(other["stats"], st, unit) or 0) if seed <= spots
                   else model.gap(st, other["stats"], unit))

        peers = model._order([r for r in div_rows if r["division"] == me["division"]],
                             unit)
        div = None
        if peers:
            rank = [p["team"] for p in peers].index(me["team"]) + 1
            behind = model.gap(st, peers[0]["stats"], unit)
            if rank == 1 and len(peers) > 1:
                behind = -abs(model.gap(peers[1]["stats"], st, unit) or 0)
            div = {"name": me["division"], "rank": rank, "of": len(peers),
                   "gap": behind}

        sections = _sections(group, me, div_rows, pool, unit, odds_table)
        # The verdict at the top of the card answers the question the sport
        # actually poses: a division leader is not in the wild-card race, so
        # reporting a wild-card gap for them would be nonsense.
        leads = bool(div and div["rank"] == 1)
        wc = next((s for s in sections if s["kind"] == "wildcard"), None)
        if leads and div:
            cut, cut_label = div["gap"], "in the division"
        elif wc:
            cut, cut_label = wc["gap"], "of the %s line" % group["spots_label"]
        else:
            cut, cut_label = cut, "of the %s line" % group["spots_label"]

        pct = odds_table.get(me["team"])
        prev, delta = history.trend(group["key"], me["team"], pct, today)
        # The odds are annotated onto my team's name in exactly ONE table: the
        # division when it is leading (that is the race it is in), otherwise
        # the wild-card race. With neither, the conference ladder carries it.
        if pct is not None:
            order = (["division"] if leads else ["wildcard"]) + ["conference",
                                                                "division"]
            target = next((sec for kind in order for sec in sections
                           if sec["kind"] == kind), None)
            if target:
                for row in target["rows"]:
                    if row["team"] == me["team"]:
                        row["odds_note"] = pct
                        row["odds_note_delta"] = delta
                        break
        cards.append({
            "team": me["team"], "logo": me["logo"], "missing": None,
            "record": model.short(st.get("overall")) or "%s-%s" % (
                st.get("wins"), st.get("losses")),
            "points": model._int(st.get("points")),
            "streak": st.get("streak"), "last10": model.short(st.get("Last Ten Games")),
            "unit": unit, "seed": seed, "spots": spots, "of": len(pool),
            "spots_label": group["spots_label"], "ladder_name": group["label"],
            "cut": cut, "cut_label": cut_label, "division": div,
            "sections": sections, "leads_division": leads,
            "clincher": (st.get("clincher") or "").strip().lower(),
            "magic": st.get("magicNumberDivision") or "",
            "odds": pct, "odds_prev": prev, "odds_delta": delta,
        })
    # Two tracked teams in one conference (the Pistons and the Cavaliers) share
    # a ladder, so only the first card draws it; the rest are highlighted
    # inside that one table instead of repeating it.
    shown = {}
    for c in cards:
        if c.get("missing"):
            continue
        # Two tracked teams in one conference share a ladder; only the first
        # card draws the tables.
        first = shown.get(c["ladder_name"])
        c["show_table"] = first is None
        if first is None:
            shown[c["ladder_name"]] = c
        else:
            # This card will not be rendered, so its odds would be lost. Move
            # the annotation onto the table that IS drawn -- otherwise the
            # Cavaliers' number simply never appears anywhere.
            _adopt_note(first, c)
    return cards


def _adopt_note(target, hidden):
    """Copy a hidden card's odds annotation onto the card that gets drawn."""
    for sec in hidden["sections"]:
        for row in sec["rows"]:
            if row.get("odds_note") is None:
                continue
            for other in target["sections"]:
                if other["kind"] != sec["kind"]:
                    continue
                for dest in other["rows"]:
                    if dest["team"] == row["team"]:
                        dest["odds_note"] = row["odds_note"]
                        dest["odds_note_delta"] = row.get("odds_note_delta")
            return


def _sections(group, me, div_rows, pool, unit, odds_table=None):
    """The tables a tracker card shows, per the league's `sections`.

    division  my division, everyone in it, games behind the leader
    wildcard  the race for the remaining spots: the conference MINUS the teams
              currently leading a division, since those hold the automatic
              berths and are not competing for a wild card
    conference  one straight ladder, seeds 1..N -- what the NBA and NHL use
    """
    tracked = group["teams"]
    wanted = group.get("sections") or ["conference"]
    # Odds go in a column, the same way the college tabs carry CFP odds, NPI
    # and projected seed -- so every sport reads the same and the card needs
    # no header explaining itself.
    # No per-team odds column: the tracked team carries its own figure in
    # parentheses after its name, and a column of everyone else's odds is
    # noise on a page about my team.
    column = None
    out = []

    for kind in wanted:
        if kind == "division":
            peers = model._order([r for r in div_rows
                                  if r["division"] == me["division"]], unit)
            if not peers:
                continue
            out.append({
                "kind": "division", "label": me["division"], "cut": None,
                "cut_label": None,
                "gap": model.gap(me["stats"], peers[0]["stats"], unit),
                "column": column,
                "rows": _with_odds(rows_for(peers, me, unit, tracked), odds_table),
            })
        elif kind == "wildcard":
            leaders = set()
            for row in div_rows:
                if row["conference"] != me["conference"]:
                    continue
                same = model._order([r for r in div_rows
                                     if r["division"] == row["division"]], unit)
                if same:
                    leaders.add(same[0]["team"])
            chase = [r for r in pool if r["team"] not in leaders]
            if not chase:
                continue
            spots = group.get("wildcards", 3)
            names = [r["team"] for r in chase]
            gap = None
            if me["team"] in names and len(chase) > spots:
                at = names.index(me["team"])
                other = chase[spots] if at < spots else chase[spots - 1]
                gap = (-abs(model.gap(other["stats"], me["stats"], unit) or 0)
                       if at < spots
                       else model.gap(me["stats"], other["stats"], unit))
            # Games behind the LAST wild-card spot, which is the number that
            # answers "am I in". Teams above the line come out negative and
            # render with a plus.
            line = chase[spots - 1] if len(chase) >= spots else None
            out.append({
                "kind": "wildcard", "label": "Wild Card Race", "cut": spots,
                "cut_label": group["spots_label"], "gap": gap,
                "from_cut": True, "column": column,
                "rows": _with_odds(rows_for(chase, me, unit, tracked, leader=line),
                                   odds_table),
            })
        else:
            out.append({
                "kind": "conference", "label": group["label"],
                "cut": group["spots"], "cut_label": group["spots_label"],
                "gap": None, "column": column,
                "rows": _with_odds(rows_for(pool, me, unit, tracked), odds_table),
            })
    return out


def _with_odds(rows, odds_table):
    for row in rows:
        row["extra"] = (odds_table or {}).get(row["team"])
    return rows


def rows_for(pool, me, unit, tracked, leader=None):
    """leader defaults to the top of the field; a wild-card table passes the
    team holding the LAST spot instead, so the column reads as distance from
    the cut line rather than from a leader nobody is racing."""
    names = [t.lower() for t in tracked]
    out = []
    for p in pool:
        row = model._row(p, me, unit, "overall", leader or pool[0])
        row["mine"] = any(n in p["team"].lower() for n in names)
        out.append(row)
    return out


def _extra_column(group, pool):
    """(spec, {team: value}) for an optional per-team column.

    Keyed on ESPN's displayName and matched EXACTLY -- the power index and the
    standings both use it, and anything looser hands Michigan State the
    Wolverines' number.
    """
    spec = group.get("column")
    if not spec:
        return None, {}
    if spec["source"] == "npi":
        return spec, {r["team"]: r.get("npi") for r in pool}
    if spec["source"] == "powerindex":
        table = fetch.power_index(spec["path"], spec["key"])
        return spec, {name: vals.get(spec["field"]) for name, vals in table.items()}
    return None, {}


def table(group, today):
    """The college and soccer view: a straight standings table."""
    unit = group["unit"]
    basis = group.get("basis", "overall")
    if group.get("derived"):
        rows = chockey.standings(today)
    else:
        rows = fetch.rows(group["path"], level=2, group=group.get("group"))
    if not rows:
        return None
    me = _find(rows, group["teams"][0])
    others = [t for t in group["teams"][1:]]
    if not me:
        return None
    pool = model._order([r for r in rows if r["conference"] == me["conference"]]
                        or rows, unit, basis)
    mine = {t.lower() for t in group["teams"]}

    poll_rank = {}
    if group.get("poll"):
        poll_rank = fetch.poll(group["path"], group["poll"])

    spec, extra = _extra_column(group, pool)

    out_rows = []
    for r in pool:
        row = model._row(r, me, unit, basis, pool[0])
        row["extra"] = extra.get(r["team"])
        row["mine"] = any(m in r["team"].lower() for m in mine)
        # The rank chip: college hockey has no poll, so it is left to the NPI
        # column instead of duplicating the number beside the name.
        row["poll"] = (None if group.get("derived")
                       else (poll_rank.get(str(r.get("id") or "")) or {}).get("rank"))
        out_rows.append(row)

    # Before a college season starts every conference record is 0-0, so the
    # table comes out in whatever order ESPN felt like. Fall back to the poll
    # in that case: ranked teams first, in rank order, then the rest by name.
    if poll_rank and len({(r["wins"], r["losses"]) for r in out_rows}) == 1:
        out_rows.sort(key=lambda r: (r["poll"] or 999, r["team"]))
    for i, row in enumerate(out_rows):
        row["rank"] = i + 1
    tab_odds = None
    if group.get("odds"):
        pct = odds_src.lookup(odds_src.for_league(group["odds"]), group["teams"][0])
        if pct is not None:
            tab_odds = {"team": group["teams"][0], "pct": pct,
                        "label": group.get("odds_label") or "to make the playoffs"}
    return {
        "label": group["label"], "name": me["conference"] or group["label"],
        "unit": unit, "basis": basis, "line": group.get("line"),
        "odds": tab_odds,
        "column": spec,
        "drop_overall": bool(group.get("drop_overall")),
        "derived": bool(group.get("derived")),
        "line_label": group.get("line_label"), "rows": out_rows,
        "extra_teams": others,
    }


def build_all(today=None, include_offseason=False):
    today = today or datetime.date.today()
    # Only the morning build writes history. A local run would otherwise append
    # its own rows for today, which then conflict with the ones the workflow
    # committed hours earlier -- the same day recorded twice, with different
    # numbers, and a merge conflict on the next push.
    record = bool(os.environ.get("GITHUB_ACTIONS"))
    tabs = []
    for tab in leagues.TABS:
        payload = {"key": tab["key"], "label": tab["label"], "mode": tab["mode"],
                   "live": False, "cards": [], "tables": [], "notes": []}
        for group in tab["groups"]:
            live = season.is_live(group["path"], today)
            if live:
                payload["live"] = True
            if not live and not include_offseason:
                if not group.get("optional"):
                    payload["notes"].append("%s: out of season" % group.get(
                        "label", group["key"]))
                continue
            phase = group.get("require_phase")
            if phase and phase not in " ".join(season.current_phase(
                    group["path"], today)):
                continue
            if tab["mode"] == "tracker":
                payload["cards"].extend(
                    tracker(group, today, record=live and record))
            else:
                built = table(group, today)
                if built:
                    payload["tables"].append(built)
                elif not group.get("optional"):
                    payload["notes"].append(
                        "%s: no standings available" % group.get("label"))
        _match_columns(payload["tables"])
        tabs.append(payload)
    return {"built": today.isoformat(), "tabs": tabs, "failures": fetch.FAILURES}


def _match_columns(tables):
    """Give every table on a tab the same column count.

    The Ivy tables carry no metric -- FCS has no FPI odds and the BPI ranks
    only 50 teams -- so they came out one column narrower than the Big Ten
    table above them, and the numbers shifted sideways halfway down the page.
    They now carry the same column, empty.
    """
    spec = next((t["column"] for t in tables if t.get("column")), None)
    if not spec:
        return
    for t in tables:
        if not t.get("column"):
            t["column"] = spec
            for row in t["rows"]:
                row["extra"] = None


if __name__ == "__main__":
    import sys
    data = build_all(include_offseason="--all" in sys.argv)
    for tab in data["tabs"]:
        print("== %-10s live=%-5s cards=%d tables=%d" % (
            tab["label"], tab["live"], len(tab["cards"]), len(tab["tables"])))
        for c in tab["cards"]:
            if c.get("missing"):
                print("    %s -- %s" % (c["team"], c["missing"]))
            else:
                print("    %-22s %-16s seed %s/%s cut %s odds %s (was %s)" % (
                    c["team"], c["record"], c["seed"], c["spots"], c["cut"],
                    c["odds"], c["odds_prev"]))
        for t in tab["tables"]:
            print("    %-34s %d rows, line %s" % (t["label"], len(t["rows"]), t["line"]))
        for n in tab["notes"]:
            print("    note: %s" % n)
