"""Historical rankings: Kyle's spreadsheet formulas, rebuilt in Python.

Each sport's hidden tabs hold what happened, season by season -- a finish, a
playoff round, a poll rank -- and formulas turn those into a 0-100 Value per
team. rankings/inputs/ holds what he typed (import_sheet.py); this module does
what the formulas did, and selftest proves it against rankings/expected/.

Nearly every input tab is one of three shapes, and they share one blend:

    PLACE    finishes (1st, 2nd...) scored from the tab's own Place->Pts
             table, averaging the BEST FOUR of five seasons
    POINTS   values already in points (a playoff round, a CFP result),
             best four of five
    RATING   a rank where lower is better (SP+, KenPom, PairWise): the five
             seasons summed minus the worst, a missing season counted as N

    val   = 0.75 * last five seasons + 0.25 * the five before, minus a tiny
            row-number tie-break (the sheet's own: the earlier row wins)
    Value = log10(val - min + 1) / log10(max - min + 1) * 100  (RATING: 100 -)

"Five seasons" means five COLUMNS, as in the sheet, not five calendar years:
a tab with no 2019-20 column (no NCAA tournament) simply reaches further back.

SHEET_COMPAT reproduces the sheet exactly, faults included, so the port can
be proven cell for cell. With it off, three faults are corrected -- his call,
2026-09-21:

  * MLB_val weighted the division part B*B (squared) and NHL_val 25*B; every
    other sport uses 0.25*B. Either way division swamped the playoffs.
  * EPL_val's UEFA share pointed at #REF!, so it counted as zero; restored to
    EPL_val!E42:E180, the UEFA value it evidently used to read.
  * numbers pasted as TEXT (the whole 2024 and 2023 SP+ columns) were skipped
    by SUM and MAX, so those seasons counted for nothing.
"""

import csv
import math
import os
import re
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
INPUTS = os.path.join(HERE, "rankings", "inputs")
SEASONS = os.path.join(HERE, "rankings", "seasons")      # fill.py writes here

SHEET_COMPAT = False

# Season headers mistyped in the sheet. CBB_seed's "2045-25" is the 2024-25
# tournament -- harmless there, where columns were matched by position, but
# the Python matches seasons by label.
HEADER_FIXES = {"2045-25": "2024-25"}


def _col_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n


class Text(str):
    """A number the sheet held as TEXT (imported with a leading apostrophe).
    Compat mode treats it the way Sheets did -- invisible to SUM, MAX, SMALL,
    LARGE, COUNT -- and otherwise it is simply the number it says."""


def _parse(cell):
    if cell == "":
        return None
    if cell.startswith("'") and re.fullmatch(r"'-?\d+(\.\d+)?", cell):
        return Text(cell[1:]) if SHEET_COMPAT else float(cell[1:])
    try:
        return float(cell)
    except ValueError:
        return cell


def is_num(v):
    return isinstance(v, float)


def season_label(v):
    """Header cells hold '2025-26', '2025' or a Text('2025') -- all labels."""
    if v is None:
        return None
    if isinstance(v, float):
        return str(int(v))
    return str(v)


class Tab:
    """One imported tab. Rows keep their SHEET row numbers (1-based), because
    the tie-break is row-based and must match."""

    def __init__(self, name):
        self.name = name
        path = os.path.join(INPUTS, name.replace("+", "plus") + ".csv")
        with open(path, encoding="utf-8") as f:
            self.grid = [[_parse(c) for c in row] for row in csv.reader(f)]
        for r, row in enumerate(self.grid):
            for c, v in enumerate(row):
                if isinstance(v, str) and v.startswith("="):
                    row[c] = self._formula(r + 1, v)
        self.header = self.grid[0] if self.grid else []
        self.raw_header = self.header
        self.header = [HEADER_FIXES.get(v, v) for v in self.header]
        if not SHEET_COMPAT:
            self._lay_overlay()

    def _lay_overlay(self):
        """Seasons finished since the import (fill.py, rankings/seasons/),
        inserted in front of the sheet's own, newest first -- so to every
        formula here they are simply more columns, exactly as if he had typed
        them. Never in compat mode: the proof is of the sheet alone."""
        path = os.path.join(SEASONS, self.name.replace("+", "plus") + ".csv")
        if not os.path.exists(path) or not self.grid:
            return
        with open(path, encoding="utf-8") as f:
            entries = [(r["season"], r["name"], r["value"]) for r in csv.DictReader(f)]
        try:
            first = self.col_of("Prior 5 Yr") + 1
        except KeyError:
            return
        have = set(self.seasons())
        new = sorted({s for s, _n, _v in entries if s not in have}, reverse=True)
        if not new:
            return
        width = max(len(row) for row in self.grid)
        for row in self.grid:
            row.extend([None] * (width - len(row)))
            row[first - 1:first - 1] = [None] * len(new)
        self.header = self.grid[0][:first - 1] + new + self.header[first - 1:]
        self.grid[0] = list(self.header)
        rows = {}
        for r in range(2, len(self.grid) + 1):
            name = self.cell(r, 1)
            if name is not None:
                rows.setdefault(str(name).lower(), r)
        for season, name, value in entries:
            if season not in new:
                continue
            if name.startswith("#row"):
                # A row with no name to find it by: Concacaf_GC's row 2,
                # which says whether a season was a Gold Cup or a Copa.
                self.grid[int(name[4:]) - 1][first - 1 + new.index(season)] = _parse(value)
                continue
            key = name.lower()
            offset = 0
            m = re.fullmatch(r"(.*)\+(\d+)", name)
            if key not in rows and m:
                key, offset = m.group(1).lower(), int(m.group(2))
            r = rows.get(key)
            if r is None:
                # A team new to the tab joins the bottom of the team block.
                last = self.teams()[-1][0] if self.teams() else 1
                self.grid.insert(last, [name] + [None] * (len(self.header) - 1))
                rows = {k: (v + 1 if v > last else v) for k, v in rows.items()}
                r = rows[key] = last + 1
            self.grid[r - 1 + offset][first - 1 + new.index(season)] = _parse(value)

    def _formula(self, row, text):
        """The one formula kept as data: =AVERAGE(M5:O5), a season filled in
        from the three after it (HKY_PW, the Ivies' missing 2020-21)."""
        m = re.fullmatch(r"=AVERAGE\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)", text)
        if not m or int(m.group(2)) != row or int(m.group(4)) != row:
            raise ValueError("%s row %d: unsupported formula %s" % (self.name, row, text))
        first, last = _col_index(m.group(1)), _col_index(m.group(3))
        nums = [v for v in self.grid[row - 1][first - 1:last] if is_num(v)]
        return sum(nums) / len(nums) if nums else None

    def override(self, row, label):
        """A number typed where the sheet normally computes one -- HKY_FF gives
        Bentley a flat Prior 5 Yr of 1, CBB_seed row 185 is frozen values.
        The formula cells import blank, so anything present was typed."""
        try:
            v = self.cell(row, self.col_of(label))
        except KeyError:
            return None
        return v if is_num(v) else None

    def cell(self, row, col):
        """1-based, like the sheet. Out of range reads as blank."""
        try:
            return self.grid[row - 1][col - 1]
        except IndexError:
            return None

    def teams(self):
        """[(sheet row, name)] -- the block from row 2 down to the first
        blank name. Footer rows (champions, runners-up) sit below a gap."""
        out = []
        for r in range(2, len(self.grid) + 1):
            name = self.cell(r, 1)
            if name is None:
                if out:
                    break
                continue        # Concacaf_GC: row 2 names each event, no team
            out.append((r, name))
        return out

    def col_of(self, label):
        for i, v in enumerate(self.header):
            if v == label or season_label(v) == label:
                return i + 1
        raise KeyError("%s has no %r column" % (self.name, label))

    def season_cols(self):
        """The season columns, newest first: everything right of 'Prior 5 Yr'."""
        start = self.col_of("Prior 5 Yr") + 1
        return list(range(start, len(self.header) + 1))

    def seasons(self):
        return [season_label(self.header[c - 1]) for c in self.season_cols()]

    def row_of(self, name):
        key = str(name).lower()
        for r, n in self.teams():
            if str(n).lower() == key:
                return r
        return None

    def values(self, row, cols):
        return [self.cell(row, c) for c in cols]

    def footer(self, label):
        """The row whose first cell is `label`, as {season: value}."""
        for r in range(1, len(self.grid) + 1):
            if self.cell(r, 1) == label:
                return self.footer_row(r)
        return {}

    def footer_row(self, r):
        return {season_label(self.header[c - 1]): self.cell(r, c)
                for c in self.season_cols()}


