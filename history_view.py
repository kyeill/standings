"""The History view: the rankings from rankings.py, as HTML.

A first, deliberately plain layout -- his words, 2026-09-21: "Switch, though
I am not 100% sure what layout I want yet." Each tab gets a Standings /
History switch; a tab whose sport is out of season shows History alone, so
every tab is on all year.

Tables mirror the sheet's front tabs: the same sections, the same columns, the
same season words. On a phone only the Value and the three latest seasons
stay -- a phone fits about four columns beside the name.
"""

import html
import sys

import rankings

# key -> the rankings function for that tab. Order is irrelevant here; the
# tab row takes its order from leagues.TABS, with these two appended.
SOURCES = {
    "cfb": rankings.cfb, "cbb": rankings.cbb, "hky": rankings.hky,
    "epl": rankings.epl, "mls": rankings.mls,
    "nfl": lambda: rankings.pro("NFL"), "mlb": lambda: rankings.pro("MLB"),
    "nba": lambda: rankings.pro("NBA"), "nhl": lambda: rankings.pro("NHL"),
    "ncaa": rankings.ncaa, "concacaf": rankings.concacaf,
}

# History-only tabs, after the nine sports -- "push them to the end for now".
EXTRA_TABS = [("ncaa", "NCAA"), ("concacaf", "CONCACAF")]

# The sheet marks his teams by writing them in CAPITALS. Those rows are shaded
# in the same colours the standings use; the key is the sheet's name, the
# value the COLORS key in site.py, per sport where one name means several.
MINE = {
    "MICHIGAN": "Michigan Wolverines", "CORNELL": "Cornell Big Red",
    "TOTTENHAM HOTSPUR": "Tottenham Hotspur", "ATLANTA": "Atlanta United FC",
    "CLEVELAND": "Cleveland Cavaliers",
    "UNITED STATES": "",                # no colour of its own: the accent
}
DETROIT = {"nfl": "Detroit Lions", "mlb": "Detroit Tigers",
           "nba": "Detroit Pistons", "nhl": "Detroit Red Wings"}


def esc(s):
    return html.escape(str(s if s is not None else ""))


def build():
    """{tab key: payload or {"error": text}} -- one failure never sinks the
    others, or the build."""
    out = {}
    for key, fn in SOURCES.items():
        try:
            data = fn()
            data.pop("_internals", None)
            out[key] = data
        except Exception as e:           # noqa: BLE001 -- reported, not hidden
            print("history: %s failed: %r" % (key, e), file=sys.stderr)
            out[key] = {"error": "History could not be built (%s)." % e}
    return out


def display_name(name):
    """The sheet's capitals are a marker, not a spelling -- but only on the
    names that ARE markers. UCLA and VCU are simply capitals."""
    text = str(name)
    return text.title() if text in MINE or text == "DETROIT" else text


def shade_key(tab_key, name):
    """The COLORS key for one of his teams, "" for his team with no colour of
    its own, None for everyone else."""
    text = str(name)
    if text == "DETROIT":
        return DETROIT.get(tab_key)
    return MINE.get(text)


def season_head(label):
    """'2025-26' -> '25-26', which fits a phone column; single years stay."""
    text = str(label or "")
    if len(text) == 7 and text[4] == "-":
        return text[2:]
    return text


def cell(value, column):
    if value is None or value == "":
        return ""
    if isinstance(value, float):
        # A Value always carries one decimal so 100.0 and 98.3 line up; ranks
        # and counts are whole.
        if column == "Value":
            return "%.1f" % value
        return "%d" % value if value.is_integer() else "%.1f" % value
    return str(value)


def _visible(columns, seasons):
    """Per column: shown on a phone? The index and team always; Value always;
    the three most recent seasons. A tab without seasons (NCAA, Concacaf)
    keeps its first three numbers instead."""
    season_idx = [i for i, c in enumerate(columns) if c in seasons]
    keep = {0, 1}
    if season_idx:
        keep |= set(season_idx[:3])
        keep |= {i for i, c in enumerate(columns) if c == "Value"}
    else:
        keep |= {2, 3, 4}
    return [i in keep for i in range(len(columns))]


def section_html(tab_key, sec, seasons, shade):
    cols = sec["columns"]
    # The sheet's blank spacer columns carry nothing.
    use = [i for i, c in enumerate(cols) if c != ""]
    vis = _visible(cols, set(seasons) | {c for c in cols if _looks_season(c)})
    is_season = [_looks_season(c) for c in cols]
    head = "".join('<th class="%s">%s</th>' % (
        " ".join(x for x in ("" if vis[i] else "hide-sm",
                             "s" if is_season[i] else "") if x),
        esc(season_head(cols[i]) if is_season[i] else HEADS.get(cols[i], cols[i])))
        for i in use)
    body = []
    for row in sec["rows"]:
        name = row[1]
        key = shade_key(tab_key, name)
        style = ' style="--tintbg:#%s"' % shade(key) if key is not None else ""
        klass = "mine" if key is not None else ""
        cells = []
        for i in use:
            value = row[i] if i < len(row) else None
            if i == 1:
                cells.append('<td><span class="nm">%s</span></td>'
                             % esc(display_name(value)))
                continue
            cls = [] if vis[i] else ["hide-sm"]
            if is_season[i]:
                cls.append("s")
            if i == 0 or (isinstance(value, float) and cols[i] != "Value"):
                cls.append("muted")
            if isinstance(value, str) and value in WORDS_STRONG:
                cls.append("win")
            cells.append('<td class="%s">%s</td>' % (" ".join(cls), esc(cell(value, cols[i]))))
        body.append('<tr class="%s"%s>%s</tr>' % (klass, style, "".join(cells)))
    return ('<div class="card hist"><div class="who">%s</div>'
            '<table><tr>%s</tr>%s</table></div>'
            % (esc(sec["title"]), head, "".join(body)))


# Column headings too wide for a number column, shortened on the page only.
HEADS = {"Division": "Div"}

# A season word worth picking out: a title of any kind.
WORDS_STRONG = {"CHAMPS", "TREBLE"}


def _looks_season(label):
    text = str(label or "")
    return (len(text) in (4, 7) and text[:4].isdigit()) or (
        len(text) > 5 and text[:4].isdigit() and text[4] == " ")


def footers_html(data):
    """Champions and runners-up, one small table per calendar -- a new header
    row whenever the seasons change (Concacaf's Gold Cups, World Cups and
    Nations Leagues each run on their own)."""
    lines = data.get("footers") or []
    if not lines:
        return ""
    rows, last = [], None
    for label, values, seasons in lines:
        if seasons != last:
            rows.append('<tr><th></th>%s</tr>' % "".join(
                '<th class="%s">%s</th>' % ("" if i < 3 else "hide-sm",
                                            esc(season_head(x)))
                for i, x in enumerate(seasons)))
            last = seasons
        rows.append('<tr><td class="lbl">%s</td>%s</tr>' % (
            esc(label), "".join('<td class="%s">%s</td>' % (
                "" if i < 3 else "hide-sm", esc(cell(v, "")))
                for i, v in enumerate(values))))
    return ('<div class="card hist foot"><div class="who">Champions</div>'
            '<table>%s</table></div>' % "".join(rows))


def tab_html(tab_key, data, shade):
    if not data:
        return ""
    if data.get("error"):
        return '<div class="note">%s</div>' % esc(data["error"])
    seasons = data.get("seasons") or []
    parts = [section_html(tab_key, s, seasons, shade) for s in data["sections"]]
    parts.append(footers_html(data))
    return "".join(parts)
