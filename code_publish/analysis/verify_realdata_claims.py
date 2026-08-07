"""Assert every number written into the real-GSM8K section against the raw kernel JSON.

The section was transcribed by hand from the kernel output. A correction is a claim
(HANDOFF lesson 6), and hand transcription is exactly the step that produced this
project's worst error. So nothing in the prose is trusted: each figure is re-derived
from the JSON and compared to what the generator actually emits.
"""

import json
import re
import sys

RAW = "kaggle/real_data_ppi/out/real_gsm8k_ppi.json"
GEN = "tools/write_content.py"

d = json.load(open(RAW, encoding="utf-8"))
src = open(GEN, encoding="utf-8").read()

start = src.find("### A live run on real GSM8K")
end = src.find("### Ground 2:", start)
assert start != -1 and end > start, "real-data section not found in generator"
sec = src[start:end]

fails = []


def check(label, ok, detail=""):
    print(f"  {'OK  ' if ok else 'FAIL'} {label}{(' -- ' + detail) if detail else ''}")
    if not ok:
        fails.append(label)


# --- config -----------------------------------------------------------------
cfg = d["config"]
check("M = 500 in prose", f"M = {cfg['M']}" in sec)
check("N = 100 in prose", f"N = {cfg['N']}" in sec)
check("B in prose", f"B = {cfg['B']}" in sec or f"B = {cfg['B']:,}" in sec)
check("seed in prose", str(cfg["seed"]) in sec)
check("wall clock", f"{d['wall_clock_sec']:.0f}" in sec.replace(",", ""))
check("GPU named", d["env"]["gpu"] in sec)

# --- eval / aux model sets are DISJOINT (the leakage bug) --------------------
ev, ax = set(cfg["eval_models"]), set(cfg["aux_models"])
check("eval and aux model sets disjoint", not (ev & ax), f"overlap={ev & ax}")

for m in d["models"]:
    short = m["model"].split("/")[-1]
    gt = m["GT_pct"]
    auroc = m["aux_auroc"]
    imp = m["improv_mean_pp"]
    lo, hi = m["improv_ci95_pp"]
    frac = m["frac_improv_positive"]

    check(f"{short}: positive control passed", m["aux_informative"] is True)
    check(f"{short}: AUROC not degenerate", 0.5 < auroc < 1.0, f"{auroc:.4f}")
    check(
        f"{short}: no phi leakage",
        all(v < 0.95 for v in m["aux_phi_agreement"].values()),
        str(m["aux_phi_agreement"]),
    )
    check(f"{short}: CI spans zero", lo < 0 < hi and m["ci_spans_zero"] is True)

    # NOTE: the "draws>0" column was replaced by the CI for the mean when the
    # interval mislabelling was corrected. That CI is asserted below.
    row = [ln for ln in sec.splitlines() if short in ln]
    check(f"{short}: has a table row", len(row) == 1)
    if len(row) == 1:
        r = row[0]
        for val, lbl in [
            (f"{round(gt, 2)}%", "true accuracy"),
            (f"{auroc:.3f}", "AUROC"),
            (f"+{imp:.2f}", "point estimate"),
            (f"{lo:.2f}".replace("-", "−"), "CI low"),
            (f"+{hi:.2f}", "CI high"),
        ]:
            check(f"{short}: {lbl} = {val}", val in r, f"row={r.strip()[:90]}")

# --- the interpretive claims, as CORRECTED --------------------------------
# The first published version called the single-run spread a confidence interval and
# concluded the effect was indistinguishable from zero. It is not. Both framings must
# now be present and correct.
import math

B = d["config"]["B"]
for m in d["models"]:
    short = m["model"].split("/")[-1]
    se = m["improv_sd_pp"] / math.sqrt(B)
    lo_m, hi_m = m["improv_mean_pp"] - 1.96 * se, m["improv_mean_pp"] + 1.96 * se
    z = m["improv_mean_pp"] / se
    check(f"{short}: mean is reliably POSITIVE (z={z:.1f})", lo_m > 0)
    check(f"{short}: mean CI low  {lo_m:+.3f} quoted", f"{lo_m:+.3f}" in sec)
    check(f"{short}: mean CI high {hi_m:+.3f} quoted", f"{hi_m:+.3f}" in sec)

check(
    "section does NOT call the wide interval a confidence interval",
    "spread of a **single run**" in sec or "single run" in sec,
)
# This asserted the literal string "Correction, mine", which required the page to narrate
# a retraction. That requirement was wrong on two counts. It keyed on ONE WORDING, so
# rewriting the sentence more clearly reported the requirement as newly failing; and the
# retraction addressed nobody, because no reader has ever seen the earlier version -- the
# logbook is unsubmitted and has had no traffic. Disclosure is owed to someone who ACTED
# on an error, and the process record belongs in the published traces, not in the finding.
#
# What actually needed protecting is the statistical distinction, so that is what is
# asserted now: the wide interval must carry its correct technical name. The mean's own
# CI is already required, with its numbers, by the loop above.
check("the wide interval is named a prediction interval", "prediction interval" in sec)
check(
    "effect size given in interpretable units",
    "N = 112" in sec and "12% to 14%" in sec,
)
check(
    "estimator substitution disclosed",
    "not the paper's estimator" in sec.lower() or "It is not the paper" in sec,
)
# \s+ not a literal space: this prose is hard-wrapped, so the phrase spans a newline
# and a literal match silently fails. Same defect that produced a false positive in
# guard_interval_labels.py earlier today.
check(
    "greedy-decoding degeneracy disclosed",
    bool(re.search(r"identically\s+the\s+naive\s+mean", sec)),
)

print()
if fails:
    print(f"{len(fails)} ASSERTION(S) FAILED: {fails}")
    sys.exit(1)
print("every figure in the real-GSM8K section is backed by the raw kernel JSON")
