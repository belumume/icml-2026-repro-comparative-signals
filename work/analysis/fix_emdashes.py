"""Remove em dashes from the prose that ships, one considered rewrite at a time.

Deliberately NOT a blanket character substitution. A batch replace satisfies the count
and leaves grammatical debris behind (a stray space, a clause that needed a sentence
break, a parenthetical whose second dash carried the closing). Each pair below was read
in context and rewritten; the script only applies and verifies them.

The one em dash left standing is the table placeholder in vr_table(), where "—" means
"no value for this cell". That is a typographic convention, not prose.
"""

import sys

P = "tools/write_content.py"

REWRITES = [
    # (old, new, why)
    (
        "so it is not that estimator's semiparametric efficiency bound — while\nFigure 3 uses it as the reference the empirical curve is read against.",
        "so it is not that estimator's semiparametric efficiency bound, yet\nFigure 3 uses it as the reference the empirical curve is read against.",
        "contrastive dash -> 'yet', keeps the concession",
    ),
    (
        "1. **A single draw's 95% interval spans zero at every N tested — including N = 1000**,",
        "1. **A single draw's 95% interval spans zero at every N tested, including N = 1000**,",
        "appositive dash -> comma",
    ),
    (
        "This was designed to show a *contrast* — a clear per-draw",
        "This was designed to show a *contrast*: a clear per-draw",
        "dash introducing a definition -> colon",
    ),
    (
        "on its own `P(>0)` — the\nsmall-N values sit inside it.",
        "on its own `P(>0)`, and the\nsmall-N values sit inside it.",
        "dash joining two independent clauses -> comma + conjunction",
    ),
    (
        "own numbers imply a loss. (It is not the smallest positive gain in the tables — they\n  also contain +0.08 and +0.10 — which makes the stated range itself a poor summary of",
        "own numbers imply a loss. (It is not the smallest positive gain in the tables, which\n  also contain +0.08 and +0.10, so the stated range is itself a poor summary of",
        "paired parenthetical dashes -> commas; 'which makes' -> 'so' to keep the subject clear",
    ),
    (
        "> (benchmark, model) — because Config 1 and Config 2 share an evaluation subset and\n> several pairs are numerically identical — gives",
        "> (benchmark, model), which is necessary because Config 1 and Config 2 share an\n> evaluation subset and several pairs are numerically identical, gives",
        "paired parenthetical dashes -> commas; adds 'which is necessary' so the clause has a head",
    ),
    (
        "> A pure *variance* reduction — exactly what Corollary 4.7 promises and what Claims 1–3\n> verify — produces this positive sign pattern",
        "> A pure *variance* reduction, exactly what Corollary 4.7 promises and what Claims 1–3\n> verify, produces this positive sign pattern",
        "paired parenthetical dashes -> commas",
    ),
    (
        "does not draw — that the gap is **bounded**.",
        "does not draw, namely that the gap is **bounded**.",
        "dash introducing an appositive -> 'namely'",
    ),
]


def main():
    src = open(P, encoding="utf-8").read()
    before = src.count("—")
    missing = [w for old, _, w in REWRITES if old not in src]
    if missing:
        print("ANCHORS NOT FOUND (file changed under me):")
        for m in missing:
            print("  ", m)
        return 1

    for old, new, why in REWRITES:
        assert "—" not in new, f"replacement still has an em dash: {why}"
        src = src.replace(old, new, 1)
        print(f"  applied: {why}")

    # No double spaces or space-before-punctuation introduced by the edits.
    for bad, label in [
        ("  ", "double space"),
        (" ,", "space before comma"),
        (" .", "space before period"),
        (",,", "double comma"),
    ]:
        # only flag inside the prose bodies, code indentation legitimately has runs
        for line in src.splitlines():
            st = line.strip()
            if st.startswith(("*", ">", "-", "1.", "|")) and bad in st:
                print(f"  WARN {label}: {st[:80]}")

    open(P, "w", encoding="utf-8", newline="\n").write(src)
    after = src.count("—")
    print(f"\nem dashes in generator: {before} -> {after}")
    print("remaining should be exactly 1 (the vr_table 'no value' placeholder)")
    return 0 if after == 1 else 1


if __name__ == "__main__":
    sys.exit(main())
