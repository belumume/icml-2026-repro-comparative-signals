"""A ratio printed beside its operands must divide out FROM THE PRINTED DIGITS.

A reader with a calculator checks the arithmetic in front of them, not the float that
produced it. This project shipped a table reading

    | 0.08 | 0.0001 | 0.0003 | 0.0846 | 668.5x |

where 0.0846 / 0.0001 is 846, not 668. Nothing was miscomputed: the ratio came from the
full-precision values and the operand column was rounded to four DECIMAL PLACES, which
at ~1.27e-4 leaves barely one significant figure. Two rows were affected and they were
precisely the two quoted as headline numbers on three other pages and on the poster.

So this gate re-derives every ratio from the digits AS PRINTED and requires it to agree
with the printed ratio inside the tolerance those digits can support. It reads the
rendered page, not the source data, because the defect exists only in the rendering.

Run:  python tools/check_table_arithmetic.py
"""

import glob
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PAGES = sorted(
    glob.glob(
        os.path.join(ROOT, "logbook", ".trackio", "logbook", "pages", "*", "page.md")
    )
)
NUM = re.compile(r"^\*{0,2}([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\*{0,2}$")
RATIO = re.compile(r"^\*{0,2}([\d.]+)\s*(?:x|×)\*{0,2}$")


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def as_num(s):
    m = NUM.match(s.strip())
    return float(m.group(1)) if m else None


# A half-ULP band is the WRONG instrument here and it let the shipped defect through.
# "0.0001" legitimately stands for anything in [0.00005, 0.00015], so 0.0846/0.0001 has
# a band of roughly [564, 1693] and a printed 668.5x sits happily inside it. Strictly
# consistent, and useless: the reader does not integrate over the rounding interval,
# they divide the digits in front of them and get 846.
#
# So the test is what a reader actually experiences: dividing the printed digits must
# land near the printed ratio. 2% is loose enough for honest last-digit rounding on
# well-formed rows and tight enough to catch a column that has lost its significant
# figures.
REL_TOL = 0.02


def scan(text, name):
    problems = []
    for ln, line in enumerate(text.split("\n"), 1):
        if not line.strip().startswith("|"):
            continue
        c = cells(line)
        if len(c) < 3:
            continue
        rm = RATIO.match(c[-1])
        if not rm:
            continue
        printed_ratio = float(rm.group(1))
        # the ratio is <some column> / <some other column>; find the pair that the
        # printed ratio is MEANT to be, by testing every ordered pair of numeric cells
        nums = [(i, as_num(x), x) for i, x in enumerate(c[:-1])]
        nums = [(i, v, s) for i, v, s in nums if v is not None and v != 0]
        if len(nums) < 2:
            continue
        best = None
        for i, a, sa in nums:
            for j, b, sb in nums:
                if i == j:
                    continue
                q = a / b
                if best is None or abs(q - printed_ratio) < abs(
                    best[0] - printed_ratio
                ):
                    best = (q, sa, sb, a, b)
        if best is None:
            continue
        q, sa, sb, a, b = best
        # The RATIO's own printed precision counts too. "1.2x" stands for anything in
        # [1.15, 1.25], so an operand quotient of 1.15 is correct rounding, not a defect
        # -- flagging it would be over-correction, and two such rows appeared the moment
        # the relative test alone went in.
        rs = rm.group(1)
        half_ulp_r = 0.5 * 10 ** -(len(rs.split(".")[1]) if "." in rs else 0)
        tol = max(REL_TOL * abs(printed_ratio), half_ulp_r)
        if abs(q - printed_ratio) > tol:
            problems.append(
                (
                    ln,
                    f"printed {printed_ratio:g}x, but dividing the printed digits "
                    f"{sa} / {sb} gives {q:.4g} "
                    f"({abs(q - printed_ratio) / printed_ratio * 100:.0f}% off)",
                )
            )
    return problems


def selftest():
    """The shipped row must be caught; a correctly-printed row must not."""
    bad = "| 0.08 | 0.0001 | 0.0003 | 0.0846 | 668.5x |"
    good = "| 0.08 | 0.0001266 | 0.0003 | 0.0846 | 668.5x |"
    fine = "| 0.25 | 0.01 | 0.0219 | 0.2871 | 28.7x |"
    # over-correction controls: a coarsely-printed ratio is correct rounding, not a
    # defect. Both of these fired as false positives before the ratio's own printed
    # precision was folded into the tolerance.
    round12 = "| 2.0 | 0.7686 | 0.8423 | **0.8840** | 1.2× |"
    round11 = "| 3.0 | 0.8858 | 0.9256 | **0.9349** | 1.1× |"
    cases = [
        ("the shipped 4dp row is caught", bool(scan(bad, "t"))),
        ("...and 4 significant figures clears it", not scan(good, "t")),
        ("a row that already divides out is not flagged", not scan(fine, "t")),
        (
            "1.15 printed as 1.2x is correct rounding, not flagged",
            not scan(round12, "t"),
        ),
        (
            "1.055 printed as 1.1x is correct rounding, not flagged",
            not scan(round11, "t"),
        ),
    ]
    ok = True
    for label, good_ in cases:
        ok &= good_
        print(f"  {'OK  ' if good_ else 'FAIL'} selftest: {label}")
    return ok


def main():
    if not selftest():
        print("this gate failed its own control; its verdict means nothing")
        return 1
    print()
    total = 0
    for p in PAGES:
        name = os.path.basename(os.path.dirname(p))
        found = scan(open(p, encoding="utf-8").read(), name)
        if found:
            print(name)
            for ln, msg in found:
                print(f"  line {ln:>5}  {msg}")
            total += len(found)
    print(f"\n{len(PAGES)} pages, {total} ratio(s) that do not divide out as printed")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
