"""Fast Gaussian surrogate for the paper's ranking experiment (claim 5).

The paper's own simulation trains a 5-fold cross-fitted MLP per trial (~24 s on
CPU), which makes a wide sigma sweep expensive. But the estimator sampling
distributions are known in closed form from the paper's own config.py:

    theta_l          = sigma_l^2                       (true target)
    Var(theta_naive) = 2 sigma_l^4 / N                 (var of a sample variance)
    R2_l             = rho1^2 sigma_l^2 / (rho1^2 sigma_l^2 + sigma_eta^2)
    VR_l             = (R2_l)^2                        (config.theoretical_variance_reduction)
    Var(theta_eff)   = Var(theta_naive) * (1 - VR_l)

So ranking accuracy can be Monte-Carlo'd directly from two Gaussians per model,
millions of draws in seconds, with no MLP. This gives the SHAPE of the curve over
any sigma range. The closed-form VR this rests on is checked against the authors'
real simulation by vr_sweep.py in this directory, which runs their unmodified
run_single_trial and compares empirical against theoretical VR with a positive
control at the paper's default sigma=1.0 -- the surrogate is never trusted on
its own.

Question under test (anchored claim 5): does the naive-vs-one-step ranking gap
widen MONOTONICALLY as per-model noise variance grows?
"""

import json
import os

import numpy as np

RHO1 = 0.8
SIGMA_ETA = 0.6
N = 1000
GAP = 0.05
L = 3
PAPER_MIN, PAPER_MAX = 0.5, 3.0  # sigma_analysis.py CLI defaults


def theta_and_vars(base_sigma):
    """Return true thetas and the naive/eff sampling variances, per the paper."""
    sig = np.array([base_sigma + i * GAP for i in range(L)])
    theta = sig**2
    var_naive = 2 * sig**4 / N
    r2 = (RHO1**2 * sig**2) / (RHO1**2 * sig**2 + SIGMA_ETA**2)
    vr = r2**2
    var_eff = var_naive * (1 - vr)
    return theta, var_naive, var_eff, r2, vr


def kendall_tau_vs_identity(order):
    """Kendall tau between a permutation and the identity, for L=3 (vectorised)."""
    n = order.shape[1]
    conc = np.zeros(order.shape[0])
    tot = 0
    for i in range(n):
        for j in range(i + 1, n):
            conc += np.sign(order[:, j] - order[:, i])
            tot += 1
    return conc / tot


def ranking_metrics(theta, var, draws, rng):
    """Monte-Carlo exact-match accuracy and Kendall tau for one estimator."""
    est = rng.normal(theta[None, :], np.sqrt(var)[None, :], size=(draws, L))
    order = np.argsort(np.argsort(est, axis=1), axis=1)  # rank of each model
    exact = np.all(order == np.arange(L)[None, :], axis=1).mean()
    tau = kendall_tau_vs_identity(order).mean()
    return float(exact), float(tau)


def main():
    rng = np.random.default_rng(42)
    draws = 200_000
    # Log-spaced sweep spanning FAR beyond the paper's [0.5, 3.0] window
    sigmas = np.unique(
        np.concatenate(
            [
                np.linspace(PAPER_MIN, PAPER_MAX, 6),  # the paper's exact grid
                np.geomspace(0.25, 64.0, 40),
            ]
        )
    )

    rows = []
    for s in sigmas:
        theta, vn, ve, r2, vr = theta_and_vars(s)
        n_exact, n_tau = ranking_metrics(theta, vn, draws, rng)
        e_exact, e_tau = ranking_metrics(theta, ve, draws, rng)
        # z-score for separating adjacent models (model 0 vs 1)
        d_theta = theta[1] - theta[0]
        z_naive = d_theta / np.sqrt(vn[0] + vn[1])
        z_eff = d_theta / np.sqrt(ve[0] + ve[1])
        rows.append(
            {
                "base_sigma": float(s),
                "in_paper_window": bool(PAPER_MIN <= s <= PAPER_MAX),
                "theoretical_VR_m1": float(vr[0]),
                "R2_m1": float(r2[0]),
                "z_naive": float(z_naive),
                "z_eff": float(z_eff),
                "naive_exact": n_exact,
                "eif_exact": e_exact,
                "gap_exact": e_exact - n_exact,
                "naive_tau": n_tau,
                "eif_tau": e_tau,
                "gap_tau": e_tau - n_tau,
            }
        )

    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "surrogate_sweep.json"
    )
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=1)

    print(
        f"{'sigma':>8} {'win':>4} {'VR':>7} {'z_nai':>7} {'z_eff':>7} "
        f"{'nai_ex':>7} {'eif_ex':>7} {'GAP_ex':>8} {'GAP_tau':>8}"
    )
    for r in rows:
        mark = "IN" if r["in_paper_window"] else ""
        print(
            f"{r['base_sigma']:>8.3f} {mark:>4} {r['theoretical_VR_m1']:>7.4f} "
            f"{r['z_naive']:>7.3f} {r['z_eff']:>7.3f} "
            f"{r['naive_exact']:>7.4f} {r['eif_exact']:>7.4f} "
            f"{r['gap_exact']:>8.4f} {r['gap_tau']:>8.4f}"
        )

    # --- the decisive question -------------------------------------------------
    g = np.array([r["gap_exact"] for r in rows])
    s = np.array([r["base_sigma"] for r in rows])
    inw = np.array([r["in_paper_window"] for r in rows])
    print("\n" + "=" * 78)
    print("CLAIM 5 UNDER TEST: does the gap widen MONOTONICALLY with noise?")
    print("=" * 78)
    gi = g[inw]
    print(f"  Inside the paper's window sigma in [{PAPER_MIN}, {PAPER_MAX}] (6 pts):")
    print(f"    gap: {np.round(gi, 4).tolist()}")
    print(f"    monotonically increasing there? {bool(np.all(np.diff(gi) > -1e-3))}")
    print(f"  Across the FULL swept range sigma in [{s.min():.2f}, {s.max():.2f}]:")
    print(f"    argmax gap at sigma = {s[int(np.argmax(g))]:.3f}  (gap={g.max():.4f})")
    print(f"    gap at largest sigma = {g[-1]:.4f}")
    print(f"    monotone over full range? {bool(np.all(np.diff(g) > -1e-3))}")
    tail = g[s > PAPER_MAX]
    if len(tail) > 1:
        print(
            f"    tail (sigma>{PAPER_MAX}) decreasing? {bool(np.all(np.diff(tail) < 1e-3))}"
        )
        print(
            f"    tail first={tail[0]:.4f} last={tail[-1]:.4f} "
            f"delta={tail[-1] - tail[0]:+.4f}"
        )
    print(f"\n  wrote {out}")


if __name__ == "__main__":
    main()
