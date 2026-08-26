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
import sys

import build
import fetch
import leagues

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "output", "site")

# Row shading colours. Several are deliberately NOT what ESPN returns: it
# gives the Tigers navy, Michigan blue, the Cavaliers a muted antique gold
# (#bc945c) rather than their actual gold, and it has no teal for the Pistons
# at all -- only blue and red.
COLORS = {
    "Detroit Lions": "0076b6", "Detroit Tigers": "fa4616",
    "Detroit Pistons": "00a3a5",        # the 1996-2001 teal, his pick
    "Detroit Red Wings": "ce1126",
    "Cleveland Cavaliers": "fdbb30",    # the gold, not ESPN's dull version
    "Michigan Wolverines": "ffcb05",
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
h1 span{color:var(--muted);font-weight:400;font-size:14px;margin-left:8px}
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
.sub{color:var(--muted);font-size:13.5px;margin-top:3px}
.verdict{display:flex;align-items:baseline;gap:9px;margin:11px 0 2px;
         flex-wrap:wrap}
.big{font-size:27px;font-weight:700;line-height:1}
.big.in{color:var(--good)} .big.out{color:var(--bad)}
.delta{font-size:13px;color:var(--muted)}
.delta.up{color:var(--good)} .delta.down{color:var(--bad)}
.gapline{color:var(--muted);font-size:13.5px}
/* Fixed layout so the numeric columns land in the SAME place on every tab.
   With auto layout the team column ranged from 436px to 545px and the numbers
   jumped sideways as you swiped between sports. */
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;
      margin-top:11px;table-layout:fixed}
th:not(:first-child),td:not(:first-child){width:58px}
td:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
th{font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;
   color:var(--muted);font-weight:600;text-align:right;padding:0 0 5px}
th:first-child{text-align:left}
td{padding:4px 0;border-top:1px solid var(--line);text-align:right;font-size:13.5px}
td:first-child{text-align:left}
/* The row is shaded in a lightened version of the team's own colour. The
   old 3px inset bar sat on top of the crest, which is why it looked like it
   was running over the logo. */
tr.mine td{background:var(--tintbg,rgba(255,255,255,.05));font-weight:600}
tr.belowcut td{border-top:2px dashed var(--cut)}
tr.skip td{color:var(--muted);font-size:12px;padding:2px 0}
.logo{width:16px;height:16px;vertical-align:middle;margin-right:6px}
.nm{vertical-align:middle}
.rk{color:var(--cut);font-size:11.5px;margin-right:4px;vertical-align:middle}
.oddsnote{color:var(--muted);font-weight:400}
.muted{color:var(--muted)}
.note{color:var(--muted);font-size:13px;margin:9px 0;padding:9px 11px;
      border:1px dashed var(--line);border-radius:9px}
footer{margin-top:34px;color:var(--muted);font-size:12px;
       border-top:1px solid var(--line);padding-top:11px}
@media (max-width:420px){
  td,th{font-size:12.5px}
  .big{font-size:24px}
}
/* Desktop only. Everything above is the phone layout, which is already right,
   so this scales UP from 641px rather than touching the base rules. Sizes
   match the Games page: an 860px column and a 26px heading. */
