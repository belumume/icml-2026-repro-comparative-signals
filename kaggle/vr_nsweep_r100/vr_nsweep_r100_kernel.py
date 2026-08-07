"""N sweep at fixed low sigma, R=100, on the UNMODIFIED estimator. No monkeypatching.

RERUN AT R=100. THE R=60 VERSION'S CONTROL FAILED, AND WE NOW KNOW WHY
---------------------------------------------------------------------
The first run of this sweep used R=60 and its N=1000 control returned VR = +0.0394,
where the published value is -0.3300. By its own rule every row was discarded.

A later stability measurement explained it. Ten independent replicates at sigma=0.08 with
R=100 gave -0.2565 to -0.1227, negative 10 times out of 10, across-run SD 0.047, against a
sigma=1.0 control that was near-noiseless at SD 0.004. The two wild values that started the
alarm, -0.5084 and +0.0394, were BOTH R=60. VR is a ratio of two variance estimates and a
variance ratio is badly behaved at small R; at R=100 it does not change sign once in ten
tries.

So R=60 was the defect, not the finding. This rerun uses R=100, where the same measurement
is known to be stable, and keeps everything else identical: no patching, banking after
every N, and a guard below the wall rather than above it.


WHAT THIS REPLACES, AND WHY THE PREVIOUS ATTEMPT WAS DISCARDED
--------------------------------------------------------------
A previous kernel bundled this sweep with a standardisation control and produced
impossible numbers: VR = -1038 at sigma=0.08, VR = -6793 at N=16000. VR is
1 - var_eif/var_naive, so -1038 means the one-step estimator carried 1039x the naive
variance. Its control arm also reported -0.1312 where the published value is -0.3300, so
the control did not reproduce and nothing in that run was interpretable. It was then
cancelled at the session wall after ~11.5 hours.

Two bugs, both mine, both avoided here by construction rather than by care:

  1. SCALE MIXING. That kernel patched `fit` and `predict` to standardise the nuisance
     target, but NOT `predict_integrated`. m-hat comes from predict_integrated, which
     calls self.model(features) directly, so m-hat stayed on the standardised scale while
     tau-hat was de-standardised on the way out of predict. psi = m_hat + phi - tau_hat
     then subtracts quantities on different scales.

  2. WORKER CONTAMINATION. The patch mutated the CLASS and never restored it. joblib/loky
     reuses worker processes, so once a standardised trial ran in a worker, every later
     "unpatched" trial in that same worker was still patched. That is why the control arm
     was wrong too, and why sigma=0.15 reported the patched and unpatched arms as
     bit-identical.

THIS KERNEL APPLIES NO PATCH OF ANY KIND. It runs the authors' estimator exactly as
shipped, varying only cfg.N. Neither bug can occur, because there is nothing to restore
and no scale to mix.

THE QUESTION. Corollary 4.7 is asymptotic, and the term blamed for the low-sigma failure
is the one that vanishes in N. So: does the promised gain appear as N grows, and if so
where? A single grid point cannot answer that; the published finding rests on N=1000.

THREE THINGS THIS DOES THAT THE LAST ONE DID NOT
  * BANKS INCREMENTALLY. The JSON is rewritten after every single N. The previous kernel
    wrote only at the end, so a wall-clock kill destroyed everything it had computed. A
    long run whose value materialises only at the end is a design error, not bad luck.
  * DROPS N=64000. At N=1000 a trial is ~21s; 64x the data across 60 reps cannot finish
    in a session, and attempting it is what consumed the previous run.
  * GUARDS BELOW THE WALL, not above it. The previous guard sat at 9.5h, above the limit
    that actually killed it, so it never fired.
"""

import json
import os
import subprocess
import sys
import time

REPO = "https://github.com/zihandong02/AI_evaluation.git"
PIN = "aa03c3064e532a13dc65e0d58aa62a1a5402260f"
SRC = "/kaggle/working/AI_evaluation"
OUT = "/kaggle/working/vr_nsweep_r100_results.json"

RHO1, SIGMA_ETA, GAP, L = 0.8, 0.6, 0.05, 3
SIGMA = 0.08
NS = [1000, 4000, 16000]
REPS = 100
BUDGET_S = 9.0 * 3600  # comfortably under the session wall, unlike the last attempt
PUBLISHED_VR = -0.3300  # what N=1000 must land near, or the run means nothing


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True)


if not os.path.isdir(SRC):
    sh("git", "clone", "--quiet", REPO, SRC)
