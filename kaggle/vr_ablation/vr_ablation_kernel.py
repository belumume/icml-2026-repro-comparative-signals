"""NUISANCE ABLATION: is the negative variance reduction a property of the estimator, or
of how its nuisance happens to be fit?

WHY THIS IS THE DECISIVE TEST, and why it is not the same as the standardisation control
---------------------------------------------------------------------------------------
The claim-3 page reports VR = -0.3300 at sigma = 0.08: the one-step estimator carries 33%
MORE variance than the naive mean it replaces. The measurement reproduces. What is
contested is the MECHANISM. An audit found the paper's own numbers inconsistent with the
published explanation ("too little signal"): the tau_hat residual sits near an absolute
floor while the target's SD falls 3.5x, and below sigma=0.15 the fitted tau_hat is beaten
by the CONSTANT predictor tau_hat == 0 -- which is inside the MLP's own hypothesis class.
That is an underfitting signature.

The visible candidate cause: models.py fits the nuisance with a bare nn.MSELoss at
lr=0.001 / 50 epochs, on a target whose mean is 0.0064, using hyperparameters chosen at
sigma ~ 1 where the target is ~150x larger.

A companion kernel tests that by STANDARDISING the target. This kernel attacks the same
question from the opposite side and is stronger, because it removes the failure mode
instead of compensating for it:

    RIDGE IS CLOSED-FORM. No learning rate, no epoch count, no SGD. Its solution is
    equivariant in the target scale (scale y by c and the fitted weights scale by c, for
    a correspondingly scaled penalty). It CANNOT underfit a small target the way a
    fixed-step-count gradient descent can.

So the two outcomes are cleanly separating, and neither is a null result:

    ridge ALSO gives negative VR at sigma=0.08
        -> underfitting is REFUTED as the mechanism. The effect survives its strongest
           objection and the falsification is stronger than currently published.

    ridge gives VR >= 0 where the MLP gave -0.33
        -> the published MECHANISM is wrong and the finding is about the nuisance fit,
           not the estimator. The measurement stands; the explanation must be rewritten,
           and the authors' likely reply lands.

kNN is included as a second, nonparametric witness with no gradient and no scale
sensitivity at all, so a ridge result is not resting on linearity.

METHOD. The authors' code is cloned at its pinned commit and NEVER edited. Only
`self.model` is swapped -- the object both `predict` and `predict_integrated` call -- so
the authors' own feature construction, cross-fitting, Monte-Carlo integration and estimator
algebra all run unchanged. The MLP arm is included as a CONTROL in the same run: if it does
not reproduce -0.33, the harness is wrong and no other arm means anything.
"""

import json
import os
import subprocess
import sys
import time

REPO = "https://github.com/zihandong02/AI_evaluation.git"
PIN = "aa03c3064e532a13dc65e0d58aa62a1a5402260f"
SRC = "/kaggle/working/AI_evaluation"
OUT = "/kaggle/working/vr_ablation_results.json"

RHO1, SIGMA_ETA, GAP, L = 0.8, 0.6, 0.05, 3


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True)


if not os.path.isdir(SRC):
    sh("git", "clone", "--quiet", REPO, SRC)
sh("git", "-C", SRC, "checkout", "--quiet", PIN)
head = sh("git", "-C", SRC, "rev-parse", "HEAD").stdout.strip()
dirty = sh("git", "-C", SRC, "status", "--porcelain").stdout.strip()
assert head == PIN, f"pin did not take: {head}"
assert dirty == "", f"authors' tree is DIRTY: {dirty[:200]}"
print(f"authors' code at {head}, tree clean")

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


class _Shim:
    """Stands in for the fitted nn.Module so the authors' call sites work untouched.

    Both `predict` and `predict_integrated` do `self.model(features)` after `.eval()`, so
    supplying an object with those two behaviours swaps the REGRESSOR while leaving every
    other line of their pipeline in place.
    """

    def __init__(self, fn):
        self.fn = fn

    def eval(self):
        # torch Module.eval(), i.e. inference mode. NOT the builtin eval(): nothing
        # in this file executes a string. The authors' predict paths call .eval()
        # before predicting, so the shim must answer to it.
        return self

    def train(self):
        return self

    def parameters(self):
        return iter(())

    def to(self, *_a, **_k):
        return self

    def __call__(self, feats):
        with torch.no_grad():
            x = feats.detach().cpu().numpy().astype(np.float64)
        return torch.as_tensor(self.fn(x), dtype=torch.float32)


def _ridge_fit(Xf, y, lam=1e-3):
    """Closed form, with an intercept and a scale-matched penalty.

    lam is scaled by mean(diag(X'X)) so the penalty means the same thing regardless of how
    large the features are; without that, 'ridge' would smuggle in its own scale
    sensitivity and defeat the purpose of the arm.
    """
    n, d = Xf.shape
    A = np.hstack([np.ones((n, 1)), Xf])
    G = A.T @ A
    scale = np.trace(G[1:, 1:]) / max(d, 1)
    P = np.eye(d + 1) * (lam * max(scale, 1e-12))
    P[0, 0] = 0.0  # never penalise the intercept
    w = np.linalg.solve(G + P, A.T @ y)
    return lambda Z: (np.hstack([np.ones((Z.shape[0], 1)), Z]) @ w)


