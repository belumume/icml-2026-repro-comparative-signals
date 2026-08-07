#!/usr/bin/env python3
"""Build papers.json from https://huggingface.co/datasets/ai-conferences/ICML2026.

ICML virtual-site URLs use event IDs from the official catalogue, not OpenReview
submission numbers. See https://icml.cc/static/virtual/data/icml-2026-orals-posters.json
"""

import concurrent.futures
import json
import re
import urllib.request
from datasets import load_dataset

AREA_MAP = {
    "deep_learning": "Deep Learning",
    "applications": "Applications",
    "general_machine_learning": "General Machine Learning",
    "social_aspects": "Social Aspects",
    "theory": "Theory",
    "reinforcement_learning": "Reinforcement Learning",
    "optimization": "Optimization",
    "probabilistic_methods": "Probabilistic Methods",
    "uncategorized": "Uncategorized",
}

ICML_CATALOGUE_URL = (
    "https://icml.cc/static/virtual/data/icml-2026-orals-posters.json"
)
FORUM_ID_RE = re.compile(r"forum\?id=([^&]+)")


def title_case(s: str) -> str:
    return " ".join(w.capitalize() for w in s.split("_") if w)


def parse_area(primary_area: str) -> tuple[str, str]:
    parts = (primary_area or "").split("->")
    prefix = parts[0] or "uncategorized"
    area = AREA_MAP.get(prefix, title_case(prefix))
    sub = title_case(parts[1]) if len(parts) > 1 else ""
    return area, sub


def parse_type(paper_type: str) -> tuple[str, bool]:
    if paper_type == "Oral":
        return "Oral", False
    if paper_type == "Spotlight":
        return "Poster", True
    return "Poster", False


def hf_indexed(arxiv_id: str) -> bool:
    if not arxiv_id:
        return False
    try:
        req = urllib.request.Request(
            f"https://huggingface.co/api/papers/{arxiv_id}",
            method="HEAD",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception:
        return False


def hf_index_map(arxiv_ids: list[str]) -> dict[str, bool]:
    unique = sorted({a for a in arxiv_ids if a})
    out: dict[str, bool] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(hf_indexed, arxiv_id): arxiv_id for arxiv_id in unique}
        for future in concurrent.futures.as_completed(futures):
            arxiv_id = futures[future]
            out[arxiv_id] = future.result()
    return out


def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "ICML-2026-agent-repro"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip().lower())


def load_icml_virtual_map() -> dict[str, dict]:
    """Map OpenReview forum id (and unique titles) → ICML virtual event info."""
    catalogue = fetch_json(ICML_CATALOGUE_URL)
    results = catalogue.get("results") or []
    by_orid: dict[str, dict] = {}
    by_title: dict[str, list[dict]] = {}
    for item in results:
        event_id = item.get("id")
        path = item.get("virtualsite_url") or ""
        if event_id is None or not path:
            continue
        info = {
            "pid": str(event_id),
            "vs": "https://icml.cc" + path
            if path.startswith("/")
            else path,
        }
        paper_url = item.get("paper_url") or ""
        match = FORUM_ID_RE.search(paper_url)
        if match:
            by_orid[match.group(1)] = info
        title_key = normalize_title(item.get("name") or "")
        if title_key:
            by_title.setdefault(title_key, []).append(info)
    # Title fallback only when unambiguous.
    title_map = {
        title: infos[0] for title, infos in by_title.items() if len(infos) == 1
    }
    return {"by_orid": by_orid, "by_title": title_map}


def virtual_site_for(orid: str, title: str, virtual_map: dict) -> tuple[str, str]:
    info = virtual_map["by_orid"].get(orid) or virtual_map["by_title"].get(
        normalize_title(title)
    )
    if not info:
        return "", ""
    return info["pid"], info["vs"]


def main() -> None:
    virtual_map = load_icml_virtual_map()
    ds = load_dataset("ai-conferences/ICML2026", split="train")
    papers = []
    abstracts = {}
    areas = set()
    area_tree: dict[str, set[str]] = {}
    missing_virtual = 0

    for i, row in enumerate(ds):
        area, sub = parse_area(row["primary_area"])
        paper_type, spot = parse_type(row["type"])
        sub_no = row["submission_number"]
        orid = row["paper_id"]
        title = row["title"]
        pid, vs = virtual_site_for(orid, title, virtual_map)
        if not vs:
            missing_virtual += 1
        papers.append(
            {
                "i": sub_no if sub_no is not None else i + 1,
                "pid": pid,
                "orid": orid,
                "title": title,
                "authors": row["authors"] or [],
                "insts": [],
                "area": area,
                "sub": sub,
                "type": paper_type,
                "spot": spot,
                "or": row["paper_url"],
                "vs": vs,
                "arxiv": row["arxiv_id"] or "",
                "alphaxiv": row["arxiv_id"] or "",
            }
        )
        if row["abstract"]:
            abstracts[orid] = row["abstract"]
        areas.add(area)
        if sub:
            area_tree.setdefault(area, set()).add(sub)

    papers.sort(key=lambda p: p["i"])
    indexed = hf_index_map([p["arxiv"] for p in papers])
    for paper in papers:
        paper["hf"] = paper["arxiv"] if indexed.get(paper["arxiv"]) else ""
    area_tree_out = {
        area: sorted(subs) for area, subs in sorted(area_tree.items())
    }
    index_payload = {
        "papers": papers,
        "areas": sorted(areas),
        "areaTree": area_tree_out,
    }
    with open("index.json", "w", encoding="utf-8") as f:
        json.dump(index_payload, f, ensure_ascii=False, separators=(",", ":"))
    with open("abstracts.json", "w", encoding="utf-8") as f:
        json.dump(abstracts, f, ensure_ascii=False, separators=(",", ":"))
    payload = {**index_payload, "abstracts": abstracts}
    with open("papers.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(
        f"wrote {len(papers)} papers to index.json, abstracts.json, papers.json "
        f"({missing_virtual} missing ICML virtual links)"
    )


if __name__ == "__main__":
    main()
