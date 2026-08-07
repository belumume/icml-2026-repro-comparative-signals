"""Audit the outward-facing form explanation in SUBMISSION.md.

This is the highest-stakes text in the whole submission: it is what a judge reads on the
form itself, and it is the one surface no reviewer pass had ever checked. It was found
stale in three ways the logbook had already corrected (it quoted the anti-conservative
unclustered p, claimed two cells survive the null when the corrected count is one, and
cited the pre-sign-fix 322x). That is the redecision-sweep failure landing on the worst
possible surface, so it now gets a machine check instead of a re-read.

The binding requirement is not "is this well written" but "does this contradict the
published logbook". So every statistic is checked against the generated claim-4 page and
the raw kernel JSON, not against memory.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
LIMIT = 1500

SUB = os.path.join(REPO, "SUBMISSION.md")
PAGE = os.path.join(
    REPO,
    "logbook",
    ".trackio",
    "logbook",
    "pages",
    "claim-4-real-benchmark-gains-of-the-one-step-estimator-over-naive",
    "page.md",
)
RAW = os.path.join(REPO, "kaggle", "real_data_ppi", "out", "real_gsm8k_ppi.json")

sub = open(SUB, encoding="utf-8").read()
page = open(PAGE, encoding="utf-8").read()
rd = json.load(open(RAW, encoding="utf-8"))

# The label also appears in this file's own header comment, so anchoring on its first
# occurrence captured the `fals-url` fence instead (89 chars, 1 word). Anchor on the
# DEFINITION site: the label followed by a parenthetical.
m = re.search(r"`fals-explanation` \(.*?```\n(.*?)\n```", sub, re.S)
assert m, "fals-explanation definition block not found"
assert len(m.group(1)) > 500, (
    f"captured only {len(m.group(1))} chars -- wrong block again"
)
expl = m.group(1).strip()

fails = []


def note(label):
    """Report a figure the field does not cite. Not a failure: the field is a pointer,
    and the logbook is where completeness is enforced."""
    print(f"  --   {label}")


def check(label, ok, detail=""):
    print(f"  {'OK  ' if ok else 'FAIL'} {label}{(' -- ' + detail) if detail else ''}")
    if not ok:
        fails.append(label)


# --- form mechanics ----------------------------------------------------------
check(
    f"length {len(expl)} <= {LIMIT}", len(expl) <= LIMIT, f"{LIMIT - len(expl)} spare"
)
check("ASCII only", expl.isascii(), repr([c for c in expl if not c.isascii()][:8]))
check("zero em dashes", "—" not in expl)

# --- must not contradict the published page ---------------------------------
# Conditional for the same reason as the figures below: the field is a pointer, so it
# need not quote a p-value at all. What must never happen is quoting the WRONG one --
# the unclustered p is anti-conservative and the logbook explicitly disowns it.
if re.search(r"p\s*=", expl):
    check(
        "if a p is quoted it is the CLUSTERED one",
        "4.2e-06" in expl and "4.2e-06" in page,
    )
else:
    note("field quotes no p-value; the page states the clustered one")
check(
    "does NOT quote the anti-conservative p",
    "8.8e-11" not in expl and "5.19e-12" not in expl,
)
# CONDITIONAL, and this is a deliberate rescope. These used to REQUIRE each figure to
# appear. That was right for a field trying to be self-contained, and it is wrong for
# the field the form actually asks for: "2-3 sentences, in your own words". Requiring a
# fixed inventory of numbers forced the logbook's contents into a pointer field and
# produced exactly the density a judge would read as padding. The evidence belongs in
# the logbook, where these same figures are checked against the raw JSON already.
#
# What must still hold is that the field is never WRONG: any figure it does cite has to
# match the published page. Completeness moved to the logbook; consistency stays here.
for tok in ["27 of 30", "58 of 60", "+3.50%"]:
    if tok in expl:
        check(f"'{tok}' agrees with the page", tok in page)
    else:
        note(f"'{tok}' not cited in the field (it is on the page)")

# --- corrections that must not regress ---------------------------------------
check(
    "does NOT claim two cells survive",
    not re.search(r"[Tt]wo cells (do )?survive", expl),
)
check("does NOT cite the pre-sign-fix 322x", "322" not in expl)
check("body cites the corrected 349x", "349" in sub)

# --- real-data figures, against the raw JSON ---------------------------------
# Same rescope. If the field quotes the wide interval it must quote BOTH ends and the
# positive control with it -- a lone scary-looking interval with no AUROC beside it is
# the misreading this project already made once. If it quotes none of them, that is a
# pointer doing its job, and the logbook states all of them under their own gate.
lo, hi = rd["models"][0]["improv_ci95_pp"]
cites_interval = f"{lo:.2f}" in expl or f"{hi:.2f}" in expl
if cites_interval:
    check("real-data CI low", f"{lo:.2f}" in expl, f"{lo:.2f}")
    check("real-data CI high", f"{hi:.2f}" in expl, f"{hi:.2f}")
    check(
        "positive control (AUROC) stated alongside the interval",
        all(f"{mm['aux_auroc']:.2f}" in expl for mm in rd["models"]),
        str([round(mm["aux_auroc"], 2) for mm in rd["models"]]),
    )
else:
    note("field does not quote the single-run interval; the logbook does, with AUROC")
if f"{rd['models'][0]['improv_mean_pp']:.2f}" in expl:
    check("point estimate agrees with the raw JSON", True)
else:
    note("field does not quote the +0.24pp point estimate")

print(f"\n{len(expl)} chars / {LIMIT}, {len(expl.split())} words")
if fails:
    print(f"{len(fails)} FAILED: {fails}")
    sys.exit(1)
print("form explanation is consistent with the published logbook")
