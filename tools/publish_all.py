"""Publish the logbook correctly, in the one order that works, and verify the result.

WHY THIS EXISTS
---------------
`trackio logbook publish` REWRITES README.md on the Space, replacing whatever is there
with 586 bytes of generated boilerplate. So the hand-written front page (verdicts,
findings, reproduction pointers) must be restored AFTER every publish, never before.

That was found only by fetching the live file after a publish that reported success.
The publish command's exit code says nothing about it. A note in a handoff would be
forgotten on the next publish, so the ordering lives here instead.

Run from the repo root:  python tools/publish_all.py
"""

import subprocess
import sys
import urllib.request
from pathlib import Path

# Imported at MODULE scope on purpose. This was a late import inside main(), so on a run
# where sys.executable resolved to a venv without it, the publish had ALREADY happened
# and clobbered README.md before the ImportError fired -- the script failed in exactly
# the way it exists to prevent. Failing here costs nothing; failing there costs the
# front page.
try:
    from huggingface_hub import HfApi
except ImportError:
    sys.exit(
        "huggingface_hub is not importable by this interpreter "
        f"({sys.executable}). Run with one that has it. Refusing to publish, because "
        "a publish whose README restore then fails leaves the Space front page "
        "clobbered with generated boilerplate."
    )

ROOT = Path(__file__).resolve().parent.parent
SPACE = "passagereptile455/repro-evaluating-llms-comparative-signals"
RAW = f"https://huggingface.co/spaces/{SPACE}/raw/main/"
README_SRC = ROOT / "work" / "space_README.md"
README_MARKER = "The three findings"


PY = sys.executable


