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
python selftest.py       check the back end (74 assertions)
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
layout so the numeric columns land in the same place on every tab.

## Columns

Every table leads with an index. A row **tied with the one above is left
blank**, where tied means the same value in the column the table is ordered by
-- conference games behind for college, games behind for the American sports,
points behind for hockey and soccer. Comparing overall records instead would
number three 15-5 Big Ten teams 2, 3 and 4. Soccer counts as tied on POINTS
even though goal difference decides the order.

    NFL MLB   # | Team | Record | GB
    NBA       # | Team | Record | GB
    NHL       # | Team | Points | PB     points, no "pts" suffix
    CFB CBB   # | Team | Conf | Overall | GB | <metric>
    HKY       # | Team | Conf | GB | NPI  no overall record, at any size
    EPL MLS   # | Team | P | W-D-L | GD | Pts

The metric column -- CFP odds, projected NCAA seed (header "Seed"), or NPI --
sits at the very end.

**Under 640px one column steps aside**: Overall on college, W-D-L on soccer,
and the index and numeric columns tighten. Six columns had left the team name
47px on a 375px phone, truncating most of it; it is now 143px. Desktop keeps
every column. College hockey is the exception that needs no breakpoint: it
drops Overall at every size (`drop_overall`), because NPI already says how good
the team is nationally.

As a rule of thumb a phone fits about four columns besides the team name.

## Crests

ESPN publishes two variants per team and the `-dark` one is usually right on a
dark page -- but for some clubs it is a flat white silhouette, so Liverpool and
Tottenham become indistinguishable at 19px. `logos.py` measures the actual
pixels of both and picks per team, exactly as sports-daily does: the dark
variant when it carries colour, otherwise the default if it is light enough,
otherwise the dark one anyway. The 15 exceptions live in `logo-overrides.json`,
which the build just reads -- re-run `python logos.py --write` when the tracked
teams change. The default variant is always the `onerror` fallback, since a few
teams have no dark file at all.

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

HKY is COLLEGE hockey; the NHL has its own tab. Two tracked teams in one
conference (the Pistons and the Cavaliers) share a single ladder rather than
printing it twice -- and because only the first card is drawn, the second
team's odds are moved onto the table that IS drawn, or they would vanish.

## Only what is actually on

A sport that is not currently being played is dropped entirely -- tab and all.
`season.py` decides by asking the scoreboard whether real games fall within ten
days, which is the only reliable test: an out-of-season league does not return
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
`output/history/odds-<league>.csv`, for leagues actually in season. **This
cannot be backfilled** -- no source publishes yesterday's number -- so it is
worth exactly as much as the number of days it has been running. It started
2026-08-25.

The page does NOT currently show the movement: the week-over-week delta was
built and then removed on 2026-08-25 because the line it lived on was clutter.
The recording continues so the option stays open.

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
