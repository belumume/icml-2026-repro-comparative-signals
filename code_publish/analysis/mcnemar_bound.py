"""Bound the PAIRED standard error of each published gain, using only published numbers.

THE PROBLEM THIS SOLVES
-----------------------
The Claim 4 page scores each reported gain against a MARGINAL binomial SE. That is the
wrong scale for a paired contrast, and the page says so: the two accuracies are computed
on the same items, so their difference has less variance than the marginal SE implies.
The evidence is in the paper's own numbers. The 60 gains have SD 2.39 pp against a mean
column SE of 5.98 pp, a ratio of 0.40, and 58 of 60 land inside 1 SE where a correct
Gaussian SE permits at most about 41.

The page then said the correct paired SD "cannot be recovered from the published tables,
because that needs per-item scores the paper does not release". The first half is true
and the conclusion drawn from it was too strong. Per-item scores are not needed for a
BOUND.

THE BOUND
---------
These are paired BINARY outcomes: each item is right or wrong under each estimator. Write
b = items the one-step estimator gets right and the naive mean gets wrong, and c for the
reverse. Then

    gain (as a proportion)  d = (b - c) / N
    Var(d)                    = [ (b + c) - (b - c)^2 / N ] / N^2      (McNemar)

Only b - c is published, through the gain. But b + c >= |b - c| always, with equality when
the discordance is entirely one-sided. Substituting b + c = |b - c| = |d| N into the
variance above gives

    Var(d) = [ |d| N - (|d| N)^2 / N ] / N^2 = ( |d| - d^2 ) / N = |d| (1 - |d|) / N

so the SMALLEST paired SE consistent with a published gain is

    SE_min = sqrt( |d| (1 - |d|) / N )

and that is the yardstick most favourable to the paper: it is the tightest error bar the
published numbers can support, so scoring the gains against it is the hardest test this
falsification can be given. Anything the gains fail against SE_min, they fail against
every admissible paired SE.

CORRECTION, and it ran against this file's own framing. This returned sqrt(|d|/N) until
2026-08-03, dropping the -(b-c)^2/N term of the McNemar variance. Since (1 - |d|) < 1 the
dropped term made the SE LARGER, i.e. the bar WIDER, i.e. MORE gains read as inside the
noise -- so the error favoured this falsification while the text called the bar "most
favourable to the paper". The correction is nil in effect (35/60 either way, zero cells
flip, the SE moves by at most 6.60%) and is applied because the code must mean what it
says. See selftest() for the case that separates the two formulas.

THE LIMIT OF THIS WHOLE BOUND, stated because it is larger than the correction above.
McNemar needs BOTH arms to be per-item binary indicators, so that b and c are counts of
items. That holds for `naive` -- all 60 published naive accuracies sit on the k/N grid --
and fails for `one-step`, which lands off that grid in 56 of 60 cells because it is the
naive proportion plus the mean of a CONTINUOUS correction. There are no discordance counts
b, c for it. Separately, the quantity being scored is Improv = |naive-GT| - |one-step-GT|,
a difference of absolute errors, which is not a McNemar contrast at all. So SE_min is an
ANALOGY, not a derivation, and it is the weakest of the three yardsticks on the Claim 4
page rather than the strongest. The sound one is the paired SD measured on the authors'
own simulator, which is 1.8x to 3.7x LARGER than the marginal SE and puts 60 of 60 gains
under 1.0. Run `python work/analysis/claim4_noise_floor.py` for that measurement.

The upper end, b + c = N (every item discordant), gives SE_max = 1/sqrt(N).

Run:  python work/analysis/mcnemar_bound.py
"""

import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "work" / "analysis" / "claim4_noise_floor.json"


def se_min_pp(gain_pp, n):
    """Tightest paired SE (in pp) consistent with this gain, via one-sided discordance."""
    d = abs(gain_pp) / 100.0
    if d == 0:
        # a tie: the smallest non-degenerate discordance is b = c = 0, no information.
        # Use b + c = 1, the smallest discordance that can occur at all.
        return math.sqrt(1.0) / n * 100.0
    # McNemar Var(d) = [(b+c) - (b-c)^2/N]/N^2; at b+c = |b-c| = |d|N this is
    # |d|(1-|d|)/N. The (1-|d|) factor is NOT optional: dropping it widens the bar.
    return math.sqrt(d * (1.0 - d) / n) * 100.0


def se_max_pp(n):
    return 100.0 / math.sqrt(n)


