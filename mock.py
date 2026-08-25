"""Render three candidate designs for the standings page onto one review page.

Same idea as sports-daily's styles.py / showcase.py: put the options side by
side with REAL data so the awkward sports show their awkwardness, and pick by
eye rather than from a description.

    python mock.py   ->  output/mockups.html
"""

import datetime
import html
import os

import fetch
import model

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")

# Only the tracked teams need a colour. ESPN's own values are wrong for
# several of them (it returns navy for the Tigers and blue for Michigan), so
# these repeat sports-daily's team_colors overrides rather than trusting it.
COLORS = {
    "Detroit Lions": "0076b6", "Detroit Tigers": "fa4616",
    "Detroit Pistons": "c8102e", "Detroit Red Wings": "ce1126",
    "Cleveland Cavaliers": "860038", "Michigan Wolverines": "ffcb05",
    "Cornell Big Red": "b31b1b", "Tottenham Hotspur": "132257",
    "Atlanta United FC": "80000a",
}

FONT = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=Source+Sans+3:wght@400;600;700&display=swap">')

CSS = """
:root{
  --bg:#16161a; --card:#1e1e23; --ink:#ececea; --muted:#9a9a95;
  --line:#2e2e35; --accent:#e0834f; --chip:#2a2a31; --rank:#8fb0d8;
  --good:#6bbf7b; --bad:#d4676a; --cut:#c8863f;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
     font-family:"Source Sans 3",system-ui,-apple-system,"Segoe UI",sans-serif;
     font-size:15px;line-height:1.45}
.wrap{max-width:860px;margin:0 auto;padding:28px 18px 80px}
h1{font-size:23px;margin:0 0 4px}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);
   margin:44px 0 6px;padding-bottom:6px;border-bottom:1px solid var(--line)}
h3{font-size:15px;margin:22px 0 8px;font-weight:600}
p.lede{color:var(--muted);margin:0 0 6px}
p.note{color:var(--muted);font-size:13.5px;margin:6px 0 16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
      padding:12px 14px;margin:10px 0}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);
   font-weight:600;text-align:right;padding:0 0 5px}
th:first-child{text-align:left}
td{padding:4px 0;border-top:1px solid var(--line);text-align:right;font-size:14px}
td:first-child{text-align:left}
tr.mine td{background:rgba(255,255,255,.045);font-weight:600}
tr.mine td:first-child{box-shadow:inset 3px 0 0 var(--tint,var(--accent))}
tr.mine td:first-child span.nm{padding-left:7px}
tr.gapline td{border-top:1px dashed var(--cut);color:var(--cut);font-size:11px;
              text-transform:uppercase;letter-spacing:.07em;padding-top:3px}
tr.skip td{color:var(--muted);font-size:12px;padding:2px 0}
.logo{width:17px;height:17px;vertical-align:middle;margin-right:7px}
.nm{vertical-align:middle}
.muted{color:var(--muted)}
.good{color:var(--good)} .bad{color:var(--bad)}
.head{display:flex;align-items:baseline;justify-content:space-between;gap:10px;
      margin-bottom:8px;flex-wrap:wrap}
.head .who{font-weight:700;font-size:16px}
.head .ctx{color:var(--muted);font-size:13px}
.pill{display:inline-block;background:var(--chip);border-radius:99px;
      padding:1px 9px;font-size:12px;color:var(--muted);margin-left:6px}
.pill.on{background:#243026;color:var(--good)}
.pill.off{background:#2e2326;color:var(--bad)}
.strip{display:grid;grid-template-columns:1fr auto;gap:2px 14px;
       padding:9px 0;border-top:1px solid var(--line)}
.strip:first-of-type{border-top:0}
.strip .t{font-weight:600}
.strip .sub{color:var(--muted);font-size:13px}
.strip .od{text-align:right;font-weight:700;font-size:17px}
.strip .odsub{text-align:right;color:var(--muted);font-size:11.5px;
              text-transform:uppercase;letter-spacing:.06em}
.bar{height:4px;background:var(--chip);border-radius:3px;overflow:hidden;
     margin-top:5px;grid-column:1 / -1}
.bar i{display:block;height:100%;background:var(--accent)}
.matrix td{font-size:13.5px}
.matrix td:first-child{font-weight:600}
.yes{color:var(--good)} .no{color:var(--bad)} .part{color:var(--cut)}
footer{margin-top:60px;color:var(--muted);font-size:12.5px;
       border-top:1px solid var(--line);padding-top:12px}
@media (max-width:640px){
  .wrap{padding:20px 12px 60px}
  td,th{font-size:13px}
  .logo{width:15px;height:15px;margin-right:5px}
}
"""


def esc(s):
    return html.escape(str(s if s is not None else ""))