# ---- the shared arithmetic ------------------------------------------------

def log_scale(vals, invert=False):
    lo, hi = min(vals.values()), max(vals.values())
    out = {}
    for k, v in vals.items():
        x = math.log10(v - lo + 1) / math.log10(hi - lo + 1) * 100
        out[k] = 100 - x if invert else x
    return out


def min_max(vals):
    lo, hi = min(vals.values()), max(vals.values())
    return {k: (v - lo) * 100 / (hi - lo) for k, v in vals.items()}


def rank_desc(vals):
    """{key: 1-based rank}, highest first -- RANK(x, range, 0)."""
    order = sorted(vals, key=lambda k: -vals[k])
    return {k: order.index(k) + 1 for k in vals}


def _nums(xs):
    return [x for x in xs if is_num(x)]


def _round_half_up(x):
    return math.floor(x + 0.5)


def place_block(tab, cols, pts):
    """Best four finishes of the five, each scored from Place->Pts; /4.
    SMALL skips blanks and text; a missing k-th finish scores 0 (IFERROR)."""
    finishes = sorted(_nums(cols))[:4]
    return sum(pts.get(f, 0) for f in finishes) / 4


def points_block(cols):
    return sum(sorted(_nums(cols), reverse=True)[:4]) / 4


def rating_block(cols, missing):
    """(SUM - MAX + blanks*N) / 4 -- the worst of five dropped, a season with
    no rating at all scored as `missing` (N, the field size)."""
    nums = _nums(cols)
    blanks = sum(1 for c in cols if c is None)
    return (sum(nums) - (max(nums) if nums else 0) + blanks * missing) / 4


def blend(recent, prior, row):
    return 0.75 * recent + 0.25 * prior - row / 1e6


def _finish(tab, parts, invert=False):
    """parts = {team: (row, recent, prior)} -> {team: Value}, honouring any
    number typed over the 5 Yr Avg, Prior 5 Yr, val or Value cells."""
    val = {}
    for team, (r, recent, prior) in parts.items():
        recent = _first(tab.override(r, "5 Yr Avg"), recent)
        prior = _first(tab.override(r, "Prior 5 Yr"), prior)
        val[team] = _first(tab.override(r, "val"), blend(recent, prior, r))
    out = log_scale(val, invert)
    for team, (r, _a, _b) in parts.items():
        out[team] = _first(tab.override(r, "Value"), out[team])
    return out


def _first(a, b):
    return a if a is not None else b


def points_table(tab):
    """Place -> Pts from columns B and C, first match winning (VLOOKUP)."""
    out = {}
    for r in range(2, len(tab.grid) + 1):
        p, q = tab.cell(r, 2), tab.cell(r, 3)
        if is_num(p) and is_num(q) and p not in out:
            out[p] = q
    return out


def _bonus_rows(tab, labels, value_col):
    """[(sheet row, points)] for footer rows that award a flat bonus -- a
    conference tournament, a domestic cup -- found by their label in column
    A, worth the number in `value_col` of the same row."""
    out = []
    for label in labels:
        for r in range(1, len(tab.grid) + 1):
            if tab.cell(r, 1) == label:
                out.append((r, tab.cell(r, value_col)))
                break
        else:
            raise KeyError("%s has no %r row" % (tab.name, label))
    return out


def _bonus(tab, bonus, team, cols):
    """COUNTIFS(bonus row over these seasons, team) * points, summed."""
    key = str(team).lower()
    total = 0
    for r, points in bonus:
        hits = sum(1 for c in cols if str(tab.cell(r, c) or "").lower() == key)
        total += hits * (points or 0)
    return total


def place_tab(name, median_prior=False, bonus=(), bonus_inside=False):
    """{team: Value} for a PLACE tab.

    median_prior (NHL_div, MLS_table): a team with fewer than five recent
    seasons -- an expansion club -- is given a PRIOR score equal to the
    points for its median recent finish, rather than zeros for seasons it
    never played.

    bonus: footer-row labels whose winners earn that row's column-C points
    per title (the Big Ten Tournament, the FA Cup...). bonus_inside puts the
    bonus inside the average (CBB_B1G), otherwise it is added after it.
    """
    tab = Tab(name)
    pts = points_table(tab)
    rows = _bonus_rows(tab, bonus, 3)
    cols = tab.season_cols()
    val = {}
    for r, team in tab.teams():
        recent, prior = cols[:5], cols[5:10]

        def block(c):
            base = sum(pts.get(f, 0) for f in sorted(_nums(tab.values(r, c)))[:4])
            extra = _bonus(tab, rows, team, c)
            return (base + extra) / 4 if bonus_inside else base / 4 + extra

        recent_nums = _nums(tab.values(r, recent))
        if median_prior and len(recent_nums) < 5:
            prior_score = (pts[_round_half_up(statistics.median(recent_nums))]
                           + _bonus(tab, rows, team, prior))
        else:
            prior_score = block(prior)
        val[team] = (r, block(recent), prior_score)
    return _finish(tab, val)


def points_tab(name, bonus=(), bonus_rows_override=None):
    """{team: Value} for a POINTS tab. bonus as in place_tab, always inside
    the average and valued from column B (EPL_UCL's Europa/Conference rows)."""
    tab = Tab(name)
    rows = bonus_rows_override or _bonus_rows(tab, bonus, 2)
    cols = tab.season_cols()
    val = {}
    for r, team in tab.teams():
        def block(c):
            return (sum(sorted(_nums(tab.values(r, c)), reverse=True)[:4])
                    + _bonus(tab, rows, team, c)) / 4
        val[team] = (r, block(cols[:5]), block(cols[5:10]))
    return _finish(tab, val)


def rating_tab(name, missing=None):
    """missing=None means COUNTA(A:A): every non-blank name cell on the tab."""
    tab = Tab(name)
    if missing is None:
        missing = sum(1 for row in tab.grid if row and row[0] is not None)
    cols = tab.season_cols()
    val = {}
    for r, team in tab.teams():
        val[team] = (r, rating_block(tab.values(r, cols[:5]), missing),
                     rating_block(tab.values(r, cols[5:10]), missing))
    return _finish(tab, val, invert=True)


def lookup(values, name):
    """VLOOKUP is case-blind: the _val tabs write DETROIT, the inputs Detroit."""
    key = str(name).lower()
    for k, v in values.items():
        if str(k).lower() == key:
            return v
    raise KeyError(name)


def count_in(tab, name, first_col, n, pred):
    """COUNTIFS over n season columns of a team's row: titles, cut lines..."""
    r = tab.row_of(name)
    if r is None:
        return 0
    return sum(1 for v in tab.values(r, range(first_col, first_col + n))
               if v is not None and pred(v))


# ---- the Big 4 --------------------------------------------------------------