def selftest():
    """Check the algebra on a hand case before trusting any count."""
    ok = True
    # N=100, gain 4pp -> |b-c| = 4 items. one-sided: b+c = 4, so
    # Var = [4 - 16/100]/100^2 = 3.84/10000 and SE = sqrt(3.84)/100 = 1.9596pp.
    # The DROPPED-TERM answer here is exactly 2.0pp, which this file asserted until
    # 2026-08-03. This case therefore fails under the old formula.
    got = se_min_pp(4.0, 100)
    good = abs(got - 1.9595917942265424) < 1e-9
    ok &= good
    print(
        f"  {'OK  ' if good else 'FAIL'} selftest: N=100 gain 4pp -> SE_min {got:.4f}pp "
        f"(expect 1.9596; the dropped-term formula returns 2.0000)"
    )
    # A case where the two formulas are far apart, so no tolerance argument can hide a
    # regression: at d = 0.5, sqrt(|d|/N) = 7.0711pp and sqrt(|d|(1-|d|)/N) = 5.0000pp.
    got = se_min_pp(50.0, 100)
    good = abs(got - 5.0) < 1e-9
    ok &= good
    print(
        f"  {'OK  ' if good else 'FAIL'} selftest: N=100 gain 50pp -> SE_min {got:.4f}pp "
        f"(expect 5.0000; the dropped-term formula returns 7.0711)"
    )
    # DIRECTION. The correction always NARROWS the bar, so the old formula was reporting
    # more gains as inside the noise than the algebra permits -- an error that favoured
    # this falsification, not the paper.
    good = all(
        se_min_pp(g, n) < math.sqrt(g / 100.0 / n) * 100.0
        for n in (15, 50, 100)
        for g in (0.1, 1.0, 5.0, 12.0)
    )
    ok &= good
    print(
        f"  {'OK  ' if good else 'FAIL'} selftest: correction narrows the bar at every "
        f"gain tested (so the old code favoured the falsifier)"
    )
    # SE_min must never exceed SE_max
    good = all(
        se_min_pp(g, n) <= se_max_pp(n) + 1e-9
        for n in (15, 50, 100)
        for g in (0.1, 1.0, 5.0, 12.0)
    )
    ok &= good
    print(f"  {'OK  ' if good else 'FAIL'} selftest: SE_min never exceeds SE_max")
    # A bigger gain implies a bigger minimum SE -- but only up to d = 0.5, where
    # |d|(1-|d|) peaks. Scoped to the observed range: the largest published |gain| is
    # 12 pp, so every cell sits well inside the increasing branch.
    good = se_min_pp(1.0, 50) < se_min_pp(4.0, 50) < se_min_pp(12.0, 50)
    ok &= good
    print(
        f"  {'OK  ' if good else 'FAIL'} selftest: SE_min grows with the gain up to 12pp"
    )
    good = se_min_pp(50.0, 100) > se_min_pp(80.0, 100)
    ok &= good
    print(
        f"  {'OK  ' if good else 'FAIL'} selftest: and TURNS OVER past d=0.5, as "
        f"|d|(1-|d|) requires and sqrt(|d|/N) would not"
    )
    return ok


def main():
    if not selftest():
        print("algebra check failed; the counts below mean nothing")
        return 1
    print()
    rows = json.loads(SRC.read_text(encoding="utf-8"))["rows"]

    marg = sum(1 for r in rows if abs(r["recomputed_in_SE"]) < 1.0)
    print(
        f"Under the MARGINAL binomial SE the page currently uses: {marg}/{len(rows)} under 1.0"
    )
    print(
        f"  (a correct Gaussian SE permits at most ~41/60, so that count is anomalous)\n"
    )

    inside_min = 0
    ratios = []
    per_bench = defaultdict(lambda: [0, 0])
    for r in rows:
        g, n = r["improv_recomputed"], r["N"]
        smin = se_min_pp(g, n)
        ratio = abs(g) / smin if smin else float("inf")
        ratios.append(ratio)
        b = r["bench"]
        per_bench[b][1] += 1
        if ratio < 1.0:
            inside_min += 1
            per_bench[b][0] += 1

    print("Under SE_min, the TIGHTEST paired error bar the published numbers admit")
    print(
        "(most favourable to the paper, so the hardest ARITHMETIC test of this claim --"
    )
    print(
        " but an ANALOGY, not a derivation: one-step is off the k/N grid in 56/60 cells,"
    )
    print(" so it has no per-item discordance counts. This is the WEAKEST of the three")
    print(" yardsticks on the Claim 4 page; the measured paired SD is the sound one):")
    print(f"  {inside_min}/{len(rows)} gains under 1.0 SE_min")
    for b, (i, t) in sorted(per_bench.items()):
        print(f"    {b:6} {i}/{t}")
    print(f"  median gain in SE_min units: {st.median(ratios):.2f}")
    print()
    print("Reference points, per benchmark (pp):")
    seen = set()
    for r in rows:
        if r["bench"] in seen:
            continue
        seen.add(r["bench"])
        n = r["N"]
        print(
            f"  {r['bench']:6} N={n:3}  SE_min at a 1pp gain = {se_min_pp(1.0, n):5.2f}"
            f"   SE_max = {se_max_pp(n):5.2f}   marginal SE used = {r['binom_se_pp']:5.2f}"
        )
    print()
    if inside_min >= len(rows) * 0.5:
        print(
            "READING: the gains remain inside the noise even under the tightest paired"
        )
        print(
            "error bar their own published numbers permit, so the conclusion does not"
        )
        print("depend on the marginal-SE choice that produced the anomaly.")
    else:
        print(
            "READING: under the tightest admissible paired SE the gains are NOT inside"
        )
        print(
            "the noise. The marginal-SE framing overstated the case and must be dropped."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
