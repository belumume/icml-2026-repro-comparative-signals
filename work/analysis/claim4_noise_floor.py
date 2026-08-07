"""Claim 4: are the reported real-benchmark gains resolvable at the reported N?

The paper reports 60 result cells (3 tables x 10 models x 2 configs) and states the
one-step estimator "consistently yields estimates that are significantly closer to
the ground truth". Independently verified against the full text: the strings
"bootstrap" and "standard error" appear ZERO times; "confidence interval" appears
once, in Remark 4.6, which argues CIs are exactly what distinguishes genuine
improvement from noise.

CORRECTION (this file was rewritten after an error of mine). An earlier version
hand-transcribed a 17-cell subset and MISLABELLED two of the three tables, using
N=50 for what is actually AIME (N=15) and N=15 for what is actually GSM8K
(N=100). Every "gain in units of noise" it printed was therefore wrong, in both
directions. The rows are now parsed from the paper's HTML with each table bound
to its caption by document position (see extract_tables.py), so the benchmark
label and N come from the paper rather than from me, and all 60 cells are used.

This script does NOT re-run any LLM call. It tests the INFERENCE from the
published tables alone:
  1. binomial sampling noise on an accuracy estimated from N items
  2. each reported gain expressed in units of that noise
  3. the paper's own metric under a null where the one-step estimate carries no
     signal (simulated, because the metric is a difference of absolute errors)
  4. a sign test over all 60 cells, which is the one aggregate the data DOES
     support
  5. an internal-consistency check of the paper's own Improv. column
"""

import json
import math
import os
from math import comb

import numpy as np

from extract_tables import consistency, extract

HERE = os.path.dirname(os.path.abspath(__file__))

# Ground-truth reference size. GPQA/AIME GT% is the naive estimator on the FULL
# dataset; GSM8K's caption states no full-set size.
GT_N = {"GPQA": 198, "AIME": 30, "GSM8K": None}


def binom_se(p_pct, n):
    p = p_pct / 100.0
    return 100.0 * math.sqrt(max(p * (1 - p), 1e-12) / n)


def null_improv_distribution(gt, se_naive, se_step, draws=400_000, seed=0):
    """Distribution of |naive-GT| - |onestep-GT| when one-step adds NO signal.

    Null: both estimators are unbiased reads of the same quantity, drawn
    independently. With se_step == se_naive this null is SYMMETRIC, so the null
    mean of Improv is 0 and P(Improv>0)=0.5. That is the CONSERVATIVE choice --
    the easiest null for the paper's claim to beat. The stricter null
    (one-step = naive + extra independent noise) would make the observed pattern
    even harder to explain by chance.
    """
    rng = np.random.default_rng(seed)
    nai = rng.normal(gt, se_naive, draws)
    stp = rng.normal(gt, se_step, draws)
    return np.abs(nai - gt) - np.abs(stp - gt)


def build_rows():
    tabs = extract()
    rows = []
    for bench in ("GPQA", "AIME", "GSM8K"):
        for r in tabs[bench]:
            se = binom_se(r["naive"], r["N"])
            for cfg, step, imp in (
                (1, r["step1"], r["imp1"]),
                (2, r["step2"], r["imp2"]),
            ):
                recomp = abs(r["naive"] - r["GT"]) - abs(step - r["GT"])
                rows.append(
                    {
                        "bench": bench,
                        "N": r["N"],
                        "model": r["model"],
                        "cfg": cfg,
                        "GT": r["GT"],
                        "naive": r["naive"],
                        "onestep": step,
                        "improv_printed": imp,
                        "improv_recomputed": round(recomp, 3),
                        "self_consistent": abs(recomp - imp) <= 0.02,
                        "binom_se_pp": round(se, 3),
                        "printed_in_SE": round(imp / se, 3),
                        "recomputed_in_SE": round(recomp / se, 3),
                    }
                )
    return tabs, rows