# Per sport: the two halves of the _val tab (how many teams in each), the
# playoff-points labels (15 = conference champion, 5 = lost the conference
# final), and whether 0.5 marks a play-in team. The division part's weight
# is where MLB and NHL carried their typos.
PRO = {
    "NFL": {"halves": (("National Conference", 16, "NFC", "NFCCG"),
                       ("American Conference", 16, "AFC", "AFCCG")),
            "div_weight": 0.25,
            "footers": ("SUPER BOWL CHAMPIONS", "SUPER BOWL RUNNER-UP")},
    "MLB": {"halves": (("American League", 15, "AL", "ALCS"),
                       ("National League", 15, "NL", "NLCS")),
            "div_weight": 0.25, "compat_weight": "square",
            "footers": ("WORLD SERIES CHAMPIONS", "WORLD SERIES RUNNER-UP")},
    "NBA": {"halves": (("Eastern Conference", 15, "East", "ECF"),
                       ("Western Conference", 15, "West", "WCF")),
            "div_weight": 0.25, "play_in": True,
            "footers": ("NBA FINALS CHAMPIONS", "NBA FINALS RUNNER-UP")},
    "NHL": {"halves": (("Eastern Conference", 16, "East", "ECF"),
                       ("Western Conference", 16, "West", "WCF")),
            "div_weight": 0.25, "compat_weight": 25, "median_prior": True,
            "footers": ("STANLEY CUP CHAMPIONS", "STANLEY CUP RUNNER-UP")},
}


def _combo_weight(cfg, div):
    if SHEET_COMPAT and cfg.get("compat_weight") == "square":
        return div * div
    if SHEET_COMPAT and cfg.get("compat_weight"):
        return cfg["compat_weight"] * div
    return cfg["div_weight"] * div


def _blank_zero(n, zero):
    return zero if not n else n


def pro(sport):
    """The front tab for one of the Big 4: two conference tables ranked by
    Value, each row carrying titles, division titles and the last five
    seasons as words ("CHAMPS", "NFCCG", "1st Div", "playoff" or a place)."""
    cfg = PRO[sport]
    div_tab, po_tab = Tab(sport + "_div"), Tab(sport + "_playoffs")
    div_val = place_tab(sport + "_div", cfg.get("median_prior", False))
    po_val = points_tab(sport + "_playoffs")
    val_tab = Tab(sport + "_val")
    teams = val_tab.teams()

    combo = {}
    for r, team in teams:
        combo[team] = (_combo_weight(cfg, lookup(div_val, team))
                       + 0.75 * lookup(po_val, team) - (100 - r) / 1e6)
    overall, value = rank_desc(combo), min_max(combo)

    seasons = div_tab.seasons()[:5]
    div_cols = div_tab.season_cols()
    po_cols = po_tab.season_cols()
    sections, start = [], 0
    for title, size, champ15, lost5 in cfg["halves"]:
        half = teams[start:start + size]
        start += size
        order = sorted(half, key=lambda t: -combo[t[1]])
        rows = []
        for i, (_r, team) in enumerate(order, 1):
            labels = []
            for s in seasons:
                place = div_tab.cell(div_tab.row_of(team), div_tab.col_of(s))
                pr = po_tab.row_of(team)
                pts = po_tab.cell(pr, po_tab.col_of(s)) if pr and s in po_tab.seasons() else None
                labels.append(_season_word(pts, place, champ15, lost5,
                                           cfg.get("play_in")))
            rows.append([i, team, overall[team], value[team],
                         _blank_zero(count_in(po_tab, team, po_cols[0], 10,
                                              lambda v: v == 30), ""),
                         _blank_zero(count_in(div_tab, team, div_cols[0], 10,
                                              lambda v: v == 1), ".")]
                        + labels)
        sections.append({"title": title, "rows": rows,
                          "columns": ["#", "Team", sport, "Value", "CHAMPS",
                                      "Division"] + seasons})
    footers = [(label, [po_tab.cell(r, po_tab.col_of(s)) for s in seasons],
                seasons)
               for label, r in zip(cfg["footers"], _footer_rows(po_tab))]
    return {"sections": sections, "footers": footers, "seasons": seasons}


def _footer_rows(tab):
    """The rows below the team block's gap, in order (champion, runner-up)."""
    last = tab.teams()[-1][0]
    return [r for r in range(last + 1, len(tab.grid) + 1)
            if any(v is not None for v in tab.grid[r - 1][1:])]


def _season_word(pts, place, champ15, lost5, play_in):
    pts = pts if is_num(pts) else 0
    if pts == 30:
        return "CHAMPS"
    if pts == 15:
        return champ15
    if pts == 5:
        return lost5
    if play_in and pts == 0.5:
        return "play-in"
    if place == 1:
        return "1st Div"
    if pts > 0:
        return "playoff"
    return place if place is not None else 0


# ---- college football -------------------------------------------------------

def _nonzero(values, name):
    """IFERROR(1/(1/VLOOKUP(...)),0): missing or zero both read as 0."""
    try:
        return lookup(values, name) or 0
    except KeyError:
        return 0


def _coerce(v):
    """Arithmetic on a number-as-text coerces it, even in the sheet -- only
    SUM/MAX/SMALL/LARGE skip text. CFB_rk's sums are arithmetic."""
    if isinstance(v, Text):
        return float(v)
    return v


def _cell_by(tab, name, season):
    r = tab.row_of(name)
    if r is None or season not in tab.seasons():
        return None
    return tab.cell(r, tab.season_cols()[tab.seasons().index(season)])


def combined_rank(poll_tab, rating_tab_, teams, season):
    """CFB_rk / CBB_rk: a season's national order -- the poll first, then the
    rating for everyone unranked. Poll rank (1000 if unranked) plus rating
    rank (a million if unrated), ranked ascending. Ties SHARE a rank, as in
    RANK(): nothing breaks them."""
    score = {}
    for t in teams:
        p = _coerce(_cell_by(poll_tab, t, season))
        s = _coerce(_cell_by(rating_tab_, t, season))
        score[t] = ((p if is_num(p) and p else 1000)
                    + (s if is_num(s) and s else 1000000))
    return {t: 1 + sum(1 for u in score if score[u] < score[t]) for t in score}


def _count_name(tab, label, name, n=10):
    """How many of the first n seasons a footer row (e.g. "B1G Champion")
    names this team -- the conference-title count. Case-blind, like COUNTIFS."""
    row = tab.footer(label)
    return sum(1 for s in tab.seasons()[:n]
               if str(row.get(s) or "").lower() == str(name).lower())


def _footer_lines(tab, labels, seasons, follow=0):
    """[(label, [value per season], seasons)] for footer rows found by their
    label -- champions, runners-up, the CFP's four teams (follow=n takes the
    n unlabelled rows beneath). Each line carries its seasons, because one
    tab's footers can mix calendars: Concacaf lists World Cups every four
    years beside a yearly Nations League."""
    out = []
    for label in labels:
        for r in range(1, len(tab.grid) + 1):
            if tab.cell(r, 1) == label:
                for extra in range(follow + 1):
                    row = tab.footer_row(r + extra)
                    out.append((label if not extra else "",
                                [row.get(s) for s in seasons], list(seasons)))
                break
    return out


CFP_WORDS = ((30, "CHAMPS"), (15, "Final"), (10, "Semis"), (3, "Qtrs"),
             (1, "CFP"), (0.5, "NY6"))


