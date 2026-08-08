"""Check every headline number in this logbook against the published results.

    python verify_headlines.py

No arguments, no dependencies beyond the Python standard library, no GPU, no network,
no API keys. It reads only the JSON files published alongside this logbook under
`results/` and checks each claim against them, printing PASS or FAIL per line.

TWO KINDS OF CHECK, AND THEY ARE NOT WORTH THE SAME
---------------------------------------------------
This file used to open by saying it "recomputes each claim". That was a wider claim
than the code delivers, and the gap is worth naming rather than smoothing over.

  RE-DERIVED. Computed here from more primitive fields, so the check can catch the
  published figure itself being wrong. Verified instances: the variance reduction
  (`1 - var_eif/var_naive`, with a further check that the stored `vr_empirical`
  agrees with it); the sign tests (exact binomial over the per-cell values); the
  Claim 3 multiplicity chain (`se` from the interval width, then `z`, `p`, and the
  Bonferroni product); the noise-floor counts (tallied from the per-row fields);
  the sigma = 0.1 bound ratio (`with_V` over `config_py`); and the GSM8K CI for the
  MEAN (`improv_sd_pp / sqrt(B)`).

  READ AS PUBLISHED ENDPOINTS. No more primitive form exists in the published JSON,
  so the check confirms the PROSE matches the DATA. Verified instances: the
  bootstrap CI whose raw replicates were not published (`vr_emp_m1_ci95`), the
  replication count `R`, the oracle variant `vr_oracle`, the exact bound at
  sigma = 1.0, and on the GSM8K side `improv_mean_pp`, `aux_auroc`, and the
  single-run spread `improv_ci95_pp`.

Note the two categories run through the SAME claim in places: the GSM8K block
re-derives the interval for the mean while reading the mean itself, so "Claim 4 is
verified" is too coarse a statement to be true. The line-level labels are the
honest granularity.

A PASS on a re-derived line is evidence about the arithmetic. A PASS on an endpoint
line is evidence about transcription: it catches a number edited in the write-up and
not in the run, and it cannot catch the run having recorded a wrong value. Both
print identically, and this paragraph is the only place the difference is stated.

Why this exists: the logbook asserts about twenty numbers, and a reader has no way to
check them short of re-running a 73 minute CPU sweep. That is a bad trade for someone
evaluating the work. The sweep produced the raw JSON; the raw JSON is published; so
every derived claim can be re-derived here in under a second. Verification beats
assertion, and this is the cheapest honest form of it.

The EXPECTED values below are the numbers the logbook prints. If a claim in the prose
is ever edited away from what the data supports, this script fails and says so.
"""

import json
import math
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
# published layout puts the JSONs in results/ next to this file; the dev tree keeps
# them in work/analysis/. Try both so the script runs from either.
CANDIDATES = [
    os.path.join(HERE, "results"),
    os.path.join(HERE, "..", "results"),
    os.path.join(HERE, "..", "work", "analysis"),
]
KAGGLE_NAMES = ("real_gsm8k_ppi.json",)

_fails = []
_checks = 0


def find(name):
    for d in CANDIDATES:
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    # the kaggle output also lives under its own tree in the dev checkout
    alt = os.path.join(HERE, "..", "kaggle", "real_data_ppi", "out", name)
    return alt if os.path.isfile(alt) else None


def load(name):
    p = find(name)
    if not p:
        print(f"  SKIP  {name} not found; cannot check claims that depend on it")
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def check(label, got, want, tol=0.0):
    """Compare a recomputed value against what the logbook claims."""
    global _checks
    _checks += 1
    if isinstance(want, float) or isinstance(got, float):
        ok = abs(float(got) - float(want)) <= tol
        shown = f"{got:.4f} vs {want:.4f}"
    else:
        ok = got == want
        shown = f"{got} vs {want}"
    print(f"  {'PASS' if ok else 'FAIL'}  {label:<58} {shown}")
    if not ok:
        _fails.append(label)


def sign_test(values):
    pos = sum(1 for v in values if v > 0)
    n = pos + sum(1 for v in values if v < 0)
    if not n:
        return 0, 0, 1.0
    p = sum(math.comb(n, k) for k in range(pos, n + 1)) / 2**n
    return pos, n, p


