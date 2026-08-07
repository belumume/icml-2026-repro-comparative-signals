"""Second-pass shortlist over the FULL 4,579-paper anchored set.

Target profile: a falsification that is CHEAP (no GPU credits available) and
DECISIVE (recomputable from released artifacts / analytically checkable), on a
paper nobody else has claimed the negative result for.
"""

import json
import re
import sys
from collections import Counter

KNOWN_BAD = {"Iexhb5lL3t", "CoAHlJuMdh", "NJes6aeTem", "5EtByXq4bX"}

# Areas where a decisive check is affordable on CPU / a laptop.
AREA_W = {
    "Theory": 9.0,
    "Optimization": 8.0,
    "Probabilistic Methods": 7.0,
    "General Machine Learning": 5.0,
    "Social Aspects": 4.0,
    "Uncategorized": 2.0,
    "Applications": 1.0,
    "Deep Learning": 0.0,
    "Reinforcement Learning": -1.0,
}

# Claim shapes that are cheap to test decisively.
CHECKABLE = [
    "theorem",
    "lemma",
    "proposition",
    "bound",
    "convergence",
    "regret",
    "sample complexity",
    "consistency",
    "unbiased",
    "variance",
    "guarantee",
    "provably",
    "optimal rate",
    "lower bound",
    "upper bound",
    "complexity",
    "closed form",
    "identifiab",
    "monotonic",
    "asymptotic",
    "benchmark",
    "leaderboard",
    "human evaluation",
    "annotation",
    "dataset of",
    "correlation",
    "agreement",
    "auroc",
    "calibration",
    "statistically significant",
]
# Claim shapes that need serious compute.
HEAVY = [
    "pretrain",
    "pre-train",
    "fine-tun",
    "billion",
    "70b",
    "13b",
    "8b ",
    "7b ",
    "video",
    "3d ",
    "robot",
    "imagenet",
    "gpu-hour",
    "gpu hour",
    "a100",
    "h100",
    "trillion",
    "diffusion model",
    "text-to-image",
    "world model",
    "sft",
    "rlhf",
    "reinforcement learning",
    "env steps",
    "trajector",
]
NUM = re.compile(r"\b\d+\.\d+\b|\b\d+(?:\.\d+)?\s?%")


def main():
    papers_blob = json.load(open("data/papers_full.json", encoding="utf-8"))
    # papers.json is a dict of buckets; find the list of paper records
    papers = None
    for v in papers_blob.values():
        if isinstance(v, list) and v and isinstance(v[0], dict) and "orid" in v[0]:
            papers = v if papers is None else papers + v
    anchored = json.load(open("data/claims_anchored.json", encoding="utf-8"))
    verd = json.load(open("data/verdicts.json", encoding="utf-8"))

    att, fals = Counter(), Counter()
    for r in verd.values() if isinstance(verd, dict) else verd:
        o = r.get("orid")
        if not o:
            continue
        att[o] += 1
        if any(
            (c.get("verdict") or "") == "falsified" for c in (r.get("claims") or [])
        ):
            fals[o] += 1

    seen, rows = set(), []
    for p in papers:
        o = p.get("orid")
        if not o or o in KNOWN_BAD or o in seen:
            continue
        seen.add(o)
        cl = anchored.get(o) or []
        if len(cl) < 4:
            continue
        if att[o] > 1 or fals[o] > 0:
            continue  # want novelty: unclaimed negative result
        if not p.get("arxiv"):
            continue  # must be able to actually read the paper

        blob = " ".join(c.get("text", "") for c in cl).lower()
        area = p.get("area") or "?"
        chk = sum(1 for k in CHECKABLE if k in blob)
        hvy = sum(1 for k in HEAVY if k in blob)
        nums = len(NUM.findall(blob))

        score = (
            AREA_W.get(area, 0.0)
            + chk * 3.5
            - hvy * 4.0
            + min(nums, 10) * 0.8
            + (3.0 if p.get("spot") else 0.0)
            + (2.0 if p.get("hf") else 0.0)
            - att[o] * 3.0
        )
        rows.append(
            {
                "score": round(score, 1),
                "orid": o,
                "title": p.get("title", ""),
                "area": area,
                "sub": p.get("sub", ""),
                "type": p.get("type"),
                "spot": p.get("spot"),
                "n_claims": len(cl),
                "attempts": att[o],
                "chk": chk,
                "hvy": hvy,
                "nums": nums,
                "arxiv": p.get("arxiv"),
                "or": p.get("or"),
                "hf": p.get("hf"),
            }
        )

    rows.sort(key=lambda r: -r["score"])
    print(f"papers scanned: {len(seen):,}   candidates: {len(rows):,}\n")
    print(
        f"{'score':>6} {'att':>3} {'N':>2} {'sp':>2}  {'area':<24} {'orid':<12} title"
    )
    for r in rows[:30]:
        print(
            f"{r['score']:>6} {r['attempts']:>3} {r['n_claims']:>2} "
            f"{'Y' if r['spot'] else '-':>2}  {r['area'][:24]:<24} {r['orid']:<12} {r['title'][:60]}"
        )
    json.dump(rows[:120], open("data/shortlist2.json", "w", encoding="utf-8"), indent=1)
    print("\nwrote data/shortlist2.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
