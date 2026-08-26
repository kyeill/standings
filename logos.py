"""Pick a readable crest for every team, and record the exceptions.

    python logos.py            report what would change
    python logos.py --write    write logo-overrides.json

The same problem, and the same answer, as sports-daily's logos.py: ESPN's
`-dark` crest is usually right on a dark page, but for some clubs it is a flat
white silhouette -- Liverpool and Tottenham are both pure white, so at 19px
they are indistinguishable. This measures the actual pixels of both 500px
variants and picks per team:

  * the dark variant when it carries colour
  * otherwise the default variant, if it is light enough to read
  * otherwise the dark one anyway -- some crests read badly either way

Deliberately NOT imported from sports-daily: the two projects share no code.
The thresholds and the decision below are copied because they were arrived at
by measurement there, and re-deriving them would only risk getting them wrong.

Run this by hand when the tracked teams change; the daily build just reads the
JSON. Measurements are cached, so a re-run only fetches what is new.
"""

import json
import os
import struct
import sys
import zlib

import requests

import build
import leagues

HERE = os.path.dirname(os.path.abspath(__file__))
# Source data, not build output: `output/` is gitignored.
OVERRIDES = os.path.join(HERE, "logo-overrides.json")
CACHE = os.path.join(HERE, "output", "logo-measurements.json")

COLOURLESS = 0.15      # mean saturation below this reads as a silhouette
TOO_DARK = 60          # mean luminance below this disappears on #16161a
FLAT = 40              # channel spread below this is a black/grey crest


def read_png(data):
    """Minimal 8-bit PNG reader -> (width, height, pixels, channels).

    Most ESPN crests are colour type 6 at depth 8; a few are palette images
    (type 3), expanded to RGBA here. Anything else returns None rather than
    guessing.
    """
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos, idat, width = 8, [], None
    palette = trns = None
    channels = 3
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        if tag == b"IHDR":
            width, height, depth, ctype = struct.unpack(">IIBB", chunk[:10])
            if depth != 8 or ctype not in (2, 3, 6):
                return None
            channels = {6: 4, 3: 1}.get(ctype, 3)
        elif tag == b"PLTE":
            palette = chunk
        elif tag == b"tRNS":
            trns = chunk
        elif tag == b"IDAT":
            idat.append(chunk)
        elif tag == b"IEND":
            break
        pos += 12 + length
    if width is None:
        return None

    raw = zlib.decompress(b"".join(idat))
    stride = width * channels
    out, prev, at = [], bytearray(stride), 0
    for _ in range(height):
        filt = raw[at]
        at += 1
        line = bytearray(raw[at:at + stride])
        at += stride
        # Undo the per-scanline filter; this is the whole of PNG decoding.
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b = prev[i]
            c = prev[i - channels] if i >= channels else 0
            if filt == 1:
                line[i] = (line[i] + a) & 0xFF
            elif filt == 2:
                line[i] = (line[i] + b) & 0xFF
            elif filt == 3:
                line[i] = (line[i] + (a + b) // 2) & 0xFF
            elif filt == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else
                                      b if pb <= pc else c)) & 0xFF
        out.append(bytes(line))
        prev = line

    if channels == 1:
        if not palette:
            return None
        rgba = bytearray()
        for line in out:
            for index in line:
                start = index * 3
                rgba += palette[start:start + 3]
                rgba.append(trns[index] if trns and index < len(trns) else 255)
        return width, height, bytes(rgba), 4

    return width, height, b"".join(out), channels


_seen = {}


def _load_cache():
    if os.path.exists(CACHE):
        try:
            with open(CACHE, encoding="utf-8") as fh:
                _seen.update(json.load(fh))
        except (OSError, ValueError):
            pass


def _save_cache():
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as fh:
        json.dump(_seen, fh, indent=0, sort_keys=True)


def _pixels(url, session):
    try:
        data = session.get(url, timeout=20).content
    except Exception:
        return None
    return read_png(data)


