"""The EXACT semiparametric efficiency bound for the paper's own simulation DGP.

Why this file exists
--------------------
The repo's config.py reports

    theoretical_variance_reduction = (R2)^2,  R2 = rho1^2 s^2 / (rho1^2 s^2 + sigma_eta^2)

which uses ONLY rho1 -- i.e. only the first auxiliary responder. But
data_generation.py builds the auxiliary as the triple

    Z = (W1, W2, V),   W_k = X + rho_k eps + eta_k,
    V = 1{(W1 - Y)^2 <= (W2 - Y)^2}                         # preference label

so the deployed estimator conditions on strictly more than rho1. The dashed
"theoretical" curve the authors plot against their empirical VR is therefore not
the efficiency bound of their own design; it sits below it.

The exact bound is analytic. Write Z_k := W_k - X = rho_k eps + eta_k. Then
W_k - Y = Z_k - eps, so

    V = 1{(Z1 - eps)^2 <= (Z2 - eps)^2}
      = 1{Z1^2 - Z2^2 <= 2 eps (Z1 - Z2)}
      = 1{eps >= t} if Z1 > Z2 else 1{eps <= t},     t := (Z1 + Z2)/2

i.e. V is exactly an indicator of eps lying above/below a threshold determined by
Z. Since eps | (Z1, Z2) is Gaussian, conditioning further on V truncates that
Gaussian to a half-line, and E[eps^2 | Z1, Z2, V] is a truncated-Gaussian second
moment in closed form.

Efficiency identity (verified separately in claims12_eif_check.py):
    sigma^2_eff = sigma^2_naive - E[u^2],   u = tau - m,
    tau = E[phi | X, Z],  m = E[phi | X] = s^2,  phi = eps^2,  sigma^2_naive = 2 s^4
so VR_exact = E[u^2] / (2 s^4).
"""

import json
import os

import numpy as np
from scipy.stats import norm

RHO1, RHO2, SIGMA_ETA = 0.8, 0.6, 0.6


def trunc_moments(mu, sd, a, upper):
    """First two moments of N(mu, sd^2) truncated to (-inf,a] or [a,inf).

    upper=True  -> truncate to eps <= a
    upper=False -> truncate to eps >= a
    """
    alpha = (a - mu) / sd
    if upper:
        Z = np.clip(norm.cdf(alpha), 1e-12, 1.0)
        lam = -norm.pdf(alpha) / Z  # E[x] = mu + sd*lam
        m1 = mu + sd * lam
        var = sd**2 * (1.0 + alpha * lam - lam**2)
    else:
        Z = np.clip(1.0 - norm.cdf(alpha), 1e-12, 1.0)
        lam = norm.pdf(alpha) / Z
        m1 = mu + sd * lam
        var = sd**2 * (1.0 + alpha * lam - lam**2)
    var = np.clip(var, 1e-15, None)
    return m1, var


def exact_vr(sigma, n=4_000_000, seed=0):
    """Monte-Carlo over Z (exact conditional moments given Z) -> VR_exact."""
    rng = np.random.default_rng(seed)
    s2 = sigma**2
    eps = rng.normal(0.0, sigma, n)
    z1 = RHO1 * eps + rng.normal(0.0, SIGMA_ETA, n)
    z2 = RHO2 * eps + rng.normal(0.0, SIGMA_ETA, n)

    # eps | (z1, z2) is Gaussian
    Szz = np.array(
        [
            [RHO1**2 * s2 + SIGMA_ETA**2, RHO1 * RHO2 * s2],
            [RHO1 * RHO2 * s2, RHO2**2 * s2 + SIGMA_ETA**2],
        ]
    )
    Sez = np.array([RHO1 * s2, RHO2 * s2])
    Sinv = np.linalg.inv(Szz)
    w = Sez @ Sinv  # [2]
    mu = w[0] * z1 + w[1] * z2  # E[eps | Z]
    cvar = s2 - Sez @ Sinv @ Sez  # Var(eps | Z), scalar
    sd = np.sqrt(max(cvar, 1e-15))

    # --- tau WITHOUT V: E[eps^2 | Z1,Z2] = mu^2 + cvar
    tau_noV = mu**2 + cvar

    # --- tau WITH V: truncate at t = (z1+z2)/2, side depends on sign(z1 - z2)
    t = 0.5 * (z1 + z2)
    v_obs = np.where(z1 > z2, (eps >= t), (eps <= t))
    # For each unit we need E[eps^2 | Z, V=v_obs]
    upper = np.where(
        z1 > z2, ~v_obs, v_obs
    )  # V=1 & z1>z2 -> lower tail [t,inf) => upper=False
    m1 = np.empty(n)
    vv = np.empty(n)
    for flag in (True, False):
        idx = upper == flag
        if idx.any():
            a, b = trunc_moments(mu[idx], sd, t[idx], upper=flag)
            m1[idx], vv[idx] = a, b
    tau_V = m1**2 + vv

    phi = eps**2
    s2_naive = 2.0 * s2**2  # Var(eps^2) for eps ~ N(0, s^2)
    out = {}
    for name, tau in (("no_V", tau_noV), ("with_V", tau_V)):
        u = tau - s2  # m(X) = E[phi] = s^2
        eu2 = float((u**2).mean())
        out[name] = {"E_u2": eu2, "VR": eu2 / s2_naive}
    # config.py's published curve
    r2 = (RHO1**2 * s2) / (RHO1**2 * s2 + SIGMA_ETA**2)
    out["config_py"] = {"R2": float(r2), "VR": float(r2**2)}
    out["sigma"] = sigma
    out["sigma2_naive"] = s2_naive
    out["phi_var_check"] = float(phi.var(ddof=1))
    return out


def main():
    rows = [
        exact_vr(s)
        for s in (0.08, 0.1, 0.15, 0.2, 0.25, 0.35, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0)
    ]
    print(
        f"{'sigma':>6} {'config.py VR':>13} {'VR (W1,W2)':>12} {'VR EXACT(+V)':>13} "
        f"{'exact/config':>13}"
    )
    for r in rows:
        c = r["config_py"]["VR"]
        print(
            f"{r['sigma']:>6.2f} {c:>13.4f} {r['no_V']['VR']:>12.4f} "
            f"{r['with_V']['VR']:>13.4f} {r['with_V']['VR'] / max(c, 1e-12):>13.2f}x"
        )

    print("\n" + "=" * 78)
    print("WHY THIS MATTERS")
    print("=" * 78)
    print("  config.py's theoretical_variance_reduction conditions on rho1 only.")
    print("  The deployed estimator conditions on (W1, W2, V). The exact bound is")
    print("  therefore strictly higher everywhere, so the paper's own plotted")
    print("  'theoretical' curve UNDERSTATES what its estimator should achieve.")
    print("  Empirical VR exceeding the dashed curve is expected, not anomalous.")

    p = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "exact_efficiency_bound.json"
    )
    with open(p, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=1)
    print(f"\nwrote {p}")


if __name__ == "__main__":
    main()
