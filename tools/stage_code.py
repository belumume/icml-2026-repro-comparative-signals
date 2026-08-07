"""Build `code_publish/` from the live sources, so the published code cannot go stale.

WHY THIS EXISTS
---------------
`code_publish/` began as a hand-staged copy, uploaded to the Space once by hand. From
that moment the published `code/` tree and the working sources drifted, silently and in
both directions:

  * `code_publish/tools/write_content.py` was 47,770 B while the live file was 64,019 B
    -- sixteen kilobytes behind, so a judge reading the published copy would have been
    reading a version that no longer produced the numbers in the logbook.
  * `code_publish/analysis/gaussian_surrogate.py` was AHEAD: it had fixed a dead
    reference to `validate_surrogate.py`, a file that has never existed in this repo,
    which the live source still carried.

Neither direction is detectable by looking at either tree alone, which is the whole
problem. So the staging directory is no longer a thing anyone edits: everything derived
is copied here from its real source on every publish, and the manifest below fails loudly
if a source moves or is renamed. Copying is cheap; two versions of one file disagreeing
in public is not.

`OWN` lists the few files whose source genuinely IS this directory -- the code README,
the pinned requirements, the paper snapshot, and the standalone verifier. Those are
authored here and are left alone.

Run:  python tools/stage_code.py           (also runs inside tools/publish_all.py)
"""

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "code_publish"

# Derived: (source relative to repo root) -> (destination relative to code_publish/).
ANALYSIS = [
    "audit_submission_quality.py",
    "audit_submission_text.py",
    "check_improv_ceiling.py",
    "claim4_at_reported_N.py",
    "claim4_noise_floor.py",
    "claims12_eif_check.py",
    "exact_efficiency_bound.py",
    "extract_tables.py",
    "gaussian_surrogate.py",
    "guard_interval_labels.py",
    "live_page_diff.py",
    "verify_paper_quotes.py",
    "verify_realdata_claims.py",
    "vr_sweep.py",
    "mcnemar_bound.py",
]
# The build and gate scripts. A reader who is told "a gate enforces X" should be able to
# open the gate and see whether it does; that is the difference between a claim and a
# checkable one.
TOOLS = [
    "analyze_verdicts.py",
    "build_figures.py",
    "build_pages.py",
    "build_poster_embed.py",
    "build_session_trace.py",
    "audit_public_surfaces.py",
    "check_handoff_fresh.py",
    "check_links.py",
    "check_renderer_contract.py",
    "check_table_arithmetic.py",
    "check_poster_consistency.py",
    "check_rendered.py",
    "export_evidence_csv.py",
    "fix_table_headers.py",
    "gen_poster_gates.py",
    "publish_all.py",
    "render_safe.py",
    "sanitize_trace.py",
    "stage_code.py",
    "stage_results.py",
    "write_content.py",
]

MANIFEST = (
    [(f"work/analysis/{n}", f"analysis/{n}") for n in ANALYSIS]
    + [(f"tools/{n}", f"tools/{n}") for n in TOOLS]
    + [("kaggle/real_data_ppi/real_gsm8k_ppi.py", "kaggle/real_gsm8k_ppi.py")]
)

# Authored in code_publish/ itself; never overwritten from elsewhere.
OWN = {"README.md", "requirements.txt", "verify_headlines.py"}
OWN_DIRS = {"paper"}


def selftest():
    """A staging script that silently skips a missing source is worse than none.

    The control drives the same resolution the real run uses, against a path that
    cannot exist, and requires it to be reported as missing rather than skipped.
    """
    ok = True
    bogus = ROOT / "work" / "analysis" / "__no_such_source__.py"
    missing = [] if bogus.is_file() else ["__no_such_source__.py"]
    good = missing == ["__no_such_source__.py"]
    ok &= good
    print(f"  {'OK  ' if good else 'FAIL'} selftest: a missing source is detected")
    # and a real one must resolve, or the check above passes for the wrong reason
    real = (ROOT / MANIFEST[0][0]).is_file()
    ok &= real
    print(f"  {'OK  ' if real else 'FAIL'} selftest: a real source resolves")

    # THE GAP THIS SCRIPT HAD, and it is the direction a manifest is always blind in.
    # Every check above asks "does each manifest ENTRY exist". None asked "is every gate
    # IN the manifest". So a gate written AFTER this list was authored is simply never
    # published, silently, while the staging run reports success -- and the run reports
    # success precisely because it only ever looks at what it already knows about.
    #
    # Measured 2026-08-03: three gates were unpublished this way, and they were the three
    # written that same session to PREVENT drift -- check_renderer_contract.py,
    # check_table_arithmetic.py, audit_public_surfaces.py. The drift guards had drifted.
    #
    # So derive the expectation from the source of truth (what publish_all actually runs)
    # rather than from a second hand-maintained list, which would inherit the same defect.
    pub = (ROOT / "tools" / "publish_all.py").read_text(encoding="utf-8")
    invoked = set(re.findall(r'"tools/([a-z_0-9]+\.py)"', pub))
    invoked |= set(re.findall(r'"work/analysis/([a-z_0-9]+\.py)"', pub))
    staged = {d.split("/")[-1] for _, d in MANIFEST}
    unpublished = sorted(n for n in invoked if n not in staged)
    good = not unpublished
    ok &= good
    print(
        f"  {'OK  ' if good else 'FAIL'} selftest: every gate publish_all runs is in the manifest"
    )
    for n in unpublished:
        print(
            f"         UNPUBLISHED GATE: {n} -- publish_all runs it, code_publish lacks it"
        )
    return ok


def main():
    if not selftest():
        print("stage_code failed its own control; refusing to stage")
        return 1

    missing = [src for src, _ in MANIFEST if not (ROOT / src).is_file()]
    if missing:
        print("\nsources in the manifest that do not exist:")
        for m in missing:
            print(f"  {m}")
        print("A rename must update this manifest. Refusing to publish a partial tree.")
        return 1

    copied = 0
    for src, dst in MANIFEST:
        d = STAGE / dst
        d.parent.mkdir(parents=True, exist_ok=True)
        s = ROOT / src
        if not d.is_file() or d.read_bytes() != s.read_bytes():
            shutil.copy2(s, d)
            copied += 1
    print(f"  {len(MANIFEST)} files staged from live sources, {copied} changed")

    # __pycache__ would otherwise be uploaded to a public Space, where a .pyc is pure
    # noise to a reader and carries the absolute build path of this machine.
    pyc = 0
    for p in list(STAGE.rglob("__pycache__")):
        if p.is_dir():
            shutil.rmtree(p)
            pyc += 1
    if pyc:
        print(f"  removed {pyc} __pycache__ director{'y' if pyc == 1 else 'ies'}")

    # Anything in the staging tree that is neither derived nor explicitly OWN is a
    # leftover from the hand-staged era and should not ship.
    derived = {(STAGE / d).resolve() for _, d in MANIFEST}
    stray = []
    for p in STAGE.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(STAGE)
        if p.resolve() in derived or rel.as_posix() in OWN:
            continue
        if rel.parts and rel.parts[0] in OWN_DIRS:
            continue
        stray.append(rel.as_posix())
    if stray:
        print("\n  files in the staging tree with no source and not declared OWN:")
        for s in stray:
            print(f"    {s}")
        print("  Declare them in OWN/OWN_DIRS or delete them; they ship to the public")
        print("  Space as-is and nothing keeps them current.")
        return 1

    print("  staging tree matches the live sources")
    return 0


if __name__ == "__main__":
    sys.exit(main())
