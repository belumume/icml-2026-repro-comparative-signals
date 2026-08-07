"""Every audit finding, with its disposition VERIFIED against the repo rather than recalled.

WHY THIS EXISTS
---------------
"Is anything dropped?" was answered from memory three times in one session and was wrong
twice. First: seven findings sat undispositioned while the state was described as "waiting
on Kaggle". Second: two of those seven were left out of the delegation that was reported as
covering all seven. Both were caught by the operator asking again, not by any check.

Memory is the wrong instrument for a completeness question, because the failure mode is
precisely that the missing item does not come to mind. So this encodes the finding list
once and re-derives each disposition from the repo on every run. A closed finding must
prove it is closed; it cannot simply be remembered as closed.

Findings that are closed by an EXTERNAL result (a Kaggle kernel that has not returned) are
reported OPEN, deliberately. Pending is not closed, and a ledger that blurs the two is the
thing being fixed.

Run:  python tools/check_findings_closed.py
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "logbook" / ".trackio" / "logbook" / "pages"


def pages_text():
    if not PAGES.is_dir():
        return ""
    return "\n".join(
        p.read_text(encoding="utf-8", errors="replace") for p in PAGES.glob("*/page.md")
    )


def read(rel):
    p = ROOT / rel
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def gate(rel, *args):
    """Run a gate and return True on exit 0. A finding closed BY a gate must re-run it."""
    p = ROOT / rel
    if not p.is_file():
        return False
    r = subprocess.run(
        [sys.executable, str(p), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    return r.returncode == 0


def kernel_done(slug):
    """A pending external result is OPEN. Never report it closed on optimism."""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "kaggle", "kernels", "status", slug],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        return "COMPLETE" in (r.stdout or "").upper()
    except Exception:
        return False


# (id, what it is, closed_when) -- closed_when returns (bool, evidence string)
def _f_gates_staged():
    src = read("tools/stage_code.py")
    pub = read("tools/publish_all.py")
    invoked = set(re.findall(r'"tools/([a-z_0-9]+\.py)"', pub))
    invoked |= set(re.findall(r'"work/analysis/([a-z_0-9]+\.py)"', pub))
    missing = [n for n in invoked if f'"{n}"' not in src]
    return not missing, f"{len(invoked)} gates invoked, {len(missing)} unstaged"


def _f_results_published():
    pub = read("tools/publish_all.py") + read("tools/stage_results.py")
    ok = "results" in pub
    return (
        ok,
        "results/ referenced by the publish path" if ok else "results/ hand-uploaded",
    )


def _no_overclaim():
    t = pages_text()
    n = len(re.findall(r"re-derives in about a second", t))
    return n == 0, f"{n} 're-derives' overclaim(s) on rendered pages"


def _pii_clean():
    hits = sum(
        1
        for p in (ROOT / "code_publish").rglob("*")
        if p.is_file() and "OPERATOR" in p.read_text(encoding="utf-8", errors="replace")
    )
    return hits == 0, f"{hits} operator-identifier hit(s) in the staged tree"


FINDINGS = [
    (
        "A  mechanism (published explanation contradicted)",
        # CLOSED BY THE ABLATION, not by the cancelled vr-mechanism kernel. This check
        # pointed at that dead kernel for three days and therefore reported OPEN for a
        # finding that was settled and published. A ledger keyed to a superseded source
        # is the failure it exists to prevent.
        lambda: (
            "mechanism stated here until" in pages_text(),
            "retraction published on the claim-3 page",
        ),
    ),
    (
        "B  McNemar algebra sqrt(|d|/n) -> sqrt(|d|(1-|d|)/n)",
        lambda: (
            "d * (1.0 - d)" in read("work/analysis/mcnemar_bound.py"),
            "corrected formula present in source",
        ),
    ),
    (
        "B2 McNemar self-test no longer certifies the error",
        lambda: (gate("work/analysis/mcnemar_bound.py"), "selftest re-run"),
    ),
    (
        "C  SE_min reframed as analogy, ranked weakest",
        lambda: ("analogy" in pages_text(), "claim-4 page wording"),
    ),
    (
        "D  binomial SD removed from BOTH pages",
        lambda: _no_overclaim()
        if False
        else (
            len(re.findall(r"4\.7 binomial SD", pages_text())) <= 1,
            "only claim-4's own retraction may quote it",
        ),
    ),
    ("E  operator identifier off the published tree", _pii_clean),
    ("F1 every gate publish_all runs is staged", _f_gates_staged),
    ("F2 results/ published by the pipeline", _f_results_published),
    ("F3 verify_headlines claim matches what it does", _no_overclaim),
    (
        "F4 kaggle run reachable from the README",
        lambda: (
            "kaggle" in read("code_publish/README.md").lower(),
            "kaggle referenced in published README",
        ),
    ),
    (
        "C1 N sweep at fixed low sigma",
        # GENUINELY OPEN. The nsweep kernel ran but its N=1000 control failed, and the
        # stability run later explained why: R=60 is unreliable for a variance ratio.
        # So the sweep needs a rerun at R>=100 before any row can be read.
        lambda: (
            kernel_done("ubaidullahshuaib/icml-repro-vr-nsweep-r100"),
            "needs R>=100; the R=60 run's control failed",
        ),
    ),
    (
        "C2 standardisation control",
        # DELIBERATELY NOT REBUILT. The ablation answered the same question better, by
        # REMOVING the failure mode (closed-form ridge) rather than compensating for it.
        # Rerunning it would corroborate something already settled.
        lambda: (
            "ridge, closed form" in pages_text(),
            "superseded by the ablation, which is published",
        ),
    ),
    (
        "C3 author contact drafted (send is the operator's)",
        lambda: (
            (ROOT / "work" / "author-contact-DRAFT.md").is_file(),
            "draft on disk",
        ),
    ),
    (
        "C4 temperature sweep on real models",
        lambda: (
            False,
            "DEFERRED with reason recorded in task #16 - needs the GPU inference path",
        ),
    ),
    (
        "C5 multiplicity stated",
        lambda: ("Multiplicity" in pages_text(), "claim-3 page"),
    ),
    (
        "C6 nuisance ablation (ridge/kNN)",
        lambda: (
            kernel_done("ubaidullahshuaib/icml-repro-vr-ablation"),
            "Kaggle vr-ablation kernel",
        ),
    ),
    (
        "C7 generalisation stated, narrowly",
        lambda: (
            bool(re.search(r"generalis|generaliz", pages_text(), re.I)),
            "conclusion page",
        ),
    ),
    (
        "C8 claim-3 / claim-4 seam reconciled",
        lambda: ("harmless" in pages_text(), "cross-referenced section on both pages"),
    ),
]


def main():
    print("FINDING DISPOSITION -- re-derived from the repo, not recalled\n")
    open_items = []
    for label, fn in FINDINGS:
        try:
            ok, why = fn()
        except Exception as e:
            ok, why = False, f"CHECK ERRORED: {type(e).__name__}"
        print(f"  {'CLOSED' if ok else 'OPEN  '}  {label:52} {why}")
        if not ok:
            open_items.append(label)

    print()
    if open_items:
        print(f"{len(open_items)} OPEN of {len(FINDINGS)}:")
        for o in open_items:
            print(f"  - {o}")
        print("\nOpen is the honest state while a kernel is running or a lever is")
        print("deliberately deferred. It is not a failure; a false CLOSED would be.")
    else:
        print(f"all {len(FINDINGS)} findings closed and re-verified")
    # Deliberately exit 0 either way: this is a LEDGER, not a gate. Making it fail the
    # publish would create pressure to mark a pending kernel closed, which is the exact
    # dishonesty it exists to prevent.
    return 0


if __name__ == "__main__":
    sys.exit(main())
