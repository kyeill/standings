# Standings

A playoff-race app: where my teams sit, how far from the line, and which way
the odds are moving. Separate from `sports-daily` on purpose -- it imports
nothing from it and touches none of its files. See `NOTES.md` for the trap
list and what each sport's data can actually support.

```
python site.py           build into output/site/  (in-season sports only)
python site.py --all     same, but keep every sport, for testing
python build.py          print what each tab resolved to, no HTML
python mock.py           the three original design mockups
python logos.py --write  re-measure which crest variant reads (rarely)
python selftest.py       check the back end (168 assertions)
python rankings_proof.py prove the History rankings against the old sheet
python import_sheet.py   ONE-TIME import from the rankings sheet (needs openpyxl)
```

Python is not on PATH:
`C:\Users\kyleh\AppData\Local\Programs\Python\Python312-arm64\python.exe`

No pandas or numpy. Standard library plus `requests`, same as sports-daily.

## The two display modes

Set per tab in `leagues.py`.

**tracker** -- the Big 4 American sports. The NFL and MLB show their division
and then the Wild Card Race among the teams NOT leading one; the NBA and NHL
show a single conference ladder. My team's playoff odds sit in parentheses
after its name on exactly one of those tables: the division when it leads that
division, the wild-card race otherwise. A blue dashed line marks the playoff
cut; there is no caption, because the line says it.

**table** -- college and soccer. A straight standings table, because those
sports have no cut line worth computing: college races are decided by a poll
or a selection committee, and a soccer league table IS the competition. Soccer
tables still draw a line where one is meaningful (EPL at 4 for the Champions
League, MLS at 9 for the playoffs). The college tabs carry a per-team metric
column: CFP odds, projected NCAA seed, and NPI respectively.

Every table shows every team -- nothing is collapsed -- and tables use a fixed
layout so the numeric columns land in the same place on every tab. Tables on
the SAME tab are forced to the same column count too: the Ivy tables carry no
metric of their own, and without this they came out a column wider than the
Big Ten table above them, shifting every number sideways halfway down the
page.

## Columns

Every table leads with an index. A row **tied with the one above is left
blank**, where tied means the same value in the column the table is ordered by
-- conference games behind for college, games behind for the American sports,
points behind for hockey and soccer. Comparing overall records instead would
number three 15-5 Big Ten teams 2, 3 and 4. Soccer counts as tied on POINTS
even though goal difference decides the order.

    NFL MLB   # | Team | Record | GB      GB on both tables, though the wild
                                        card one measures from the cut line
    NBA       # | Team | Record | GB
    NHL       # | Team | Points | PB     points, no "pts" suffix
    CFB CBB   # | Team | Conf | Overall | GB | <metric>
    HKY       # | Team | Conf | GB | NPI  no overall record, at any size
    EPL MLS   # | Team | P | W-D-L | GD | Pts

The metric column -- CFP odds, projected NCAA seed (header "Seed"), or NPI --
sits at the very end.

**College football and basketball break ties on conference record his way**
(2026-09-21): the poll rank (football reads the CFP committee's ranking once
it is published, the AP poll before; basketball the AP), then the metric
column (CFP odds, higher first; projected seed, lower first), then the
non-conference record. Before a season starts every record is 0-0, so this is
also the preseason order. `tiebreak` in `leagues.py`, `_college_key` in
`build.py`. College hockey is untouched.

