"""Settle WHY the variance reduction goes negative at low model noise.

THE QUESTION THIS ANSWERS
-------------------------
The claim-3 page reports a real, reproducible result: at low model noise the one-step
estimator carries MORE variance than the plain mean it replaces (VR = -0.33 at sigma=0.08,
95% CI [-0.495, -0.185], 250 reps, with the authors' default sigma=1.0 passing as a
control). That measurement is not in dispute here and re-derives from the shipped JSON.

The page then attributes it to a MECHANISM: too little signal for the nuisance regression
to exploit. An independent audit found that attribution contradicted by the repo's own
numbers -- backing SD(phi - tau_hat) out of results/vr_lowsigma.json, the residual sits
near an absolute floor while the target's own SD falls 3.5x across the sweep, and below
sigma=0.15 the fitted tau_hat is beaten by the CONSTANT predictor tau_hat == 0, which is
inside the MLP's own hypothesis class. No vanishing-signal story produces that. An
underfitting story does, and there is a visible candidate cause: models.py fits a bare
nn.MSELoss() with no target standardisation, at lr=0.001 / 50 epochs, on a target whose
mean is 0.0064 -- hyperparameters chosen at sigma ~ 1, where the target is ~150x larger.

So the measurement may be right and the published REASON wrong. That distinction matters:
"the estimator has a regime where it hurts" is a claim about the estimator, while "the
estimator hurts when you run its reference hyperparameters against an unstandardised
target two orders of magnitude smaller" is a claim about the tuning, and the authors'
strongest reply is exactly the second.

TWO PROBES, both against the authors' unmodified code on disk
--------------------------------------------------------------
A. STANDARDISATION CONTROL. Monkeypatch the nuisance regressor at RUNTIME so its target
   is z-scored before fitting and the prediction is mapped back. Nothing else changes:
   same seeds, same architecture, same epochs, same data. If VR moves toward zero or
   flips sign, the published mechanism is wrong and the finding is about tuning. If VR
   stays negative, the mechanism survives its strongest objection and the finding is
   about the estimator.

B. N SWEEP AT FIXED LOW SIGMA. Corollary 4.7 is asymptotic, and the term the page blames
   is the one that vanishes in N. Run sigma=0.08 across N and locate the crossover N*
   where VR turns positive -- or show it does not turn within reach. Either outcome is
   decisive; a single grid point cannot be.

The authors' files are NOT edited. Both probes patch in-process, so `git status` on
work/AI_evaluation stays clean and the "ran their code unmodified" claim is untouched.

Run:
  python work/analysis/vr_mechanism_probe.py --probe std --sigmas 0.08 0.15 --R 60
  python work/analysis/vr_mechanism_probe.py --probe n   --sigma 0.08 --Ns 1000 4000 16000
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
SIM = ROOT / "work" / "AI_evaluation" / "simulation"
sys.path.insert(0, str(SIM))

import torch  # noqa: E402
from config import SimulationConfig  # noqa: E402
from experiment import run_single_trial  # noqa: E402

torch.set_num_threads(1)

RHO1, SIGMA_ETA, GAP, L = 0.8, 0.6, 0.05, 3


def theoretical(base_sigma):
    sig = np.array([base_sigma + i * GAP for i in range(L)])
    r2 = (RHO1**2 * sig**2) / (RHO1**2 * sig**2 + SIGMA_ETA**2)
    return sig, sig**2, r2, r2**2


def patch_standardise():
    """Z-score the nuisance target inside fit, invert inside predict. Runtime only.

    This is the ONE change. The optimiser, architecture, epochs, batch size and seeds are
    untouched, so any movement in VR is attributable to target scale and nothing else.
    """
    import models as M

    cls = None
    for name in dir(M):
        obj = getattr(M, name)
        if isinstance(obj, type) and hasattr(obj, "fit") and hasattr(obj, "predict"):
            if "Regress" in name or "Nuisance" in name or "Tau" in name:
                cls = obj
                break
    if cls is None:
        raise SystemExit("could not locate the nuisance regressor class in models.py")

    orig_fit, orig_predict = cls.fit, cls.predict

    def fit(self, X, W1, W2, V, phi_targets):
        t = phi_targets.detach().clone().float()
        self._mu = float(t.mean())
        sd = float(t.std())
        self._sd = sd if sd > 1e-12 else 1.0
        return orig_fit(self, X, W1, W2, V, (t - self._mu) / self._sd)

    def predict(self, X, W1, W2, V):
        out = orig_predict(self, X, W1, W2, V)
        mu = getattr(self, "_mu", 0.0)
        sd = getattr(self, "_sd", 1.0)
        return out * sd + mu

    cls.fit, cls.predict = fit, predict
    return cls.__name__


def one_trial(trial_id, base_sigma, seed, n=None, standardise=False):
    if standardise:
        patch_standardise()
    np.random.seed(seed)
    torch.manual_seed(seed)
    cfg = SimulationConfig()
    cfg.sigma_list = [base_sigma + i * GAP for i in range(L)]
    cfg.num_models = L
    cfg.R = 1
    if n is not None:
        cfg.N = n
    r = run_single_trial(trial_id=trial_id, config=cfg, verbose=False)
    return (
        np.asarray(r["naive_estimates"], dtype=float),
        np.asarray(r["eif_estimates"], dtype=float),
        np.asarray(r["oracle_estimates"], dtype=float),
    )


def measure(sigma, reps, jobs, n=None, standardise=False, seed_base=0):
    from joblib import Parallel, delayed

    res = Parallel(n_jobs=jobs, backend="loky")(
        delayed(one_trial)(i + 1, sigma, seed_base + i, n, standardise)
        for i in range(reps)
    )
    naive = np.array([x[0] for x in res])
    eif = np.array([x[1] for x in res])
    v_naive = naive.var(axis=0, ddof=1)
    v_eif = eif.var(axis=0, ddof=1)
    vr = 1.0 - v_eif / v_naive

    # Bootstrap CONFIDENCE INTERVAL for the VR estimate, not a prediction interval for a
    # single run: the loop resamples the SAME `reps` replications already drawn above,
    # with replacement, so the percentiles describe the sampling distribution of the
    # estimate. A loop that redrew fresh data each iteration would mean the other thing.
    rng = np.random.default_rng(7)
    boot = []
    for _ in range(2000):
        idx = rng.integers(0, reps, reps)
        boot.append(1.0 - eif[idx, 0].var(ddof=1) / naive[idx, 0].var(ddof=1))
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {
        "vr_m1": float(vr[0]),
        "ci95": [float(lo), float(hi)],
        "vr_all": vr.tolist(),
        "var_naive_m1": float(v_naive[0]),
        "var_eif_m1": float(v_eif[0]),
        "R": reps,
        "N": n,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", choices=["std", "n"], required=True)
    ap.add_argument("--sigmas", type=float, nargs="+", default=[0.08, 0.15])
    ap.add_argument("--sigma", type=float, default=0.08)
    ap.add_argument("--Ns", type=int, nargs="+", default=[1000, 4000, 16000])
    ap.add_argument("--R", type=int, default=60)
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    t0 = time.time()
    rows = []

    if args.probe == "std":
        print("PROBE A: standardisation control (same seeds, same everything else)\n")
        for si, s in enumerate(args.sigmas):
            _, _, _, vr_theo = theoretical(s)
            base = 10_000 * (si + 1)
            off = measure(s, args.R, args.jobs, standardise=False, seed_base=base)
            on = measure(s, args.R, args.jobs, standardise=True, seed_base=base)
            row = {
                "sigma": s,
                "vr_theoretical_m1": float(vr_theo[0]),
                "as_published": off,
                "standardised": on,
                "delta_vr": on["vr_m1"] - off["vr_m1"],
            }
            rows.append(row)
            print(
                f"sigma={s:<6} theory={vr_theo[0]:+.4f}  "
                f"as-published={off['vr_m1']:+.4f} [{off['ci95'][0]:+.3f},{off['ci95'][1]:+.3f}]  "
                f"standardised={on['vr_m1']:+.4f} [{on['ci95'][0]:+.3f},{on['ci95'][1]:+.3f}]  "
                f"delta={row['delta_vr']:+.4f}",
                flush=True,
            )
    else:
        print(f"PROBE B: N sweep at sigma={args.sigma} (as published, no patch)\n")
        _, _, _, vr_theo = theoretical(args.sigma)
        for ni, n in enumerate(args.Ns):
            r = measure(args.sigma, args.R, args.jobs, n=n, seed_base=20_000 * (ni + 1))
            rows.append(
                {"sigma": args.sigma, **r, "vr_theoretical_m1": float(vr_theo[0])}
            )
            print(
                f"N={n:<7} VR={r['vr_m1']:+.4f} [{r['ci95'][0]:+.3f},{r['ci95'][1]:+.3f}]  "
                f"theory={vr_theo[0]:+.4f}  "
                f"{'POSITIVE' if r['ci95'][0] > 0 else 'negative' if r['ci95'][1] < 0 else 'spans zero'}",
                flush=True,
            )

    out = Path(args.out or (ROOT / "work" / f"vr_probe_{args.probe}.json"))
    out.write_text(
        json.dumps(
            {"probe": args.probe, "rows": rows, "secs": round(time.time() - t0, 1)},
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {out}  ({round(time.time() - t0, 1)}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