def dark_logo(url):
    """ESPN's default crests are near-invisible on a dark page; the /500-dark/
    variant is not. Every league returns 200 for it, but an onerror swap keeps
    a team that lacks one from showing a broken image."""
    return (url or "").replace("/500/", "/500-dark/")


def crest(row):
    d, plain = dark_logo(row.get("logo")), row.get("logo") or ""
    if not plain:
        return ""
    return ('<img class="logo" src="%s" onerror="this.onerror=null;this.src=\'%s\'" alt="">'
            % (esc(d), esc(plain)))


def signed(value, unit, zero="even"):
    """'2.5 back' / '1.0 up' / 'even', or points for the points sports."""
    if value is None:
        return '<span class="muted">-</span>'
    word = "pts" if unit == model.POINTS else ""
    if abs(value) < 0.01:
        return '<span class="muted">%s</span>' % zero
    n = ("%g" % abs(value)) + (" " + word if word else "")
    if value > 0:
        return '<span class="bad">%s back</span>' % n
    return '<span class="good">+%s</span>' % n


def tint(team):
    return COLORS.get(team, "e0834f")


# --- Approach A: the full division table ------------------------------------

def approach_a(card):
    d = card.get("division")
    if not d:
        return ""
    unit = card["unit"]
    head = ('<div class="head"><span class="who">%s</span>'
            '<span class="ctx">%s &middot; %s of %s%s</span></div>') % (
        esc(d["name"]), esc(card["record"]), d["rank"], d["of"],
        (" &middot; %.0f%% %s" % (card["odds"]["pct"], esc(card["odds"]["label"])))
        if card.get("odds") else "")
    college = card.get("basis") == "conference"
    first = "Conf" if college else "Record"
    second = "Overall" if college else "L10"
    cols = ("<tr><th>Team</th><th>%s</th><th>GB</th><th>Streak</th><th>%s</th></tr>"
            % (first, second))
    body = []
    for r in d["rows"]:
        left = ("%s-%s" % (r["wins"], r["losses"])) if college else short_record(r, unit)
        right = r["record"] if college else clean_l10(r["last10"])
        body.append(
            '<tr class="%s" style="--tint:#%s"><td>%s<span class="nm">%s</span></td>'
            '<td>%s</td><td>%s</td><td class="muted">%s</td><td class="muted">%s</td></tr>' % (
                "mine" if r["mine"] else "", tint(r["team"]), crest(r), esc(r["team"]),
                esc(left), behind(r["gb"], unit),
                esc(r["streak"] or "-"), esc(right)))
    return '<div class="card">%s<table>%s%s</table></div>' % (head, cols, "".join(body))


def behind(value, unit):
    """The conventional standings column: how far behind the group leader.
    Always zero or positive, and the leader shows a dash."""
    if value is None:
        return '<span class="muted">-</span>'
    if abs(value) < 0.01:
        return '<span class="muted">-</span>'
    return "%g%s" % (abs(value), " pts" if unit == model.POINTS else "")


def short_record(row, unit):
    rec = row.get("record") or ""
    if "," in rec:                       # hockey: "41-31-10, 92 PTS"
        rec = rec.split(",")[0]
    if unit == model.POINTS and row.get("points") is not None:
        return "%s  %s pts" % (rec, row["points"])
    return rec


def clean_l10(value):
    """Hockey's last-ten reads '7-2-1, 0 PTS'; the points half is always 0."""
    if not value:
        return "-"
    return value.split(",")[0]


# --- Approach B: the cut line ------------------------------------------------

def window(rows, spots, mine_at):
    """Indices worth showing: the top of the table, the two teams either side
    of the cut line, and my team's neighbourhood. Everything else collapses."""
    keep = {0, 1, 2}
    keep |= {spots - 2, spots - 1, spots, spots + 1}
    if mine_at is not None:
        keep |= {mine_at - 1, mine_at, mine_at + 1}
    return sorted(i for i in keep if 0 <= i < len(rows))