def cfb():
    b1g_tab, cfp_tab = Tab("CFB_B1G"), Tab("CFB_CFP")
    poll_tab, sp_tab, rk_tab = Tab("CFB_poll"), Tab("CFB_SP+"), Tab("CFB_rk")
    b1g_val = place_tab("CFB_B1G")
    poll_val = place_tab("CFB_poll")
    cfp_val = points_tab("CFB_CFP")
    sp_val = rating_tab("CFB_SP+")

    val_tab = Tab("CFB_val")
    rows = val_tab.teams()
    n_b1g = len(b1g_tab.teams())
    conf_rows, nat_rows = rows[:n_b1g], rows[n_b1g:]
    blue = {team for r, team in nat_rows if val_tab.cell(r, 2) == "x"}

    # The national block: CFP-weighted, and the SP+ rank within it.
    nat = {}
    for r, team in nat_rows:
        nat[team] = (0.2 * lookup(sp_val, team) + 0.2 * _nonzero(poll_val, team)
                     + 0.6 * _nonzero(cfp_val, team) - (100 - r) / 1e6)
    nat_rank, nat_value = rank_desc(nat), min_max(nat)
    sp_rank = rank_desc({t: lookup(sp_val, t) for _r, t in nat_rows})

    seasons = b1g_tab.seasons()[:5]
    ranks = {s: combined_rank(poll_tab, sp_tab, [t for _r, t in rk_tab.teams()], s)
             for s in seasons}

    def national_word(team, s):
        pts = _cell_by(cfp_tab, team, s)
        for value, word in CFP_WORDS:
            if pts == value:
                return word
        return lookup(ranks[s], team)

    def nat_key(team):
        return next(t for t in nat if t.lower() == team.lower())

    # The Big Ten block: half conference finish, the rest national.
    conf = {}
    for r, team in conf_rows:
        k = nat_key(team)
        conf[team] = (0.1 * lookup(sp_val, k) + 0.1 * _nonzero(poll_val, k)
                      + 0.3 * _nonzero(cfp_val, k) + 0.5 * lookup(b1g_val, team)
                      - (100 - r) / 1e6)
    conf_value = min_max(conf)
    champs, cg = b1g_tab.footer("B1G Champion"), b1g_tab.footer("Championship Game")

    def conf_word(team, s):
        national = national_word(nat_key(team), s)
        if national == "CHAMPS":
            return "CHAMPS"
        if str(champs.get(s) or "").lower() == team.lower():
            return "B1G"
        if national in ("Final", "CFP"):
            return "CFP"
        if str(cg.get(s) or "").lower() == team.lower():
            return "B1GCG"
        return _cell_by(b1g_tab, team, s)

    cfp_cols = cfp_tab.season_cols()
    b1g_section = []
    for i, team in enumerate(sorted(conf, key=lambda t: -conf[t]), 1):
        k = nat_key(team)
        b1g_section.append(
            [i, team, nat_rank[k], conf_value[team],
             _blank_zero(_count_name(b1g_tab, "B1G Champion", team), ""), None,
             _blank_zero(count_in(cfp_tab, team, cfp_cols[0], 10,
                                  lambda v: is_num(v) and v >= 1), ".")]
            + [conf_word(team, s) for s in seasons])

    def nat_row(i, team, first):
        return ([i, team, first, nat_value[team],
                 _blank_zero(count_in(cfp_tab, team, cfp_cols[0], 10,
                                      lambda v: v == 30), ""), None,
                 _blank_zero(count_in(cfp_tab, team, cfp_cols[0], 10,
                                      lambda v: is_num(v) and v >= 1), ".")]
                + [national_word(team, s) for s in seasons])

    top = sorted(nat, key=lambda t: -nat[t])
    national = [nat_row(i, t, sp_rank[t]) for i, t in enumerate(top[:25], 1)]
    bb = [nat_row(i, t, nat_rank[t])
          for i, t in enumerate([t for t in top if t in blue], 1)]

    cols = ["#", "Team", "CFB", "Value", "CHAMPS", "", "CFP"] + seasons
    footers = (_footer_lines(b1g_tab, ["Winner"], seasons, follow=1)
               + _footer_lines(cfp_tab, ["CFP"], seasons, follow=3)
               + _footer_lines(cfp_tab, ["No. 1", "SP+", "SEC", "Big XII",
                                         "ACC", "G5"], seasons))
    internals = {"conf_value": conf_value, "nat_rank": nat_rank,
                 "nat_value": nat_value, "rating_rank": sp_rank,
                 "rating_value": {t: lookup(sp_val, t) for t in nat}}
    return {"seasons": seasons, "footers": footers, "_internals": internals,
            "sections": [
        {"title": "Big Ten Conference", "columns": cols, "rows": b1g_section},
        {"title": "College Football", "columns": cols[:2] + ["SP+"] + cols[3:],
         "rows": national},
        {"title": "Football Blue Bloods", "columns": cols, "rows": bb}]}


# ---- college basketball -----------------------------------------------------

DUPLICATE = " (second row)"   # marks a repeated row, compat mode only

S16_WORDS = ((30, "CHAMPS"), (15, "Final"), (10, "Four"), (3, "Elite"),
             (1, "Sweet"))


def _title_count(tab, outright, shared, name, n=10):
    """Regular-season titles: outright ones, plus shared ones where the
    outright row names someone else (so a shared title is not counted twice)."""
    out, sh = tab.footer(outright), tab.footer(shared)
    key = str(name).lower()
    total = 0
    for s in tab.seasons()[:n]:
        o, x = str(out.get(s) or "").lower(), str(sh.get(s) or "").lower()
        if o == key or (x == key and o != key):
            total += 1
    return total


def _conf_word(tab, team, s, rows):
    """A season in conference terms: the first footer row naming the team
    decides the word, otherwise the finish. rows = [(label, word)]."""
    for label, word in rows:
        if str(tab.footer(label).get(s) or "").lower() == str(team).lower():
            return word
    return _cell_by(tab, team, s)


