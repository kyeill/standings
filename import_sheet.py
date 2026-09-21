"""One-time import of Kyle's rankings spreadsheet into rankings/.

The sheet (link-shared, read without signing in) is where the historical
rankings used to live: hand-entered finishes per season in hidden tabs, and
formulas turning them into a 0-100 Value per team. The app now computes those
Values itself (rankings.py), so the sheet is being retired. This copies what
he TYPED so nothing is lost, and what the formulas PRODUCED so the Python can
be proven against it.

    rankings/inputs/<tab>.csv     constants only -- every formula cell blank
    rankings/expected/<tab>.csv   every cell's computed value, as the sheet
                                  last showed it; the answer key for selftest

Run it again only while the sheet is still the source (before the app fills
new seasons itself) -- afterwards it would overwrite app-written results.

Needs openpyxl, which the build does NOT: this runs locally, once. The xlsx
export is used rather than CSV because only the xlsx carries formulas, and
the formula/constant split is the whole point.
"""

import csv
import io
import os
import re
import sys

import requests

SHEET = "1Eb3XIu2fzVR_Dk_xRpbvrGw_5GFq-iLhBOMEUpOnikg"
URL = "https://docs.google.com/spreadsheets/d/%s/export?format=xlsx" % SHEET
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "rankings")

# Everything after the ">>>" divider (cur_*, B1G, Prem) is a separate
# in-season scratchpad that feeds none of the ranking tabs, and Sheet3/Sheet4,
# ">" and the Ivy_* tabs feed nothing either. The rest is imported.
SKIP = {"Sheet3", "Sheet4", ">", ">>", ">>>", "B1G", "Prem", "cur_val",
        "cur_CFP", "cur_CBB", "cur_KP", "cur_seed", "cur_SP+", "cur_val II",
        "cur_odds", "cur_EPL", "cur_UEFA", "cur_elo", "Ivy_val", "Ivy_CFB",
        "Ivy_SP+"}


def _cell(value):
    """A cell as text. A NUMBER STORED AS TEXT keeps a leading apostrophe,
    the way Sheets itself shows one: the sheet's SUM and MAX skip such cells
    (a few SP+ ranks were pasted as text), so the Python has to be able to
    tell them apart to reproduce the sheet exactly -- and then to fix it."""
    if value is None:
        return ""
    if isinstance(value, str) and re.fullmatch(r"\s*-?\d+(\.\d+)?\s*", value):
        return "'" + value.strip()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _write(path, rows):
    # Trailing empty rows and columns are trimmed so a diff shows real change.
    while rows and not any(rows[-1]):
        rows.pop()
    width = max((max((i + 1 for i, v in enumerate(r) if v), default=0)
                 for r in rows), default=0)
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([r[:width] for r in rows])


def main():
    import openpyxl
    from openpyxl.worksheet.formula import ArrayFormula

    data = requests.get(URL, timeout=120).content
    if not data.startswith(b"PK"):
        sys.exit("the sheet did not come back as xlsx -- is it still link-shared?")
    formulas = openpyxl.load_workbook(io.BytesIO(data))
    values = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    for sub in ("inputs", "expected"):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)

    for ws in formulas.worksheets:
        if ws.title in SKIP:
            continue
        wv = values[ws.title]
        inputs, expected = [], []
        header = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
        # A formula INSIDE the season columns is data, not machinery: HKY_PW
        # fills the 2020-21 season the Ivies skipped with =AVERAGE() of the
        # next three. Those are kept as written; rankings.py evaluates them.
        seasons_from = (header.index("Prior 5 Yr") + 2
                        if "Prior 5 Yr" in header else ws.max_column + 1)
        for r in range(1, ws.max_row + 1):
            irow, erow = [], []
            for c in range(1, ws.max_column + 1):
                raw = ws.cell(r, c).value
                text = raw.text if isinstance(raw, ArrayFormula) else raw
                is_formula = isinstance(text, str) and text.startswith("=")
                if is_formula and r > 1 and c >= seasons_from:
                    irow.append(text)
                    erow.append(_cell(wv.cell(r, c).value))
                    continue
                irow.append("" if is_formula else _cell(raw))
                erow.append(_cell(wv.cell(r, c).value))
            inputs.append(irow)
            expected.append(erow)
        name = ws.title.replace("+", "plus")
        _write(os.path.join(OUT, "inputs", name + ".csv"), inputs)
        _write(os.path.join(OUT, "expected", name + ".csv"), expected)
        print("%-16s %s" % (ws.title, ws.sheet_state))


if __name__ == "__main__":
    main()
