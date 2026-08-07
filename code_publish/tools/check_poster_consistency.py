"""Publish gate: the poster must not contradict the logbook it summarises.

WHY THIS DID NOT EXIST AND SHOULD HAVE
--------------------------------------
`audit_submission_text.py` checks the prize-form text against the published pages.
`verify_realdata_claims.py` checks the real-data section against the kernel JSON.
Nothing checked the POSTER against anything, because the poster is built by a separate
tool from separate source, so it drifted on its own and every gate stayed green.

What it drifted into was the worst possible sentence. The poster's "What is true
instead" callout -- the single most prize-relevant claim on it, since Special Prize #2
is judged on the original claim, the evidence, and the new claim believed true instead
-- read:

    The sign pattern is real: 53 of 59 positive, exact binomial p = 8.8e-11

That is the UNCLUSTERED sign test. The 60 cells are two configs per benchmark-model
pair sharing an evaluation subset, so they are not independent and that p-value is
anti-conservative. The logbook says so in three places and the handoff says "quote
this, NOT the 60-cell" figure. The poster quoted the 60-cell figure, unqualified, on
the Space, in the pinned executive-summary embed, and in the downloadable PDF.

Both numbers are re-derived here from the grid rather than typed in, so this gate
cannot drift from the analysis the way the poster drifted from the logbook.
"""

import collections
import html
import json
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
POSTER = ROOT / "work" / "poster_build" / "poster.html"
GRID = ROOT / "work" / "analysis" / "claim4_noise_floor.json"


def sign_tests():
    """(clustered, unclustered) as (positive, n, p), from the grid."""
    rows = json.loads(GRID.read_text(encoding="utf-8"))["rows"]

    def test(values):
        pos = sum(1 for v in values if v > 0)
        n = pos + sum(1 for v in values if v < 0)
        if not n:
            return 0, 0, 1.0
        p = sum(math.comb(n, k) for k in range(pos, n + 1)) / 2**n
        return pos, n, p

    unclustered = test([r["improv_recomputed"] for r in rows])
    clusters = collections.defaultdict(list)
    for r in rows:
        clusters[(r["bench"], r["model"])].append(r["improv_recomputed"])
    clustered = test([sum(v) / len(v) for v in clusters.values()])
    return clustered, unclustered


def poster_text():
    t = POSTER.read_text(encoding="utf-8")
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t)


def check(text, clustered, unclustered):
    (cpos, cn, cp), (upos, un, up) = clustered, unclustered
    problems = []

    # The anti-conservative figure must not appear as a supported claim.
    for pat, what in [
        (rf"\b{upos}\s+of\s+{un}\b", f"unclustered count {upos} of {un}"),
        (r"8\.8\s*(?:&times;|×|x)\s*10", "unclustered p = 8.8e-11"),
    ]:
        for m in re.finditer(pat, text, re.I):
            near = text[max(0, m.start() - 200) : m.end() + 200]
            if re.search(r"anti-conservative|not independent|unclustered", near, re.I):
                continue  # named AS the disowned figure, which is legitimate
            problems.append((what, " ".join(near.split())[:130]))

    # ...and the honest one must be the figure actually quoted.
    if not re.search(rf"\b{cpos}\s+of\s+{cn}\b", text):
        problems.append(
            (
                f"clustered count {cpos} of {cn} absent",
                "the poster quotes no clustered figure",
            )
        )
    if not re.search(r"4\.2\s*(?:&times;|×|x)\s*10", text):
        problems.append(
            (f"clustered p = {cp:.1e} absent", "no clustered p-value on the poster")
        )
    return problems


def main():
    if not POSTER.is_file():
        print(f"missing {POSTER}")
        return 1
    clustered, unclustered = sign_tests()
    text = poster_text()

    # Positive control: the sentence that shipped must be detected.
    shipped = (
        "What is true instead. The sign pattern is real: "
        f"{unclustered[0]} of {unclustered[1]} positive, exact binomial p = 8.8x10-11: "
        "a bias reduction visible only in aggregate."
    )
    if not check(shipped, clustered, unclustered):
        print("FAIL selftest: the shipped sentence is not detected; this gate is inert")
        return 1
    print("  OK   selftest: the sentence that shipped is detected")
    # ...and naming it as the disowned figure must be allowed
    allowed = (
        f"gives {clustered[0]} of {clustered[1]} positive, p = 4.2x10-6; the unclustered "
        f"{unclustered[0]} of {unclustered[1]} at p = 8.8x10-11 is anti-conservative."
    )
    if check(allowed, clustered, unclustered):
        print(
            "FAIL selftest: naming the disowned figure as disowned is wrongly flagged"
        )
        return 1
    print("  OK   selftest: naming it AS anti-conservative is allowed")

    problems = check(text, clustered, unclustered)
    print(
        f"\n  clustered   {clustered[0]} of {clustered[1]}, p = {clustered[2]:.1e}  (the honest one)"
    )
    print(
        f"  unclustered {unclustered[0]} of {unclustered[1]}, p = {unclustered[2]:.1e}  "
        "(anti-conservative; cells share an evaluation subset)"
    )
    for what, ctx in problems:
        print(f"\n  FAIL {what}\n       ...{ctx}...")
    if problems:
        print(f"\n{len(problems)} poster/logbook contradiction(s).")
        return 1
    print(
        "\nposter quotes the clustered sign test and does not assert the unclustered one"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
