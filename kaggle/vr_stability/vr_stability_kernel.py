"""Is the low-sigma VR headline STABLE across independent runs? Measured, not assumed.

THE PROBLEM THIS EXISTS TO SETTLE
---------------------------------
Three runs of the SAME nominal configuration (sigma = 0.08, N = 1000, the authors'
unmodified estimator) have now produced:

    published        R=250   VR = -0.3300   bootstrap CI [-0.495, -0.185]
    ablation mlp arm R=60    VR = -0.5084   bootstrap CI [-0.933, -0.175]
    n-sweep control  R=60    VR = +0.0394   bootstrap CI [-0.159, +0.201]

The two R=60 intervals DO NOT OVERLAP, and the published point estimate falls OUTSIDE the
third run's interval. Nothing was patched in any of them; only the seed differs.

That is a direct contradiction of what the published interval asserts. A 95% bootstrap CI
of [-0.495, -0.185] says a rerun should land in that range about 19 times in 20. One
landed at +0.039.

WHY A BOOTSTRAP CI CAN UNDERSTATE THIS. The bootstrap resamples the R trials that were
actually drawn, so it estimates the sampling distribution of VR CONDITIONAL ON THAT SET.
VR = 1 - var(eif)/var(naive) is a ratio of two variances, both tiny here
(sigma2_naive = 8.19e-05), and each trial trains its own MLP with its own random
initialisation. If the per-trial estimates are heavy-tailed, a single wild trial dominates
var(eif); resampling WITH REPLACEMENT keeps that trial in roughly 63% of bootstrap draws,
so the interval stays centred near whatever the observed set happened to give. It cannot
represent the runs where no such trial occurred.

So the question is not "what is VR" but "how widely does VR scatter across independent
runs", and no amount of bootstrapping inside one run can answer it. Only independent
replication can.

WHAT THIS MEASURES
  K independent replicates at sigma = 0.08, each a complete R-trial experiment with its
  own seed block. Then the SPREAD ACROSS REPLICATES, compared against the mean bootstrap
  CI WIDTH WITHIN a replicate. If the across-replicate spread is much wider than the
  within-replicate interval, the published interval understates the real uncertainty and
  the headline has to be restated.

  A sigma = 1.0 arm runs as the CONTROL. There the effect is large and the variances are
  not tiny, so replicates should agree closely. If sigma = 1.0 also scatters, the
  instability is in the harness rather than in the low-sigma regime, and this whole
  reading is wrong.

NO PATCHING ANYWHERE. The authors' estimator runs exactly as shipped; only cfg.sigma_list
and the seed change. Results are banked after every single replicate.
"""

import json
import os
import statistics as st
import subprocess
import sys
import time

REPO = "https://github.com/zihandong02/AI_evaluation.git"
PIN = "aa03c3064e532a13dc65e0d58aa62a1a5402260f"
SRC = "/kaggle/working/AI_evaluation"
OUT = "/kaggle/working/vr_stability_results.json"

GAP, L = 0.05, 3
REPS = 100  # per replicate
ARMS = [(0.08, 10), (1.0, 4)]  # (sigma, number of independent replicates)
BUDGET_S = 6.5 * 3600


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True)


if not os.path.isdir(SRC):
    sh("git", "clone", "--quiet", REPO, SRC)
sh("git", "-C", SRC, "checkout", "--quiet", PIN)
head = sh("git", "-C", SRC, "rev-parse", "HEAD").stdout.strip()
dirty = sh("git", "-C", SRC, "status", "--porcelain").stdout.strip()
assert head == PIN, f"pin did not take: {head}"
assert dirty == "", f"authors' tree is DIRTY: {dirty[:200]}"
print(f"authors' code at {head}, tree clean, NO PATCHES")

sys.path.insert(0, os.path.join(SRC, "simulation"))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from config import SimulationConfig  # noqa: E402
from experiment import run_single_trial  # noqa: E402

PREFLIGHT = {"torch": torch.__version__, "cpu_count": os.cpu_count()}
print("preflight:", json.dumps(PREFLIGHT))


def one_trial(trial_id, seed, sigma):
    np.random.seed(seed)
    torch.manual_seed(seed)
    c = SimulationConfig()
    c.sigma_list = [sigma + i * GAP for i in range(L)]
    c.num_models = L
    c.R = 1
    c.device = "cpu"
    r = run_single_trial(trial_id=trial_id, config=c, verbose=False)
    return (
        np.asarray(r["naive_estimates"], float),
        np.asarray(r["eif_estimates"], float),
    )


