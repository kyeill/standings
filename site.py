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
  --line:#2e2e35; --accent:#e0834f; --chip:#2a2a31;
  --good:#6bbf7b; --bad:#d4676a; --cut:#c8863f;
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
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;
      margin-top:11px}
th{font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;
   color:var(--muted);font-weight:600;text-align:right;padding:0 0 5px}
th:first-child{text-align:left}
td{padding:4px 0;border-top:1px solid var(--line);text-align:right;font-size:13.5px}
td:first-child{text-align:left}
tr.mine td{background:rgba(255,255,255,.05);font-weight:600}
tr.mine td:first-child{box-shadow:inset 3px 0 0 var(--tint,var(--accent))}
tr.mine td:first-child .nm{padding-left:7px}
tr.cut td{border-top:1px dashed var(--cut);color:var(--cut);font-size:10.5px;
          text-transform:uppercase;letter-spacing:.07em;padding:3px 0 2px}
tr.skip td{color:var(--muted);font-size:12px;padding:2px 0}
.logo{width:16px;height:16px;vertical-align:middle;margin-right:6px}
.nm{vertical-align:middle}
.rk{color:#8fb0d8;font-size:11.5px;margin-right:4px;vertical-align:middle}
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
  .logo{width:19px;height:19px;margin-right:8px}
  .rk{font-size:12.5px}
  tr.cut td{font-size:11.5px}
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
  e.respondWith(fetch(e.request).then(r=>{
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


def tint(team):
    return COLORS.get(team, "e0834f")


def unit_word(unit):
    return " pts" if unit == leagues.POINTS else ""


def fmt(value, unit):
    return "%g%s" % (abs(value), unit_word(unit))


def behind(value, unit):
    if value is None or abs(value) < 0.01:
        return '<span class="muted">-</span>'
    return fmt(value, unit)


# --- tracker ----------------------------------------------------------------

def window_rows(n, spots, mine_at):
    keep = {0, 1, 2, spots - 2, spots - 1, spots, spots + 1}
    keep |= {mine_at - 1, mine_at, mine_at + 1}
    return sorted(i for i in keep if 0 <= i < n)


def tracker_card(card):
    if card.get("missing"):
        return '<div class="note">%s -- %s</div>' % (esc(card["team"]),
                                                     esc(card["missing"]))
    unit, spots = card["unit"], card["spots"]
    inside = card["cut"] is not None and card["cut"] <= 0
    clinched = card["clincher"] in ("z", "y", "x", "*")
    eliminated = card["clincher"] == "e"

    if eliminated:
        verdict, cls = "Eliminated", "out"
    elif clinched:
        verdict, cls = "Clinched", "in"
    elif card["cut"] is None:
        verdict, cls = "-", ""
    elif inside:
        verdict, cls = "%s clear" % fmt(card["cut"], unit), "in"
    else:
        verdict, cls = "%s back" % fmt(card["cut"], unit), "out"

    odds_bit = ""
    if card["odds"] is not None:
        delta = card["odds_delta"]
        if delta is None:
            move = '<span class="delta">no reading a week ago yet</span>'
        elif abs(delta) < 0.05:
            move = '<span class="delta">level with a week ago</span>'
        else:
            move = ('<span class="delta %s">%s%.0f pts vs a week ago</span>'
                    % ("up" if delta > 0 else "down",
                       "+" if delta > 0 else "-", abs(delta)))
        odds_bit = ('<div class="verdict"><span class="big">%.0f%%</span>'
                    '<span class="gapline">to make the playoffs</span>%s</div>'
                    % (card["odds"], move))

    div = card.get("division")
    sub = []
    if div:
        sub.append("%s in the %s" % (ordinal(div["rank"]), esc(short_name(div["name"]))))
        if div["gap"] is not None and abs(div["gap"]) > 0.01:
            sub.append(("%s back" % fmt(div["gap"], unit)) if div["gap"] > 0
                       else ("%s ahead" % fmt(div["gap"], unit)))
    if card["streak"]:
        sub.append("%s, %s in last 10" % (esc(card["streak"]), esc(card["last10"] or "-")))

    head = ('<div class="who">%s%s</div>'
            '<div class="sub">%s &middot; %s seed of %s &middot; %s</div>' % (
                crest(card["logo"], "logo"), esc(card["team"]),
                esc(card["record"]), ordinal(card["seed"]), card["of"],
                " &middot; ".join(sub) if sub else ""))
    verdict_row = ('<div class="verdict"><span class="big %s">%s</span>'
                   '<span class="gapline">of the %s line</span></div>' % (
                       cls, esc(verdict), esc(card["spots_label"])))

    rows = card["rows"]
    idx = window_rows(len(rows), spots, (card["seed"] or 1) - 1)
    body, last = [], None
    for i in idx:
        if last is not None and i > last + 1:
            body.append('<tr class="skip"><td colspan="4">%d more</td></tr>'
                        % (i - last - 1))
        if i == spots:
            body.append('<tr class="cut"><td colspan="4">%s cut line</td></tr>'
                        % esc(card["spots_label"]))
        r = rows[i]
        body.append('<tr class="%s" style="--tint:#%s"><td>%s<span class="nm">%s</span>'
                    '</td><td class="muted">%s</td><td>%s</td><td>%s</td></tr>' % (
                        "mine" if r["mine"] else "", tint(r["team"]),
                        crest(r["logo"]), esc(r["team"]), i + 1,
                        esc(record_of(r, unit)),
                        behind(r["gb"], unit)))
        last = i
    table = ""
    if card.get("show_table", True):
        table = ('<table><tr><th>%s</th><th>Seed</th><th>Record</th><th>GB</th></tr>'
                 '%s</table>' % (esc(card["ladder_name"]), "".join(body)))
    return '<div class="card">%s%s%s%s</div>' % (head, verdict_row, odds_bit, table)


def record_of(row, unit):
    rec = row.get("record") or ""
    rec = rec.split(",")[0]
    if unit == leagues.POINTS and row.get("points") is not None:
        return "%s pts" % row["points"]
    return rec


# --- straight table ---------------------------------------------------------

def table_block(t):
    unit, college = t["unit"], t["basis"] == "conference"
    if college:
        cols = "<tr><th>Team</th><th>Conf</th><th>Overall</th><th>GB</th></tr>"
    else:
        cols = "<tr><th>Team</th><th>P</th><th>W-D-L</th><th>GD</th><th>Pts</th></tr>"
    body = []
    for i, r in enumerate(t["rows"]):
        if t["line"] and i == t["line"]:
            span = 4 if college else 5
            body.append('<tr class="cut"><td colspan="%d">%s line</td></tr>'
                        % (span, esc(t["line_label"] or "cut")))
        rank = ('<span class="rk">%s</span>' % r["poll"]) if r.get("poll") else ""
        name = '%s%s<span class="nm">%s</span>' % (crest(r["logo"]), rank,
                                                   esc(r["team"]))
        if college:
            # college hockey has ties, so print the record string as given
            # rather than rebuilding it from wins and losses alone
            conf = r.get("conf_record") or "%s-%s" % (r["wins"], r["losses"])
            cells = '<td>%s</td><td class="muted">%s</td><td>%s</td>' % (
                esc(conf), esc(r["record"]), behind(r["gb"], unit))
        else:
            cells = ('<td class="muted">%s</td><td class="muted">%s</td>'
                     '<td class="muted">%s</td><td>%s</td>' % (
                         r["gp"] if r["gp"] is not None else "-",
                         esc(r["record"]), goal_diff(r), r["points"]))
        body.append('<tr class="%s" style="--tint:#%s"><td>%s</td>%s</tr>' % (
            "mine" if r["mine"] else "", tint(r["team"]), name, cells))
    # Say so when the numbers are computed rather than published.
    note = ('<div class="sub">computed from game results &mdash; ESPN publishes '
            "no college hockey standings. Rank shown is the NCAA&rsquo;s NPI, "
            'which decides tournament selection.</div>') if t.get("derived") else ""
    return ('<div class="card"><div class="who">%s</div>%s<table>%s%s</table></div>'
            % (esc(t["label"]), note, cols, "".join(body)))


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
    with open(os.path.join(SITE, "sw.js"), "w", encoding="utf-8") as fh:
        fh.write(SW % {"v": data["built"].replace("-", "")})
    live = [t["label"] for t in data["tabs"] if t["live"]]
    print("wrote %s (%.1f KB)" % (os.path.join(SITE, "index.html"), len(page) / 1024))
    print("in season: %s" % (", ".join(live) or "nothing"))
    if fetch.FAILURES:
        print("failures: %s" % ", ".join(sorted(set(fetch.FAILURES))))


if __name__ == "__main__":
    main()
