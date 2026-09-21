"""Prove rankings.py against the sheet it replaced, cell by cell.

rankings/expected/ holds every value the sheet's visible tabs displayed when
they were imported. With SHEET_COMPAT on, rankings.py must reproduce all of
them; this module knows which sheet rows each table landed on. selftest.py
runs it, and so can you:

    python rankings_proof.py

The row maps carry the sheet's own layout quirks, each noted where it
applies: display gaps, a skipped #21, a typed-over row, formulas that were
never filled down. None of those are carried into the app.
"""

import csv
import os

import rankings

EXPECTED = os.path.join(rankings.HERE, "rankings", "expected")


def _expected(tab):
    with open(os.path.join(EXPECTED, tab + ".csv"), encoding="utf-8") as f:
        return list(csv.reader(f))


def _same(got, want):
    if got in (None, "") and want in ("", "0"):
        return True
    want = want.lstrip("'")
    try:
        return abs(float(got) - float(want)) < 1e-6
    except (TypeError, ValueError):
        return str(got).removesuffix(".0") == want


def compare(tab, rows, first_col, sheet_rows, report=None):
    """Mismatched cells between our rows and the sheet's, placed from
    first_col (0-based) on the given sheet rows."""
    grid, bad = _expected(tab), 0
    for row, sheet_row in zip(rows, sheet_rows):
        want = grid[sheet_row - 1][first_col:first_col + len(row)]
        for j, (a, b) in enumerate(zip(row, want)):
            if not _same(a, b):
                bad += 1
                if report is not None:
                    report.append("%s r%d c%d: got %r, sheet has %r (%s)"
                                  % (tab, sheet_row, first_col + j + 1, a, b, row[1]))
    return bad


def _rows(out):
    return [s["rows"] for s in out["sections"]]


def checks():
    """[(name, mismatches, report)] -- one per table the sheet displayed."""
    old = rankings.SHEET_COMPAT
    rankings.SHEET_COMPAT = True
    try:
        return list(_checks())
    finally:
        rankings.SHEET_COMPAT = old


def _checks():
    def run(name, tab, rows, col, sheet_rows):
        report = []
        return name, compare(tab, rows, col, sheet_rows, report), report

    for sport in ("NFL", "MLB", "NBA", "NHL"):
        a, b = _rows(rankings.pro(sport))
        n = len(a)
        yield run(sport + " first conference", sport, a, 0, range(2, 2 + n))
        yield run(sport + " second conference", sport, b, 12, range(2, 2 + len(b)))

    b1g, nat, bb = _rows(rankings.cfb())
    yield run("CFB Big Ten", "CFB", b1g, 0, range(2, 20))
    # The sheet's list skips #21: row 22 is a gap, but the formula beneath it
    # still counts ROW-1, so rows 23-26 show ranks 22-25 under typed 21-24.
    yield run("CFB national 1-20", "CFB", nat[:20], 13, range(2, 22))
    yield run("CFB national 22-25", "CFB", [r[1:] for r in nat[21:25]], 14,
              range(23, 27))
    yield run("CFB blue bloods", "CFB", bb, 13, [31, 32, 33, 34, 36, 37, 38, 39])

    b1g, ivy, nat, bb = _rows(rankings.cbb())
    yield run("CBB Big Ten", "CBB", b1g, 0, range(2, 20))
    yield run("CBB Ivy", "CBB", ivy, 0, range(23, 31))
    yield run("CBB national", "CBB", nat, 13, list(range(2, 22)) + list(range(23, 28)))
    yield run("CBB blue bloods", "CBB", bb, 13, [31, 32, 33, 35, 36, 37, 38, 39])

    b1g, ecac, nat, bb, ccha = _rows(rankings.hky())
    yield run("HKY Big Ten", "HKY", b1g, 0, range(2, 9))
    yield run("HKY ECAC", "HKY", ecac, 0, range(12, 24))
    # Row 21 is typed over by hand (Alaska Anchorage), so #19 is skipped.
    yield run("HKY national", "HKY", nat[:18] + nat[19:], 13,
              list(range(2, 12)) + list(range(13, 21)) + [22])
    yield run("HKY blue bloods", "HKY", bb, 13, [26, 28, 29, 30, 31, 32])
    yield run("HKY original CCHA", "HKY", ccha, 13,
              [36, 37, 38, 39, 40, 41, 42, 44, 45, 46, 47, 48])

    eng, sl, other = _rows(rankings.epl())
    yield run("EPL table", "EPL", eng, 0, list(range(2, 20)) + [21, 22])
    yield run("EPL super league", "EPL", sl, 13, range(2, 17))
    yield run("EPL additional", "EPL", other, 13,
              [20, 21, 22, 23, 24, 26, 27, 28, 29, 30, 31, 32, 34, 35, 36, 37,
               38, 39, 40, 41, 43, 44, 45, 46, 47])

    east, west, cont = _rows(rankings.mls())
    yield run("MLS East", "MLS", east, 0, range(2, 17))
    yield run("MLS West", "MLS", west, 0, range(17, 32))
    yield run("MLS continental 1-32", "MLS", cont[:32], 12, range(2, 34))
    # Row 34's competition cells sit one row low in the sheet, and below
    # row 44 the competition formulas were never filled down.
    yield run("MLS continental 33", "MLS", [r[:11] for r in cont[32:33]], 12, [34])
    yield run("MLS continental 34-41", "MLS", cont[33:41], 12,
              list(range(36, 42)) + [43, 44])
    yield run("MLS continental 42+", "MLS", [r[:11] for r in cont[41:]], 12,
              range(45, 52))

    b1g, nat = _rows(rankings.ncaa())
    yield run("NCAA Big Ten", "NCAA", b1g, 0, range(2, 20))
    yield run("NCAA 1-25", "NCAA", nat[:25], 0, range(27, 52))
    yield run("NCAA 26-75", "NCAA", nat[25:75], 12, range(2, 52))
    yield run("NCAA 76-125", "NCAA", nat[75:125], 24, range(2, 52))

    tourn, nations = _rows(rankings.concacaf())
    yield run("Concacaf tournaments", "Concacaf", tourn, 0, range(3, 23))
    yield run("Concacaf Nations League", "Concacaf", nations, 10, range(3, 23))


if __name__ == "__main__":
    total = 0
    for name, bad, report in checks():
        total += bad
        print("  %-4s %s" % ("ok" if not bad else "%d" % bad, name))
        for line in report[:10]:
            print("         " + line)
    print("mismatched cells: %d" % total)