def main():
    print("Recomputing every headline number from the published results.")
    print()

    # ---- Claim 4: the 60-cell grid -----------------------------------------
    grid = load("claim4_noise_floor.json")
    if grid:
        rows = grid["rows"]
        print("Claim 4, the 60 published cells:")
        check("cells in the three tables", len(rows), 60)
        check(
            "recomputed gains under 1.0 binomial SE",
            sum(1 for r in rows if abs(r["recomputed_in_SE"]) < 1.0),
            58,
        )
        check(
            "gains as PRINTED under 1.0 binomial SE",
            sum(1 for r in rows if abs(r["printed_in_SE"]) < 1.0),
            57,
        )
        check(
            "recomputed gains under 2.0 binomial SE",
            sum(1 for r in rows if abs(r["recomputed_in_SE"]) < 2.0),
            60,
        )
        med = sorted(abs(r["recomputed_in_SE"]) for r in rows)
        n = len(med)
        median = med[n // 2] if n % 2 else (med[n // 2 - 1] + med[n // 2]) / 2
        check("median gain, in SE units", round(median, 2), 0.41, 0.005)
        check(
            "cells contradicting their own printed row",
            sum(1 for r in rows if not r["self_consistent"]),
            3,
        )

        clusters = defaultdict(list)
        for r in rows:
            clusters[(r["bench"], r["model"])].append(r["improv_recomputed"])
        cpos, cn, cp = sign_test([sum(v) / len(v) for v in clusters.values()])
        print("\n  the sign test, clustered because the two configs share a subset:")
        check("clusters positive", f"{cpos} of {cn}", "27 of 30")
        check("one-sided exact binomial p", cp, 4.2e-06, 5e-08)
        upos, un, up = sign_test([r["improv_recomputed"] for r in rows])
        check(
            "UNCLUSTERED figure, anti-conservative, not quoted as the result",
            f"{upos} of {un}",
            "53 of 59",
        )
        # ...and this is WHY it is not quoted: treating cells that share an evaluation
        # subset as independent buys four orders of magnitude of significance for free.
        check("...and it is the more flattering of the two", up < cp, True)

    # ---- Claim 3: the low-sigma failure ------------------------------------
    low = load("vr_lowsigma.json")
    if low:
        print("\nClaim 3, Remark 4.8's practical guarantee at low model noise:")
        r = next((x for x in low if abs(x["base_sigma"] - 0.08) < 1e-9), None)
        if r:
            # RECOMPUTED from the two variances, not read back from `vr_empirical`.
            # Reading the stored figure and comparing it to the number printed in the
            # prose only shows that two copies of one value agree; it cannot catch the
            # stored value itself being wrong, which is the thing worth catching. The
            # definition is the one the paper uses: the fraction of the naive mean's
            # variance that the estimator removes, negative when it adds variance.
            vr = 1.0 - r["var_eif"][0] / r["var_naive"][0]
            lo, hi = r["vr_emp_m1_ci95"]
            check("variance reduction at sigma = 0.08", vr, -0.3300, 5e-04)
            # ...and the file agrees with its own primitives. This is the check the
            # re-read version could not make, because it WAS the stored value.
            check(
                "...and the stored vr_empirical matches that recompute",
                abs(vr - r["vr_empirical"][0]) < 1e-12,
                True,
            )
            check("...i.e. MORE variance than the naive mean", vr < 0, True)
            check("95% CI lower", lo, -0.4952, 5e-04)
            check("95% CI upper", hi, -0.1845, 5e-04)
            check("...entire interval below zero", hi < 0, True)
            check("replications at this sigma", r["R"], 250)
            check(
                "oracle m variant at the same sigma, unreported by the paper",
                r["vr_oracle"][0],
                -26.7261,
                5e-04,
            )
            # Multiplicity. The Claim 3 table is one row per swept sigma, and sigma =
            # 0.08 is one of them, so the page states the Bonferroni-corrected p. The
            # cell count is COUNTED from the two sweep files rather than written down,
            # because a hardcoded 12 would silently stop matching the table the moment a
            # sigma is added. The interval is a percentile bootstrap and the raw
            # replicates are not published, so the p-value goes through a normal
            # approximation whose standard error comes from the interval's own width;
            # the page says so and also reports the conservative wider-half variant.
            broad = load("vr_sweep_results.json") or []
            cells = {round(x["base_sigma"], 4) for x in broad} | {
                round(x["base_sigma"], 4) for x in low
            }
            check("sigma cells in the Claim 3 sweep", len(cells), 12)
            z975 = 1.959963984540054
            se = (hi - lo) / (2 * z975)
            z = vr / se
            p = math.erfc(abs(z) / math.sqrt(2))
            check("...implied standard error", se, 0.0793, 5e-05)
            check("...z on a normal approximation", z, -4.16, 5e-03)
            check("...two-sided p", p, 3.1e-05, 5e-07)
            check(
                "...Bonferroni corrected across the cells",
                p * len(cells),
                3.8e-04,
                5e-06,
            )
            check("...still inside 0.05", p * len(cells) < 0.05, True)
            se_wide = (vr - lo) / z975
            p_wide = math.erfc(abs(vr / se_wide) / math.sqrt(2))
            check("conservative wider-half z", vr / se_wide, -3.92, 5e-03)
            check(
                "...its corrected p, also inside 0.05",
                p_wide * len(cells),
                1.1e-03,
                5e-05,
            )

    bound = load("exact_efficiency_bound.json")
    if bound:
        eb = {round(x["sigma"], 4): x for x in bound}
        print("\nThe finding in the paper's favour:")
        if 0.1 in eb:
            ratio = eb[0.1]["with_V"]["VR"] / eb[0.1]["config_py"]["VR"]
            check(
                "plotted curve understates the true bound, sigma = 0.1", int(ratio), 349
            )
        if 1.0 in eb:
            check(
                "exact bound at the paper's default sigma = 1.0",
                eb[1.0]["with_V"]["VR"],
                0.7753,
                5e-04,
            )

    # ---- the live GSM8K run -------------------------------------------------
    kag = None
    for nm in KAGGLE_NAMES:
        kag = load(nm)
        if kag:
            break
    if kag:
        print("\nThe live GSM8K run, which needs none of the paper's tables:")
        B = kag["config"]["B"]
        for m in kag["models"]:
            short = m["model"].split("/")[-1]
            se = m["improv_sd_pp"] / math.sqrt(B)
            lo, hi = m["improv_mean_pp"] - 1.96 * se, m["improv_mean_pp"] + 1.96 * se
            check(
                f"{short}: auxiliary signal informative (AUROC > 0.5)",
                m["aux_auroc"] > 0.5,
                True,
            )
            check(
                f"{short}: mean gain, pp",
                m["improv_mean_pp"],
                0.24 if "1.5B" in short else 0.23,
                0.005,
            )
            check(f"{short}: CI for the MEAN excludes zero", lo > 0, True)
            check(
                f"{short}: a SINGLE run's spread includes zero",
                m["improv_ci95_pp"][0] < 0 < m["improv_ci95_pp"][1],
                True,
            )

    print()
    # ---- Cross-run reproducibility of the sigma=0.08 variance ratio ---------
    # These figures were prose-only until 2026-08-08 and therefore ungated: the page
    # asserted an across-run SD and a conservatism factor that nothing recomputed. A
    # second independent run at the identical nominal configuration then disagreed with
    # the first, which is precisely the class of drift a gate exists to catch, so the
    # numbers are now derived here from the published JSON rather than typed.
    stab = load("vr_stability_results.json")
    nsw = load("vr_nsweep_r100_results.json")
    # NOT `if stab and nsw:`. A missing input would silently drop every check below and
    # still print "all N checks pass", which is the exact shape of a gate that certifies
    # nothing. An absent input is a failure of this verifier, not an absence of findings.
    if not stab or not nsw:
        check("cross-run inputs present (vr_stability / vr_nsweep_r100)", False, True)
    else:
        arm = next(a for a in stab["arms"] if abs(a["sigma"] - 0.08) < 1e-9)
        sv = [r["vr"] for r in arm["replicates"]]
        row = next(r for r in nsw["rows"] if r["N"] == 1000)
        nv = row["vr_all"]

        check("stability replicates at sigma=0.08", len(sv), 10)
        check("separate-run replicates at sigma=0.08", len(nv), 3)
        check(
            "every replicate negative, both runs", sum(1 for v in sv + nv if v < 0), 13
        )

        # the two runs must genuinely not overlap; if a later run makes them overlap,
        # the page's "do not overlap" sentence is wrong and this fails rather than drifts
        check("the two runs' ranges do not overlap", max(sv) < min(nv), True)

        pooled_sd = statistics.stdev(sv + nv)
        check("pooled across-run SD", pooled_sd, 0.0654, tol=5e-4)
        check("pooled mean", statistics.mean(sv + nv), -0.1572, tol=5e-4)
        check(
            "pooled conservatism factor (within-CI width / pooled spread)",
            arm["mean_within_ci_width"] / (3.92 * pooled_sd),
            1.5,
            tol=0.05,
        )

        # the sweep this run was built for is discarded by its own pre-registered
        # control; assert the control really did fail, so the page cannot quietly
        # start citing rows the control refused
        check(
            "the N-sweep control FAILED, so its rows are discarded",
            nsw["control_ok"],
            False,
        )

    if _fails:
        print(f"{len(_fails)} of {_checks} checks FAILED: {_fails}")
        return 1
    # Wording matters here, and this line used to overclaim in exactly the way the
    # docstring now warns about: it said every number "re-derives from" the results,
    # while a documented subset is checked against published endpoints rather than
    # recomputed. A summary line is the part a reader quotes, so it gets the narrower
    # and true verb.
    print(
        f"all {_checks} checks pass: every headline number agrees with the "
        "published results (see the module docstring for which are re-derived "
        "and which are checked against published endpoints)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
