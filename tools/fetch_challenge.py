"""Download the ICML-2026-agent-repro challenge Space files we need, locally.

Uses urllib (curl is slow/flaky to HF from this box). Writes into ../data/.
"""

import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://huggingface.co/spaces/ICML-2026-agent-repro/challenge/resolve/main/"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

FILES = [
    "scripts/validate_icml_logbook.py",
    "scripts/scaffold_icml_logbook.py",
    "PROMPT.md",
    "README.md",
    "curated.json",
    "areas.json",
    "avatars.json",
    "leaderboard.js",
    "gallery.js",
    "papers.js",
    "repro.js",
    "icml2026-data.js",
    "build_papers.py",
    "claim_audit/current_manifest.json",
    "challenge.json",
]


def fetch(path):
    url = BASE + path
    dest = os.path.join(OUT, path.replace("/", "__"))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        with open(dest, "wb") as f:
            f.write(data)
        return (path, len(data), None)
    except Exception as e:  # noqa: BLE001
        return (path, 0, repr(e))


def main():
    os.makedirs(OUT, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(fetch, FILES))
    ok = 0
    for path, n, err in results:
        if err:
            print(f"FAIL {path}: {err}")
        else:
            ok += 1
            print(f"OK   {n:>9,}  {path}")
    print(f"\n{ok}/{len(FILES)} downloaded into {os.path.abspath(OUT)}")
    return 0 if ok == len(FILES) else 1


if __name__ == "__main__":
    sys.exit(main())
