"""Settle the MECHANISM behind the negative variance reduction, off the operator's laptop.

WHY THIS RUNS HERE AND NOT LOCALLY
----------------------------------
Measured on the laptop 2026-08-03: one trial = 21.08s, and driving it 12-wide put the
machine at 93% CPU with 2.6 GB of 15.4 GB free -- unusable. Probe A alone is 240 trials
(~84 min serial). Probe B at N=16000 is roughly 16x per trial again. That belongs on free
cloud compute, not on the machine the operator is using.

Also measured locally: the installed torch is `2.7.0+cpu`, a CPU-ONLY BUILD, so
`torch.cuda.is_available()` is False and the RTX 3060 in that laptop is invisible to it.
The GPU question therefore CANNOT be answered locally at all. Kaggle ships a CUDA build,
so this kernel measures it directly rather than asserting an answer: it times one trial on
CPU and one on CUDA and prints both. A 64->32 MLP on N=1000 with batch 128 is plausibly
launch-overhead-bound on a GPU, but that is a hypothesis until the numbers land here.

WHAT IS BEING SETTLED
---------------------
The claim-3 page reports a real, reproducible result: at low model noise the one-step
estimator carries MORE variance than the plain mean (VR = -0.33 at sigma=0.08, 250 reps).
That measurement is not in dispute. The page attributes it to a MECHANISM -- too little
signal for the nuisance regression -- and an independent audit found that attribution
contradicted by the repo's own numbers: the tau_hat residual sits at an absolute floor
while the target's SD falls 3.5x, and below sigma=0.15 the fitted tau_hat is BEATEN by the
constant predictor tau_hat==0, which is inside the MLP's own hypothesis class. That is an
underfitting signature. The visible candidate cause is that models.py fits a bare
nn.MSELoss() with no target standardisation, at lr=0.001 / 50 epochs, on a target whose
mean is 0.0064 -- hyperparameters chosen at sigma~1 where the target is ~150x larger.

  PROBE A  standardisation control. Z-score the nuisance target in fit(), invert in
           predict(). ONE change; seeds, architecture, epochs, batch all identical.
           VR moves toward zero  -> published mechanism is WRONG, the finding is about
                                    tuning and the authors' strongest reply lands.
           VR stays negative     -> the mechanism survives its strongest objection.

  PROBE B  N sweep at fixed low sigma. Corollary 4.7 is asymptotic and the blamed term is
           the one that vanishes in N. Locate the crossover N* where VR turns positive, or
           show it does not turn within reach. A single grid point cannot settle this.

The authors' code is CLONED AT ITS PINNED COMMIT and never edited; both probes patch in
process. So "ran their code unmodified" stays literally true and independently checkable.
"""

import json
import os
import subprocess
import sys
import time

REPO = "https://github.com/zihandong02/AI_evaluation.git"
PIN = "aa03c3064e532a13dc65e0d58aa62a1a5402260f"
SRC = "/kaggle/working/AI_evaluation"
OUT = "/kaggle/working/vr_mechanism_results.json"

RHO1, SIGMA_ETA, GAP, L = 0.8, 0.6, 0.05, 3


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True)


def clone():
    if not os.path.isdir(SRC):
        sh("git", "clone", "--quiet", REPO, SRC)
    sh("git", "-C", SRC, "checkout", "--quiet", PIN)
    head = sh("git", "-C", SRC, "rev-parse", "HEAD").stdout.strip()
    dirty = sh("git", "-C", SRC, "status", "--porcelain").stdout.strip()
    # A pin that did not take, or a tree we edited, silently invalidates every number
    # below -- so assert both rather than trusting the clone.
    assert head == PIN, f"pin did not take: HEAD={head}"
    assert dirty == "", f"authors' tree is DIRTY: {dirty[:200]}"
    print(f"authors' code at {head}, tree clean")


clone()
sys.path.insert(0, os.path.join(SRC, "simulation"))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from config import SimulationConfig  # noqa: E402
from experiment import run_single_trial  # noqa: E402

PREFLIGHT = {
    "torch": torch.__version__,
    "cuda_available": torch.cuda.is_available(),
    "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    "gpu_count": torch.cuda.device_count(),
    "cpu_count": os.cpu_count(),
}
print("preflight:", json.dumps(PREFLIGHT))


def theoretical(base_sigma):
    sig = np.array([base_sigma + i * GAP for i in range(L)])
    r2 = (RHO1**2 * sig**2) / (RHO1**2 * sig**2 + SIGMA_ETA**2)
    return sig, sig**2, r2, r2**2


def patch_standardise():
    """Z-score the nuisance target in fit, invert in predict. Runtime only, idempotent."""
    import models as M

    cls = None
    for name in dir(M):
        obj = getattr(M, name)
        if isinstance(obj, type) and hasattr(obj, "fit") and hasattr(obj, "predict"):
            if any(k in name for k in ("Regress", "Nuisance", "Tau")):
                cls = obj
                break
    assert cls is not None, "could not locate the nuisance regressor in models.py"
    if getattr(cls, "_std_patched", False):
        return cls.__name__
    of, op = cls.fit, cls.predict

    def fit(self, X, W1, W2, V, phi_targets):
        t = phi_targets.detach().clone().float()
        self._mu = float(t.mean())
        s = float(t.std())
        self._sd = s if s > 1e-12 else 1.0
        return of(self, X, W1, W2, V, (t - self._mu) / self._sd)

    def predict(self, X, W1, W2, V):
        return op(self, X, W1, W2, V) * getattr(self, "_sd", 1.0) + getattr(
            self, "_mu", 0.0
        )

    cls.fit, cls.predict, cls._std_patched = fit, predict, True
    return cls.__name__