def cbb():
    b1g_tab, ivy_tab = Tab("CBB_B1G"), Tab("CBB_Ivy")
    s16_tab, seed_tab, kp_tab = Tab("CBB_sweet16"), Tab("CBB_seed"), Tab("CBB_kenpom")
    rk_tab = Tab("CBB_rk")
    b1g_val = place_tab("CBB_B1G", bonus=["B1G Tournament"], bonus_inside=True)
    ivy_val = place_tab("CBB_Ivy")
    seed_val, s16_val = place_tab("CBB_seed"), points_tab("CBB_sweet16")
    kp_val = rating_tab("CBB_kenpom")

    val_tab = Tab("CBB_val")
    rows = val_tab.teams()
    n_b1g, n_ivy = len(b1g_tab.teams()), len(ivy_tab.teams())
    conf_rows = rows[:n_b1g]
    ivy_rows = rows[n_b1g:n_b1g + n_ivy]
    nat_rows = rows[n_b1g + n_ivy:]
    blue = {t for r, t in nat_rows if str(val_tab.cell(r, 2) or "").startswith("x")}

    nat = {}
    for r, team in nat_rows:
        if team in nat:
            # St. John's is listed twice. The sheet ranks both rows, which
            # pushes every team below them down a place; corrected, the
            # second copy is simply ignored.
            if not SHEET_COMPAT:
                continue
            team = team + DUPLICATE
        nat[team] = (0.2 * lookup(kp_val, team.removesuffix(DUPLICATE))
                     + 0.2 * _nonzero(seed_val, team.removesuffix(DUPLICATE))
                     + 0.6 * _nonzero(s16_val, team.removesuffix(DUPLICATE))
                     - (100 - r) / 1e6)
    nat_rank, nat_value = rank_desc(nat), min_max(nat)
    kp_rank = rank_desc({t: lookup(kp_val, t.removesuffix(DUPLICATE)) for t in nat})

    def nat_key(team):
        return next(t for t in nat if t.lower() == team.lower())

    seasons = b1g_tab.seasons()[:5]
    rk_teams = [t for _r, t in rk_tab.teams()]

    def rk(s):
        score = {}
        # Here the sheet DID match the seed season by label, so its
        # "2045-25" typo hid every 2024-25 seed from this ranking.
        typo = SHEET_COMPAT and s not in [season_label(v) for v in seed_tab.raw_header]
        for t in rk_teams:
            seed = None if typo else _coerce(_cell_by(seed_tab, t, s))
            kp = _coerce(_cell_by(kp_tab, t, s))
            seed = seed if is_num(seed) and seed else 100
            score[t] = (0 if seed <= 12 else 1000) + (kp if is_num(kp) and kp else 1000)
        return {t: 1 + sum(1 for u in score if score[u] < score[t]) for t in score}

    ranks = {s: rk(s) for s in seasons}

    def national_word(team, s):
        pts = _cell_by(s16_tab, team, s)
        for value, word in S16_WORDS:
            if pts == value:
                return word
        seed = _cell_by(seed_tab, team, s)
        if is_num(seed) and seed > 0:
            return "ncaa"
        try:
            return lookup(ranks[s], team)
        except KeyError:
            return 0

    def blended(r, team, conf_value_of):
        k = nat_key(team)
        return (0.1 * lookup(kp_val, k) + 0.1 * _nonzero(seed_val, k)
                + 0.3 * _nonzero(s16_val, k) + 0.5 * conf_value_of(team)
                - (100 - r) / 1e6)

    s16_cols, seed_cols = s16_tab.season_cols(), seed_tab.season_cols()

    # Big Ten
    conf = {t: blended(r, t, lambda x: lookup(b1g_val, x)) for r, t in conf_rows}
    conf_value = min_max(conf)
    b1g_words = [("Champions x2", "B1G x2"), ("Outright Champion", "B1G"),
                 ("B1G Tournament", "BTT")]

    def b1g_word(team, s):
        national = national_word(nat_key(team), s)
        if national == "CHAMPS":
            return "CHAMPS"
        if national in ("Final", "Four"):
            return "Four"
        return _conf_word(b1g_tab, team, s, b1g_words)

    b1g_section = [
        [i, t, nat_rank[nat_key(t)], conf_value[t],
         _blank_zero(_title_count(b1g_tab, "Outright Champion", "Champions x2", t), ""),
         _blank_zero(_count_name(b1g_tab, "B1G Tournament", t), ""),
         _blank_zero(count_in(s16_tab, t, s16_cols[0], 10,
                              lambda v: is_num(v) and v > 0), ".")]
        + [b1g_word(t, s) for s in seasons]
        for i, t in enumerate(sorted(conf, key=lambda x: -conf[x]), 1)]

    # Ivy League: its own titles, and the NCAA tournament as the national word
    ivy = {t: blended(r, t, lambda x: lookup(ivy_val, x)) for r, t in ivy_rows}
    ivy_value = min_max(ivy)
    ivy_words = [("Champions x2", "BOTH"), ("Regular Season", "CHAMPS"),
                 ("Ivy Tournament", "IBT")]

    def ivy_word(team, s):
        own = _conf_word(ivy_tab, team, s, ivy_words)
        if own in ("BOTH", "IBT"):
            return "S16" if _cell_by(s16_tab, nat_key(team), s) == 1 else "NCAA"
        national = national_word(nat_key(team), s)
        return national if isinstance(national, str) else own

    ivy_section = [
        [i, t, nat_rank[nat_key(t)], ivy_value[t],
         _blank_zero(_title_count(ivy_tab, "Regular Season", "Champions x2", t), ""),
         _blank_zero(_count_name(ivy_tab, "Ivy Tournament", t), ""),
         _blank_zero(count_in(seed_tab, t, seed_cols[0], 10,
                              lambda v: is_num(v) and v > 0), ".")]
        + [ivy_word(t, s) for s in seasons]
        for i, t in enumerate(sorted(ivy, key=lambda x: -ivy[x]), 1)]

    def nat_row(i, team, first):
        return ([i, team, first, nat_value[team],
                 _blank_zero(count_in(s16_tab, team, s16_cols[0], 10,
                                      lambda v: v == 30), ""), None,
                 _blank_zero(count_in(s16_tab, team, s16_cols[0], 10,
                                      lambda v: is_num(v) and v > 0), ".")]
                + [national_word(team, s) for s in seasons])

    top = sorted(nat, key=lambda t: -nat[t])
    top = [t for t in top if not t.endswith(DUPLICATE)]
    national = [nat_row(i, t, kp_rank[t]) for i, t in enumerate(top[:25], 1)]
    bb = [nat_row(i, t, nat_rank[t])
          for i, t in enumerate([t for t in top if t in blue], 1)]

    cols = ["#", "Team", "CBB", "Value", "CHAMPS", "", "S16"] + seasons
    footers = (_footer_lines(b1g_tab, ["Season", "Winner"], seasons)
               + _footer_lines(ivy_tab, ["Winner"], seasons)
               + _footer_lines(s16_tab, ["NCAA Tournament"], seasons, follow=3))
    internals = {"conf_value": conf_value, "nat_rank": nat_rank,
                 "nat_value": nat_value, "rating_rank": kp_rank,
                 "rating_value": {t: lookup(kp_val, t.removesuffix(DUPLICATE))
                                  for t in nat}}
    return {"seasons": seasons, "footers": footers, "_internals": internals,
            "sections": [
        {"title": "Big Ten Conference", "columns": cols, "rows": b1g_section},
        {"title": "Ivy League", "columns": cols[:6] + ["NCAAT"] + seasons,
         "rows": ivy_section},
        {"title": "College Basketball", "columns": cols[:2] + ["KP"] + cols[3:],
         "rows": national},
        {"title": "Basketball Blue Bloods", "columns": cols, "rows": bb}]}


# ---- college hockey -----------------------------------------------------------

FF_WORDS = ((30, "CHAMPS"), (15, "Final"), (10, "Frozen"), (0.001, "n/a"))


