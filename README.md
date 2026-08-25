# Standings

A playoff-race app: where my teams sit, how far from the line, and which way
the odds are moving. Separate from `sports-daily` on purpose -- it imports
nothing from it and touches none of its files. See `NOTES.md` for the trap
list and what each sport's data can actually support.

```
python site.py           build the app into output/site/  (in-season sports only)
python site.py --all     same, but keep every sport, for testing
python build.py          print what each tab resolved to, no HTML
python mock.py           the three original design mockups
```

Python is not on PATH:
`C:\Users\kyleh\AppData\Local\Programs\Python\Python312-arm64\python.exe`

No pandas or numpy. Standard library plus `requests`, same as sports-daily.

## The two display modes

Set per tab in `leagues.py`.

**tracker** -- the Big 4 American sports. A race, not a table: the verdict
("2.5 back", "Clinched", "Eliminated"), the playoff odds and how they have
moved in a week, then a ladder with everyone not adjacent to a decision
collapsed to "5 more". The dashed cut line is drawn where the playoff spots
actually end.

**table** -- college and soccer. A straight standings table, because those
sports have no cut line worth computing: college races are decided by a poll
or a selection committee, and a soccer league table IS the competition. Soccer
tables still draw a line where one is meaningful (EPL at 4 for the Champions
League, MLS at 9 for the playoffs).

## Tabs

| Tab | Mode | Contents |
|---|---|---|
| NFL / MLB / NBA / NHL | tracker | Lions, Tigers, Pistons + Cavaliers, Red Wings |
| College | table | Michigan and Cornell across football, basketball, hockey |
| Tottenham | table | Premier League plus whichever European competition is running |
| Atlanta | table | Atlanta United, MLS Eastern Conference |

Two tracked teams in one conference (the Pistons and the Cavaliers) share a
single ladder rather than printing it twice.

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
| College football | ESPN FPI | means CFP odds; empty in the preseason |
| College hockey | NCAA NPI rank | not odds, but the metric that decides selection |
| Everything else | none exists | college basketball, soccer |

MoneyPuck, the obvious NHL source, explicitly asks not to be scraped, so it is
not used. Hockey-Reference's `/friv/playoff_prob.cgi` is not disallowed by
their robots.txt (checked 2026-08-25) and the code honours their published
`Crawl-delay: 3`, fetching once a day and caching for twelve hours. If that
ever feels wrong, delete the source and the NHL simply loses its odds column.

## The trend

`history.py` appends one row per team per day to
`output/history/odds-<league>.csv`, and the page shows the move against the
reading closest to a week ago. **This cannot be backfilled** -- no source
publishes yesterday's number -- so the feature is worth exactly as much as the
number of days it has been running. It started 2026-08-25.

## Known gaps

* College hockey conference POINTS are not derived, only W-L-T -- the leagues
  weight overtime differently and change the rules between seasons.
* The NPI rank comes from a community mirror of ncaa.com, not a first-party
  feed. If it goes away the hockey tables just lose their rank column.
* College basketball and soccer have no odds source at all.
* The college football spread of FPI odds is unverified until the season starts.
