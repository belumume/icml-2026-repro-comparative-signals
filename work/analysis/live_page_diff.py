"""Byte-compare every locally generated logbook page against the LIVE Space copy.

The publish step reports success on its own exit code; this checks the artifact.
Run from the repo root.
"""

import collections
import glob
import json
import math
import urllib.request

BASE = (
    "https://huggingface.co/spaces/passagereptile455/"
    "repro-evaluating-llms-comparative-signals/raw/main/"
)
LOCAL_ROOT = "logbook/.trackio/logbook/"
GRID = "work/analysis/claim4_noise_floor.json"


def clustered_sign_test_p():
    """Re-derive the clustered one-sided exact binomial p from the grid.

    Deliberately a re-derivation rather than a constant: the token this feeds used to
    be hardcoded and went stale silently. cfg1/cfg2 share an evaluation subset, so the
    60 cells are clustered to one value per (benchmark, model) before the test -- the
    same clustering the generator does, and the reason the unclustered p is not quoted.
    """
    rows = json.load(open(GRID, encoding="utf-8"))["rows"]
    clusters = collections.defaultdict(list)
    for r in rows:
        clusters[(r["bench"], r["model"])].append(r["improv_recomputed"])
    means = [sum(v) / len(v) for v in clusters.values()]
    pos = sum(1 for v in means if v > 0)
    n = pos + sum(1 for v in means if v < 0)
    if not n:
        return 1.0
    return sum(math.comb(n, k) for k in range(pos, n + 1)) / 2**n


def fetch(rel):
    req = urllib.request.Request(BASE + rel, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=90).read().decode("utf-8", "replace")


def main():
    local = sorted(glob.glob(LOCAL_ROOT + "pages/*/page.md"))
    assert local, f"no pages found under {LOCAL_ROOT} -- wrong root?"
    print(f"{len(local)} local page.md files\n")
    differ = 0
    for path in local:
        rel = path.replace("\\", "/").replace(LOCAL_ROOT, "")
        text = open(path, encoding="utf-8").read()
        try:
            live = fetch(rel)
        except Exception as exc:
            print(f"  ERR   {rel}: {exc}")
            differ += 1
            continue
        same = text.replace("\r\n", "\n") == live.replace("\r\n", "\n")
        differ += not same
        name = rel.split("/")[1][:44]
        print(
            f"  {'SAME' if same else 'DIFF'}  {name:46} local={len(text):>6,} live={len(live):>6,}"
        )

    print()
    if differ:
        print(f"{differ} page(s) differ -- the live logbook is NOT what was generated")
        return 1
    print("LIVE == LOCAL for every page")

    # Load-bearing tokens that must be present on the live pages.
    #
    # This block used to PRINT its counts and return 0 regardless, so a token that
    # matched nothing reported "0x on: []" and the publish still went green. It did
    # exactly that: the clustered p-value was searched as the literal "4.22" while the
    # generator formats it "{:.1e}" and the pages render "4.2e-06". A zero-hit marker
    # is now a failure, and the p-value token is DERIVED from the same computation the
    # generator uses instead of being typed in, so it cannot drift again when the
    # format string or the underlying count changes.
    joined = "\n".join(open(p, encoding="utf-8").read() for p in local)
    clustered_p = f"{clustered_sign_test_p():.1e}"
    missing = []
    for token, label in [
        (clustered_p, "clustered sign-test p"),
        ("Two rows need a note", "exact-bound exceedance note"),
        ("FALSIFIED", "falsification verdict"),
        ("poster", "poster embed"),
    ]:
        hits = [
            # normalise first: glob returns backslashes on Windows, so splitting on
            # "/" put the same useless segment ("logbook") against every token
            p.replace("\\", "/").split("/")[-2][:40]
            for p in local
            if token in open(p, encoding="utf-8").read()
        ]
        count = joined.count(token)
        print(f"  {label:30} {count:>3}x on: {hits}")
        if count == 0:
            missing.append((label, token))
    if missing:
        print()
        for label, token in missing:
            print(f"  FAIL {label}: {token!r} appears on no page")
        print("A load-bearing token is absent, or the token itself is stale.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
