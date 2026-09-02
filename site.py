"""Build the standings PWA into output/site/.

One page, a tab per sport, every tab inlined so switching is instant and the
whole thing works offline once installed. Same shape as sports-daily's site.py
but a separate app -- these two do not share code yet.

    python site.py            in-season sports only (what ships)
    python site.py --all      every sport, including out of season (testing)
"""

import datetime
import html
import json
import os
import struct
import sys
import unicodedata
import zlib

import build
import fetch
import leagues

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "output", "site")

# Row shading colours. Several are deliberately NOT what ESPN returns: it
# gives the Tigers navy, Michigan blue, the Cavaliers a muted antique gold
# (#bc945c) rather than their actual gold, and it has no teal for the Pistons
# at all -- only blue and red.
#
# DELIBERATELY LOCAL, and not read from the shared Colors tab that sports-daily
# and k-money use. Those two draw a 3px STRIPE beside a card; this draws a WASH
# across a whole table row, and the two want different answers -- a navy that
# reads as a crisp edge disappears when it is spread out and lightened. That is
# why these diverged in the first place, and why sharing them made the Tigers
# navy and Tottenham near-white here. His call, 2026-08-30: keep these.
COLORS = {
    "Detroit Lions": "0076b6", "Detroit Tigers": "fa4616",
    "Detroit Pistons": "00a3a5",        # the 1996-2001 teal, his pick
    "Detroit Red Wings": "ce1126",
    "Cleveland Cavaliers": "fdbb30",    # the gold, not ESPN's dull version
    "Michigan Wolverines": "ffcb05",
    "Cornell Big Red": "b31b1b", "Tottenham Hotspur": "132257",
    "Atlanta United FC": "80000a",
}


# Which crest variant reads on a dark page, measured by logos.py. ESPN's
# -dark variant is right for most teams but is a flat white silhouette for
# some (Liverpool and Tottenham are both pure white), so those keep the
# default. Regenerate with `python logos.py --write` when teams change.
# sports-daily is the generator: its `logos.py --write` measures the actual
# pixels of both crest variants and records which teams need the default one.
# Pulled from its repo so the pages cannot drift -- his call 2026-08-30. Unlike
# the row COLOURS, which stay local here because a wash and a stripe want
# different answers, a crest either reads on a dark page or it does not, and
# that judgement is the same everywhere.
LOGO_SOURCE = ("https://raw.githubusercontent.com/kyeill/sports-daily/"
               "main/config.json")