def main():
    tabs, rows = build_rows()

    print("=" * 78)
    print("SOURCE: parsed from arXiv HTML, table->caption bound by position")
    print("=" * 78)
    for b in ("GPQA", "AIME", "GSM8K"):
        r0 = tabs[b][0]
        print(f"  Table {r0['table']}  {b:<6} N={r0['N']:<4} 10 models x 2 configs")
    print(f"  cells: {len(rows)}")

    print("\n" + "=" * 78)
    print("INTERNAL CONSISTENCY OF THE PAPER'S OWN 'Improv.' COLUMN")
    print("  Improv := |naive - GT| - |one-step - GT|, recomputed from the same row")
    print("=" * 78)
    bad = consistency([r for b in tabs for r in tabs[b]])
    print(f"  cells checked: {len(rows)}    inconsistent (>0.02pp): {len(bad)}")
    for b in bad:
        print(
            f"    {b['bench']:<6} {b['model']:<30} cfg{b['cfg']}  "
            f"printed {b['printed']:+.2f}  row implies {b['recomputed']:+.2f}  "
            f"delta {b['delta']:+.2f}"
        )
    signflip = [b for b in bad if b["printed"] * b["recomputed"] < 0]
    if signflip:
        print(
            f"  of these, {len(signflip)} FLIP SIGN (printed a gain where the row implies a loss)"
        )

    print("\n" + "=" * 78)
    print("GAINS RELATIVE TO BINOMIAL SAMPLING NOISE AT THE REPORTED N")
    print("=" * 78)
    print(
        f"{'bench':<7}{'N':>5}{'SE(pp)':>9}{'cells':>7}{'<1 SE':>8}{'<2 SE':>8}{'med |g|/SE':>12}"
    )
    for b in ("GPQA", "AIME", "GSM8K"):
        sub = [r for r in rows if r["bench"] == b]
        z = np.array([r["recomputed_in_SE"] for r in sub])
        ses = np.array([r["binom_se_pp"] for r in sub])
        print(
            f"{b:<7}{sub[0]['N']:>5}{ses.mean():>9.2f}{len(sub):>7}"
            f"{int((np.abs(z) < 1).sum()):>8}{int((np.abs(z) < 2).sum()):>8}"
            f"{np.median(np.abs(z)):>12.2f}"
        )
    z_all = np.array([r["recomputed_in_SE"] for r in rows])
    print(
        f"{'ALL':<7}{'':>5}{'':>9}{len(rows):>7}"
        f"{int((np.abs(z_all) < 1).sum()):>8}{int((np.abs(z_all) < 2).sum()):>8}"
        f"{np.median(np.abs(z_all)):>12.2f}"
    )

    print("\n" + "=" * 78)
    print("NULL DISTRIBUTION OF THE PAPER'S OWN METRIC (conservative symmetric null)")
    print("=" * 78)
    for b in ("GPQA", "AIME", "GSM8K"):
        sub = [r for r in rows if r["bench"] == b]
        gt = float(np.mean([r["GT"] for r in sub]))
        se = float(np.mean([r["binom_se_pp"] for r in sub]))
        d = null_improv_distribution(gt, se, se)
        big = float(
            np.mean(
                np.abs(d) >= np.median(np.abs([r["improv_recomputed"] for r in sub]))
            )
        )
        print(
            f"  {b:<6} SE~{se:5.2f}pp  null mean={d.mean():+.3f}pp  P(>0)={np.mean(d > 0):.3f}  "
            f"null 95th={np.percentile(d, 95):+.2f}pp"
        )
        print(
            f"          a gain as large as this benchmark's MEDIAN would arise by chance "
            f"{big * 100:.0f}% of the time"
        )

    print("\n" + "=" * 78)
    print("WHAT THE DATA DOES SUPPORT: aggregate sign test over all 60 cells")
    print("=" * 78)
    print("  INDEPENDENCE. The 60 cells are NOT independent: Config 1 and Config 2 for")
    print("  a given model/benchmark use the SAME evaluation subset (several pairs are")
    print(
        "  numerically identical), and all 10 models within a benchmark are scored on"
    )
    print("  the SAME items, so item-difficulty error is shared. A plain 60-cell")
    print("  binomial p is therefore ANTI-CONSERVATIVE. Quote the clustered figure.")
    for label, key in (
        ("as printed by the paper", "improv_printed"),
        ("recomputed from each row", "improv_recomputed"),
    ):
        vals = np.array([r[key] for r in rows])
        pos = int((vals > 0).sum())
        neg = int((vals < 0).sum())
        tot = pos + neg
        tail = sum(comb(tot, k) for k in range(pos, tot + 1)) / 2**tot
        print(
            f"  {label:<26} positive {pos}/{tot} (ties {len(vals) - tot})  exact one-sided p = {tail:.2e}"
        )
    # clustered: collapse cfg1/cfg2 to one value per (benchmark, model)
    import collections

    cl = collections.defaultdict(list)
    for r in rows:
        cl[(r["bench"], r["model"])].append(r["improv_recomputed"])
    clus = [sum(v) / len(v) for v in cl.values()]
    cp = sum(1 for v in clus if v > 0)
    cn = sum(1 for v in clus if v < 0)
    ct = cp + cn
    ctail = sum(comb(ct, k) for k in range(cp, ct + 1)) / 2**ct
    print(
        f"  {'CLUSTERED (bench, model)':<26} positive {cp}/{ct} clusters"
        f"          exact one-sided p = {ctail:.2e}  <-- quote this"
    )
    print("  -> the aggregate direction is real; per-cell resolution is not.")

    out = os.path.join(HERE, "claim4_noise_floor.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "inconsistent": bad}, f, indent=1)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
