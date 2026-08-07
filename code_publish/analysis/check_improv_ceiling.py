"""Test the reviewer's finding D against the extracted tables before publishing from it.

CLAIM UNDER TEST: `Improv = |naive - GT| - |one-step - GT|` is bounded above by
|naive - GT|, so the metric mechanically rewards an unlucky naive draw, and some
published gains "exceed what any unbiased estimator can achieve in expectation".

Two things this deliberately does NOT take on trust.

1. Exceeding an EXPECTATION is not an impossibility. A single draw routinely exceeds its
   own mean, so "above E|naive-GT|" is a weak statement. The HARD ceiling is the realised
   |naive - GT| for that row: no estimator, however good, can beat the naive estimator by
   more than the naive estimator's own error. That IS checkable per row.
2. A positive correlation between Improv and |naive - GT| is true BY CONSTRUCTION, since
   the first is defined as the second minus something. Reporting it as a finding would be
   reporting a tautology. What would be real is the reported rows being enriched for
   unlucky naive draws relative to what sampling predicts, which is tested separately.

Schema note: tables_extracted.json is {bench: [row, ...]} with keys
bench/table/N/model/GT/naive/step1/imp1/step2/imp2. Read off the file, not assumed.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TABLES = os.path.join(HERE, "tables_extracted.json")
SQ = math.sqrt(2 / math.pi)


def phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def main():
    data = json.load(open(TABLES, encoding="utf-8"))

    rows = []
    for bench, cells in data.items():
        for r in cells:
            for cfg in (1, 2):
                imp = r.get(f"imp{cfg}")
                step = r.get(f"step{cfg}")
                if imp is None or step is None:
                    continue
                gt, naive, N = float(r["GT"]), float(r["naive"]), int(r["N"])
                rows.append(
                    dict(
                        bench=bench,
                        model=r["model"],
                        cfg=cfg,
                        N=N,
                        GT=gt,
                        naive=naive,
                        step=float(step),
                        imp=float(imp),
                    )
                )

    print(f"{len(rows)} published cells\n")

    # --- 1. the HARD ceiling: Improv can never exceed the naive estimator's own error
    viol = []
    for r in rows:
        r["ceiling"] = abs(r["naive"] - r["GT"])
        if r["imp"] > r["ceiling"] + 1e-9:
            viol.append(r)

    print("A. HARD CEILING  (Improv <= |naive - GT|, true for ANY estimator)")
    if viol:
        print(f"   {len(viol)} cell(s) EXCEED it, which is internally impossible:")
        for r in sorted(viol, key=lambda x: x["imp"] - x["ceiling"], reverse=True):
            print(
                f"     {r['bench']:6} {r['model'][:32]:32} cfg{r['cfg']} "
                f"Improv {r['imp']:+.2f} > |naive-GT| {r['ceiling']:.2f} "
                f"(excess {r['imp'] - r['ceiling']:+.2f})"
            )
    else:
        print("   0 violations. The 'no estimator could achieve this' framing does NOT")
        print("   hold as an impossibility claim. Do not publish it as one.")

    # --- 2. are the reported rows enriched for unlucky naive draws?
    print("\nB. ARE THE ROWS ENRICHED FOR UNLUCKY NAIVE DRAWS?")
    print("   (mean realised |naive-GT| vs what binomial sampling predicts)")
    for bench in data:
        sub = [r for r in rows if r["bench"] == bench and r["cfg"] == 1]
        if not sub:
            continue
        realised = sum(abs(r["naive"] - r["GT"]) for r in sub) / len(sub)
        expected = sum(
            math.sqrt(max(r["GT"] / 100 * (1 - r["GT"] / 100), 1e-12) / r["N"])
            * 100
            * SQ
            for r in sub
        ) / len(sub)
        ratio = realised / expected if expected else float("nan")
        print(
            f"   {bench:6} n={len(sub):2}  realised {realised:5.2f}pp  "
            f"expected {expected:5.2f}pp  ratio {ratio:4.2f}x"
        )

    # --- 3. how extreme is each gain relative to the naive error distribution?
    print("\nC. TAIL POSITION of the largest gains")
    print("   P(|naive-GT| >= reported Improv) under an unbiased naive estimator.")
    print("   A large Improv is only reachable when the naive draw is far out.")
    scored = []
    for r in rows:
        p = r["GT"] / 100.0
        sd = math.sqrt(max(p * (1 - p), 1e-12) / r["N"]) * 100.0
        z = r["imp"] / sd if sd > 0 else float("inf")
        r["tail"] = 2 * (1 - phi(z)) if z < 40 else 0.0
        r["sd"] = sd
        scored.append(r)
    for r in sorted(scored, key=lambda x: -x["imp"])[:8]:
        print(
            f"   {r['bench']:6} {r['model'][:30]:30} cfg{r['cfg']} "
            f"Improv {r['imp']:+6.2f}  sd {r['sd']:4.2f}  P {r['tail']:.4f}"
        )

    print("\nVERDICT: publish only what survived above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