def _load_overrides():
    """sports-daily's list, falling back to the copy committed here.

    That copy is the FALLBACK, not the source: a GitHub blip must not silently
    change every crest on the page, and a list a few days old beats one that
    cannot be read at all.
    """
    shared = {}
    try:
        text = fetch.get_text(LOGO_SOURCE, key="sd-config", max_age_min=720)
        shared = (json.loads(text) or {}).get("logo_overrides") or {}
    except Exception as exc:
        print("  ! sports-daily logo list unreadable (%s)" % exc)
    if shared:
        print("  %d logo override(s) from sports-daily" % len(shared))
        return shared
    path = os.path.join(HERE, "logo-overrides.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


LOGO_OVERRIDES = _load_overrides()

FONT = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=Source+Sans+3:wght@400;600;700&display=swap">')

CSS = """
:root{
  --bg:#16161a; --card:#1e1e23; --ink:#ececea; --muted:#9a9a95;
  --line:#2e2e35; --accent:#e0834f; --chip:#2a2a31;
  --good:#6bbf7b; --bad:#d4676a;
  /* sports-daily's --rank blue; the orange read as an alert it is not */
  --cut:#8fb0d8;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
     font-family:"Source Sans 3",system-ui,-apple-system,"Segoe UI",sans-serif;
     font-size:15px;line-height:1.45;-webkit-text-size-adjust:100%}
.wrap{max-width:720px;margin:0 auto;padding:0 14px 70px}
header{padding:18px 0 10px}
h1{font-size:20px;margin:0}
.updated{color:var(--muted);font-size:14px;margin-top:2px}
nav{position:sticky;top:0;z-index:5;background:var(--bg);
    border-bottom:1px solid var(--line);margin:0 -14px;padding:0 8px;
    display:flex;gap:2px;overflow-x:auto;scrollbar-width:none}
nav::-webkit-scrollbar{display:none}
nav button{flex:0 0 auto;background:none;border:0;color:var(--muted);
    font:inherit;font-size:14px;padding:11px 12px;cursor:pointer;
    border-bottom:2px solid transparent;white-space:nowrap}
nav button[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--accent)}
section{display:none;padding-top:14px}
section.on{display:block}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
      padding:13px 14px;margin:11px 0}
.who{display:flex;align-items:center;gap:9px;font-weight:700;font-size:17px}
.who img{width:22px;height:22px}
/* Fixed layout so the numeric columns land in the SAME place on every tab.
   With auto layout the team column ranged from 436px to 545px and the numbers
   jumped sideways as you swiped between sports. */
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;
      margin-top:11px;table-layout:fixed}
/* Column 1 is the index and column 2 the team, which absorbs the slack: in a
   fixed layout the one column without a width takes what is left. The index is
   centred with padding on both sides so it does not sit against the crest. */
th:first-child,td:first-child{width:38px;text-align:center;padding:4px 4px 4px 6px}
th:nth-child(2),td:nth-child(2){text-align:left;padding-left:10px}
th:nth-child(n+3),td:nth-child(n+3){width:58px}
td:nth-child(2){overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
td:last-child,th:last-child{padding-right:6px}
th{font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;
   color:var(--muted);font-weight:600;text-align:right;padding:0 0 5px}
td{padding:4px 0;border-top:1px solid var(--line);text-align:right;font-size:13.5px}

/* The row is shaded in a lightened version of the team's own colour. The
   old 3px inset bar sat on top of the crest, which is why it looked like it
   was running over the logo. */
tr.mine td{background:var(--tintbg,rgba(255,255,255,.05));font-weight:600}
tr.belowcut td{border-top:1px dashed var(--cut)}
.logo{width:16px;height:16px;vertical-align:middle;margin-right:6px}
.nm{vertical-align:middle}
.rk{color:var(--cut);font-weight:400}
.oddsnote{color:var(--muted);font-weight:400}
.nick{}
.muted{color:var(--muted)}
.note{color:var(--muted);font-size:13px;margin:9px 0;padding:9px 11px;
      border:1px dashed var(--line);border-radius:9px}
footer{margin-top:34px;color:var(--muted);font-size:12px;
       border-top:1px solid var(--line);padding-top:11px}
/* Under 640px the six-column tables left the team name just 47px. The least
   useful column steps aside -- the overall record on college, W-D-L on soccer
   -- and the rest tighten up. */
@media (max-width:640px){
  .hide-sm{display:none}
  th:first-child,td:first-child{width:30px;padding:4px 2px 4px 4px}
  th:nth-child(2),td:nth-child(2){padding-left:8px}
  /* Narrow: the cells hold "0-0", "76%" and "62-70", so the room goes to the
     team name instead -- it is what carries the school nickname. */
  th:nth-child(n+3),td:nth-child(n+3){width:46px}
}
@media (max-width:420px){
  td,th{font-size:12.5px}
  th:nth-child(n+3),td:nth-child(n+3){width:44px}
}
/* Desktop only. Everything above is the phone layout, which is already right,
   so this scales UP from 641px rather than touching the base rules. Sizes
   match the Games page: an 860px column and a 26px heading. */
@media (min-width:641px){
  body{font-size:16px;line-height:1.5}
  .wrap{max-width:860px;padding:0 16px 80px}
  header{padding:24px 0 12px}
  h1{font-size:26px;letter-spacing:-0.01em}
  .updated{font-size:15px;margin-top:3px}
  nav{margin:0 -16px;padding:0 10px}
  nav button{font-size:15px;padding:12px 15px}
  section{padding-top:18px}
  .card{padding:15px 17px;margin:13px 0;border-radius:11px}
  .who{font-size:19px;gap:10px}
  .who img{width:25px;height:25px}
  table{margin-top:13px}
  th{font-size:11.5px}
  td{font-size:15px;padding:6px 0}
  th:first-child,td:first-child{width:48px;padding:6px 5px 6px 8px}
  th:nth-child(2),td:nth-child(2){padding-left:13px}
  th:nth-child(n+3),td:nth-child(n+3){width:82px}
  td:last-child,th:last-child{padding-right:8px}
  .logo{width:19px;height:19px;margin-right:8px}
  .rk{font-size:12.5px}
  .note{font-size:14px;padding:11px 13px}
  footer{font-size:13px}
}
"""

SW = """
const CACHE='standings-v%(v)s';
self.addEventListener('install',e=>{self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c=>c.addAll(['./','./index.html'])))});
self.addEventListener('activate',e=>{e.waitUntil(
  caches.keys().then(k=>Promise.all(k.filter(n=>n!==CACHE).map(n=>caches.delete(n))))
  .then(()=>self.clients.claim()))});
self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET')return;
  // The page itself is always fetched with the HTTP cache bypassed. GitHub
  // Pages serves index.html with max-age=600, so after a rebuild the browser
  // would hand the service worker a stale copy for ten minutes and the app
  // would quietly show yesterday's build.
  const opts = e.request.mode === 'navigate' ? {cache:'no-store'} : undefined;
  e.respondWith(fetch(e.request, opts).then(r=>{
    const copy=r.clone();
    // Cross-origin font and logo responses are opaque and reject on put,
    // so the write must never be allowed to fail the fetch.
    caches.open(CACHE).then(c=>{try{c.put(e.request,copy)}catch(_){}}).catch(()=>{});
    return r;
  }).catch(()=>caches.match(e.request)));
});
"""

JS = """
const tabs=[...document.querySelectorAll('nav button')];
const panes=[...document.querySelectorAll('section')];
function show(key,push){
  tabs.forEach(b=>b.setAttribute('aria-selected',b.dataset.k===key));
  panes.forEach(p=>p.classList.toggle('on',p.dataset.k===key));
  const btn=tabs.find(b=>b.dataset.k===key);
  if(btn&&btn.scrollIntoView)btn.scrollIntoView({inline:'nearest',block:'nearest'});
  try{localStorage.setItem('tab',key)}catch(e){}
  if(push)history.replaceState(null,'','#'+key);
}
tabs.forEach(b=>b.onclick=()=>show(b.dataset.k,true));
const start=location.hash.slice(1)||(()=>{try{return localStorage.getItem('tab')}
  catch(e){return null}})()||(tabs[0]&&tabs[0].dataset.k);
if(start&&tabs.some(b=>b.dataset.k===start))show(start,false);
else if(tabs[0])show(tabs[0].dataset.k,false);
// Swipe between tabs. The gesture must be HORIZONTAL -- comparing dx to dy
// and requiring a clear winner -- or an ordinary vertical scroll down a long
// standings table keeps flicking you into the next sport.
let sx=0, sy=0, tracking=false;
const MIN=50;
addEventListener('touchstart',e=>{
  if(e.touches.length!==1){tracking=false;return}
  sx=e.touches[0].clientX; sy=e.touches[0].clientY; tracking=true;
},{passive:true});
addEventListener('touchend',e=>{
  if(!tracking)return;
  tracking=false;
  const t=e.changedTouches[0];
  const dx=t.clientX-sx, dy=t.clientY-sy;
  if(Math.abs(dx)<MIN||Math.abs(dx)<=Math.abs(dy))return;
  const cur=tabs.findIndex(b=>b.getAttribute('aria-selected')==='true');
  const next=cur+(dx<0?1:-1);
  if(next>=0&&next<tabs.length)show(tabs[next].dataset.k,true);
},{passive:true});

if('serviceWorker' in navigator)
  navigator.serviceWorker.register('./sw.js').catch(()=>{});

// A page that is left open does not refetch. An installed app resumed from the
// home screen shows its last render for as long as the phone keeps it alive,
// and a desktop tab restored from the back/forward cache does the same. Either
// way the build behind it can move on without the reader ever seeing it.
//
// BUILT is the day this page was made. On coming back to it, reload if the day
// has moved on, or if it has simply been sitting a while. Nothing happens while
// it is in use.
const BUILT='%%BUILT%%';
let hidden=Date.now();
function stale(){
  const n=new Date();
  const today=new Date(n.getTime()-n.getTimezoneOffset()*6e4).toISOString().slice(0,10);
  return today!==BUILT||(Date.now()-hidden)>18e5;
}
document.addEventListener('visibilitychange',()=>{
  if(document.visibilityState==='hidden'){hidden=Date.now();return;}
  if(stale())location.reload();
});
// Restored from the back/forward cache: no visibilitychange fires, so this is
// the desktop equivalent of the same problem.
window.addEventListener('pageshow',e=>{if(e.persisted&&stale())location.reload();});
"""


def esc(s):
    return html.escape(str(s if s is not None else ""))


def crest(row, cls="logo"):
    """The crest variant that actually reads on a dark page.

    ESPN's -dark variant suits most teams, but for some it is a flat white
    silhouette; logos.py measures both and records the exceptions. The default
    variant is always the onerror fallback, since a few teams have no -dark
    file at all.
    """
    logo = (row.get("logo") or "").replace("/500-dark/", "/500/")
    if not logo:
        return ""
    src = (LOGO_OVERRIDES.get(row.get("team") or "")
           or logo.replace("/500/", "/500-dark/"))
    return ('<img class="%s" src="%s" onerror="this.onerror=null;this.src=\'%s\'"'
            ' alt="" loading="lazy">' % (cls, esc(src), esc(logo)))


CARD_BG = (0x1e, 0x1e, 0x23)


def tint(team):
    return COLORS.get(team, "e0834f")


def row_shade(team, lighten=0.42, strength=0.34):
    """A readable wash of the team's colour over the card background.

    Done here rather than with CSS color-mix so the result is a plain hex that
    renders the same everywhere. The colour is first lightened towards white --
    Tottenham navy and Cornell red are otherwise too dark to register against
    a #1e1e23 card -- then laid over the card at partial strength so the text
    on top stays readable.
    """
    raw = tint(team)
    r, g, b = (int(raw[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (int(c + (255 - c) * lighten) for c in (r, g, b))
    out = tuple(int(bg + (c - bg) * strength) for bg, c in zip(CARD_BG, (r, g, b)))
    return "%02x%02x%02x" % out



def fmt(value, unit=None):
    """Games behind always carries one decimal, so 7 and 2.5 line up as 7.0 and
    2.5 down the column. Points behind stays whole -- hockey deals in whole
    points and "17.0" would be inventing precision."""
    if unit == leagues.POINTS:
        return "%g" % abs(value)
    return "%.1f" % abs(value)


def behind(value, unit):
    """Distance from whatever the table measures against. Positive is behind;
    negative means ahead, which only happens in a wild-card table measured
    from the cut line, and reads as "+2.5"."""
    if value is None or abs(value) < 0.01:
        return '<span class="muted">-</span>'
    if value < 0:
        return '<span class="good">+%s</span>' % fmt(value, unit)
    return fmt(value, unit)


# --- tracker ----------------------------------------------------------------


def tracker_card(card):
    """A tracker tab reads exactly like a table tab: a heading per table and
    nothing else. The team is not named -- the tab already says which sport,
    and the shaded row says which team. Odds live in a column, so no header is
    needed to carry them."""
    if card.get("missing"):
        return '<div class="note">%s &mdash; %s</div>' % (esc(card["team"]),
                                                          esc(card["missing"]))
    if not card.get("show_table", True):
        return ""
    out = []
    for i, sec in enumerate(card.get("sections") or []):
        out.append('<div class="card"><div class="who">%s</div>%s</div>'
                   % (esc(sec["label"]), section_table(sec, card)))
    return "".join(out)


def section_table(sec, card):
    """One table inside a tracker card: division, wild card, or conference."""
    unit = card["unit"]
    rows, cut = sec["rows"], sec["cut"]
    # Every team, every table -- his call. Longer, but nothing is hidden.
    idx = index_cells(rows)
    body = []
    for i in range(len(rows)):
        r = rows[i]
        # The first row below the line carries the line itself, so there is no
        # caption row taking up a whole row's height to say what is obvious.
        klass = " ".join(x for x in ["mine" if r["mine"] else "",
                                     "belowcut" if cut and i == cut else ""] if x)
        body.append('<tr class="%s" style="--tintbg:#%s">'
                    '<td class="muted">%s</td>'
                    '<td>%s<span class="nm">%s</span></td>'
                    '<td>%s</td><td>%s</td></tr>' % (
                        klass, row_shade(r["team"]), idx[i],
                        crest(r), esc(name_of(r)) + odds_note(r),
                        esc(record_of(r, unit)), behind(r["gb"], unit)))
    points = unit == leagues.POINTS
    # Hockey is behind on POINTS, not games, and the column holds points, not
    # a win-loss record.
    # Even in the wild-card table, where the gap is measured from the cut line
    # rather than the leader, the column is still games (or points) behind.
    gap_head = "PB" if points else "GB"
    rec_head = "Points" if points else "Record"
    return ('<table><tr><th>#</th><th>Team</th><th>%s</th><th>%s</th></tr>'
            '%s</table>' % (rec_head, gap_head, "".join(body)))


# Letters that carry their sound in the glyph rather than in a mark, so NFKD
# leaves them alone and they need naming. Same list as sports-daily.
_LETTERS = {"ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE",
            "đ": "d", "Đ": "D", "ł": "l", "Ł": "L",
            "ß": "ss", "œ": "oe", "Œ": "OE",
            "þ": "th", "Þ": "Th", "ð": "d", "Ð": "D"}


def plain_text(text):
    """Accents stripped: Atletico, Malmo. Mirrors sports-daily."""
    for letter, flat in _LETTERS.items():
        text = text.replace(letter, flat)
    return "".join(c for c in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(c))


# Clubs the suffix rule cannot get right, keyed on ESPN's displayName. Kept
# small on purpose: a rule that needs a long exception list is the wrong rule.
NAME_OVERRIDES = {
    # ESPN files them by sponsor; nobody calls them that.
    "Red Bull New York": "New York Red Bulls",
    # Stripping SC generally would reduce Nashville SC to a bare city, so
    # Orlando is named here instead.
    "Orlando City SC": "Orlando City",
}


def club_name(name):
    """A soccer club as people say it. His rule, 2026-08-26.

    Only **FC** and **AFC** come off; CF and SC stay, so Nashville SC and
    Inter Miami CF keep theirs. A leading "AFC" always goes -- AFC Bournemouth
    is just Bournemouth -- but a trailing "FC" goes only while at least two
    words survive, or Charlotte FC, Austin FC and Toronto FC would collapse to
    bare city names. A leading "FC Dallas" keeps its FC, where the letters are
    part of the name.
    """
    if name in NAME_OVERRIDES:
        return NAME_OVERRIDES[name]
    parts = plain_text(name or "").split()
    if len(parts) > 1 and parts[0] == "AFC":
        parts = parts[1:]
    if len(parts) > 2 and parts[-1] == "FC":
        parts = parts[:-1]
    return " ".join(parts)


def college_parts(row):
    """(school, nickname) -- "Michigan" and " Wolverines".

    The nickname is worth showing where there is room and is the first thing
    to go on a phone, so it is rendered as its own span.
    """
    full = row.get("team") or ""
    school = row.get("location") or ""
    if school and full.startswith(school) and len(full) > len(school):
        return school, full[len(school):]
    return full, ""


def name_of(row, plain=False):
    """The name to print. College keeps its school only here; the nickname is
    added separately so it can be dropped on a narrow screen."""
    if plain and row.get("location"):
        return row["location"]
    return row.get("team") or ""


def index_cells(rows):
    """The leading 1,2,3 column, blanking a row tied with the one above it.

    Tied means the same value in the column the table is ORDERED by, which is
    the gap column: conference games behind for college, games behind for the
    American sports, points behind for hockey and soccer. Comparing overall
    records instead would number three 15-5 Big Ten teams 2, 3 and 4.

    Soccer counts as tied on POINTS even though goal difference decides the
    table order -- his call, and it matches how a league table is read.
    """
    out, last = [], object()
    for i, r in enumerate(rows):
        key = round(r["gb"], 3) if r.get("gb") is not None else None
        out.append("" if (i and key == last) else str(i + 1))
        last = key
    return out


def odds_note(row):
    """My team's playoff odds, in parentheses after its name, on exactly one
    table: the division when it leads one, the wild-card race otherwise."""
    pct = row.get("odds_note")
    if pct is None:
        return ""
    return ' <span class="oddsnote">(%.0f%%)</span>' % pct


def record_of(row, unit):
    """A points sport shows its points and nothing else; the header says so."""
    if unit == leagues.POINTS and row.get("points") is not None:
        return "%s" % row["points"]
    return (row.get("record") or "").split(",")[0]


# --- straight table ---------------------------------------------------------

def table_block(t):
    unit, college = t["unit"], t["basis"] == "conference"
    spec = t.get("column")
    extra_head = "<th>%s</th>" % esc(spec["label"]) if spec else ""
    overall_head = "" if t.get("drop_overall") else '<th class="hide-sm">Overall</th>'
    if college:
        cols = ('<tr><th>#</th><th>Team</th><th>Conf</th>%s<th>GB</th>%s</tr>'
                % (overall_head, extra_head))
    else:
        # On a phone a league table is P and Pts; W-D-L and GD step aside so
        # the longest club name ("New England Revolution") still fits.
        cols = ('<tr><th>#</th><th>Team</th><th>P</th>'
                '<th class="hide-sm">W-D-L</th><th class="hide-sm">GD</th>'
                '<th>Pts</th>%s</tr>' % extra_head)
    idx = index_cells(t["rows"])
    body = []
    for i, r in enumerate(t["rows"]):
        # The rank goes AFTER the name. As a prefix its variable width ("1"
        # versus "14") pushed every team name to a different x position.
        rank = ('<span class="rk"> (#%s)</span>' % r["poll"]) if r.get("poll") else ""
        if college:
            school, nick = college_parts(r)
            label = '<span class="nm">%s</span>%s' % (
                esc(school),
                '<span class="nick">%s</span>' % esc(nick) if nick else "")
        else:
            label = '<span class="nm">%s</span>' % esc(club_name(r["team"]))
        name = "%s%s%s" % (crest(r), label, rank)
        cell = "<td>%s</td>" % extra_value(r.get("extra"), spec) if spec else ""
        if college:
            # college hockey has ties, so print the record string as given
            # rather than rebuilding it from wins and losses alone
            conf = r.get("conf_record") or "%s-%s" % (r["wins"], r["losses"])
            overall = ("" if t.get("drop_overall")
                       else '<td class="muted hide-sm">%s</td>' % esc(r["record"]))
            cells = '<td>%s</td>%s<td>%s</td>%s' % (
                esc(conf), overall, behind(r["gb"], unit), cell)
        else:
            cells = ('<td class="muted">%s</td><td class="muted hide-sm">%s</td>'
                     '<td class="muted hide-sm">%s</td><td>%s</td>' % (
                         r["gp"] if r["gp"] is not None else "-",
                         esc(r["record"]), goal_diff(r), r["points"])) + cell
        klass = " ".join(x for x in ["mine" if r["mine"] else "",
                                     "belowcut" if t["line"] and i == t["line"] else ""]
                         if x)
        body.append('<tr class="%s" style="--tintbg:#%s">'
                    '<td class="muted">%s</td><td>%s</td>%s</tr>' % (
                        klass, row_shade(r["team"]), idx[i], name, cells))
    # Say so when the numbers are computed rather than published.
    note = ""
    return ('<div class="card"><div class="who">%s</div>%s<table>%s%s</table></div>'
            % (esc(t["label"]), note, cols, "".join(body)))


def extra_value(value, spec):
    """A percentage, a seed, or a rank -- blank when the source has no figure
    for that team (the BPI only covers 50 teams, so most of a conference is
    legitimately empty)."""
    if value is None:
        return '<span class="muted">-</span>'
    if spec.get("fmt") == "pct":
        return "%.0f%%" % value
    return "%d" % round(value)



def goal_diff(row):
    value = row.get("diff")
    return esc(value) if value not in (None, "") else "-"




# --- page -------------------------------------------------------------------

def render(data, include_all=False):
    # A sport that is not actively going on is dropped entirely, tab and all --
    # not shown as an empty tab saying so. Test mode keeps everything.
    shown = [t for t in data["tabs"]
             if t["cards"] or t["tables"] or (include_all and t["notes"])]
    nav = "".join('<button data-k="%s">%s</button>' % (esc(t["key"]), esc(t["label"]))
                  for t in shown)
    panes = []
    for t in shown:
        inner = []
        for card in t["cards"]:
            inner.append(tracker_card(card))
        for table in t["tables"]:
            inner.append(table_block(table))
        for note in t["notes"]:
            inner.append('<div class="note">%s</div>' % esc(note))
        if not inner:
            inner.append('<div class="note">Nothing to show.</div>')
        panes.append('<section data-k="%s">%s</section>' % (esc(t["key"]),
                                                            "".join(inner)))
    fail = ""
    if data.get("failures"):
        fail = ('<div class="note">Some data could not be loaded today: %s</div>'
                % esc(", ".join(sorted(set(data["failures"])))))
    return ('<!-- built %s -->'
            '<meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,'
            'viewport-fit=cover">'
            '<meta name="theme-color" content="#16161a">'
            '<link rel="manifest" href="./manifest.webmanifest">'
            # Without an explicit icon a desktop browser asks for /favicon.ico,
            # which this site does not ship, and shows a blank tab after the
            # 404 -- which is exactly what it was doing.
            '<link rel="icon" href="./icon-192.png">'
            '<link rel="apple-touch-icon" href="./icon-180.png">'
            '<title>Standings</title>' + FONT +
            '<style>%s</style>'
            '<div class="wrap"><header><h1>Standings</h1>'
            '<div class="updated">Updated %s</div></header>'
            '<nav>%s</nav>%s%s'
            '<footer>Standings from ESPN. Playoff odds: ESPN FPI for the NFL, '
            'BPI for the NBA, the MLB standings feed, and Hockey-Reference for '
            'the NHL. College and soccer have no odds source.</footer></div>'
            '<script>%s</script>') % (
        esc(data["built"]), CSS, esc(pretty(data["built"])), nav,
        fail, "".join(panes), JS.replace("%%BUILT%%", data["built"]))


def pretty(iso):
    """"September 1" -- no leading zero, which %-d would give but does not
    exist on Windows."""
    day = datetime.date.fromisoformat(iso)
    return "%s %d" % (day.strftime("%B"), day.day)


PNG_SIGNATURE = bytes([137, 80, 78, 71, 13, 10, 26, 10])

ICON_BG = (0x16, 0x16, 0x1a)
# Three standings rows, the top one in the accent colour. Every bar corner sits
# inside the maskable safe zone -- a circle of radius 0.4 about the centre --
# so nothing is clipped when a launcher masks the icon to a circle.
ICON_BARS = [
    (0.203, 0.250, 0.594, 0.086, (0xe0, 0x83, 0x4f)),
    (0.203, 0.453, 0.406, 0.086, (0x9a, 0x9a, 0x95)),
    (0.203, 0.656, 0.500, 0.086, (0x9a, 0x9a, 0x95)),
]


def _png(size):
    """The icon, drawn by pixel maths -- there is no image library here.

    Full bleed on purpose: the manifest marks it `maskable`, so the platform
    crops it to its own shape (a circle on most Android launchers) rather than
    padding a square into a container.
    """
    bars = [(int(x * size), int(y * size), int(w * size), max(2, int(h * size)), c)
            for x, y, w, h, c in ICON_BARS]
    rows = []
    for y in range(size):
        row = bytearray([0])                    # filter byte: none
        for x in range(size):
            colour = ICON_BG
            for bx, by, bw, bh, c in bars:
                if bx <= x < bx + bw and by <= y < by + bh:
                    colour = c
                    break
            row += bytes(colour)
        rows.append(bytes(row))

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    return (PNG_SIGNATURE
            + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
            + chunk(b"IEND", b""))


ICON_SIZES = (180, 192, 512)

MANIFEST = {
    "name": "Standings", "short_name": "Standings", "start_url": "./",
    "display": "standalone", "background_color": "#16161a",
    "theme_color": "#16161a",
    "scope": "./",
    # "maskable" is what makes a launcher crop the icon to its own shape --
    # a circle on Android. Without it the square is padded into a container,
    # which is why this looked unlike Games on the home screen.
    "icons": [{"src": "icon-%d.png" % n, "sizes": "%dx%d" % (n, n),
               "type": "image/png", "purpose": "any maskable"}
              # 180 is only for apple-touch-icon; iOS ignores the
              # manifest and applies its own rounded-square mask.
              for n in (192, 512)],
}


def main():
    include_all = "--all" in sys.argv
    data = build.build_all(include_offseason=include_all)
    os.makedirs(SITE, exist_ok=True)
    page = render(data, include_all)
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(page)
    with open(os.path.join(SITE, "manifest.webmanifest"), "w", encoding="utf-8") as fh:
        json.dump(MANIFEST, fh, indent=1)
    for n in ICON_SIZES:
        with open(os.path.join(SITE, "icon-%d.png" % n), "wb") as fh:
            fh.write(_png(n))
    # Include the build time, not just the date: two builds on one day would
    # otherwise share a cache name and the old entries would survive.
    stamp = data["built"].replace("-", "") + datetime.datetime.now().strftime("%H%M%S")
    with open(os.path.join(SITE, "sw.js"), "w", encoding="utf-8") as fh:
        fh.write(SW % {"v": stamp})
    live = [t["label"] for t in data["tabs"] if t["live"]]
    print("wrote %s (%.1f KB)" % (os.path.join(SITE, "index.html"), len(page) / 1024))
    print("in season: %s" % (", ".join(live) or "nothing"))
    if fetch.FAILURES:
        print("failures: %s" % ", ".join(sorted(set(fetch.FAILURES))))


if __name__ == "__main__":
    main()
