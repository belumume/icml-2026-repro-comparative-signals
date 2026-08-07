"""Build `results/` from the live outputs, so the published results cannot go stale.

WHY THIS EXISTS
---------------
`stage_code.py` exists because `code_publish/` was hand-staged once and then drifted from
its sources in both directions with nothing to notice. `results/` had the identical
defect, on the more load-bearing directory: every headline number in the logbook derives
from `results/*.json`, `verify_headlines.py` reads them to re-derive all 36 figures, and
the twelve files on the Space were put there BY HAND. `tools/publish_all.py` had zero
occurrences of the string "results" -- it published the pages, the evidence CSVs, the
code tree and the README, and never once touched the data every claim rests on.

So a re-run of the sweep that changed a number would update `work/analysis/*.json`
locally, the logbook prose would be regenerated from it, and the published `results/`
would keep serving the OLD JSON to anyone who checked. The reader doing the most
diligent possible thing -- downloading the raw results and recomputing -- is exactly the
reader that silent drift lies to.

THE MANIFEST IS DERIVED, NOT ENUMERATED
---------------------------------------
`stage_code.py` shipped a hand-written list of files and was structurally blind in one
direction: it verified that every manifest ENTRY exists, and never that every gate was IN
the manifest, so three gates written after the list was authored went unpublished while
the run reported success. A second hand-written list here would inherit that defect
exactly. So the set is globbed from the source directories, and the control below derives
its expectation from `verify_headlines.py` itself -- the actual consumer -- rather than
from anything a human keeps in sync.

Destination is the repository ROOT, not `code_publish/`. Two reasons, both load-bearing:
`RESULTS_BASE` in write_content.py points at `<space>/tree/main/results`, so the
published path is the Space root and moving it would break every published link; and
`audit_public_surfaces.py` diffs `code_publish/` against the remote `code/` tree, so a
`code_publish/results/` would make that check demand a `code/results/` that should not
exist.

Run:  python tools/stage_results.py      (also runs inside tools/publish_all.py)
"""

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "results"

# The outputs of the sweeps live beside the scripts that wrote them; the live GSM8K run
# lands under its own kernel tree. Globbed, so a new output is published by existing, not
# by being remembered.
SOURCE_GLOBS = [
    (ROOT / "work" / "analysis", ("*.json", "*.log")),
    (ROOT / "kaggle" / "real_data_ppi" / "out", ("*.json",)),
    # The nuisance ablation runs on Kaggle too, and its result is what retired this
    # project's own published mechanism for the low-sigma finding. Globbed rather than
    # named, so the next kernel output publishes by existing.
    (ROOT / "kaggle" / "vr_ablation" / "out", ("*.json",)),
    (ROOT / "kaggle" / "vr_mechanism" / "out", ("*.json",)),
    (ROOT / "kaggle" / "vr_stability" / "out", ("*.json",)),
]

VERIFIER = ROOT / "code_publish" / "verify_headlines.py"


def manifest():
    """(source path) -> (destination name), flat, deterministic order."""
    out = {}
    for d, patterns in SOURCE_GLOBS:
        for pat in patterns:
            for p in sorted(d.glob(pat)):
                out[p] = p.name
    return out


def required_by_verifier():
    """Every result file `verify_headlines.py` opens, read out of its source.

    Derived from the consumer rather than restated here. A list maintained by hand
    beside the thing it describes is the failure mode this whole file exists to answer.
    """
    src = VERIFIER.read_text(encoding="utf-8")
    names = set(re.findall(r'\bload\(\s*"([^"]+)"\s*\)', src))
    kag = re.search(r"KAGGLE_NAMES\s*=\s*\(([^)]*)\)", src)
    if kag:
        names |= set(re.findall(r'"([^"]+)"', kag.group(1)))
    return names


def selftest(staged):
    """A staging script that silently publishes an incomplete set is worse than none."""
    ok = True

    # Negative control: the detection must fire on a name that is genuinely absent, or
    # the positive check below passes for the wrong reason.
    bogus = "__no_such_result__.json"
    good = bogus not in staged
    ok &= good
    print(f"  {'OK  ' if good else 'FAIL'} selftest: an absent result is detected")

    # THE CHECK THAT MATTERS. The published results are only complete if every file the
    # published verifier opens is among them; otherwise `verify_headlines.py` prints
    # "SKIP ... cannot check claims that depend on it" and still exits 0, so an
    # incomplete upload reads to a judge as a clean pass over fewer claims.
    need = required_by_verifier()
    absent = sorted(n for n in need if n not in staged)
    good = bool(need) and not absent
    ok &= good
    print(
        f"  {'OK  ' if good else 'FAIL'} selftest: all {len(need)} files "
        "verify_headlines.py opens are staged"
    )
    for n in absent:
        print(
            f"         MISSING RESULT: {n} -- the verifier opens it, results/ lacks it"
        )
    return ok


def main():
    files = manifest()
    staged = set(files.values())

    dupes = sorted(n for n in staged if sum(1 for v in files.values() if v == n) > 1)
    if dupes:
        print("two sources would stage to the same destination name:")
        for n in dupes:
            print(f"  {n}")
        return 1

    if not selftest(staged):
        print("stage_results failed its own control; refusing to stage")
        return 1

    STAGE.mkdir(parents=True, exist_ok=True)
    copied = 0
    for src, name in files.items():
        dst = STAGE / name
        if not dst.is_file() or dst.read_bytes() != src.read_bytes():
            shutil.copy2(src, dst)
            copied += 1
    print(f"  {len(files)} results staged from live outputs, {copied} changed")

    # Anything here with no live source is a leftover of the hand-uploaded era. It would
    # keep shipping, and nothing would keep it current -- which is the exact condition
    # this script was written to end.
    stray = sorted(
        p.name for p in STAGE.iterdir() if p.is_file() and p.name not in staged
    )
    if stray:
        print("\n  files in results/ with no live source:")
        for s in stray:
            print(f"    {s}")
        print("  Delete them or point a glob at their real source; they ship as-is.")
        return 1

    print("  results tree matches the live outputs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
