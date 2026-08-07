"""Forbid a correct number from carrying the wrong label.

Two rules, both instances of one failure: every numeric assertion in this repo passes
while the prose around the number says something the number does not support. A label is
not something a numeric check can see.

RULE 1 -- the single-run spread is not a confidence interval.
This shipped live. The script resamples a fresh N=100 subset on every iteration, so its
2.5/97.5 percentiles are the spread of ONE evaluation run's outcome, a prediction
interval. I published them as a "bootstrap 95% confidence interval" and concluded the
effect was indistinguishable from zero. The mean is in fact reliably positive at z = 6.5.
Enforced: wherever the wide interval's endpoints appear, the nearby text must not call
them a confidence interval, and the narrow interval for the mean must appear too,
because either figure alone misleads.

RULE 2 -- the recomputed count is not the published count.
Same shape, found later and separately. Two counts come out of the 60-cell grid: how
many gains RECOMPUTED from the paper's numbers fall under one standard error, and how
many of the gains as PRINTED do. They differ, and the larger one is the recomputed one.
A sentence reading "N of 60 published gains" while N is the recomputed count attributes
to the paper a figure the paper does not print. One such sentence survived an earlier
sweep of exactly this wording and reached the published conclusion page. Enforced: near
any occurrence of the recomputed count, the provenance words must not appear.

Both counts are derived here from the result JSON, never typed in, so the guard cannot
drift from the analysis it polices.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "kaggle" / "real_data_ppi" / "out" / "real_gsm8k_ppi.json"
GRID = ROOT / "work" / "analysis" / "claim4_noise_floor.json"

TARGETS = [
    ROOT / "tools" / "write_content.py",
    ROOT / "work" / "space_README.md",
    ROOT / "SUBMISSION.md",
    ROOT / "HANDOFF.md",
    ROOT / "POST-BRIEF.md",
]
RENDERED = sorted(
    (ROOT / "logbook" / ".trackio" / "logbook" / "pages").glob("*/page.md")
)

# Words that assert the number came from the paper rather than from recomputation.
PROVENANCE = re.compile(
    r"\bpublished\b|\bprinted\b|\bas reported\b|\bpaper'?s own\b", re.I
)
# ...unless the same sentence also says "recomputed", which IS the distinction. Both
# "gains recomputed from the paper's own numbers" and "58 RECOMPUTED (as PRINTED, 57)"
# are exactly right, and both tripped the first version of this rule. The sentence that
# actually shipped contains no "recomputed" anywhere, so this exemption cannot retire
# the real catch -- the selftest pins that, because a narrowing which quietly disables
# its own detector is indistinguishable from one that worked.
RECOMPUTED_NEAR = re.compile(r"recomputed", re.I)
PROV_WINDOW = 160

# "confidence interval" / "CI" within this many chars of a wide-interval endpoint
WINDOW = 240
CI_WORDS = re.compile(r"confidence interval|\bCI\b|\bCI95\b", re.I)
# The correct framings that make a nearby CI mention legitimate.
# \s+ not " ": these files wrap, so a literal space never matches across a newline and
# the guard reported a false positive on correctly-worded prose.
OK_NEAR = re.compile(
    r"CI\s+for\s+the\s+\*{0,2}mean|single\s+run|single-run|spread\s+of|"
    r"prediction\s+interval|mislabell?ed|correction",
    re.I,
)


def grid_counts():
    """(recomputed_under_1SE, printed_under_1SE, n) from the grid, never typed in."""
    rows = json.load(open(GRID, encoding="utf-8"))["rows"]
    rec = sum(1 for r in rows if r["recomputed_in_SE"] < 1.0)
    pri = sum(1 for r in rows if r["printed_in_SE"] < 1.0)
    return rec, pri, len(rows)


def check_provenance(text, rec, pri, n):
    """Occurrences of the RECOMPUTED count that a provenance word claims as the paper's.

    Matches the literal ("58 of 60") and the generator's template form, which is what
    the surviving instance actually looked like -- scanning only rendered pages would
    fix the symptom and leave the generator to re-emit it on the next build.
    """
    if rec == pri:
        return []  # counts coincide; the distinction this guards is not live
    hits = []
    forms = [rf"\b{rec}\s+of\s+{n}\b", r"\{c4_under1\}\s+of\s+\{c4_n\}"]
    for form in forms:
        for m in re.finditer(form, text):
            # BOTH directions. The first version scanned only forward, and the
            # sentence that mattered most -- the outward-facing prize explanation --
            # put the word FIRST: "expressing every published gain ... puts 58 of 60
            # below 1.0 SE". It sailed through a guard written to catch exactly that
            # claim, in a file the guard was already scanning.
            near = text[max(0, m.start() - PROV_WINDOW) : m.end() + PROV_WINDOW]
            # Stop at the next bullet, blockquote or blank line. Without this the
            # window ran past the end of the sentence into an adjacent bullet that
            # legitimately says "the paper's own `Improv.` metric", and reported two
            # false positives -- which is the failure mode that buries a real finding.
            near = re.split(r"\n\s*\n|\n\s*[-*>]\s", near)[0]
            if RECOMPUTED_NEAR.search(near):
                continue
            found = PROVENANCE.search(near)
            if found:
                hits.append(
                    (
                        text[: m.start()].count("\n") + 1,
                        found.group(0),
                        " ".join(near.split())[:104],
                    )
                )
    return hits


def selftest(rec, pri, n):
    """The guard must FAIL on the sentence that shipped, and PASS on its correction.

    Without this the guard is a hypothesis: a regex that has never been shown to fire
    has not been shown to work, and a silent pass is indistinguishable from a clean run.
    """
    bad = (
        "of any kind, and {c4_under1} of {c4_n} published gains fall under one standard "
        "error of binomial\nnoise, yet the aggregate sign pattern is real"
    )
    good = bad.replace("published", "recomputed")
    control = f"{pri} of {n} gains as printed by the paper fall under one SE"
    # The two false positives the first run produced: a legitimate mention of the
    # paper's own metric in the NEXT bullet. Pinned so the window cannot later be
    # widened back without something going red.
    bleed = (
        f"- **{rec} of {n}** gains are under **1.0 SE**.\n"
        "- Simulating the paper's own `Improv.` metric under a null where the one-step\n"
        "  estimate carries no signal: a gain that large arises by chance."
    )
    results = [
        ("shipped sentence must FAIL", bool(check_provenance(bad, rec, pri, n))),
        ("its correction must PASS", not check_provenance(good, rec, pri, n)),
        (
            "printed count + 'printed' must PASS",
            not check_provenance(control, rec, pri, n),
        ),
        ("adjacent-bullet bleed must PASS", not check_provenance(bleed, rec, pri, n)),
        # The word BEFORE the count -- the shape that reached the prize form.
        (
            "provenance word PRECEDING the count must FAIL",
            bool(
                check_provenance(
                    f"expressing every published gain in units of the binomial "
                    f"sampling noise puts {rec} of {n} below 1.0 SE",
                    rec,
                    pri,
                    n,
                )
            ),
        ),
        # The two corrections that tripped the first version. They share the flagged
        # vocabulary with the shipped sentence and differ only in saying "recomputed",
        # so they are the control that proves the exemption narrowed the rule rather
        # than switching it off.
        (
            "'recomputed from the paper's own numbers' must PASS",
            not check_provenance(
                f"{rec} of {n} gains recomputed from the paper's own numbers sit "
                "under one standard error of binomial noise.",
                rec,
                pri,
                n,
            ),
        ),
        (
            "explicit both-counts disambiguation must PASS",
            not check_provenance(
                f"{rec} of {n} RECOMPUTED gains under 1.0 SE. (As PRINTED the count "
                f"is {pri} of {n}.)",
                rec,
                pri,
                n,
            ),
        ),
    ]
    for label, ok in results:
        print(f"  {'OK  ' if ok else 'FAIL'} selftest: {label}")
    return all(ok for _, ok in results)


def main():
    d = json.load(open(RAW, encoding="utf-8"))
    wide = []
    for m in d["models"]:
        lo, hi = m["improv_ci95_pp"]
        # both the ascii hyphen and the unicode minus are used across these files
        wide += [f"{lo:.2f}", f"{lo:.2f}".replace("-", "−"), f"+{hi:.2f}"]

    fails = []
    for path in TARGETS:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for token in wide:
            for m in re.finditer(re.escape(token), text):
                a = max(0, m.start() - WINDOW)
                near = text[a : m.end() + WINDOW]
                if CI_WORDS.search(near) and not OK_NEAR.search(near):
                    line = text[: m.start()].count("\n") + 1
                    fails.append((path.name, line, token, near.strip()[:110]))

    for name, line, token, ctx in fails:
        print(f"  FAIL {name}:{line} {token!r} called a CI without qualification")
        print(f"       ...{ctx}...")

    if fails:
        print(
            f"\n{len(fails)} mislabelled interval(s). The wide interval is the spread "
            "of a SINGLE RUN, not a CI for the effect."
        )
        return 1

    # And the corrected framing must actually be present where the claim is made.
    missing = [
        p.name
        for p in TARGETS
        if p.is_file()
        and any(t in p.read_text(encoding="utf-8") for t in wide)
        and "+0.167" not in p.read_text(encoding="utf-8")
    ]
    if missing:
        print(f"  FAIL quotes the wide interval without the mean's CI: {missing}")
        return 1

    # --- RULE 2: the recomputed count must not be attributed to the paper ----
    rec, pri, n = grid_counts()
    if not selftest(rec, pri, n):
        print("guard failed its own control; its verdict below means nothing")
        return 1
    prov = []
    for path in TARGETS + RENDERED:
        if not path.is_file():
            continue
        for line, word, ctx in check_provenance(
            path.read_text(encoding="utf-8"), rec, pri, n
        ):
            prov.append((path.name, line, word, ctx))
    for name, line, word, ctx in prov:
        print(f"  FAIL {name}:{line} recomputed count called {word!r}")
        print(f"       ...{ctx}...")
    if prov:
        print(
            f"\n{len(prov)} sentence(s) attribute the RECOMPUTED count ({rec} of {n}) "
            f"to the paper. The count as printed is {pri} of {n}."
        )
        return 1
    print(
        f"  OK   recomputed count ({rec} of {n}) never attributed to the paper "
        f"(printed count is {pri} of {n})"
    )

    print(
        f"checked {len(TARGETS)} files: no interval is mislabelled, and every file "
        "quoting the single-run spread also quotes the CI for the mean"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