def run(cmd, cwd=None, label=""):
    print(f"\n$ {' '.join(cmd)}")
    p = subprocess.run(
        cmd,
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (p.stdout or "") + (p.stderr or "")
    for line in out.splitlines():
        if line.strip():
            print("   ", line[:160])
    if p.returncode != 0:
        print(f"FAILED ({label}) rc={p.returncode}")
        sys.exit(p.returncode)
    return out


def fetch(rel):
    req = urllib.request.Request(RAW + rel, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=90).read().decode("utf-8", "replace")


def main():
    # 1. GENERATE FIRST. Four of the six checks below read the GENERATED pages, so
    #    running them before generation audits the previous build. That is not a
    #    theoretical risk: it silently passed a stale page once and then failed twice on
    #    an em dash that had already been removed from the generator, which reads as the
    #    fix not working rather than as the check looking at the wrong file.
    #    Any gate that inspects build output belongs after the build.
    run([sys.executable, "tools/write_content.py"], label="generate")

    # 1b. Emit the evidence CSVs from the result JSON. Before the gates, because the
    #     --check below compares them cell-by-cell against that JSON, and before the
    #     publish, because trackio builds the Workspace tab by walking `logbook/` for
    #     dataset-typed files at publish time -- these ARE that tab's contents.
    run([sys.executable, "tools/export_evidence_csv.py"], label="evidence CSVs")

    # 2. now audit what will actually ship
    run(
        [sys.executable, "work/analysis/verify_realdata_claims.py"],
        label="real-data claims",
    )
    run([sys.executable, "work/analysis/audit_submission_text.py"], label="form text")
    run(
        [sys.executable, "work/analysis/guard_interval_labels.py"],
        label="interval labels",
    )
    run(
        [sys.executable, "work/analysis/audit_submission_quality.py"],
        label="slop + prize criteria",
    )
    run(
        [sys.executable, "work/analysis/verify_paper_quotes.py"],
        label="paper quotes verbatim",
    )
    run(
        [sys.executable, "tools/fix_table_headers.py", "--check"],
        label="table headers render",
    )
    run(
        [sys.executable, "tools/export_evidence_csv.py", "--check"],
        label="evidence CSVs match their JSON",
    )
    run(
        [sys.executable, "tools/check_rendered.py"],
        label="pages render without raw markup",
    )
    run([sys.executable, "tools/check_links.py"], label="every link resolves")
    run(
        [sys.executable, "tools/check_poster_consistency.py"],
        label="poster agrees with the logbook",
    )
    run([sys.executable, "tools/check_handoff_fresh.py"], label="handoff freshness")
    # Validates the pages against the contract transcribed from logbook.js, the actual
    # renderer. render_safe.py's check is a PORT written by inference, and a checker that
    # re-implements its consumer agrees with itself: it passed three times on a Claim 4
    # table that was visibly broken to any reader.
    run([sys.executable, "tools/check_renderer_contract.py"], label="renderer contract")
    # A ratio printed beside its operands must divide out from the PRINTED digits. Two
    # rows failed this and they were the two quoted as headlines everywhere else.
    run([sys.executable, "tools/check_table_arithmetic.py"], label="table arithmetic")
    run([sys.executable, "tools/stage_code.py"], label="stage code")
    # Same discipline, applied to the directory every headline number actually comes
    # from. `results/` was hand-uploaded and this file had ZERO occurrences of the
    # string "results" -- so a re-run that changed a number would update the local JSON
    # and the prose derived from it while the published JSON kept serving the old value
    # to anyone who checked. Staged before verify_headlines below, so the verifier runs
    # against the same bytes that will ship.
    run([sys.executable, "tools/stage_results.py"], label="stage results")
    run([sys.executable, "code_publish/verify_headlines.py"], label="headline numbers")

    # 3. publish (this CLOBBERS README.md)
    run(
        ["trackio", "logbook", "publish", SPACE, "--public"],
        cwd=ROOT / "logbook",
        label="publish",
    )

    # 4a. Push the evidence CSVs into the SPACE as well as the bucket. `logbook publish`
    #     syncs them to the workspace bucket, which drives the Workspace tab, but does
    #     not put them in the Space tree -- so the `logbook/artifacts/...` links on the
    #     front page and the Claim 4 page resolved to 404 while the Workspace tab
    #     happily listed all seven. A file reachable by one route and not the other is
    #     the reachability failure this project already hit with LICENSES.
    HfApi().upload_folder(
        folder_path=str(ROOT / "logbook" / "artifacts"),
        path_in_repo="logbook/artifacts",
        repo_id=SPACE,
        repo_type="space",
    )
    print("   evidence CSVs uploaded to the Space tree")

    # 4b. Push the runnable code the same way, for the same reason. `code_publish/` was
    #     staged once and uploaded BY HAND, so from then on the published `code/` tree
    #     and the local staging directory drifted apart with nothing to notice -- when
    #     this was finally checked, 25 of 31 files were stale, `write_content.py` by
    #     sixteen kilobytes. stage_code.py (run as a gate above, so a renamed source
    #     aborts before the publish clobbers anything) rebuilds the tree from the live
    #     sources, so the two are equal by construction, not by anyone remembering.
    HfApi().upload_folder(
        folder_path=str(ROOT / "code_publish"),
        path_in_repo="code",
        repo_id=SPACE,
        repo_type="space",
    )
    print("   code/ uploaded to the Space tree")

    # 4c. And the results themselves, which were the last hand-uploaded surface. Path is
    #     the Space ROOT, matching RESULTS_BASE in write_content.py and the `results/`
    #     group audit_public_surfaces.py checks; the published links depend on it, so it
    #     is not a free choice.
    HfApi().upload_folder(
        folder_path=str(ROOT / "results"),
        path_in_repo="results",
        repo_id=SPACE,
        repo_type="space",
    )
    print("   results/ uploaded to the Space tree")

    # 4. restore the real README, which step 3 just destroyed
    HfApi().upload_file(
        path_or_fileobj=str(README_SRC),
        path_in_repo="README.md",
        repo_id=SPACE,
        repo_type="space",
    )
    print("\n   README.md restored after publish")

    # 5. verify the LIVE artifact, not the exit codes
    run(
        [sys.executable, "../data/scripts__validate_icml_logbook.py", "--space", SPACE],
        cwd=ROOT / "logbook",
        label="validator",
    )
    run([sys.executable, "work/analysis/live_page_diff.py"], label="live vs local")
    # Publishing writes four separate public repos through different mechanisms at
    # different moments. live_page_diff only covers the Space's pages; this walks all of
    # them (Space, rendered origin, traces dataset, workspace bucket) and checks each is
    # reachable, public, and carrying what it should.
    run([sys.executable, "tools/audit_public_surfaces.py"], label="public surfaces")

    live = fetch("README.md")
    if README_MARKER not in live:
        print(f"\nFAIL: live README is {len(live)} B and lacks '{README_MARKER}'.")
        print("The publish clobbered it and the restore did not take.")
        return 1
    print(f"\nlive README OK ({len(live)} B, front page intact)")
    print("published and verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