def approach_b(card):
    l = card.get("ladder")
    if not l or not l["seed"]:
        return ""
    unit, spots = card["unit"], l["spots"]
    rows = l["rows"]
    mine_at = l["seed"] - 1
    idx = window(rows, spots, mine_at)
    verdict = ("in" if (l["gap"] or 0) <= 0 else "out")
    head = ('<div class="head"><span class="who">%s</span>'
            '<span class="ctx">%s of %s &middot; top %s make the %s'
            '<span class="pill %s">%s</span></span></div>') % (
        esc(l["name"]), l["seed"], l["of"], spots, esc(l["spots_label"] or "playoffs"),
        "on" if verdict == "in" else "off",
        ("%s clear" % fmt_gap(abs(l["gap"] or 0), unit)) if verdict == "in"
        else ("%s back" % fmt_gap(abs(l["gap"] or 0), unit)))
    out, last = [], None
    for i in idx:
        if last is not None and i > last + 1:
            out.append('<tr class="skip"><td colspan="4">%d more</td></tr>'
                       % (i - last - 1))
        if i == spots:
            out.append('<tr class="gapline"><td colspan="4">%s cut line</td></tr>'
                       % esc(l["spots_label"] or "playoff"))
        r = rows[i]
        out.append(
            '<tr class="%s" style="--tint:#%s"><td>%s<span class="nm">%s</span></td>'
            '<td class="muted">%s</td><td>%s</td><td>%s</td></tr>' % (
                "mine" if r["mine"] else "", tint(r["team"]), crest(r), esc(r["team"]),
                i + 1, esc(short_record(r, unit)), signed(r["vs_me"], unit, zero="-")))
        last = i
    cols = "<tr><th>Team</th><th>Seed</th><th>Record</th><th>vs me</th></tr>"
    return '<div class="card">%s<table>%s%s</table></div>' % (head, cols, "".join(out))


def fmt_gap(value, unit):
    return ("%g pts" % value) if unit == model.POINTS else ("%g" % value)


# --- Approach C: the one-line race strip -------------------------------------

def approach_c(cards):
    out = []
    for c in cards:
        if c.get("missing"):
            out.append('<div class="strip"><div><div class="t">%s '
                       '<span class="muted">%s</span></div>'
                       '<div class="sub">%s</div></div>'
                       '<div class="od muted">-</div></div>' % (
                           esc(c["team"]), esc(c["league"]), esc(c["missing"])))
            continue
        unit = c["unit"]
        bits = []
        d, l = c.get("division"), c.get("ladder")
        if d:
            bits.append("%s in the %s" % (ordinal(d["rank"]), esc(short_div(d["name"]))))
            if d["gap"] is not None and abs(d["gap"]) > 0.01:
                bits[-1] += (" (%s back)" % fmt_gap(abs(d["gap"]), unit)
                             if d["gap"] > 0 else " (+%s)" % fmt_gap(abs(d["gap"]), unit))
        if l and l["seed"] and l["gap"] is not None:
            inside = l["gap"] <= 0
            # soccer has places, not seeds
            word = "" if unit == model.POINTS else " seed"
            if abs(l["gap"]) < 0.01:
                bits.append("%s%s, level with the %s line" % (
                    ordinal(l["seed"]), word, esc(l["spots_label"] or "playoff")))
            else:
                bits.append("%s%s, %s %s the %s line" % (
                    ordinal(l["seed"]), word, fmt_gap(abs(l["gap"]), unit),
                    "clear of" if inside else "off",
                    esc(l["spots_label"] or "playoff")))
        odds = c.get("odds")
        bar = ('<div class="bar"><i style="width:%.0f%%"></i></div>' % odds["pct"]) \
            if odds else ""
        out.append(
            '<div class="strip"><div><div class="t">%s%s <span class="muted">%s</span></div>'
            '<div class="sub">%s &middot; %s</div></div>'
            '<div><div class="od">%s</div><div class="odsub">%s</div></div>%s</div>' % (
                crest({"logo": c["logo"]}), esc(c["team"]), esc(c["league"]),
                esc(short_record({"record": c["record"], "points": c["points"]}, unit)),
                " &middot; ".join(bits) if bits else "no table for this sport",
                ("%.0f%%" % odds["pct"]) if odds else '<span class="muted">-</span>',
                esc("playoffs") if odds else "no odds", bar))
    return '<div class="card">%s</div>' % "".join(out)


def short_div(name):
    # ESPN names a soccer table by its season ("2026-27 English Premier
    # League"), which reads badly in a sentence.
    if "Premier League" in name:
        return "Premier League"
    for prefix in ("American League ", "National League "):
        if name.startswith(prefix):
            return name.replace(prefix, "AL " if "American" in prefix else "NL ")
    return name.replace(" Division", "").replace(" Conference", "")


def ordinal(n):
    if n is None:
        return "-"
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return "%d%s" % (n, suffix)


# --- what each sport can actually support ------------------------------------