sh("git", "-C", SRC, "checkout", "--quiet", PIN)
head = sh("git", "-C", SRC, "rev-parse", "HEAD").stdout.strip()
dirty = sh("git", "-C", SRC, "status", "--porcelain").stdout.strip()
assert head == PIN, f"pin did not take: {head}"
assert dirty == "", f"authors' tree is DIRTY: {dirty[:200]}"
print(f"authors' code at {head}, tree clean, NO PATCHES APPLIED")

sys.path.insert(0, os.path.join(SRC, "simulation"))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from config import SimulationConfig  # noqa: E402
from experiment import run_single_trial  # noqa: E402

PREFLIGHT = {
    "torch": torch.__version__,
    "cuda": torch.cuda.is_available(),
    "cpu_count": os.cpu_count(),
}
print("preflight:", json.dumps(PREFLIGHT))


def theoretical(base_sigma):
    sig = np.array([base_sigma + i * GAP for i in range(L)])
    r2 = (RHO1**2 * sig**2) / (RHO1**2 * sig**2 + SIGMA_ETA**2)
    return float((r2**2)[0])


def one_trial(trial_id, seed, n):
    np.random.seed(seed)
    torch.manual_seed(seed)
    c = SimulationConfig()
    c.sigma_list = [SIGMA + i * GAP for i in range(L)]
    c.num_models = L
    c.R = 1
    c.N = n
    c.device = "cpu"
    r = run_single_trial(trial_id=trial_id, config=c, verbose=False)
    return (
        np.asarray(r["naive_estimates"], float),
        np.asarray(r["eif_estimates"], float),
    )


def measure(n, jobs, seed_base):
    from joblib import Parallel, delayed

    res = Parallel(n_jobs=jobs, backend="loky")(
        delayed(one_trial)(i + 1, seed_base + i, n) for i in range(REPS)
    )
    naive = np.array([x[0] for x in res])
    eif = np.array([x[1] for x in res])
    vr = 1.0 - eif.var(axis=0, ddof=1) / naive.var(axis=0, ddof=1)
    # Bootstrap CONFIDENCE INTERVAL: resamples the SAME reps drawn above, so these
    # percentiles describe the sampling distribution of VR, not the spread of one run.
    rng = np.random.default_rng(7)
    boot = [
        1.0 - eif[i, 0].var(ddof=1) / naive[i, 0].var(ddof=1)
        for i in (rng.integers(0, REPS, REPS) for _ in range(2000))
    ]
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {
        "N": n,
        "vr_m1": float(vr[0]),
        "ci95": [float(lo), float(hi)],
        "vr_all": vr.tolist(),
        "R": REPS,
    }


JOBS = max(1, (os.cpu_count() or 4))
results = {
    "preflight": PREFLIGHT,
    "pin": PIN,
    "sigma": SIGMA,
    "patched": False,
    "vr_theoretical_m1": theoretical(SIGMA),
    "rows": [],
}
t0 = time.time()


def bank():
    """Rewrite the whole file after every N. Cheap, and it is the difference between a
    wall-clock kill costing one data point and costing the entire run."""
    results["secs"] = round(time.time() - t0, 1)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


print(f"\nN sweep at sigma={SIGMA}, R={REPS}, {JOBS} workers, unmodified estimator\n")
for ni, n in enumerate(NS):
    if time.time() - t0 > BUDGET_S:
        print(f"  stopping before N={n}: budget reached, banked results are on disk")
        results["truncated_at"] = n
        bank()
        break
    t = time.time()
    r = measure(n, JOBS, seed_base=20_000 * (ni + 1))
    r["secs"] = round(time.time() - t, 1)
    results["rows"].append(r)
    bank()  # bank BEFORE printing, so a kill mid-print still leaves the row
    lo, hi = r["ci95"]
    verdict = "POSITIVE" if lo > 0 else "negative" if hi < 0 else "spans zero"
    print(
        f"  N={n:<7} VR={r['vr_m1']:+.4f} [{lo:+.3f},{hi:+.3f}]  {verdict}  ({r['secs']}s)",
        flush=True,
    )

# The N=1000 row is the CONTROL: it is the published configuration, so it must land near
# the published -0.3300 or the harness is wrong and no larger-N row can be read. Stating
# it in the output rather than leaving a reader to notice.
ctrl = next((r for r in results["rows"] if r["N"] == 1000), None)
results["control_ok"] = bool(
    ctrl and ctrl["ci95"][0] <= PUBLISHED_VR <= ctrl["ci95"][1]
)
print(
    f"\ncontrol: published {PUBLISHED_VR:+.4f} inside the N=1000 interval? "
    f"{results['control_ok']}"
)
if not results["control_ok"]:
    print("  CONTROL FAILED -- discard every row above, as the previous kernel's were.")
bank()
print(f"wrote {OUT} ({results['secs']}s)")