def one_trial(trial_id, sigma, seed, n=None, standardise=False, device=None):
    if standardise:
        patch_standardise()
    np.random.seed(seed)
    torch.manual_seed(seed)
    c = SimulationConfig()
    c.sigma_list = [sigma + i * GAP for i in range(L)]
    c.num_models = L
    c.R = 1
    if n is not None:
        c.N = n
    if device is not None:
        c.device = device
    r = run_single_trial(trial_id=trial_id, config=c, verbose=False)
    return (
        np.asarray(r["naive_estimates"], float),
        np.asarray(r["eif_estimates"], float),
    )


def measure(sigma, reps, jobs, n=None, standardise=False, seed_base=0, device=None):
    from joblib import Parallel, delayed

    res = Parallel(n_jobs=jobs, backend="loky")(
        delayed(one_trial)(i + 1, sigma, seed_base + i, n, standardise, device)
        for i in range(reps)
    )
    naive = np.array([x[0] for x in res])
    eif = np.array([x[1] for x in res])
    vn, ve = naive.var(axis=0, ddof=1), eif.var(axis=0, ddof=1)
    vr = 1.0 - ve / vn
    # Bootstrap CONFIDENCE INTERVAL for the estimate: this resamples the SAME `reps`
    # replications drawn above, so the percentiles describe the sampling distribution of
    # VR. A loop redrawing fresh data each iteration would be a prediction interval for a
    # single future run, which is a different and much wider quantity.
    rng = np.random.default_rng(7)
    boot = [
        1.0 - eif[i, 0].var(ddof=1) / naive[i, 0].var(ddof=1)
        for i in (rng.integers(0, reps, reps) for _ in range(2000))
    ]
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {
        "vr_m1": float(vr[0]),
        "ci95": [float(lo), float(hi)],
        "vr_all": vr.tolist(),
        "R": reps,
        "N": n,
    }


results = {"preflight": PREFLIGHT, "pin": PIN}
t_start = time.time()

# ---- device choice, MEASURED rather than assumed -----------------------------------
print("\n=== device timing: one trial each, N=1000 ===", flush=True)
timing = {}
for dev in ["cpu"] + (["cuda"] if torch.cuda.is_available() else []):
    t = time.time()
    try:
        one_trial(1, 0.08, 1, device=dev)
        timing[dev] = round(time.time() - t, 2)
    except Exception as e:
        timing[dev] = f"FAILED {type(e).__name__}: {str(e)[:80]}"
    print(f"  {dev:5}: {timing[dev]}", flush=True)
results["device_timing_one_trial_s"] = timing

ok = {k: v for k, v in timing.items() if isinstance(v, (int, float))}
DEV = min(ok, key=lambda k: ok[k]) if ok else "cpu"
# CPU wins => parallelise across trials with every core. CUDA wins => the GPU is the
# bottleneck resource, so keep the fan narrow and let each trial have it.
JOBS = max(1, (os.cpu_count() or 4)) if DEV == "cpu" else 2
print(f"  -> using {DEV} with {JOBS} worker(s)\n", flush=True)
results["device_used"], results["jobs"] = DEV, JOBS

# ---- PROBE A: standardisation control ----------------------------------------------
print("=== PROBE A: standardisation control ===", flush=True)
results["probe_a"] = []
for si, s in enumerate(SIGMAS := [0.08, 0.15]):
    _, _, _, theo = theoretical(s)
    base = 10_000 * (si + 1)
    off = measure(s, 60, JOBS, standardise=False, seed_base=base, device=DEV)
    on = measure(s, 60, JOBS, standardise=True, seed_base=base, device=DEV)
    row = {
        "sigma": s,
        "vr_theoretical_m1": float(theo[0]),
        "as_published": off,
        "standardised": on,
        "delta": on["vr_m1"] - off["vr_m1"],
    }
    results["probe_a"].append(row)
    print(
        f"  sigma={s:<5} theory={theo[0]:+.4f}  published={off['vr_m1']:+.4f} "
        f"[{off['ci95'][0]:+.3f},{off['ci95'][1]:+.3f}]  standardised={on['vr_m1']:+.4f} "
        f"[{on['ci95'][0]:+.3f},{on['ci95'][1]:+.3f}]  delta={row['delta']:+.4f}",
        flush=True,
    )

# ---- PROBE B: N sweep at fixed low sigma -------------------------------------------
print("\n=== PROBE B: N sweep at sigma=0.08 (unpatched) ===", flush=True)
_, _, _, theo = theoretical(0.08)
results["probe_b"] = []
for ni, n in enumerate([1000, 4000, 16000, 64000]):
    if time.time() - t_start > 9.5 * 3600:
        print(f"  stopping before N={n}: session budget", flush=True)
        results["probe_b_truncated_at"] = n
        break
    r = measure(0.08, 60, JOBS, n=n, seed_base=20_000 * (ni + 1), device=DEV)
    r["vr_theoretical_m1"] = float(theo[0])
    results["probe_b"].append(r)
    verdict = (
        "POSITIVE"
        if r["ci95"][0] > 0
        else "negative"
        if r["ci95"][1] < 0
        else "spans zero"
    )
    print(
        f"  N={n:<7} VR={r['vr_m1']:+.4f} [{r['ci95'][0]:+.3f},{r['ci95'][1]:+.3f}]  "
        f"theory={theo[0]:+.4f}  {verdict}",
        flush=True,
    )

results["total_secs"] = round(time.time() - t_start, 1)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
print(f"\nwrote {OUT} ({results['total_secs']}s)")