MATRIX = [
    ("MLB", "yes|division of 5", "yes|6 seeds, wild card", "yes|ESPN, plus magic numbers",
     "The richest sport by far: ESPN ships playoffPercent, wildCardPercent and both magic numbers in the standings payload itself."),
    ("NFL", "yes|division of 4", "yes|7 seeds", "yes|ESPN FPI",
     "FPI also carries win-division and win-title odds if we ever want them."),
    ("NBA", "yes|division of 5", "yes|10 seeds inc. play-in", "yes|ESPN BPI",
     "BPI adds a separate play-in chance and top-6 seed probability."),
    ("NHL", "yes|division of 8", "yes|8 seeds, points", "no|nothing usable",
     "Points not games back. No odds source: MoneyPuck asks not to be scraped and ESPN has only championship futures."),
    ("College football", "part|conference table", "no|no cut line", "part|FPI, in season only",
     "The race is the CFP poll, not a table. FPI projections are EMPTY in the preseason and only appear once games are played."),
    ("College basketball", "part|conference table", "no|no cut line", "no|none",
     "At-large bids mean the race is bracketology, which has no free feed. Conference table is available and sorted worst-first."),
    ("College hockey", "no|ESPN returns nothing", "no|-", "no|none",
     "Every conference comes back with zero entries. PairWise, the ranking that actually decides the tournament, has no free API."),
    ("Premier League", "yes|one table of 20", "part|line is a choice", "no|none",
     "No playoffs, so the cut line has to be picked: top 4/5 for the Champions League, top 6/7 for Europe, or the relegation line."),
    ("MLS", "yes|conference of 15", "yes|top 9 make it", "no|none",
     "The only soccer league with a real playoff line. Points, not games back."),
]


def matrix_table():
    rows = []
    for sport, div, ladder, odds, note in MATRIX:
        cells = []
        for value in (div, ladder, odds):
            state, _, label = value.partition("|")
            cls = {"yes": "yes", "no": "no", "part": "part"}[state]
            mark = {"yes": "yes", "no": "no", "part": "partial"}[state]
            cells.append('<td><span class="%s">%s</span> <span class="muted">%s</span></td>'
                         % (cls, mark, esc(label)))
        rows.append('<tr><td>%s</td>%s</tr>'
                    '<tr><td colspan="4" class="muted" style="border-top:0;'
                    'padding-top:0;padding-bottom:9px;font-size:12.5px">%s</td></tr>'
                    % (esc(sport), "".join(cells), esc(note)))
    return ('<div class="card"><table class="matrix">'
            '<tr><th>Sport</th><th style="text-align:left">Division table</th>'
            '<th style="text-align:left">Playoff cut line</th>'
            '<th style="text-align:left">Odds</th></tr>%s</table></div>'
            % "".join(rows))


def build():
    cards = model.all_cards()
    live = [c for c in cards if not c.get("missing")]
    parts = []

    parts.append("<h1>Standings &mdash; three ways</h1>")
    parts.append('<p class="lede">Same real data from ESPN, three different '
                 'answers to "how is my team doing". Built %s.</p>'
                 % datetime.date.today().strftime("%d %B %Y"))
    parts.append('<p class="note">Nothing here is wired to sports-daily. The '
                 'seasons are where they really are today, which is the point: '
                 'the NFL is two games in, MLB is down the stretch, the NBA and '
                 'NHL are showing a finished season, and college football has '
                 'not kicked off. Whatever we build has to look sane in all '
                 'four of those states.</p>')

    parts.append("<h2>Approach A &mdash; the division table</h2>")
    parts.append('<p class="note">Closest to the tool you built before. Shows '
                 'everyone, so you can see the whole neighbourhood, but it is '
                 'the same five rows every day and most of them never matter. '
                 'Nine of these stacked is a long page.</p>')
    for c in live:
        if c["key"] in ("mlb", "nhl", "cbb"):
            parts.append(approach_a(c))

    parts.append("<h2>Approach B &mdash; the cut line</h2>")
    parts.append('<p class="note">Drops everyone who is not adjacent to a '
                 'decision. You see the top of the conference, the two teams '
                 'either side of the playoff line, and your own neighbours. '
                 'The dashed line is the thing you are actually watching.</p>')
    for c in live:
        if c["key"] in ("mlb", "nhl", "nba", "mls"):
            parts.append(approach_b(c))

    parts.append("<h2>Approach C &mdash; the race strip</h2>")
    parts.append('<p class="note">No tables at all. One line per team, every '
                 'sport on one screen, answering only "am I in, by how much, '
                 'and what are the odds". This is the whole page, not an '
                 'excerpt.</p>')
    parts.append(approach_c(cards))

    parts.append("<h2>What each sport can actually support</h2>")
    parts.append('<p class="note">Measured against the live API today, not '
                 'assumed. This is the constraint that shapes the design.</p>')
    parts.append(matrix_table())

    parts.append('<footer>Standings from ESPN. Playoff odds from ESPN FPI/BPI '
                 'for the NFL and NBA and from the MLB standings payload. '
                 'Sports with no odds column have no free source.</footer>')

    page = ('<meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Standings mockups</title>' + FONT +
            "\n<style>%s</style>\n<div class=\"wrap\">%s</div>"
            % (CSS, "".join(parts)))
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "mockups.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)
    print("wrote %s (%.1f KB)" % (path, len(page) / 1024))
    if fetch.FAILURES:
        print("failed fetches:", ", ".join(fetch.FAILURES))


if __name__ == "__main__":
    build()
