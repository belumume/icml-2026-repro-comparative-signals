"""Fail if HANDOFF.md has drifted from the repository it describes.

The operator's standing requirement: "if we compact, the handoff shouldn't be stale."
Discipline alone does not deliver that. A handoff goes stale silently, by construction:
the work moves, the file does not, and nothing errors. It reads as authoritative right up
until a fresh session acts on a fact that stopped being true hours ago.

So this converts "is the handoff current" from a judgement into a check with an exit code.
It verifies four classes of drift, chosen because each one has actually bitten:

  1. DEAD PATHS. Every file the handoff names must exist. A resume procedure that points
     at a moved or renamed script fails at exactly the moment nobody has context.
  2. STALE IN-FLIGHT STATE. Words like RUNNING or DELEGATED are claims about right now.
     They were true when written and are the first thing to rot.
  3. NUMBERS THAT NO LONGER MATCH THEIR SOURCE. Headline figures are re-derived from the
     JSON rather than trusted, because a handoff quoting a superseded number is worse
     than one quoting none: it is confidently wrong.
  4. AN OLDER TIMESTAMP THAN THE WORK. If artifacts changed after the handoff was last
     touched, something happened that it does not describe.

Exit 0 means checked, not merely present.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HANDOFF = ROOT / "HANDOFF.md"
RAW = ROOT / "kaggle" / "real_data_ppi" / "out" / "real_gsm8k_ppi.json"

# Artifacts whose change implies the handoff should have been touched too.
WATCH = [
    ROOT / "tools" / "write_content.py",
    ROOT / "SUBMISSION.md",
    ROOT / "POST-BRIEF.md",
    ROOT / "work" / "poster_build" / "poster.html",
]

STALE_WORDS = re.compile(
    r"\b(RUNNING|IN FLIGHT|DELEGATED|pending|still running|watched by)\b", re.I
)
# a repo-relative path token, e.g. work/analysis/foo.py or tools/bar.py
PATH_TOKEN = re.compile(r"`((?:tools|work|kaggle|logbook|data)/[A-Za-z0-9_./-]+)`")

fails, warns = [], []


def bad(msg, detail=""):
    print(f"  STALE {msg}{(' -- ' + detail) if detail else ''}")
    fails.append(msg)


def warn(msg, detail=""):
    print(f"  WARN  {msg}{(' -- ' + detail) if detail else ''}")
    warns.append(msg)


def ok(msg, detail=""):
    print(f"  OK    {msg}{(' -- ' + detail) if detail else ''}")


def main():
    if not HANDOFF.is_file():
        print("HANDOFF.md missing entirely")
        return 1
    text = HANDOFF.read_text(encoding="utf-8")
    print(f"HANDOFF.md {len(text):,} B\n")

    # --- 1. dead paths ------------------------------------------------------
    print("1. PATHS THE HANDOFF NAMES")
    paths = sorted(set(PATH_TOKEN.findall(text)))
    missing = [p for p in paths if not (ROOT / p).exists()]
    for p in missing:
        bad(f"dead path: {p}")
    if not missing:
        ok(f"all {len(paths)} named paths exist")

    # --- 2. in-flight language ----------------------------------------------
    print("\n2. IN-FLIGHT CLAIMS (true when written, first to rot)")
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        if STALE_WORDS.search(line) and not line.lstrip().startswith(">"):
            hits.append((i, line.strip()[:100]))
    if hits:
        for i, line in hits:
            warn(f"line {i} asserts live state", line)
        print("      Each needs re-confirming or rewording to a past-tense fact.")
    else:
        ok("no unqualified live-state claims")

    # --- 3. numbers vs their source -----------------------------------------
    print("\n3. HEADLINE NUMBERS RE-DERIVED FROM SOURCE")
    if RAW.is_file():
        d = json.load(open(RAW, encoding="utf-8"))
        for m in d["models"]:
            short = m["model"].split("/")[-1]
            lo, hi = m["improv_ci95_pp"]
            for val, label in [
                (f"{m['improv_mean_pp']:+.2f}", f"{short} mean"),
                (f"{lo:.2f}".replace("-", "−"), f"{short} spread low"),
                (f"+{hi:.2f}", f"{short} spread high"),
                (f"{m['aux_auroc']:.3f}", f"{short} AUROC"),
            ]:
                (ok if val in text else bad)(f"{label} = {val}")
    else:
        warn("raw result JSON absent; numbers unverifiable")

    # --- 4. timestamp vs the work -------------------------------------------
    print("\n4. TIMESTAMP VS THE ARTIFACTS")
    m = re.search(r"Last updated:\s*(\d{4}-\d{2}-\d{2})[^\n]*?(\d{2}):(\d{2})", text)
    if not m:
        bad("no parseable 'Last updated:' line")
    else:
        stamp = datetime(
            *map(int, m.group(1).split("-")),
            int(m.group(2)),
            int(m.group(3)),
            tzinfo=timezone.utc,
        )
        ok(f"handoff stamped {stamp:%Y-%m-%d %H:%M} UTC")
        newer = []
        for f in WATCH:
            if not f.is_file():
                continue
            mt = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mt > stamp:
                newer.append((f.name, mt))
        for name, mt in sorted(newer, key=lambda x: -x[1].timestamp()):
            warn(f"{name} changed at {mt:%H:%M} UTC, after the handoff was stamped")
        if not newer:
            ok("no watched artifact is newer than the handoff")

    print()
    if fails:
        print(f"{len(fails)} STALE, {len(warns)} to re-confirm. Fix before compacting.")
        return 1
    if warns:
        print(f"0 stale, {len(warns)} claim(s) to re-confirm by hand.")
        return 0
    print("handoff is consistent with the repository it describes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