There is no page footer -- removed at his request, 2026-09-21. (The History
view's "Champions" card is a separate thing and is still there.)

Games behind always carries one decimal, so 7 and 2.5 line up as 7.0 and 2.5
down the column. Points behind stays whole: hockey deals in whole points and
"17.0" would be inventing precision.

**Under 640px columns step aside**: Overall on college, W-D-L and GD on
soccer (a phone league table is P and Pts),
and the index and numeric columns tighten. Six columns had left the team name
47px on a 375px phone, truncating most of it; it is now 143px. Desktop keeps
every column. College hockey is the exception that needs no breakpoint: it
drops Overall at every size (`drop_overall`), because NPI already says how good
the team is nationally.

As a rule of thumb a phone fits about four columns besides the team name.

## Row colours

Each tracked team shades its own row: its colour lightened towards white, then
laid over the card at partial strength so the text on top stays readable. The
lightening matters -- Tottenham navy and Cornell red are otherwise too dark to
register against a #1e1e23 card.

Several colours are deliberately NOT what ESPN returns. It gives the Tigers
navy, Michigan blue, the Cavaliers a muted antique gold rather than their real
one, and has no teal for the Pistons at all.

**These are local on purpose, and are NOT read from the shared `Colors` tab**
that sports-daily and k-money use. It was wired up to that tab and then pulled
back out, because the two uses want different answers: those pages draw a **3px
stripe** beside a card, this draws a **wash across a whole table row**. A navy
that reads as a crisp edge disappears once it is spread out and lightened, and
sharing the list turned the Tigers navy and Tottenham near-white here.

That is why the two lists diverged in the first place. Do not fix it by
pointing this at the shared tab -- it has been tried.

## Crests

ESPN publishes two variants per team and the `-dark` one is usually right on a
dark page -- but for some clubs it is a flat white silhouette, so Liverpool and
Tottenham become indistinguishable at 19px. `logos.py` measures the actual
pixels of both and picks per team, exactly as sports-daily does: the dark
variant when it carries colour, otherwise the default if it is light enough,
otherwise the dark one anyway.

**The exception list now comes from sports-daily**, pulled from its repo at
build time: its `logos.py` is the generator, and a crest either reads on a dark
page or it does not -- that judgement is the same on both sites, unlike the row
COLOURS, which stay local here because a wash and a stripe want different
answers. Its list is 77 teams against the 15 measured here, and the two agreed
on 14 of those 15; Coventry City is the only one that changes.

`logo-overrides.json` here is the committed FALLBACK,
which the build just reads -- re-run `python logos.py --write` when the tracked
teams change. The default variant is always the `onerror` fallback, since a few
teams have no dark file at all.

## Team names

Soccer clubs keep their whole name except **FC** and **AFC** -- his call. CF
and SC stay, so Nashville SC and Inter Miami CF keep theirs.

* a leading "AFC" always goes: AFC Bournemouth is just Bournemouth
* a trailing "FC" goes only while two words survive, or Charlotte FC, Austin FC
  and Toronto FC would collapse to bare city names
* a leading "FC Dallas" keeps its FC, where the letters are part of the name
* accents are stripped, as in sports-daily

Two clubs the rule cannot get right are named explicitly in `NAME_OVERRIDES`:
Orlando City (dropping an SC that Nashville must keep) and New York Red Bulls
(ESPN files them by sponsor as "Red Bull New York"). The list is kept short on
purpose -- a rule needing a long exception list is the wrong rule.

Every MLS club then reads as two words or more, except LAFC, which is ESPN's
actual one-word name rather than anything this rule removed.

College is the other way round -- the school alone is too bare, so the tables
read "Michigan Wolverines" at **every** size. The room comes from the numeric
columns instead, which hold "0-0", "76%" and "62-70" and shrink to 46px on a
phone. At 393px that leaves 174px for the name and one or two of the 71
college names truncate; hiding the nickname to save two names was the worse
trade.

A poll rank renders as a **suffix**, "Oregon (#2)". As a prefix its variable
width ("1" against "14") started every team name at a different x position, so
the names did not line up down the column.

## Tabs

Nine, in this order -- his, given 2026-08-25. College splits by SPORT rather
than by school, so Michigan and Cornell sit together on each college tab.

| Tab | Mode | Contents | Metric column |
|---|---|---|---|
| CFB | table | Big Ten (Michigan) + Ivy League (Cornell) | CFP odds |
| CBB | table | Big Ten (Michigan) + Ivy League (Cornell) | projected NCAA seed |
| HKY | table | Big Ten (Michigan) + ECAC (Cornell), derived | NPI |
| EPL | table | Premier League + whichever European competition is in its league phase | -- |
| NFL | tracker | Lions: NFC North, then the Wild Card Race | -- |
| MLB | tracker | Tigers: AL Central, then the Wild Card Race | -- |
| NBA | tracker | Pistons + Cavaliers: Eastern Conference | -- |
| NHL | tracker | Red Wings: Eastern Conference | -- |
| MLS | table | Atlanta United, Eastern Conference | -- |
| NCAA | history only | schools across every sport | -- |
| CONCACAF | history only | national teams: World Cup, Gold Cup, Nations League | -- |

The last two were added 2026-09-21 "at the end for now". His sheet also has
`II` and `UEFA` tabs -- lists of teams by how far they went each season, with
no ranking -- which he wants to come back to; they are imported but unused.

HKY is COLLEGE hockey; the NHL has its own tab. Two tracked teams in one
conference (the Pistons and the Cavaliers) share a single ladder rather than
printing it twice -- and because only the first card is drawn, the second
team's odds are moved onto the table that IS drawn, or they would vanish.

## History

Every tab has a **Standings / History** switch, remembered per tab. History
is Kyle's own ranking of the last ten seasons -- a 0-100 Value per team and a
line of what each of the last five seasons came to ("CHAMPS", "B1GCG",
"1st Div", "2+^", or a finish). It used to live in his Google Sheet
(`1Eb3XIu2fzVR_Dk_xRpbvrGw_5GFq-iLhBOMEUpOnikg`, link-shared); since
2026-09-21 the app computes it, and he will retire the sheet once the app
stands on its own.

**Every tab is now on all year.** A sport out of season shows History alone
instead of disappearing. Two history-only tabs follow the nine sports:
**NCAA** (every sport per school, the Big Ten and the national top 125) and
**CONCACAF** (national teams). The layout is a first, plain pass -- he has
not decided what he wants yet.

| File | What it is |
|---|---|
| `rankings/inputs/*.csv` | what he TYPED into the sheet, one CSV per tab; formula cells blank |
| `rankings/expected/*.csv` | what the sheet DISPLAYED on import -- the answer key |
| `rankings.py` | the sheet's formulas rebuilt: one function per front tab |
| `rankings_proof.py` | which sheet rows each table landed on; checks every cell |
| `history_view.py` | the History HTML |
| `import_sheet.py` | the one-time import; do not rerun once the app fills seasons itself |

**The engine in one paragraph.** Nearly every input tab is one of three
shapes: PLACE (finishes scored from the tab's own Place->Pts table, best four
of five seasons), POINTS (values already in points, best four of five), or
RATING (a rank, lower is better: five seasons minus the worst, a missing one
counted as the field size). Each blends 75% the last five seasons with 25%
the five before, minus a row-number tie-break, onto a 0-100 log scale. The
`_val` tabs then combine those per sport -- e.g. NFL 25% division, 75%
playoffs; MLS 20% table, 60% Cup, 10% each Champions Cup and Leagues Cup. Some
tabs add a flat bonus per cup (FA Cup 3, League Cup 2, Big Ten Tournament
10...).

**Proven, then corrected.** `SHEET_COMPAT = True` reproduces the sheet
exactly, faults included, and `selftest.py` checks every displayed cell of
all eleven front tabs (0 mismatches). The app runs with it OFF, which
corrects these -- his call on the first three, the rest the same kind:

| Fault in the sheet | Effect | Corrected |
|---|---|---|
| MLB_val `B*B` and NHL_val `25*B` for the division part | division swamped the playoffs | `0.25*B`, like the NFL and NBA |
| EPL_val's UEFA share read `#REF!` | the 25% European share was zero | EPL_val column F, the UEFA value |
| 2024 and 2023 SP+ ranks pasted as TEXT | SUM/MAX skipped them: two seasons counted for nothing | read as numbers -- **this moves Ohio State above Michigan** in the CFB Big Ten |
| St. John's listed twice in CBB_val | every team below ranked a place low | second copy ignored |
| CBB_seed header typed "2045-25" | that season's seeds missing from CBB_rk | read as 2024-25 |
| EPL_UCL's second Europa semi-finalist valued from the WINNER's cell | 5 points instead of 0.5 | its own 0.5 |
| HKY ECAC word tested for "F4", which is never written | a Frozen Four run showed as the ECAC finish | tests "Frozen" |

**Three words came from named functions** -- EPL_RESULT, MLS_RESULT and
CONCACAF_RESULT / _COMPETITION -- which the xlsx export does not carry.
They were reverse-engineered from every cell they displayed and match all of
them; see `epl_result`, `mls_result`, `concacaf_result`.

**New seasons fill themselves -- for the tabs with a filler.** `fill.py`
(run by the workflow before every build) writes each season that has
FINISHED since the import into `rankings/seasons/<tab>.csv`, and
`rankings.Tab` lays those in front of the sheet's own columns. The sheet
import itself never changes, so the proof keeps proving the sheet. Every
filler was first made to re-derive the last season he typed, and matches it
exactly (`python fill.py --check`, `python fill_tournaments.py --check`).

| Tab | Filler | Checked against | Filled so far |
|---|---|---|---|
| NFL / MLB / NBA / NHL `_div` + `_playoffs` | `fill.py` | 2025 / 2025-26: 0 differences | -- (next: MLB 2026, November) |
| NCAAB_B1G (Big Ten baseball) | `fill.py` | 2025: 0 | 2026 |
| NCAAB_CWS (College World Series) | `fill_tournaments.py` | 2025: 0 | 2026 |
| Concacaf_WC | `fill_tournaments.py` | 2022: 0 | 2026 |
| Concacaf_GC | `fill_tournaments.py` | 2023: 0 | 2025 |
| MLS_CCC, MLS_LC | `fill_tournaments.py` | 2025: 0 | 2026 |

**No filler yet** -- a new season there still means typing it into the sheet
and re-importing, or editing `rankings/seasons/` by hand: CFB (Big Ten, poll,
CFP, SP+), CBB (Big Ten, Ivy, seeds, Sweet 16, KenPom), HKY (Big Ten, ECAC,
seeds, Frozen Four, PairWise), EPL (table, cups, UCL), MLS (table, Cup, Open
Cup), Concacaf Nations League. None of them has a finished season missing
today; the first due is MLS 2026 (December) and CFB 2026 (January). SP+ and
KenPom will come from his games-history sheet, where he already enters them.

## Only what is actually on

The STANDINGS view of a sport that is not being played is dropped -- the tab
stays, showing History (above).
`season.py` decides by asking the scoreboard whether real games fall within ten
days -- one day at a time, walking outward from today, because ESPN no longer
accepts a date range (see NOTES). That is the only reliable test: an out-of-season league does not return
an empty table, it returns either last season's final standings (the NBA and
NHL today) or an all-zero table for a season that has not started (college
football today). **Preseason counts as off** -- without that the NFL shows
1-1 records from August exhibitions.

