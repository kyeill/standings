# Standings — what the data actually supports

Exploratory. Nothing here is wired to `sports-daily`; the two folders are
deliberately separate until we decide whether to bundle them. This file records
what ESPN does and does not publish, measured on **2026-08-25**, so it does not
have to be rediscovered.

```
python mock.py     -> output/mockups.html   three designs, real data
python model.py    -> a one-line summary per tracked team, for sanity checks
```

## The availability matrix

| Sport | Division table | Playoff cut line | Playoff odds |
|---|---|---|---|
| MLB | yes, division of 5 | yes, 6 seeds | **yes — in the standings payload itself** |
| NFL | yes, division of 4 | yes, 7 seeds | yes, ESPN FPI |
| NBA | yes, division of 5 | yes, 10 seeds incl. play-in | yes, ESPN BPI |
| NHL | yes, division of 8 | yes, 8 seeds, **points** | **no** |
| College football | conference table only | no | FPI, **in season only** |
| College basketball | conference table only | no | no |
| College hockey | **derived from games** | no | no |
| Premier League | yes, one table of 20 | the line is a choice | no |
| MLS | yes, conference of 15 | yes, top 9 | no |

## Traps

**MLB is far richer than the other sports.** Its standings entries carry
`playoffPercent`, `wildCardPercent`, `magicNumberDivision` and
`magicNumberWildcard` directly — no FanGraphs call needed for a standings page.
Nothing else has any of these.

**College football publishes no `losses` stat.** The entry has `wins` and an
`overall` string ("8-3") and nothing else, so `stats.get("losses")` reads None
and every games-behind calculation silently collapses to nothing. Parse
`overall`.

**A college conference table is ordered by CONFERENCE record, not overall.**
Sorting or computing games-behind from the overall record puts Purdue (30-9,
13-7 in conference) below Wisconsin (24-11, 14-6) with a *smaller* number — the
column contradicts the order it sits in. Both must use the same basis.

**College payloads repeat every stat name once per split** — overall, Home,
Away, vs Division, vs Conf., vs AP Top 25. A plain dict comprehension keeps the
LAST occurrence, which is a split, not the overall figure. Take the first.

**College hockey standings are empty everywhere in ESPN** -- site API and core
API both return zero entries for every conference. They are now DERIVED in
`chockey.py` from completed game results, which was validated against the
finished 2025-26 season (a correct 12-team ECAC and 7-team Big Ten table).
Two traps in doing so: the college hockey scoreboard carries **no
conferenceId at all**, so membership has to come from the core API's group
listing; and **ESPN calls the ECAC "East Coast Athletic Conference"**, so a
name filter on "ECAC" silently matches nothing.

Conference POINTS are deliberately not derived -- the leagues weight overtime
results differently and change the rules between seasons, so a points column
would be invented rather than computed.

Sources ruled out for college hockey, all checked 2026-08-25: NCAA's data host
404s on every standings path tried; USCHO renders client side; College Hockey
News has no machine-readable standings page. The NCAA's **NPI** ranking (which
now decides tournament selection) IS reachable through a community proxy at
`ncaa-api.henrygd.me/rankings/icehockey-men/d1` -- Cornell showed there at #11,
22-10-1 -- but it is a third-party mirror, not a first-party feed, so it is not
used.

**ESPN's `playoffSeed` is not a table position.** MLB seeds 1-3 are division
winners, so a 66-66 division leader is seed 3 while a 72-59 wild card is seed 5.
The NFL does the same with seeds 1-4. Ordering a ladder by seed is correct for
the *bracket* but does not answer "who is ahead of me".

**`playoffSeed` still beats sorting by points in the NHL,** because it encodes
the regulation-wins tiebreaker. Prefer the seed where a sport has one; fall
back to points or win percentage only where it is absent (college).

**The top-level `season` block does not describe the standings you got.** MLB
returned in-progress 2026 records under a `season.year` of 2027. Do not read
the season from there.

**An out-of-season league returns something misleading, not nothing.** Today
the NBA and NHL return last season's *final* table complete with clinch flags,
while college football returns an all-zero table for a season that has not
started. Neither is worth showing, and they fail differently, so an
"is this league in season" test cannot be built on emptiness alone.

**The NHL `overall` string is `"41-31-10, 92 PTS"`** and its last-ten is
`"7-2-1, 0 PTS"` — the points half of the last-ten figure is always 0. Split on
the comma.

**College football FPI carries no projections in the preseason.** The endpoint
answers with 138 teams and an empty projections list. `probmakeplayoffs` (which
means CFP odds there) presumably appears once games are played — unverified
until September.

**NHL and MLB have no powerindex endpoint at all** — both 400. This matches
what the daily tool already found.

## Carried over from sports-daily

Same ESPN quirks apply and are already handled here: do not set a browser-style
User-Agent (403), use the `/500-dark/` logo variant on a dark background with an
`onerror` fallback, and override ESPN's team colours for the Tigers (navy) and
Michigan (blue).
