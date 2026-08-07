"""Shortlist ICML-2026 papers that are strong Best-Falsification targets for a
CPU/small-GPU, <12h reproduction window.

Selection logic (explicit, so it can be audited):
  HARD EXCLUDE  - papers with known mis-extracted claims (organizer PRs #25/#31/#34/#35)
                - papers already heavily attempted (saturated: someone else owns the story)
                - papers with no anchored claims (anchored claims are what the judge scores)
  SCORE UP      - claims that are cheaply checkable (concrete numbers, small/standard
                  datasets, classical ML, theory/algorithmic properties)
                - claims of the form "X beats baselines", which a trivial/null baseline
                  can decisively undercut
  SCORE DOWN    - claims needing large-scale LM training, RL at scale, video/3D/robotics
"""

import json
import re
import sys
from collections import Counter

# Organizer-confirmed bad claim extractions - falsifying these proves nothing
# about the paper. Sources: challenge Space discussions #25, #31, #34, #35.
KNOWN_BAD = {"Iexhb5lL3t", "CoAHlJuMdh", "NJes6aeTem", "5EtByXq4bX"}

CHEAP = [
    # classical / small-scale / analytically checkable
    "regression",
    "bandit",
    "kernel",
    "gaussian",
    "convex",
    "bound",
    "theorem",
    "convergence",
    "complexity",
    "isolation forest",
    "random forest",
    "svm",
    "clustering",
    "pca",
    "tabular",
    "time series",
    "forecast",
    "graph neural",
    "node classification",
    "cifar",
    "mnist",
    "uci",
    "synthetic",
    "gradient descent",
    "optimizer",
    "sgd",
    "adam",
    "calibration",
    "auroc",
    "auc",
    "correlation",
    "sample complexity",
    "regret",
    "estimator",
    "variance",
    "eigen",
    "spectral",
    "matrix",
    "sparse",
    "compression",
    "quantization",
    "pruning",
    "distillation",
]
EXPENSIVE = [
    "pretraining",
    "pre-training",
    "70b",
    "13b",
    "llama-3",
    "trillion tokens",
    "video",
    "3d scene",
    "robot",
    "manipulation",
    "autonomous driving",
    "nerf",
    "diffusion model training",
    "reinforcement learning from human",
    "rlhf",
    "million env steps",
    "imagenet-21k",
    "a100-days",
    "gpu-days",
    "gpu days",
]
BEATS = [
    "outperform",
    "outperforms",
    "beats",
    "surpass",
    "state-of-the-art",
    "sota",
    "improves over",
    "better than",
    "superior to",
    "achieves the best",
    "compared to baselines",
    "over baselines",
]
NUM = re.compile(r"\b\d+\.\d+\b|\b\d+(?:\.\d+)?%")


def main():
    ch = json.load(open("data/challenge.json", encoding="utf-8"))
    papers = ch["papers"]
    anchored = json.load(open("data/claims_anchored.json", encoding="utf-8"))
    verdicts = json.load(open("data/verdicts.json", encoding="utf-8"))

    attempts = Counter()
    fals_attempts = Counter()
    for r in verdicts.values() if isinstance(verdicts, dict) else verdicts:
        orid = r.get("orid")
        if not orid:
            continue
        attempts[orid] += 1
        if any(
            (c.get("verdict") or "") == "falsified" for c in (r.get("claims") or [])
        ):
            fals_attempts[orid] += 1

    rows = []
    for p in papers:
        orid = p.get("orid")
        if not orid or orid in KNOWN_BAD:
            continue
        claims = anchored.get(orid) or []
        if len(claims) < 3:
            continue  # need several claims for 2N points and a real story
        blob = " ".join(c.get("text", "") for c in claims).lower()
        title = p.get("title") or ""
        area = (p.get("area") or "") + " / " + (p.get("sub") or "")

        cheap = sum(1 for k in CHEAP if k in blob)
        exp = sum(1 for k in EXPENSIVE if k in blob)
        beats = sum(1 for k in BEATS if k in blob)
        nums = len(NUM.findall(blob))
        n_att = attempts[orid]

        # saturation penalty: someone already owns the narrative
        if n_att >= 6:
            continue
        sat_pen = n_att * 2.0
        # already-falsified-by-others penalty (novelty of the negative result)
        fals_pen = fals_attempts[orid] * 6.0

        score = (
            cheap * 3.0
            + beats * 2.5
            + min(nums, 12) * 1.0
            - exp * 6.0
            - sat_pen
            - fals_pen
            + (2.0 if p.get("arxiv") else 0.0)
        )
        rows.append(
            {
                "score": round(score, 1),
                "orid": orid,
                "title": title,
                "area": area,
                "n_claims": len(claims),
                "attempts": n_att,
                "fals_by_others": fals_attempts[orid],
                "cheap": cheap,
                "exp": exp,
                "beats": beats,
                "nums": nums,
                "arxiv": p.get("arxiv"),
                "or": p.get("or"),
            }
        )

    rows.sort(key=lambda r: -r["score"])
    print(f"candidates after filters: {len(rows):,}\n")
    print(f"{'score':>6} {'att':>3} {'fal':>3} {'N':>2}  {'orid':<12} title")
    for r in rows[:40]:
        print(
            f"{r['score']:>6} {r['attempts']:>3} {r['fals_by_others']:>3} "
            f"{r['n_claims']:>2}  {r['orid']:<12} {r['title'][:72]}"
        )
    json.dump(rows[:150], open("data/shortlist.json", "w", encoding="utf-8"), indent=1)
    print("\nwrote data/shortlist.json (top 150)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