`--all` keeps everything, for working on a sport out of season.

## Playoff odds

| Sport | Source | Notes |
|---|---|---|
| NFL | ESPN FPI | also carries win-division and win-title |
| NBA | ESPN BPI | also carries a play-in chance |
| MLB | ESPN standings | `playoffPercent`, right in the payload |
| NHL | Hockey-Reference | scraped; see below |
| College football | ESPN FPI | means CFP odds; a column on the Big Ten table |
| College basketball | ESPN BPI | projected NCAA seed, not a probability |
| College hockey | NCAA NPI rank | not odds, but the metric that decides selection |
| Everything else | none exists | college basketball, soccer |

MoneyPuck, the obvious NHL source, explicitly asks not to be scraped, so it is
not used. Hockey-Reference's `/friv/playoff_prob.cgi` is not disallowed by
their robots.txt (checked 2026-08-25) and the code honours their published
`Crawl-delay: 3`, fetching once a day and caching for twelve hours. If that
ever feels wrong, delete the source and the NHL simply loses its odds column.

## The odds history

`history.py` appends one row per team per day to
`output/history/odds-<league>.csv`, for leagues actually in season, and **only
when `GITHUB_ACTIONS` is set**. A local run would otherwise append its own rows
for today, which then conflict with the ones the workflow committed hours
earlier -- the same day recorded twice with different numbers, and a merge
conflict on the next push. That happened on 2026-08-29. **This
cannot be backfilled** -- no source publishes yesterday's number -- so it is
worth exactly as much as the number of days it has been running. It started
2026-08-25.

