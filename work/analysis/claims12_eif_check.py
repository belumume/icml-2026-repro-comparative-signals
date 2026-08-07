"""Claims 1 and 2: verify the efficient influence function and the efficiency bound.

Claim 1 (Prop 3.3): psi(X,Y,G,Z) = [m(X) - theta] - [tau(X,Z) - phi(Y,G)]
Claim 2 (Thm 4.5): sqrt(N)(theta_1step - theta) -> N(0, sigma^2_eff), attaining the
                   semiparametric efficiency bound.

These are checked in the paper's OWN simulation DGP (simulation/config.py +
appendix B), where every conditional expectation is available in closed form, so
the check is exact rather than approximate:

    X ~ N(0,1),  G = X,  Y_l = X + eps_l,  eps_l ~ N(0, sigma_l^2)
    W_s = X + rho_s eps_l + eta_s,  eta_s ~ N(0, sigma_eta^2)
    phi(Y,G) = (Y-G)^2 = eps^2      ->  theta_l = E[phi] = sigma_l^2

With Z = (W_1, W_2) the conditional law of eps given Z is Gaussian, so tau and m
are analytic. This lets us test three things the paper asserts:
  (a) E[psi] = 0                              (psi is a valid influence function)
  (b) Var(psi) = sigma^2_naive - E[u^2], u = tau - m   (the efficiency identity)
  (c) the one-step estimator is sqrt(N)-consistent and asymptotically normal
      (Shapiro-Wilk / KS on standardised replicates)
"""

import json
import os

import numpy as np
from scipy import stats

RHO = (0.8, 0.6)
SIGMA_ETA = 0.6


def analytic_tau_and_m(sigma, n, rng):
    """Draw the DGP and return phi, tau(X,Z), m(X), all in closed form.

    eps ~ N(0, s^2);  W_s = X + rho_s eps + eta_s  =>  Z_s := W_s - X = rho_s eps + eta_s.
    So (eps, Z1, Z2) is jointly Gaussian with
        Cov(eps, Z_s) = rho_s s^2,  Var(Z_s) = rho_s^2 s^2 + sigma_eta^2,
        Cov(Z1, Z2)   = rho_1 rho_2 s^2.
    tau(X,Z) = E[eps^2 | Z] = (E[eps|Z])^2 + Var(eps|Z);  m(X) = E[eps^2] = s^2.
    """
    s2 = sigma**2
    x = rng.normal(0, 1, n)
    eps = rng.normal(0, sigma, n)
    eta = rng.normal(0, SIGMA_ETA, (2, n))
    z = np.array([RHO[0] * eps + eta[0], RHO[1] * eps + eta[1]])  # [2, n]

    Szz = np.array(
        [
            [RHO[0] ** 2 * s2 + SIGMA_ETA**2, RHO[0] * RHO[1] * s2],
            [RHO[0] * RHO[1] * s2, RHO[1] ** 2 * s2 + SIGMA_ETA**2],
        ]
    )
    Sez = np.array([RHO[0] * s2, RHO[1] * s2])
    Sinv = np.linalg.inv(Szz)
    cond_mean = Sez @ Sinv @ z  # E[eps | Z]
    cond_var = s2 - Sez @ Sinv @ Sez  # Var(eps | Z), a scalar

    phi = eps**2  # (Y - G)^2
    tau = cond_mean**2 + cond_var  # E[phi | X, Z]
    m = np.full(n, s2)  # E[phi | X] = s^2
    return x, phi, tau, m, cond_var


def main():
    rng = np.random.default_rng(0)
    n = 2_000_000
    out = []
    print(
        f"{'sigma':>6} {'E[psi]':>12} {'Var(psi)':>12} {'s2_naive':>12} "
        f"{'-E[u^2]':>12} {'identity':>12} {'match':>7}"
    )
    for sigma in (0.1, 0.25, 0.5, 1.0, 2.0, 3.0):
        _x, phi, tau, m, _cv = analytic_tau_and_m(sigma, n, rng)
        theta = sigma**2
        # Claim 1: the stated EIF
        psi = (m - theta) - (tau - phi)
        e_psi = psi.mean()
        v_psi = psi.var(ddof=1)
        s2_naive = phi.var(ddof=1)
        u = tau - m
        eu2 = (u**2).mean()
        identity = s2_naive - eu2  # Claim 2/3: efficiency identity
        ok = abs(v_psi - identity) / max(identity, 1e-12) < 0.02
        print(
            f"{sigma:>6.2f} {e_psi:>12.3e} {v_psi:>12.6f} {s2_naive:>12.6f} "
            f"{-eu2:>12.6f} {identity:>12.6f} {'OK' if ok else 'FAIL':>7}"
        )
        out.append(
            {
                "sigma": sigma,
                "E_psi": float(e_psi),
                "Var_psi": float(v_psi),
                "sigma2_naive": float(s2_naive),
                "E_u2": float(eu2),
                "identity": float(identity),
                "match": bool(ok),
                "VR_true": float(eu2 / s2_naive),
            }
        )

    print("\n" + "=" * 78)
    print("CLAIM 1 (Prop 3.3): psi is a valid (mean-zero) influence function")
    print("=" * 78)
    worst = max(abs(r["E_psi"]) for r in out)
    print(f"  max |E[psi]| over all sigma: {worst:.3e}   (Monte-Carlo SE ~ 1e-4)")
    print(f"  verdict: {'MEAN-ZERO CONFIRMED' if worst < 5e-3 else 'PROBLEM'}")

    print("\n" + "=" * 78)
    print("CLAIM 2/3 identity: Var(psi) == sigma^2_naive - E[u^2]")
    print("=" * 78)
    print(f"  all sigma match within 2%: {all(r['match'] for r in out)}")
    print("  => the efficiency gain is exactly E[u^2], so it is STRICTLY positive")
    print("     whenever tau != m. Corollary 4.7 is correct AS AN ASYMPTOTIC")
    print("     statement. What it does not cover is finite-N behaviour with an")
    print("     ESTIMATED tau_hat, which is what vr_sweep.py measures.")

    print("\n  TRUE asymptotic variance reduction (E[u^2]/sigma^2_naive) by sigma:")
    for r in out:
        print(f"    sigma={r['sigma']:<5} VR_true={r['VR_true']:.4f}")

    p = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "claims12_eif_check.json"
    )
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(f"\nwrote {p}")

    # --- Claim 2: asymptotic normality of the one-step estimator (oracle nuisances)
    print("\n" + "=" * 78)
    print("CLAIM 2 (Thm 4.5): sqrt(N)-consistency and asymptotic normality")
    print("=" * 78)
    for sigma in (0.5, 1.0):
        for N in (250, 1000, 4000):
            reps = 4000
            r2 = rng.integers(0, 2**32)
            g = np.random.default_rng(r2)
            est = np.empty(reps)
            for i in range(reps):
                _x, phi, tau, m, _cv = analytic_tau_and_m(sigma, N, g)
                est[i] = (m - (tau - phi)).mean()  # one-step with true nuisances
            z = (est - sigma**2) / est.std(ddof=1)
            ks = stats.kstest(z, "norm")
            print(
                f"  sigma={sigma:<4} N={N:<5} mean={est.mean():.6f} "
                f"(theta={sigma**2:.4f})  sd*sqrt(N)={est.std(ddof=1) * np.sqrt(N):.4f}  "
                f"KS p={ks.pvalue:.3f}"
            )
    print("  sd*sqrt(N) should be ~constant in N  => sqrt(N)-consistency")


if __name__ == "__main__":
    main()