def _knn_fit(Xf, y, k=25):
    """Nonparametric witness: no gradient, no scale sensitivity in the target at all."""
    mu, sd = Xf.mean(0), Xf.std(0)
    sd[sd < 1e-12] = 1.0
    Xn = (Xf - mu) / sd
    kk = min(k, len(y))

    def pred(Z):
        Zn = (Z - mu) / sd
        out = np.empty(len(Zn))
        # chunked so a large M*N integration grid cannot blow memory
        for i in range(0, len(Zn), 2048):
            blk = Zn[i : i + 2048]
            d2 = ((blk[:, None, :] - Xn[None, :, :]) ** 2).sum(-1)
            idx = np.argpartition(d2, kk - 1, axis=1)[:, :kk]
            out[i : i + 2048] = y[idx].mean(1)
        return out

    return pred


FITTERS = {"ridge": _ridge_fit, "knn": _knn_fit}


def patch_nuisance(kind):
    """Replace ONLY the regressor. Returns the class name so the swap is auditable."""
    import models as M

    cls = None
    for name in dir(M):
        o = getattr(M, name)
        if isinstance(o, type) and hasattr(o, "fit") and hasattr(o, "predict"):
            if any(k in name for k in ("Regress", "Nuisance", "Tau")):
                cls = o
                break
    assert cls is not None, "nuisance regressor not found in models.py"

    if getattr(cls, "_orig_fit", None) is None:
        cls._orig_fit = cls.fit

    if kind == "mlp":
        cls.fit = cls._orig_fit
        return cls.__name__ + ":mlp"

    fitter = FITTERS[kind]

    def fit(self, X, W1, W2, V, phi_targets):
        feats = self._construct_features(X, W1, W2, V)
        self.feature_dim = feats.shape[1]
        Xf = feats.detach().cpu().numpy().astype(np.float64)
        y = phi_targets.detach().cpu().numpy().astype(np.float64).ravel()
        self.model = _Shim(fitter(Xf, y))
        return self

    cls.fit = fit
    return f"{cls.__name__}:{kind}"


def one_trial(trial_id, sigma, seed, kind):
    patch_nuisance(kind)
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


def measure(sigma, kind, reps, jobs, seed_base):
    from joblib import Parallel, delayed

    res = Parallel(n_jobs=jobs, backend="loky")(
        delayed(one_trial)(i + 1, sigma, seed_base + i, kind) for i in range(reps)
    )
    naive = np.array([x[0] for x in res])
    eif = np.array([x[1] for x in res])
    vr = 1.0 - eif.var(axis=0, ddof=1) / naive.var(axis=0, ddof=1)
    # Bootstrap CONFIDENCE INTERVAL: resamples the SAME reps already drawn, so these
    # percentiles describe the sampling distribution of VR, not the spread of one run.
    rng = np.random.default_rng(7)
    boot = [
        1.0 - eif[i, 0].var(ddof=1) / naive[i, 0].var(ddof=1)
        for i in (rng.integers(0, reps, reps) for _ in range(2000))
    ]
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {"vr_m1": float(vr[0]), "ci95": [float(lo), float(hi)], "R": reps}


# Explicit and deterministic. hash() on a str is randomised per process unless
# PYTHONHASHSEED is pinned, so a hash-derived seed would silently not reproduce -- the one
# defect this repo can least afford.
SEEDS = {
    (0.08, "mlp"): 10000,
    (0.08, "ridge"): 20000,
    (0.08, "knn"): 30000,
    (1.0, "mlp"): 40000,
    (1.0, "ridge"): 50000,
    (1.0, "knn"): 60000,
}

JOBS = max(1, (os.cpu_count() or 4))
results = {"preflight": PREFLIGHT, "pin": PIN, "rows": []}
t0 = time.time()

print(f"\nnuisance ablation, {JOBS} workers\n")
for sigma in (0.08, 1.0):
    for kind in ("mlp", "ridge", "knn"):
        t = time.time()
        try:
            r = measure(sigma, kind, 60, JOBS, seed_base=SEEDS[(sigma, kind)])
            r.update(sigma=sigma, nuisance=kind, secs=round(time.time() - t, 1))
        except Exception as e:
            r = {
                "sigma": sigma,
                "nuisance": kind,
                "error": f"{type(e).__name__}: {str(e)[:160]}",
            }
        results["rows"].append(r)
        if "error" in r:
            print(f"  sigma={sigma:<5} {kind:<6} FAILED {r['error']}", flush=True)
        else:
            v = (
                "POSITIVE"
                if r["ci95"][0] > 0
                else "NEGATIVE"
                if r["ci95"][1] < 0
                else "spans 0"
            )
            print(
                f"  sigma={sigma:<5} {kind:<6} VR={r['vr_m1']:+.4f} "
                f"[{r['ci95'][0]:+.3f},{r['ci95'][1]:+.3f}]  {v}  ({r['secs']}s)",
                flush=True,
            )

# The MLP arm at sigma=0.08 is the CONTROL. If it does not land near -0.33 the harness is
# wrong and no other arm in this table means anything, so say that in the output rather
# than leaving a reader to notice.
ctrl = next(
    (
        r
        for r in results["rows"]
        if r.get("nuisance") == "mlp" and r.get("sigma") == 0.08
    ),
    None,
)
results["control_ok"] = bool(ctrl and "vr_m1" in ctrl and -0.55 < ctrl["vr_m1"] < -0.15)
print(
    f"\ncontrol (mlp @ 0.08 reproduces the published -0.3300): {results['control_ok']}"
)

results["secs"] = round(time.time() - t0, 1)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
print(f"wrote {OUT} ({results['secs']}s)")