@media (min-width:641px){
  body{font-size:16px;line-height:1.5}
  .wrap{max-width:860px;padding:0 16px 80px}
  header{padding:24px 0 12px}
  h1{font-size:26px;letter-spacing:-0.01em}
  h1 span{font-size:14px}
  nav{margin:0 -16px;padding:0 10px}
  nav button{font-size:15px;padding:12px 15px}
  section{padding-top:18px}
  .card{padding:15px 17px;margin:13px 0;border-radius:11px}
  .who{font-size:19px;gap:10px}
  .who img{width:25px;height:25px}
  .sub{font-size:14px}
  .big{font-size:32px}
  .gapline{font-size:14.5px}
  .delta{font-size:14px}
  table{margin-top:13px}
  th{font-size:11.5px}
  td{font-size:15px;padding:6px 0}
  th:not(:first-child),td:not(:first-child){width:82px}
  .logo{width:19px;height:19px;margin-right:8px}
  .rk{font-size:12.5px}
  tr.skip td{font-size:13px}
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
"""


def esc(s):
    return html.escape(str(s if s is not None else ""))


def crest(logo, cls="logo"):
    if not logo:
        return ""
    dark = logo.replace("/500/", "/500-dark/")
    return ('<img class="%s" src="%s" onerror="this.onerror=null;this.src=\'%s\'"'
            ' alt="" loading="lazy">' % (cls, esc(dark), esc(logo)))


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


def unit_word(unit):
    return " pts" if unit == leagues.POINTS else ""


def fmt(value, unit):
    return "%g%s" % (abs(value), unit_word(unit))


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

def window_rows(n, spots, mine_at):
    keep = {0, 1, 2, spots - 2, spots - 1, spots, spots + 1}
    keep |= {mine_at - 1, mine_at, mine_at + 1}
    return sorted(i for i in keep if 0 <= i < n)


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
    body = []
    for i in range(len(rows)):
        r = rows[i]
        # The first row below the line carries the line itself, so there is no
        # caption row taking up a whole row's height to say what is obvious.
        klass = " ".join(x for x in ["mine" if r["mine"] else "",
                                     "belowcut" if cut and i == cut else ""] if x)
        cell = ("<td>%s</td>" % extra_value(r.get("extra"), sec["column"])
                if sec.get("column") else "")
        body.append('<tr class="%s" style="--tintbg:#%s">'
                    '<td>%s<span class="nm">%s</span></td>%s'
                    '<td class="muted">%s</td><td>%s</td><td>%s</td></tr>' % (
                        klass, row_shade(r["team"]),
                        crest(r["logo"]), esc(name_of(r)) + odds_note(r),
                        cell, i + 1,
                        esc(record_of(r, unit)), behind(r["gb"], unit)))
    # Only the conference ladder is a real seeding; the numbers beside a
    # division or a wild-card field are just positions within that field.
    head = "Seed" if sec["kind"] == "conference" else "Pos"
    gap_head = "vs line" if sec.get("from_cut") else "GB"
    extra_head = "<th>%s</th>" % esc(sec["column"]["label"]) if sec.get("column") else ""
    return ('<table><tr><th>Team</th>%s<th>%s</th><th>Record</th><th>%s</th></tr>'
            '%s</table>' % (extra_head, head, gap_head, "".join(body)))


def name_of(row, plain=False):
    """College reads better without the mascot -- "Michigan", not "Michigan
    Wolverines" -- and ESPN's `location` is exactly that."""
    if plain and row.get("location"):
        return row["location"]
    return row.get("team") or ""


def odds_note(row):
    """My team's playoff odds, in parentheses after its name, on exactly one
    table: the division when it leads one, the wild-card race otherwise."""
    pct = row.get("odds_note")
    if pct is None:
        return ""
    delta = row.get("odds_note_delta")
    move = ""
    if delta is not None and abs(delta) >= 0.5:
        move = ' <span class="delta %s">%s%.0f</span>' % (
            "up" if delta > 0 else "down", "+" if delta > 0 else "-", abs(delta))
    return ' <span class="oddsnote">(%.0f%%%s)</span>' % (pct, move)


def record_of(row, unit):
    rec = row.get("record") or ""
    rec = rec.split(",")[0]
    if unit == leagues.POINTS and row.get("points") is not None:
        return "%s pts" % row["points"]
    return rec


# --- straight table ---------------------------------------------------------

def table_block(t):
    unit, college = t["unit"], t["basis"] == "conference"
    spec = t.get("column")
    extra_head = "<th>%s</th>" % esc(spec["label"]) if spec else ""
    if college:
        cols = ("<tr><th>Team</th>%s<th>Conf</th><th>Overall</th><th>GB</th></tr>"
                % extra_head)
    else:
        cols = ("<tr><th>Team</th>%s<th>P</th><th>W-D-L</th><th>GD</th>"
                "<th>Pts</th></tr>" % extra_head)
    body = []
    for i, r in enumerate(t["rows"]):
        rank = ('<span class="rk">%s</span>' % r["poll"]) if r.get("poll") else ""
        name = '%s%s<span class="nm">%s</span>' % (crest(r["logo"]), rank,
                                                   esc(name_of(r, plain=college)))
        cell = "<td>%s</td>" % extra_value(r.get("extra"), spec) if spec else ""
        if college:
            # college hockey has ties, so print the record string as given
            # rather than rebuilding it from wins and losses alone
            conf = r.get("conf_record") or "%s-%s" % (r["wins"], r["losses"])
            cells = '%s<td>%s</td><td class="muted">%s</td><td>%s</td>' % (
                cell, esc(conf), esc(r["record"]), behind(r["gb"], unit))
        else:
            cells = (cell + '<td class="muted">%s</td><td class="muted">%s</td>'
                     '<td class="muted">%s</td><td>%s</td>' % (
                         r["gp"] if r["gp"] is not None else "-",
                         esc(r["record"]), goal_diff(r), r["points"]))
        klass = " ".join(x for x in ["mine" if r["mine"] else "",
                                     "belowcut" if t["line"] and i == t["line"] else ""]
                         if x)
        body.append('<tr class="%s" style="--tintbg:#%s"><td>%s</td>%s</tr>' % (
            klass, row_shade(r["team"]), name, cells))
    # Say so when the numbers are computed rather than published.
    note = ('<div class="sub">computed from game results &mdash; ESPN publishes '
            "no college hockey standings. Rank shown is the NCAA&rsquo;s NPI, "
            'which decides tournament selection.</div>') if t.get("derived") else ""
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


def short_team(name):
    """Config names carry the mascot; a sentence reads better without it."""
    for tail in (" Wolverines", " Big Red", " Hotspur", " United"):
        if name.endswith(tail):
            return name[: -len(tail)]
    return name


def goal_diff(row):
    value = row.get("diff")
    return esc(value) if value not in (None, "") else "-"


def short_name(name):
    if "Premier League" in name:
        return "Premier League"
    return (name.replace(" Division", "").replace(" Conference", "")
            .replace("American League ", "AL ").replace("National League ", "NL "))


def ordinal(n):
    if n is None:
        return "-"
    suffix = "th" if 10 <= (n % 100) <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return "%d%s" % (n, suffix)


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
            '<title>Standings</title>' + FONT +
            '<style>%s</style>'
            '<div class="wrap"><header><h1>Standings<span>%s</span></h1></header>'
            '<nav>%s</nav>%s%s'
            '<footer>Standings from ESPN. Playoff odds: ESPN FPI for the NFL, '
            'BPI for the NBA, the MLB standings feed, and Hockey-Reference for '
            'the NHL. College and soccer have no odds source.</footer></div>'
            '<script>%s</script>') % (
        esc(data["built"]), CSS, esc(pretty(data["built"])), nav,
        fail, "".join(panes), JS)


def pretty(iso):
    return datetime.date.fromisoformat(iso).strftime("%d %b %Y")


MANIFEST = {
    "name": "Standings", "short_name": "Standings", "start_url": "./",
    "display": "standalone", "background_color": "#16161a",
    "theme_color": "#16161a",
    "icons": [{"src": "./icon.svg", "sizes": "any", "type": "image/svg+xml"}],
}

ICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="13" fill="#16161a"/>'
        '<rect x="13" y="16" width="38" height="5" rx="2.5" fill="#e0834f"/>'
        '<rect x="13" y="29" width="26" height="5" rx="2.5" fill="#9a9a95"/>'
        '<rect x="13" y="42" width="32" height="5" rx="2.5" fill="#9a9a95"/>'
        '</svg>')


def main():
    include_all = "--all" in sys.argv
    data = build.build_all(include_offseason=include_all)
    os.makedirs(SITE, exist_ok=True)
    page = render(data, include_all)
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(page)
    with open(os.path.join(SITE, "manifest.webmanifest"), "w", encoding="utf-8") as fh:
        json.dump(MANIFEST, fh, indent=1)
    with open(os.path.join(SITE, "icon.svg"), "w", encoding="utf-8") as fh:
        fh.write(ICON)
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
