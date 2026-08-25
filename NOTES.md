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
| College hockey | **nothing at all** | no | no |
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

**College hockey standings are empty.** Every conference node returns zero
entries. PairWise, the ranking that actually decides the NCAA tournament, has
no free API. Michigan and Cornell hockey can have a page presence but not a
table.

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