def hky():
    b1g_tab, ecac_tab = Tab("HKY_B1G"), Tab("HKY_ECAC")
    ff_tab, seed_tab, pw_tab = Tab("HKY_FF"), Tab("HKY_seed"), Tab("HKY_PW")
    b1g_val, ecac_val = place_tab("HKY_B1G"), place_tab("HKY_ECAC")
    seed_val, ff_val = place_tab("HKY_seed"), points_tab("HKY_FF")
    pw_val = rating_tab("HKY_PW", missing=150)

    val_tab = Tab("HKY_val")
    rows = val_tab.teams()
    n_b1g, n_ecac = len(b1g_tab.teams()), len(ecac_tab.teams())
    conf_rows = rows[:n_b1g]
    ecac_rows = rows[n_b1g:n_b1g + n_ecac]
    nat_rows = rows[n_b1g + n_ecac:]
    league = {t: val_tab.cell(r, 2) for r, t in nat_rows}
    marks = {t: str(val_tab.cell(r, 3) or "") for r, t in nat_rows}

    # PairWise weighs least here: the NCAA tournament run is 70% of it.
    nat = {t: 0.1 * lookup(pw_val, t) + 0.2 * _nonzero(seed_val, t)
           + 0.7 * _nonzero(ff_val, t) - (100 - r) / 1e6 for r, t in nat_rows}
    nat_rank, nat_value = rank_desc(nat), min_max(nat)

    def nat_key(team):
        return next((t for t in nat if t.lower() == team.lower()), None)

    seasons = b1g_tab.seasons()[:5]

    def national_word(team, s):
        pts = _cell_by(ff_tab, team, s)
        for value, word in FF_WORDS:
            if pts == value:
                return word
        if is_num(pts) and pts > 0:
            return "ncaa"
        rank = _cell_by(pw_tab, team, s)
        return rank if rank is not None else 0

    def blended(r, team, conf_values):
        k = nat_key(team)
        return (0.1 * lookup(pw_val, k) + 0.1 * _nonzero(seed_val, k)
                + 0.3 * _nonzero(ff_val, k) + 0.5 * lookup(conf_values, team)
                - (100 - r) / 1e6)

    ff_cols = ff_tab.season_cols()

    def conf_section(tab, conf_rows_, conf_values, words, frozen):
        scores = {t: blended(r, t, conf_values) for r, t in conf_rows_}
        value = min_max(scores)

        def word(team, s):
            national = national_word(nat_key(team), s)
            if national == "CHAMPS":
                return "CHAMPS"
            if national in ("Final", frozen[0]):
                return frozen[1]
            return _conf_word(tab, team, s, words)

        return [[i, t, nat_rank.get(nat_key(t), 50), value[t],
                 _blank_zero(_title_count(tab, "Regular Season", "Champions x2", t), ""),
                 _blank_zero(_count_name(tab, words[2][0], t), ""),
                 _blank_zero(count_in(ff_tab, t, ff_cols[0], 10,
                                      lambda v: is_num(v) and v > 0), ".")]
                + [word(t, s) for s in tab.seasons()[:5]]
                for i, t in enumerate(sorted(scores, key=lambda x: -scores[x]), 1)]

    b1g_section = conf_section(
        b1g_tab, conf_rows, b1g_val,
        [("Champions x2", "B1G x2"), ("Regular Season", "B1G"),
         ("B1G Tournament", "BTT")], ("Frozen", "Frozen"))
    # The ECAC table tested for "F4", a word the national column never
    # writes, so a Frozen Four run showed as the ECAC finish instead.
    ecac_section = conf_section(
        ecac_tab, ecac_rows, ecac_val,
        [("Champions x2", "ECAC x2"), ("Regular Season", "ECAC"),
         ("ECAC Tournament", "ECACT"), ("Ivy League", "IVY")],
        ("F4", "F4") if SHEET_COMPAT else ("Frozen", "Frozen"))

    def nat_row(i, team, first):
        return ([i, team, first, league[team],
                 _blank_zero(count_in(ff_tab, team, ff_cols[0], 10,
                                      lambda v: v == 30), ""), None,
                 _blank_zero(count_in(ff_tab, team, ff_cols[0], 10,
                                      lambda v: is_num(v) and v > 0), ".")]
                + [national_word(team, s) for s in seasons])

    top = sorted(nat, key=lambda t: -nat[t])
    national = [nat_row(i, t, nat_value[t]) for i, t in enumerate(top[:20], 1)]
    bb = [nat_row(i, t, nat_rank[t])
          for i, t in enumerate([t for t in top if marks[t].startswith("x")], 1)]
    ccha = [nat_row(i, t, nat_rank[t])
            for i, t in enumerate([t for t in top if marks[t].endswith("c")], 1)]

    cols = ["#", "Team", "HKY", "Value", "CHAMPS", "", "NCAAT"]
    footers = (_footer_lines(b1g_tab, ["Regular Season", "B1G Tournament"], seasons)
               + _footer_lines(ecac_tab, ["ECAC Tournament", "Ivy League"], seasons)
               + _footer_lines(ff_tab, ["NCAA Tournament"], seasons, follow=3))
    b1g_scores = {t: blended(r, t, b1g_val) for r, t in conf_rows}
    internals = {"conf_value": min_max(b1g_scores), "nat_rank": nat_rank,
                 "nat_value": nat_value,
                 "pw_rank": rank_desc({t: lookup(pw_val, t) for t in nat})}
    return {"seasons": seasons, "footers": footers, "_internals": internals,
            "sections": [
        {"title": "Big Ten Conference", "columns": cols + seasons, "rows": b1g_section},
        {"title": "ECAC Hockey", "columns": cols + ecac_tab.seasons()[:5],
         "rows": ecac_section},
        {"title": "College Hockey",
         "columns": ["#", "Team", "Value", "Conf", "CHAMPS", "", "NCAAT"] + seasons,
         "rows": national},
        {"title": "Hockey Blue Bloods",
         "columns": ["#", "Team", "HKY", "Conf", "CHAMPS", "", "NCAAT"] + seasons,
         "rows": bb},
        {"title": "Original CCHA",
         "columns": ["#", "Team", "HKY", "Conf", "CHAMPS", "", "NCAAT"] + seasons,
         "rows": ccha}]}


# ---- Premier League and Europe ----------------------------------------------

UCL_WORDS = ((30, "CHAMPS"), (15, "Final"), (5, "Semis"), (3, "Qtrs"),
             (2, "R16"), (1, "KO"), (0.5, "group"))


def epl_result(table, ucl, team, s):
    """The season in league-table terms. The sheet calls a NAMED FUNCTION,
    EPL_RESULT, whose definition does not survive the export; this is it
    as reverse-engineered from every season it displayed:

        TREBLE     league, FA Cup and Champions League
        CHAMPS     league title
        n/a        not in the Premier League that season
        5+^        otherwise the place, + for an FA Cup, ^ for a League Cup
    """
    place = _cell_by(table, team, s)
    if not is_num(place):
        return "n/a"
    key = str(team).lower()
    fa = str(table.footer("FA Cup").get(s) or "").lower() == key
    lc = str(table.footer("League Cup").get(s) or "").lower() == key
    if place == 1:
        return "TREBLE" if fa and _cell_by(ucl, team, s) == 30 else "CHAMPS"
    return "%d%s%s" % (place, "+" if fa else "", "^" if lc else "")


def epl():
    table_tab, ucl_tab = Tab("EPL_table"), Tab("EPL_UCL")
    table_val = place_tab("EPL_table", bonus=["FA Cup", "League Cup"])
    # EPL_UCL's bonus rows carry their points in column B. The sheet valued
    # the SECOND Europa semi-finalist from the WINNER's cell (5, not 0.5).
    bonus = _bonus_rows(ucl_tab, ["Europa Winner", "Europa Final",
                                  "Europa Semis"], 2)
    semis2 = next(r for r in range(bonus[-1][0] + 1, len(ucl_tab.grid) + 1)
                  if ucl_tab.cell(r, 1) == "Europa Semis")
    bonus.append((semis2, bonus[0][1] if SHEET_COMPAT else ucl_tab.cell(semis2, 2)))
    bonus += _bonus_rows(ucl_tab, ["Conference Winner", "Conference Final"], 2)
    ucl_val = points_tab("EPL_UCL", bonus_rows_override=bonus)

    val_tab = Tab("EPL_val")
    rows = val_tab.teams()
    n_eng = next(i for i, (r, _t) in enumerate(rows) if val_tab.cell(r, 2) is not None)
    eng_rows, eur_rows = rows[:n_eng], rows[n_eng:]

    eur = {}
    for r, t in eur_rows:
        try:
            base = lookup(ucl_val, t)
        except KeyError:
            base = 0
        eur[t] = base + (1000 - r) / 1e6
    eur_rank, eur_value = rank_desc(eur), min_max(eur)
    league = {t: str(val_tab.cell(r, 2) or "")[:3] for r, t in eur_rows}
    super_league = {t for r, t in eur_rows if val_tab.cell(r, 3) == "x"}

    def eur_key(team):
        return next((t for t in eur if t.lower() == team.lower()), None)

    # The English table: a quarter European, three quarters domestic. The
    # European share read #REF! (zero); the value lives in EPL_val column F.
    eng = {}
    for r, t in eng_rows:
        try:
            domestic = lookup(table_val, t)
        except KeyError:
            domestic = 0
        k = eur_key(t)
        uefa = 0 if SHEET_COMPAT or k is None else eur_value[k]
        eng[t] = 0.25 * uefa + 0.75 * domestic - (100 - r) / 1e6
    thirtieth = sorted(eng.values(), reverse=True)[29]
    top = max(eng.values())
    eng_value = {t: (v - thirtieth) * 100 / (top - thirtieth) for t, v in eng.items()}

    seasons = table_tab.seasons()[:5]
    ucl_seasons = ucl_tab.seasons()[:5]
    t_cols, u_cols = table_tab.season_cols(), ucl_tab.season_cols()

    def euro_word(team, s):
        pts = _cell_by(ucl_tab, team, s)
        for value, word in UCL_WORDS:
            if pts == value:
                return word
        return pts          # blank, or typed words like "[UEL]" and "UEL*"

    order = sorted(eng, key=lambda t: -eng[t])
    english = [[i, t, eur_rank.get(eur_key(t)) if eur_key(t) else None,
                eng_value[t],
                _blank_zero(count_in(table_tab, t, t_cols[0], 10, lambda v: v == 1), ""),
                _blank_zero(count_in(ucl_tab, t, u_cols[0], 10,
                                     lambda v: is_num(v) and v > 0), "."), None]
               + [epl_result(table_tab, ucl_tab, t, s) for s in seasons]
               for i, t in enumerate(order[:20], 1)]

    def eur_row(t):
        return ([eur_rank[t], t, eur_value[t], league[t],
                 _blank_zero(count_in(ucl_tab, t, u_cols[0], 10, lambda v: v == 30), ""),
                 _blank_zero(count_in(ucl_tab, t, u_cols[0], 10,
                                      lambda v: is_num(v) and v > 0), "."), None]
                + [euro_word(t, s) for s in ucl_seasons])

    ranked = sorted(eur, key=lambda t: -eur[t])
    sl = [eur_row(t) for t in ranked if t in super_league]
    others = [eur_row(t) for t in ranked if t not in super_league]

    footers = (_footer_lines(table_tab, ["Prem", "FA Winner", "FA Loser",
                                         "EFL Winner", "EFL Loser"], seasons)
               + _footer_lines(ucl_tab, ["UCL Winners", "UCL Losers",
                                         "Europa League", "UEL Losers",
                                         "Conference League", "UECL Losers",
                                         "Spain", "Germany", "Italy", "France",
                                         "Club World Cup"], ucl_seasons))
    return {"seasons": seasons, "footers": footers, "sections": [
        {"title": "Premier League",
         "columns": ["#", "Team", "UEFA", "Value", "CHAMPS", "UCL", ""] + seasons,
         "rows": english},
        {"title": "UEFA Super League",
         "columns": ["#", "Team", "Value", "Lg", "CHAMPS", "UCL", ""] + ucl_seasons,
         "rows": sl},
        {"title": "UEFA Additional",
         "columns": ["#", "Team", "Value", "Lg", "CHAMPS", "UCL", ""] + ucl_seasons,
         "rows": others[:25]}]}


