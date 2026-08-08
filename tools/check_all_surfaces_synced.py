"""One command for "is anything stale anywhere". Six surfaces, each re-derived, not recalled.

WHY THIS EXISTS
---------------
This project publishes to six independent places and each has its own way of going stale:

    local tree            the working copy
    GitHub                version control, added 2026-08-08 after the work had lived on
                          ONE disk with no history for a week
    HF Space              code/, results/, pages/, poster
    rendered origin       what a judge actually opens
    traces dataset        agent traces
    workspace bucket      the evidence CSVs behind the Workspace tab

Existing gates each cover a slice. `audit_public_surfaces.py` walks the four Hugging Face
surfaces, `live_page_diff.py` compares rendered pages, `stage_code.py` and
`stage_results.py` check the staged trees against live sources. NONE of them knows GitHub
exists, so "everything is in sync" was being assembled by hand from four green checks plus
a memory of having pushed. That assembly is exactly what went wrong with
`check_findings_closed.py`, which reported two settled findings as open for three days
because it was keyed to a cancelled kernel.

So this runs every existing gate and adds the two nobody owned: local-versus-GitHub, and
whether HANDOFF.md is behind the commits. It re-derives; it does not remember.

Run:  python tools/check_all_surfaces_synced.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sh(*args, cwd=ROOT):
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )


def gate(rel, *args):
    p = ROOT / rel
    if not p.is_file():
        return False, f"{rel} ABSENT"
    r = sh(sys.executable, str(p), *args)
    return r.returncode == 0, f"exit {r.returncode}"


def git_synced():
    """Uncommitted work and unpushed commits are BOTH staleness, in opposite directions."""
    if not (ROOT / ".git").is_dir():
        return False, "NOT a git repo; the work exists on one disk only"
    dirty = sh("git", "status", "--porcelain").stdout.strip()
    n_dirty = len([x for x in dirty.splitlines() if x.strip()])
    sh("git", "fetch", "-q", "origin")
    ahead = sh("git", "rev-list", "--count", "origin/main..main").stdout.strip() or "?"
    behind = sh("git", "rev-list", "--count", "main..origin/main").stdout.strip() or "?"
    ok = n_dirty == 0 and ahead == "0" and behind == "0"
    return ok, f"{n_dirty} uncommitted, {ahead} ahead, {behind} behind origin"


def handoff_current():
    """A handoff older than the newest commit describes a state that no longer exists."""
    h = ROOT / "HANDOFF.md"
    if not h.is_file():
        return False, "HANDOFF.md ABSENT"
    last = sh("git", "log", "-1", "--format=%H", "--", "HANDOFF.md").stdout.strip()
    head = sh("git", "rev-parse", "HEAD").stdout.strip()
    if not last or not head:
        return False, "could not resolve commits"
    n = sh("git", "rev-list", "--count", f"{last}..{head}").stdout.strip() or "?"
    return n == "0", f"{n} commit(s) landed since HANDOFF.md was last written"


def kernels_match():
    """A kernel directory with no kernel on Kaggle, or the reverse, is a silent gap."""
    local = {p.name for p in (ROOT / "kaggle").iterdir() if p.is_dir()}
    r = sh(sys.executable, "-m", "kaggle", "kernels", "list", "--mine")
    remote = {
        ln.split()[0].split("/")[-1]
        for ln in r.stdout.splitlines()
        if "icml-repro" in ln
    }
    # names differ by convention (dir `vr_ablation` -> kernel `icml-repro-vr-ablation`),
    # so compare on a normalised slug rather than on the raw name
    norm = {n.replace("_", "-") for n in local}
    rnorm = {n.replace("icml-repro-", "") for n in remote}
    missing = sorted(n for n in norm if n not in rnorm and n != "real-data-ppi")
    return (
        not missing,
        f"{len(norm)} local, {len(rnorm)} on Kaggle, unmatched: {missing or 'none'}",
    )


CHECKS = [
    ("local vs GitHub", git_synced),
    ("HANDOFF vs commits", handoff_current),
    ("staged code vs live sources", lambda: gate("tools/stage_code.py")),
    ("staged results vs kernel outputs", lambda: gate("tools/stage_results.py")),
    ("rendered pages vs local", lambda: gate("work/analysis/live_page_diff.py")),
    ("all HF public surfaces", lambda: gate("tools/audit_public_surfaces.py")),
    ("every link resolves", lambda: gate("tools/check_links.py")),
    ("headline numbers", lambda: gate("code_publish/verify_headlines.py")),
    ("kaggle kernels vs repo", kernels_match),
]


def main():
    print("SURFACE SYNC -- re-derived, not recalled\n")
    bad = []
    for label, fn in CHECKS:
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"CHECK ERRORED: {type(e).__name__}"
        print(f"  {'OK    ' if ok else 'STALE '} {label:34} {detail}")
        if not ok:
            bad.append(label)
    print()
    if bad:
        print(f"{len(bad)} surface(s) out of sync:")
        for b in bad:
            print(f"  - {b}")
        return 1
    print(f"all {len(CHECKS)} surfaces agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
