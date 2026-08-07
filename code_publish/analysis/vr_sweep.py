"""Empirical vs theoretical variance reduction, using the AUTHORS' OWN simulation.

Tests the operational content of anchored claim 3 (Corollary 4.1):
    "strict variance reduction over the naive sample-average estimator whenever
     tau(X,Z) != m(X) with positive probability, i.e. sigma^2_eff < sigma^2_naive"

The corollary is asymptotically correct (re-derived independently:
sigma^2_eff = sigma^2_naive - E[u^2], u = tau - m). But the deployed estimator
plugs in tau_hat from a 5-fold cross-fitted MLP (config: hidden [64,32], 50
epochs, N=1000, M=500). Estimation error in tau_hat costs variance. At small
sigma the theoretical headroom is tiny -- VR = (R^2)^2 is only 0.010 at
sigma=0.25 and 0.095 at sigma=0.5 -- so the question is whether the realised
estimator still beats naive there, or is actually WORSE.

POSITIVE CONTROL (must pass before any negative result is believed):
at the paper's own default sigma=1.0, empirical VR must land near the
theoretical 0.4096. If the control fails, the harness is wrong, not the paper.
"""

import argparse
import json
import os
import sys
import time

import numpy as np

SIM = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "AI_evaluation", "simulation"
)
sys.path.insert(0, os.path.abspath(SIM))

import torch  # noqa: E402
from config import SimulationConfig  # noqa: E402
from experiment import run_single_trial  # noqa: E402

torch.set_num_threads(1)  # one thread per worker; joblib provides the parallelism

RHO1, SIGMA_ETA, GAP, L = 0.8, 0.6, 0.05, 3


def theoretical(base_sigma):
    sig = np.array([base_sigma + i * GAP for i in range(L)])
    r2 = (RHO1**2 * sig**2) / (RHO1**2 * sig**2 + SIGMA_ETA**2)
    return sig, sig**2, r2, r2**2


def one_trial(trial_id, base_sigma, seed):
    """Run the authors' unmodified run_single_trial at a given base sigma."""
    np.random.seed(seed)
    torch.manual_seed(seed)
    cfg = SimulationConfig()
    cfg.sigma_list = [base_sigma + i * GAP for i in range(L)]
    cfg.num_models = L
    cfg.R = 1
    r = run_single_trial(trial_id=trial_id, config=cfg, verbose=False)
    return (
        np.asarray(r["naive_estimates"], dtype=float),
        np.asarray(r["eif_estimates"], dtype=float),
        np.asarray(r["oracle_estimates"], dtype=float),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--sigmas",
        type=float,
        nargs="+",
        default=[0.1, 0.2, 0.35, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0],
    )
    ap.add_argument("--R", type=int, default=40)
    ap.add_argument("--jobs", type=int, default=14)
    ap.add_argument("--out", default="vr_sweep_results.json")
    args = ap.parse_args()

    from joblib import Parallel, delayed

    rows = []
    t0 = time.time()
    for si, s in enumerate(args.sigmas):
        sig, theta, r2, vr_theo = theoretical(s)
        t = time.time()
        res = Parallel(n_jobs=args.jobs, backend="loky")(
            delayed(one_trial)(i + 1, s, 10_000 * (si + 1) + i) for i in range(args.R)
        )
        naive = np.array([x[0] for x in res])  # [R, L]
        eif = np.array([x[1] for x in res])
        oracle = np.array([x[2] for x in res])

        v_naive = naive.var(axis=0, ddof=1)
        v_eif = eif.var(axis=0, ddof=1)
        v_oracle = oracle.var(axis=0, ddof=1)
        vr_emp = 1.0 - v_eif / v_naive
        vr_orc = 1.0 - v_oracle / v_naive
        mse_naive = ((naive - theta) ** 2).mean(axis=0)
        mse_eif = ((eif - theta) ** 2).mean(axis=0)

        # bootstrap CI on VR for model 1 (the paired quantity that matters)
        rng = np.random.default_rng(7)
        boot = []
        for _ in range(2000):
            idx = rng.integers(0, args.R, args.R)
            b = 1.0 - eif[idx, 0].var(ddof=1) / naive[idx, 0].var(ddof=1)
            boot.append(b)
        lo, hi = np.percentile(boot, [2.5, 97.5])

        row = {
            "base_sigma": float(s),
            "R": args.R,
            "sigma_list": sig.tolist(),
            "true_theta": theta.tolist(),
            "vr_theoretical": vr_theo.tolist(),
            "vr_empirical": vr_emp.tolist(),
            "vr_oracle": vr_orc.tolist(),
            "vr_emp_m1_ci95": [float(lo), float(hi)],
            "var_naive": v_naive.tolist(),
            "var_eif": v_eif.tolist(),
            "mse_naive": mse_naive.tolist(),
            "mse_eif": mse_eif.tolist(),
            "secs": round(time.time() - t, 1),
        }
        rows.append(row)
        print(
            f"sigma={s:<5} VR_theo(m1)={vr_theo[0]:.4f}  VR_emp(m1)={vr_emp[0]:+.4f} "
            f"[{lo:+.4f},{hi:+.4f}]  VR_oracle(m1)={vr_orc[0]:+.4f}  "
            f"MSE n/e={mse_naive[0]:.4f}/{mse_eif[0]:.4f}  ({row['secs']}s)",
            flush=True,
        )

        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=1)

    print(f"\ntotal {time.time() - t0:.1f}s -> {os.path.abspath(args.out)}")

    print("\n" + "=" * 72)
    print("POSITIVE CONTROL: at the paper's default sigma=1.0, empirical VR must")
    print("track the theoretical 0.4096. If it does not, the HARNESS is wrong.")
    print("=" * 72)
    for r in rows:
        if abs(r["base_sigma"] - 1.0) < 1e-9:
            print(
                f"  theoretical={r['vr_theoretical'][0]:.4f}  "
                f"empirical={r['vr_empirical'][0]:.4f}  "
                f"CI95={r['vr_emp_m1_ci95']}"
            )
    print(
        "\nCLAIM 3 OPERATIONAL TEST (strict variance reduction, sigma^2_eff < sigma^2_naive):"
    )
    for r in rows:
        v = r["vr_empirical"][0]
        lo, hi = r["vr_emp_m1_ci95"]
        verdict = (
            "REDUCES" if lo > 0 else ("WORSE" if hi < 0 else "INDISTINGUISHABLE from 0")
        )
        print(
            f"  sigma={r['base_sigma']:<5} VR_emp={v:+.4f} CI=[{lo:+.4f},{hi:+.4f}] -> {verdict}"
        )


if __name__ == "__main__":
    main()
