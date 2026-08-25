"""Standalone ESPN standings fetcher for the Sports Standings mockups.

Deliberately does NOT import anything from ../sports-daily -- this folder is
kept separate until we decide whether to bundle them. It repeats a little of
that project's endpoint knowledge on purpose.

Verified shapes 2026-08-25. See NOTES.md for what each league does and does not
carry.
"""

import json
import os
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
STANDINGS = "https://site.api.espn.com/apis/v2/sports/%s/standings"
POWERINDEX = "https://site.web.api.espn.com/apis/fitt/v3/sports/%s/powerindex"
RANKINGS = "https://site.api.espn.com/apis/site/v2/sports/%s/rankings"
# ESPN 403s browser-style User-Agents but serves the requests default fine.
UA = {"Accept": "application/json"}

FAILURES = []


def get(url, params=None, key=None, max_age_min=180):
    os.makedirs(CACHE, exist_ok=True)
    path = None
    if key:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
        path = os.path.join(CACHE, safe + ".json")
        if os.path.exists(path):
            if (time.time() - os.path.getmtime(path)) / 60 < max_age_min:
                try:
                    with open(path, encoding="utf-8") as fh:
                        return json.load(fh)
                except (OSError, ValueError):
                    pass
    try:
        resp = requests.get(url, params=params, headers=UA, timeout=25)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print("  ! %s (%s)" % (url, exc))
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        FAILURES.append(key or url)
        return None
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    return data


def get_text(url, key=None, max_age_min=180):
    """Same disk cache as get(), but for a page that is not JSON."""
    os.makedirs(CACHE, exist_ok=True)
    path = None
    if key:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
        path = os.path.join(CACHE, safe + ".html")
        if os.path.exists(path):
            if (time.time() - os.path.getmtime(path)) / 60 < max_age_min:
                with open(path, encoding="utf-8") as fh:
                    return fh.read()
    try:
        resp = requests.get(url, headers=UA, timeout=25)
        resp.raise_for_status()
        text = resp.text
    except Exception as exc:
        print("  ! %s (%s)" % (url, exc))
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                return fh.read()
        FAILURES.append(key or url)
        return None
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    return text


def _stats(entry):
    """name -> displayValue.

    College payloads repeat every stat name once per split (overall, Home,
    Away, vs. Conf., ...). The FIRST occurrence is the overall split, so a
    plain dict comprehension would keep the LAST -- iterate and skip repeats.
    """
    out = {}
    for s in entry.get("stats") or []:
        name = s.get("name")
        if name and name not in out:
            out[name] = s.get("displayValue")
    return out


def rows(league_path, level=2, group=None, max_age_min=180):
    """Flat [(conference, division, team, abbr, logo, stats)] for a league."""
    params = {"level": level}
    if group:
        params["group"] = group
    key = "standings-%s-l%s%s" % (league_path.replace("/", "-"), level,
                                  "-g%s" % group if group else "")
    data = get(STANDINGS % league_path, params, key, max_age_min)
    if not data:
        return []
    out = []

    def walk(node, conference=None, division=None):
        for entry in (node.get("standings") or {}).get("entries") or []:
            team = entry.get("team") or {}
            out.append({
                "conference": conference or "",
                "division": division or node.get("name") or "",
                "team": team.get("displayName") or "",
                # School without the mascot: "Michigan", not "Michigan
                # Wolverines". Config matching still uses the full name.
                "location": team.get("location") or "",
                "abbr": team.get("abbreviation") or "",
                "id": team.get("id") or "",
                "logo": (team.get("logos") or [{}])[0].get("href") or "",
                "stats": _stats(entry),
            })
        for child in node.get("children") or []:
            if conference is None:
                walk(child, child.get("name"), None)
            else:
                walk(child, conference, child.get("name"))

    walk(data)
    return out


def power_index(league_path, key):
    """{team displayName: {field: value}} across EVERY category, or {}.

    The category holding the projections is named differently per sport: the
    NFL and NBA call it "projections", college football calls it "fpi", and
    college basketball splits its numbers across "bpi", "resume" and
    "tournament". Reading only "projections" silently returned nothing for
    both college sports, which is why they looked like they had no odds.
    """
    data = get(POWERINDEX % league_path, key="odds-%s" % key, max_age_min=60 * 12)
    if not data:
        return {}
    names_by_cat = {c.get("name"): c.get("names") or []
                    for c in data.get("categories") or []}
    if not names_by_cat:
        return {}
    out = {}
    for entry in data.get("teams") or []:
        team = entry.get("team") or {}
        merged = {}
        for cat in entry.get("categories") or []:
            names = names_by_cat.get(cat.get("name")) or []
            for name, value in zip(names, cat.get("values") or []):
                if value is not None:
                    merged.setdefault(name, value)
        if merged:
            out[team.get("displayName") or ""] = merged
    return out


def poll(league_path, kind="ap"):
    """{team displayName-ish: rank} from a rankings poll, or {}."""
    data = get(RANKINGS % league_path, key="rankings-%s" % league_path.replace("/", "-"),
               max_age_min=60 * 6)
    if not data:
        return {}
    for r in data.get("rankings") or []:
        if r.get("type") == kind:
            # Keyed by ESPN team id, never by name. The AP poll lists
            # "michigan" and does not list Michigan State at all, so any
            # substring match hands Michigan State the Wolverines' ranking.
            out = {}
            for e in r.get("ranks") or []:
                team = e.get("team") or {}
                key = str(team.get("id") or "")
                if not key:
                    continue
                out[key] = {
                    "rank": e.get("current"),
                    "record": e.get("recordSummary") or "",
                    "trend": e.get("trend") or "-",
                    "name": team.get("nickname") or team.get("name") or "",
                }
            return out
    return {}