# ---- MLS and Concacaf club competitions --------------------------------------

CONCACAF_WORDS = ((30, "CHAMPS"), (15, "Final"), (5, "Semis"), (3, "Qtrs"),
                  (1, "R16"), (0.5, "R32"))


def _pts(tab, team, s):
    v = _cell_by(tab, team, s)
    return v if is_num(v) else 0


def mls_result(table, cup, ccc, lc, team, s, conf):
    """A season in MLS terms -- another NAMED FUNCTION (MLS_RESULT) that the
    export drops, reverse-engineered from what it displayed: an MLS Cup, then
    a Champions Cup, then a Leagues Cup, then how far the playoff run went,
    otherwise the conference finish."""
    c = _pts(cup, team, s)
    if c == 30:
        return "CHAMPS"
    if _pts(ccc, team, s) == 30:
        return "CCC"
    if _pts(lc, team, s) == 30:
        return "LC"
    if c == 15:
        return conf
    if c == 5:
        return "ECF" if conf == "East" else "WCF"
    if c > 0:
        return "playoff"
    return _cell_by(table, team, s)


def concacaf_result(ccc, lc, team, s):
    """(word, competition) for a club's best continental run that season --
    CONCACAF_RESULT and CONCACAF_COMPETITION, also named functions. The
    better of the Champions Cup and the Leagues Cup; Leagues Cup when
    neither was played."""
    known = ccc.row_of(team) is not None or lc.row_of(team) is not None
    if not known:
        return None, None
    a, b = _pts(ccc, team, s), _pts(lc, team, s)
    comp, pts = ("CCC", a) if a > b else ("LC", b)
    for value, word in CONCACAF_WORDS:
        if pts == value:
            return word, comp
    return None, comp


def mls():
    table_tab, cup_tab = Tab("MLS_table"), Tab("MLS_cup")
    ccc_tab, lc_tab = Tab("MLS_CCC"), Tab("MLS_LC")
    table_val = place_tab("MLS_table", median_prior=True,
                          bonus=["Leagues Champ", "Leagues Final", "Open Cup"])
    cup_val, ccc_val, lc_val = (points_tab("MLS_cup"), points_tab("MLS_CCC"),
                                points_tab("MLS_LC"))

    val_tab = Tab("MLS_val")
    rows = val_tab.teams()
    n_mls = len(table_tab.teams())
    mls_rows = rows[:n_mls]

    def get(values, t):
        try:
            return lookup(values, t)
        except KeyError:
            return 0

    combo = {t: 0.2 * get(table_val, t) + 0.6 * get(cup_val, t)
             + 0.1 * get(ccc_val, t) + 0.1 * get(lc_val, t) - (100 - r) / 1e6
             for r, t in mls_rows}
    overall, value = rank_desc(combo), min_max(combo)

    # The continental list covers Liga MX clubs too: 90% the better of the two
    # competitions, 10% the other.
    cont = {}
    for r, t in rows:
        a, b = get(ccc_val, t), get(lc_val, t)
        cont[t] = 0.9 * max(a, b) + 0.1 * min(a, b) - (100 - r) / 1e6
    cont_value = min_max(cont)

    seasons = table_tab.seasons()[:5]
    cup_cols, ccc_cols, lc_cols = (cup_tab.season_cols(), ccc_tab.season_cols(),
                                   lc_tab.season_cols())
    half = n_mls // 2
    sections = []
    for title, conf, block in (("Eastern Conference", "East", mls_rows[:half]),
                               ("Western Conference", "West", mls_rows[half:])):
        order = sorted((t for _r, t in block), key=lambda t: -combo[t])
        sections.append({
            "title": title,
            "columns": ["#", "Team", "MLS", "Value", "CHAMPS", "Semis"] + seasons,
            "rows": [[i, t, overall[t], value[t],
                      _blank_zero(count_in(cup_tab, t, cup_cols[0], 10,
                                           lambda v: v == 30), ""),
                      _blank_zero(count_in(ccc_tab, t, ccc_cols[0], 10,
                                           lambda v: is_num(v) and v >= 5)
                                  + count_in(lc_tab, t, lc_cols[0], 10,
                                             lambda v: is_num(v) and v >= 5), ".")]
                     + [mls_result(table_tab, cup_tab, ccc_tab, lc_tab, t, s, conf)
                        for s in seasons]
                     for i, t in enumerate(order, 1)]})

    cont_rows = []
    for i, t in enumerate(sorted(cont, key=lambda x: -cont[x]), 1):
        results = [concacaf_result(ccc_tab, lc_tab, t, s) for s in seasons]
        cont_rows.append(
            [i, t, overall.get(t), cont_value[t],
             _blank_zero(count_in(lc_tab, t, lc_cols[0], 10, lambda v: v == 30), ""),
             _blank_zero(count_in(ccc_tab, t, ccc_cols[0], 10, lambda v: v == 30), "")]
            + [w for w, _c in results] + [c for _w, c in results])
    sections.append({"title": "Leagues / Concacaf",
                     "columns": ["#", "Team", "MLS", "Value", "LC", "CCC"] + seasons,
                     "rows": cont_rows})
    footers = _footer_lines(table_tab, ["MLS Cup", "Open", "Leagues", "Champions"],
                            seasons, follow=1)
    return {"seasons": seasons, "footers": footers, "sections": sections}


# ---- NCAA: every sport at once ------------------------------------------------

def _get(d, name, default=None):
    """A case-blind dict lookup, for names written DETROIT in one tab and
    Detroit in the next."""
    key = str(name).lower()
    return next((v for k, v in d.items() if str(k).lower() == key), default)


