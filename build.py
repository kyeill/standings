"""Assemble every tab's data: trackers for the Big 4, tables for the rest."""

import datetime

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
            raw = (r["stats"].get("playoffPercent") or "").replace("%", "")
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


def tracker(group, today):
    """The Big 4 view: where my team sits against the playoff cut line."""
    unit = group["unit"]
    div_rows = fetch.rows(group["path"], level=3)
    lad_rows = fetch.rows(group["path"], level=2)
    if not lad_rows:
        return []
    odds_table = _odds_for(group, lad_rows)
    if odds_table:
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

        pct = odds_table.get(me["team"])
        prev, delta = history.trend(group["key"], me["team"], pct, today)
        cards.append({
            "team": me["team"], "logo": me["logo"], "missing": None,
            "record": model.short(st.get("overall")) or "%s-%s" % (
                st.get("wins"), st.get("losses")),
            "points": model._int(st.get("points")),
            "streak": st.get("streak"), "last10": model.short(st.get("Last Ten Games")),
            "unit": unit, "seed": seed, "spots": spots, "of": len(pool),
            "spots_label": group["spots_label"], "ladder_name": group["label"],
            "cut": cut, "division": div,
            "clincher": (st.get("clincher") or "").strip().lower(),
            "magic": st.get("magicNumberDivision") or "",
            "odds": pct, "odds_prev": prev, "odds_delta": delta,
            "rows": rows_for(pool, me, unit, group["teams"]),
        })
    # Two tracked teams in one conference (the Pistons and the Cavaliers) share
    # a ladder, so only the first card draws it; the rest are highlighted
    # inside that one table instead of repeating it.
    seen = set()
    for c in cards:
        if c.get("missing"):
            continue
        c["show_table"] = c["ladder_name"] not in seen
        seen.add(c["ladder_name"])
    return cards


def rows_for(pool, me, unit, tracked):
    names = [t.lower() for t in tracked]
    out = []
    for p in pool:
        row = model._row(p, me, unit, "overall", pool[0])
        row["mine"] = any(n in p["team"].lower() for n in names)
        out.append(row)
    return out


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

    out_rows = []
    for r in pool:
        row = model._row(r, me, unit, basis, pool[0])
        row["mine"] = any(m in r["team"].lower() for m in mine)
        # college hockey ranks by NPI, the NCAA's own selection metric;
        # the other college sports rank by poll
        row["poll"] = (r.get("npi") if group.get("derived")
                       else (poll_rank.get(str(r.get("id") or "")) or {}).get("rank"))
        out_rows.append(row)

    # Before a college season starts every conference record is 0-0, so the
    # table comes out in whatever order ESPN felt like. Fall back to the poll
    # in that case: ranked teams first, in rank order, then the rest by name.
    if poll_rank and len({(r["wins"], r["losses"]) for r in out_rows}) == 1:
        out_rows.sort(key=lambda r: (r["poll"] or 999, r["team"]))
    for i, row in enumerate(out_rows):
        row["rank"] = i + 1
    return {
        "label": group["label"], "name": me["conference"] or group["label"],
        "unit": unit, "basis": basis, "line": group.get("line"),
        "derived": bool(group.get("derived")),
        "line_label": group.get("line_label"), "rows": out_rows,
        "extra_teams": others,
    }


def build_all(today=None, include_offseason=False):
    today = today or datetime.date.today()
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
                payload["cards"].extend(tracker(group, today))
            else:
                built = table(group, today)
                if built:
                    payload["tables"].append(built)
                elif not group.get("optional"):
                    payload["notes"].append(
                        "%s: no standings available" % group.get("label"))
        tabs.append(payload)
    return {"built": today.isoformat(), "tabs": tabs, "failures": fetch.FAILURES}


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