The page does NOT currently show the movement: the week-over-week delta was
built and then removed on 2026-08-25 because the line it lived on was clutter.
The recording continues so the option stays open.

## The app icon

`site.py` draws the icon by pixel maths -- three standings rows, the top one in
the accent colour -- and writes it at 180, 192 and 512px. There is no image
library on this machine, and the same trick is what sports-daily does.

The manifest marks the icon **`purpose: "any maskable"`**, which is what makes
a launcher crop it to its own shape -- a circle on Android -- instead of
padding the square into a container. Every bar corner sits within the maskable
safe zone (a circle of radius 0.4 about the centre; the furthest is 0.388), so
nothing is clipped. 180px is written for `apple-touch-icon` only: iOS ignores
the manifest and applies its own rounded-square mask.

The page carries an explicit `<link rel="icon">`. Without it a desktop browser
asks for `/favicon.ico`, which this site does not ship, and shows a blank tab
after the 404 -- which is exactly what it did until 2026-08-29.

## Deployment

Live at <https://kyeill.github.io/standings/>, built by GitHub Actions at
06:00 Eastern with catch-up slots at 07 and 08 because GitHub delays scheduled
runs. The gate reads `output/history/_last_build.txt`; when a catch-up finds
the day already built, the build job skips AND so does deploy -- the deploy job
is gated on `needs.build.outputs.built`, without which it fails every morning
on "No artifacts named github-pages".

Two traps worth remembering, both cost time here:

* **A workflow registers only when a push MODIFIES its file.** A workflow that
  arrives in the push that first creates the repo is never scanned: the file is
  visible, but Actions lists no workflow and `gh workflow run` reports "not
  found on the default branch". Touch the file and push again.
* Reading the Pages API anonymously returns 404 even when Pages is enabled, so
  it is not a usable check.

## Known gaps

* College hockey conference POINTS are not derived, only W-L-T -- the leagues
  weight overtime differently and change the rules between seasons.
* The NPI rank comes from a community mirror of ncaa.com, not a first-party
  feed. If it goes away the hockey tables just lose their rank column.
* College basketball and soccer have no odds source at all.
* The Pistons' teal and the Cavaliers' gold are hand-picked: ESPN has no teal
  for the Pistons at all, and returns a muted antique gold for the Cavaliers.