def measure(url, session):
    """(saturation, luminance, r, g, b) over the opaque pixels, or None."""
    if url in _seen:
        got = _seen[url]
        return tuple(got) if got else None
    parsed = _pixels(url, session)
    got = None
    if parsed:
        _, _, pixels, channels = parsed
        sat = lum = 0.0
        totals = [0, 0, 0]
        count = 0
        for i in range(0, len(pixels) - channels, channels * 7):
            if channels == 4 and pixels[i + 3] < 128:
                continue
            r, g, b = pixels[i], pixels[i + 1], pixels[i + 2]
            top, bottom = max(r, g, b), min(r, g, b)
            sat += (top - bottom) / top if top else 0
            lum += 0.2126 * r + 0.7152 * g + 0.0722 * b
            for c in range(3):
                totals[c] += pixels[i + c]
            count += 1
        if count:
            got = (sat / count, lum / count,
                   totals[0] / count, totals[1] / count, totals[2] / count)
    _seen[url] = list(got) if got else None
    return got


def choose(dark_url, default_url, session):
    """-> (url, why). The rule sports-daily arrived at by measurement."""
    dark = measure(dark_url, session)
    if dark and dark[0] >= COLOURLESS:
        return dark_url, "dark variant has colour"
    plain = measure(default_url, session)
    if plain and plain[1] >= TOO_DARK:
        return default_url, "dark variant is a silhouette; default reads"
    if plain:
        r, g, b = plain[2], plain[3], plain[4]
        spread = max(r, g, b) - min(r, g, b)
        if spread < FLAT:
            return dark_url, "black or grey; stays white"
        # Blue-dominant is not the same as navy. Navy runs r < g < b; purple
        # runs g < r < b and reads perfectly well on #16161a.
        if b > r and b > g and g >= r:
            return dark_url, "navy; stays white"
        return default_url, "dark but coloured; default reads"
    return dark_url, "unreadable either way; left alone"


def every_team():
    """{team name: default logo url} for everything the app can display."""
    out = {}
    data = build.build_all(include_offseason=True)
    for tab in data["tabs"]:
        rows = [r for card in tab["cards"] for sec in card.get("sections") or []
                for r in sec["rows"]]
        rows += [r for t in tab["tables"] for r in t["rows"]]
        for row in rows:
            logo = (row.get("logo") or "").replace("/500-dark/", "/500/")
            if logo and row.get("team"):
                out.setdefault(row["team"], logo)
    return out


def main(argv=None):
    argv = argv or sys.argv[1:]
    _load_cache()
    session = requests.Session()
    session.headers.update({"Accept": "*/*"})
    teams = every_team()
    print("measuring %d teams" % len(teams))
    overrides, reasons = {}, {}
    for i, (name, default_url) in enumerate(sorted(teams.items()), 1):
        dark_url = default_url.replace("/500/", "/500-dark/")
        pick, why = choose(dark_url, default_url, session)
        reasons[why] = reasons.get(why, 0) + 1
        if pick != dark_url:
            overrides[name] = pick
        if i % 40 == 0:
            print("  %d/%d" % (i, len(teams)))
            _save_cache()
    _save_cache()
    print("\nwhy each crest was picked:")
    for why, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print("  %-46s %3d" % (why, n))
    print("\n%d teams need the DEFAULT variant:" % len(overrides))
    for name in sorted(overrides)[:20]:
        print("   ", name)
    if len(overrides) > 20:
        print("    ... and %d more" % (len(overrides) - 20))
    if "--write" in argv:
        os.makedirs(os.path.dirname(OVERRIDES), exist_ok=True)
        with open(OVERRIDES, "w", encoding="utf-8") as fh:
            json.dump(overrides, fh, indent=1, sort_keys=True)
        print("\nwrote %s" % OVERRIDES)
    else:
        print("\n(dry run -- pass --write to save)")


if __name__ == "__main__":
    main()
