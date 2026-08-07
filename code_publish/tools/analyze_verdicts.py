"""Compute the real leaderboard + falsification landscape from verdicts.json.

Answers the only questions that matter with ~18h left:
  1. Is 1st/2nd place reachable? (points gap)
  2. How rare is a `falsified` verdict? (Best Falsification prize contestability)
  3. Which papers already have strong coverage? (saturation)
"""

import json
import sys
from collections import Counter, defaultdict

PTS = {"verified": 2, "falsified": 2, "toy": 1, "inconclusive": 0}


def main(path="verdicts.json"):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    rows = list(data.values()) if isinstance(data, dict) else data
    print(f"total judged logbooks: {len(rows):,}\n")

    verdict_counts = Counter()
    quality_counts = Counter()
    # dedupe: one logbook per (user, paper) counts
    best = {}  # (user, orid) -> points
    falsified_books = []
    per_paper = defaultdict(list)

    for r in rows:
        sid = r.get("space_id") or ""
        user = sid.split("/")[0] if "/" in sid else "?"
        orid = r.get("orid") or "?"
        claims = r.get("claims") or []
        pts = 0
        n_fals = 0
        for c in claims:
            v = (c.get("verdict") or "").strip().lower()
            verdict_counts[v] += 1
            pts += PTS.get(v, 0)
            if v == "falsified":
                n_fals += 1
        quality_counts[(r.get("quality") or "?").lower()] += 1

        key = (user, orid)
        if pts > best.get(key, -1):
            best[key] = pts
        per_paper[orid].append((user, pts, r.get("quality")))
        if n_fals:
            falsified_books.append(
                {
                    "space": sid,
                    "user": user,
                    "orid": orid,
                    "title": r.get("paper_title"),
                    "n_falsified": n_fals,
                    "n_claims": len(claims),
                    "quality": r.get("quality"),
                    "points": pts,
                }
            )

    print("=== VERDICT DISTRIBUTION (per claim) ===")
    tot = sum(verdict_counts.values())
    for v, n in verdict_counts.most_common():
        print(f"  {v or '(blank)':<14} {n:>7,}  {100 * n / tot:5.1f}%")
    print(f"  {'TOTAL':<14} {tot:>7,}\n")

    print("=== QUALITY DISTRIBUTION (per logbook) ===")
    for q, n in quality_counts.most_common():
        print(f"  {q:<14} {n:>7,}  {100 * n / len(rows):5.1f}%")
    print()

    print("=== LEADERBOARD (dedup: best logbook per user+paper) ===")
    user_pts = Counter()
    user_books = Counter()
    for (user, _orid), pts in best.items():
        user_pts[user] += pts
        user_books[user] += 1
    top = user_pts.most_common(20)
    print(f"  {'rank':<5} {'user':<28} {'points':>7} {'papers':>7}")
    for i, (u, p) in enumerate(top, 1):
        print(f"  {i:<5} {u:<28} {p:>7,} {user_books[u]:>7,}")
    print(f"\n  users with >0 points: {sum(1 for v in user_pts.values() if v > 0):,}")
    print(f"  total unique users:   {len(user_pts):,}")

    print("\n=== FALSIFICATION LANDSCAPE (the $500 prize) ===")
    print(f"  logbooks containing >=1 'falsified' claim: {len(falsified_books):,}")
    print(f"  as share of all logbooks: {100 * len(falsified_books) / len(rows):.2f}%")
    fq = Counter(b["quality"] for b in falsified_books)
    print(f"  their quality mix: {dict(fq)}")
    hi = [b for b in falsified_books if (b["quality"] or "").lower() == "high"]
    print(f"  HIGH-quality logbooks with a falsification: {len(hi):,}")
    print("\n  --- top 25 falsification logbooks by (n_falsified, points) ---")
    for b in sorted(falsified_books, key=lambda x: (-x["n_falsified"], -x["points"]))[
        :25
    ]:
        t = (b["title"] or "")[:58]
        print(
            f"   {b['n_falsified']}/{b['n_claims']} fals  q={str(b['quality'])[:4]:<4} "
            f"{b['points']:>2}p  {b['user'][:18]:<18} {t}"
        )

    print("\n=== PAPER SATURATION ===")
    print(f"  distinct papers attempted: {len(per_paper):,}")
    attempts = Counter({k: len(v) for k, v in per_paper.items()})
    print(f"  most-attempted paper had {max(attempts.values())} attempts")
    solo = sum(1 for v in attempts.values() if v == 1)
    print(f"  papers with exactly 1 attempt: {solo:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