def ncaa():
    """Schools across sports. The Big Ten table weighs a school's football and
    basketball conference Values, 55% the better and 45% the other; the
    national list does the same with national RANKS, lower being better, so
    a school without football is charged its basketball rank plus 100."""
    f, b, h = cfb()["_internals"], cbb()["_internals"], hky()["_internals"]
    cfb_b1g, cbb_b1g = Tab("CFB_B1G"), Tab("CBB_B1G")
    cfp_tab, s16_tab = Tab("CFB_CFP"), Tab("CBB_sweet16")
    cws_rank = rank_desc(points_tab("NCAAB_CWS"))
    bb_rank = rank_desc(place_tab("NCAAB_B1G",
                                  bonus=["Outright Champion", "B1G Tournament"]))

    val_tab = Tab("NCAA_val")
    rows = val_tab.teams()
    n_b1g = len(cfb_b1g.teams())
    b1g_rows, nat_rows = rows[:n_b1g], rows[n_b1g:]
    conf_of = {t: val_tab.cell(r, 2) for r, t in rows}

    def avg(*xs):
        return sum(xs) / len(xs)

    # National: lower is better. Only schools with a football or basketball
    # ranking are placed -- the hockey-only rows at the bottom are not.
    k = {}
    for r, t in nat_rows:
        c, e = _get(f["nat_rank"], t), _get(b["nat_rank"], t)
        if c is None and e is None:
            # The hockey-only schools appended at the bottom. In the sheet
            # nothing below the first of them was ranked at all -- Cal State
            # Fullerton included, though it has a basketball ranking.
            if SHEET_COMPAT:
                break
            continue
        e = 300 if e is None else e
        c = 100 + e if c is None else c
        k[t] = (0.55 * min(c, e) + 0.45 * max(c, e)
                + avg(_get(f["rating_rank"], t, 150),
                      _get(b["rating_rank"], t, 300)) / 1000
                + (100 - r) / 1e9)
    order = sorted(k, key=lambda t: k[t])
    nat_rank = {t: i for i, t in enumerate(order, 1)}
    k45, kmin = sorted(k.values(), reverse=True)[44], min(k.values())
    nat_value = {t: (k45 - v) / (k45 - kmin) * 100 for t, v in k.items()}

    def titles(t):
        """CFP plus NCAA tournament titles; a school missing from a tab has
        none there."""
        return sum(count_in(tab, t, tab.season_cols()[0], 10, lambda v: v == 30)
                   for tab in (cfp_tab, s16_tab))

    def addtl(t):
        rank = _get(h["nat_rank"], t)
        return rank if rank is not None else _get(cws_rank, t)

    counts, national = {}, []
    for t in order[:125]:
        conf = conf_of[t]
        if conf:
            counts[conf] = counts.get(conf, 0) + 1
        national.append([nat_rank[t], t, _blank_zero(titles(t), ""),
                         _get(f["nat_rank"], t), _get(b["nat_rank"], t, 300),
                         nat_value[t], _get(f["rating_rank"], t, 150),
                         _get(b["rating_rank"], t, 300), addtl(t), conf,
                         counts.get(conf) if conf else None])

    # The Big Ten
    cfb_rank, cbb_rank = rank_desc(f["conf_value"]), rank_desc(b["conf_value"])
    ck = {}
    for r, t in b1g_rows:
        d, fv = _get(f["conf_value"], t), _get(b["conf_value"], t)
        ck[t] = (0.55 * max(d, fv) + 0.45 * min(d, fv)
                 + avg(_get(f["rating_value"], t, 0),
                       _get(b["rating_value"], t, 0)) / 1000
                 + (100 - r) / 1e9)
    b1g_value = min_max(ck)
    hockey = {}
    for t in ck:
        n, o = _get(h["conf_value"], t), _get(h["pw_rank"], t)
        if n is not None and o is not None:
            hockey[t] = 0.8 * n + 0.2 * o
    hockey_rank = rank_desc(hockey)

    def b1g_titles(t):
        return (_count_name(cfb_b1g, "B1G Champion", t)
                + _title_count(cbb_b1g, "Outright Champion", "Champions x2", t))

    b1g = [[i, t, _blank_zero(b1g_titles(t), ""), _get(nat_rank, t),
            _get(cfb_rank, t), _get(cbb_rank, t), b1g_value[t],
            _get(f["rating_rank"], t, 130), _get(b["rating_rank"], t, 300),
            hockey_rank.get(t), _get(bb_rank, t)]
           for i, t in enumerate(sorted(ck, key=lambda x: -ck[x]), 1)]
    return {"seasons": [], "footers": [], "sections": [
        {"title": "Big Ten Combined",
         "columns": ["#", "Team", "CHAMPS", "NCAA", "CFB", "CBB", "Value",
                     "SP+", "KP", "HKY", "CWS"], "rows": b1g},
        {"title": "NCAA Combined",
         "columns": ["#", "Team", "CHAMPS", "CFB", "CBB", "Value", "SP+",
                     "KP", "ADDTL", "Conf", "Rank"], "rows": national}]}


# ---- Concacaf national teams -------------------------------------------------

WC_WORDS = ((30, "CHAMPS"), (15, "Final"), (10, "Semis"), (8, "Qtr"),
            (5, "R16"), (2, "Group"))
CUP_WORDS = ((30, "CHAMPS"), (15, "Final"), (5, "Semis"), (3, "Qtr"),
             (1, "group"))


def _word(pts, words, other=None):
    for value, word in words:
        if pts == value:
            return word
    return other if other and is_num(pts) and pts > 0 else None


def concacaf():
    wc_tab, gc_tab, nl_tab = Tab("Concacaf_WC"), Tab("Concacaf_GC"), Tab("Concacaf_NL")
    wc_val, gc_val, nl_val = (points_tab("Concacaf_WC"), points_tab("Concacaf_GC"),
                              points_tab("Concacaf_NL"))
    nl_rank = rank_desc(nl_val)

    def get(values, t):
        return _get(values, t, 0)

    val_tab = Tab("Concacaf_val")
    combo = {t: 0.5 * get(wc_val, t) + 0.4 * get(gc_val, t) + 0.1 * get(nl_val, t)
             + r / 1e6 + (100 - r) / 1e9 for r, t in val_tab.teams()}
    overall, value = rank_desc(combo), min_max(combo)

    wc_s, gc_s, nl_s = wc_tab.seasons()[:2], gc_tab.seasons()[:3], nl_tab.seasons()[:4]
    events = dict(zip(gc_tab.seasons(), gc_tab.values(2, gc_tab.season_cols())))

    tournaments = [
        [i, t, value[t], _get(nl_rank, t)]
        + [_word(_cell_by(wc_tab, t, s), WC_WORDS, "wcq") for s in wc_s]
        + [_word(_cell_by(gc_tab, t, s), CUP_WORDS) for s in gc_s]
        for i, t in enumerate(sorted(combo, key=lambda x: -combo[x])[:20], 1)]
    nations = [
        [i, t, nl_val[t], _get(overall, t)]
        + [_word(_cell_by(nl_tab, t, s), CUP_WORDS) for s in nl_s]
        for i, t in enumerate(sorted(nl_val, key=lambda x: -nl_val[x])[:20], 1)]

    gold = [s for s in gc_tab.seasons() if events.get(s) == "Gold"][:5]
    footers = (_footer_lines(gc_tab, ["Gold Cup"], gold, follow=1)
               + _footer_lines(wc_tab, ["World Cup"], wc_tab.seasons()[:5], follow=1)
               + _footer_lines(nl_tab, ["Nations League"], nl_s, follow=1))
    return {"seasons": [], "footers": footers, "sections": [
        {"title": "Tournaments",
         "columns": ["#", "Team", "Value", "CNL"] + wc_s
                    + ["%s %s" % (s, events.get(s) or "") for s in gc_s],
         "rows": tournaments},
        {"title": "Nations League",
         "columns": ["#", "Team", "Value", "Ovr"] + nl_s, "rows": nations}]}
