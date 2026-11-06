"""Print a dated trend radar and flag entries read too long ago.

    python -m ch25.radar [on YYYY-MM-DD] [file PATH]

Each entry names a trend, its ring (use, try, watch, hold), its
label (fact, claim, forecast), the source it came from, the date
the source was published, and the date someone last read it. An
entry read more than stale_days before the day of the run is
flagged STALE: read the source again before you plan on it.
"""
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
RADAR = HERE / "radar.json"
TODAY = date(2026, 11, 4)
RINGS = ("use", "try", "watch", "hold")
LABELS = ("fact", "claim", "forecast")
NEEDS = ("id", "trend", "ring", "label", "source", "url",
         "published", "read", "says", "skill")
KEYS = {"on", "file"}
USAGE = "usage: python -m ch25.radar [on YYYY-MM-DD] [file PATH]"


def load(path):
    with open(path) as fh:
        return json.load(fh)


def problems(radar):
    """Return one line for each missing field, bad value, or date."""
    found, seen = [], set()
    for n, e in enumerate(radar["entries"]):
        name = e.get("id", f"entry {n}")
        found += [f"{name}: no {key}" for key in NEEDS
                  if not e.get(key)]
        if name in seen:
            found.append(f"{name}: id used twice")
        seen.add(name)
        if e.get("ring") and e["ring"] not in RINGS:
            found.append(f"{name}: ring {e['ring']} not in {RINGS}")
        if e.get("label") and e["label"] not in LABELS:
            found.append(f"{name}: label {e['label']} not in {LABELS}")
        if e.get("url") and not e["url"].startswith("https://"):
            found.append(f"{name}: url is not https")
        days = {}
        for key in ("published", "read"):
            try:
                days[key] = date.fromisoformat(e.get(key, ""))
            except ValueError:
                found.append(f"{name}: bad {key} {e.get(key)!r}")
        if len(days) == 2 and days["read"] < days["published"]:
            found.append(f"{name}: read before published")
    return found


def age(entry, on=TODAY):
    """Days between the last read and the day of the run."""
    return (on - date.fromisoformat(entry["read"])).days


def stale(entry, on=TODAY, days=90):
    """True when the entry was read more than `days` days before."""
    return age(entry, on) > days


def report(radar, on=TODAY):
    """Return the radar as lines, one ring at a time."""
    days = radar["stale_days"]
    out = [f"Radar {radar['radar']}, as of {on}, stale after "
           f"{days} days.",
           f"  {'ID':<16}{'LABEL':<9}{'SRC':<7}{'PUBLISHED':<12}"
           f"{'READ':<12}{'AGE':>4}"]
    old = 0
    for ring in RINGS:
        out.append(ring.upper())
        for e in radar["entries"]:
            if e["ring"] != ring:
                continue
            flag = "  STALE" if stale(e, on, days) else ""
            old += bool(flag)
            out.append(f"  {e['id']:<16}{e['label']:<9}"
                       f"{e['source']:<7}{e['published']:<12}"
                       f"{e['read']:<12}{age(e, on):>4}{flag}")
    total = len(radar["entries"])
    out.append(f"{old} of {total} entries stale: read them again "
               "before you plan on them.")
    return out


def main(argv):
    opts = dict(zip(argv[::2], argv[1::2]))
    if len(argv) % 2 or set(opts) - KEYS:
        print(USAGE)
        return 2
    radar = load(opts.get("file", RADAR))
    on = date.fromisoformat(opts.get("on", TODAY.isoformat()))
    bad = problems(radar)
    if bad:
        print("\n".join(bad))
        return 1
    print("\n".join(report(radar, on)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