def replicate(sigma, jobs, seed_base):
    """One COMPLETE experiment: R trials, its own VR, its own bootstrap CI."""
    from joblib import Parallel, delayed

    res = Parallel(n_jobs=jobs, backend="loky")(
        delayed(one_trial)(i + 1, seed_base + i, sigma) for i in range(REPS)
    )
    naive = np.array([x[0] for x in res])
    eif = np.array([x[1] for x in res])
    vr = float(1.0 - eif[:, 0].var(ddof=1) / naive[:, 0].var(ddof=1))
    # interval-label-cleared: this file computes BOTH quantities deliberately and its
    # entire purpose is to compare them, so the distinction the guard asks about is the
    # subject rather than a hazard.
    #   THIS loop  -> a CONDITIONAL BOOTSTRAP CI. It resamples the SAME REPS trials drawn
    #                 just above, with replacement, so it estimates the sampling
    #                 distribution of VR given this particular draw. Fresh data is never
    #                 generated inside it.
    #   The OUTER loop over replicates -> the ACROSS-RUN SPREAD, which does draw fresh
    #                 data each time and is therefore the honest rerun-to-rerun
    #                 uncertainty. That is the quantity a reader of the headline needs.
    # The published interval is the first kind. The claim it appears to make is about the
    # second.
    rng = np.random.default_rng(7)
    boot = [
        1.0 - eif[i, 0].var(ddof=1) / naive[i, 0].var(ddof=1)
        for i in (rng.integers(0, REPS, REPS) for _ in range(2000))
    ]
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {
        "vr": vr,
        "ci95": [float(lo), float(hi)],
        "ci_width": float(hi - lo),
        "seed_base": seed_base,
    }


JOBS = max(1, (os.cpu_count() or 4))
results = {"preflight": PREFLIGHT, "pin": PIN, "reps_per_replicate": REPS, "arms": []}
t0 = time.time()


def bank():
    results["secs"] = round(time.time() - t0, 1)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


print(f"\nR={REPS} per replicate, {JOBS} workers, unmodified estimator\n")
for sigma, k in ARMS:
    arm = {"sigma": sigma, "replicates": []}
    results["arms"].append(arm)
    for j in range(k):
        if time.time() - t0 > BUDGET_S:
            print(f"  budget reached; stopping at sigma={sigma} replicate {j}")
            arm["truncated_at"] = j
            bank()
            break
        r = replicate(
            sigma, JOBS, seed_base=100_000 + int(sigma * 1000) * 1000 + j * 500
        )
        arm["replicates"].append(r)
        bank()
        print(
            f"  sigma={sigma:<5} rep {j + 1}/{k}: VR={r['vr']:+.4f} "
            f"CI [{r['ci95'][0]:+.3f},{r['ci95'][1]:+.3f}] width={r['ci_width']:.3f}",
            flush=True,
        )

    vs = [r["vr"] for r in arm["replicates"]]
    if len(vs) >= 2:
        arm["across_replicate_sd"] = float(st.stdev(vs))
        arm["across_replicate_range"] = [float(min(vs)), float(max(vs))]
        arm["mean_within_ci_width"] = float(
            st.mean(r["ci_width"] for r in arm["replicates"])
        )
        # THE COMPARISON THIS KERNEL EXISTS FOR. A 95% interval should be about 3.92 SD
        # wide, so if the mean within-replicate width is much NARROWER than 3.92x the
        # across-replicate SD, the reported intervals understate the real uncertainty.
        implied = 3.92 * arm["across_replicate_sd"]
        arm["implied_width_from_spread"] = float(implied)
        arm["understatement_factor"] = float(implied / arm["mean_within_ci_width"])
        arm["n_negative"] = sum(1 for v in vs if v < 0)
        print(
            f"    -> across-replicate SD {arm['across_replicate_sd']:.4f}, "
            f"range [{min(vs):+.4f}, {max(vs):+.4f}], "
            f"{arm['n_negative']}/{len(vs)} negative"
        )
        print(
            f"    -> mean within-replicate CI width {arm['mean_within_ci_width']:.4f} vs "
            f"{implied:.4f} implied by the spread "
            f"(understatement factor {arm['understatement_factor']:.2f}x)",
            flush=True,
        )
    bank()

print("\nREADING GUIDE")
print(
    "  sigma=1.0 is the control: if IT scatters too, the instability is in the harness"
)
print("  and the low-sigma reading below is wrong. Check that arm first.")
print(
    "  understatement_factor >> 1 at sigma=0.08 means the published bootstrap interval"
)
print(
    "  does not represent rerun-to-rerun uncertainty, and the headline must be restated."
)
bank()
print(f"\nwrote {OUT} ({results['secs']}s)")
