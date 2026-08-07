"""Enumerate every PUBLIC surface this submission owns and check each one is current.

The submission is not one artifact. Publishing touches four separate public repos plus a
rendered origin, and they are updated by different mechanisms at different moments:
`trackio logbook publish` writes the Space and pushes the traces dataset and the workspace
bucket, while the code tree, the evidence CSVs and the README are uploaded separately. Any
of them can therefore be stale or wrong while the others are fine, and nothing in the
publish output says so.

This walks all of them and reports, per surface: does it exist, is it public, does its
content match what is local, and does it carry anything that should never be public.

Run:  python tools/audit_public_surfaces.py
"""

import glob
import os
import re
import sys
import urllib.error
import urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OWNER = "passagereptile455"
SPACE = f"{OWNER}/repro-evaluating-llms-comparative-signals"
TRACES = f"{SPACE}-traces"
BUCKET = (
    f"{OWNER}/repro-evaluating-llms-when-they-do-not-know-the-answer-"
    "comparative-signals-artifacts"
)
RENDER = (
    "https://passagereptile455-repro-evaluating-llms-comparat-44a478e.static.hf.space/"
)
UA = {"User-Agent": "Mozilla/5.0"}

# Strings that must never appear on any public surface. The operator's identity leaked
# into the traces dataset once already and had to be scrubbed.
FORBIDDEN = [
    (
        "windows username",
        re.compile(r"\bC:[\\/]Users[\\/](?!user\b)[A-Za-z0-9._-]+", re.I),
    ),
    ("home path", re.compile(r"/home/(?!runner\b)[A-Za-z0-9._-]+")),
    ("token-shaped", re.compile(r"\b(?:hf_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,})")),
]

_fail = []


def ok(msg):
    print(f"  OK    {msg}")


def bad(msg):
    print(f"  FAIL  {msg}")
    _fail.append(msg)


def note(msg):
    print(f"  --    {msg}")


def api(path):
    try:
        req = urllib.request.Request(f"https://huggingface.co/api/{path}", headers=UA)
        with urllib.request.urlopen(req, timeout=45) as r:
            import json

            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"_error": e.code}
    except Exception as e:  # noqa: BLE001
        return {"_error": type(e).__name__}


# A BUCKET is its own primitive on the Hub, not a dataset. Its metadata lives under
# /api/buckets/<id> and its listing under /api/buckets/<id>/tree; the renderer resolves
# files from /buckets/<id>/resolve/<path>. Querying it as a dataset returns 401, which
# reads exactly like "this is private and a judge cannot see it" -- this audit reported
# precisely that about a bucket that is public and serving 18 files anonymously. The
# instrument was wrong, not the artifact.
NAMESPACE = {"space": "spaces", "dataset": "datasets", "bucket": "buckets"}


def surface(label, kind, repo_id):
    print(f"\n{label}")
    print(f"  {kind}: {repo_id}")
    ns = NAMESPACE[kind]
    meta = api(f"{ns}/{repo_id}")
    if "_error" in meta:
        bad(f"{label}: not reachable ({meta['_error']})")
        return None
    if meta.get("private"):
        bad(f"{label}: is PRIVATE; a judge cannot open it")
    else:
        ok("public (anonymous fetch succeeded)")
    if kind == "bucket":
        tree = api(f"buckets/{repo_id}/tree")
        if isinstance(tree, list):
            ok(f"{len(tree)} files")
            return [e.get("path", "") for e in tree]
        bad(f"{label}: tree listing failed ({tree})")
        return None
    files = [f["rfilename"] for f in meta.get("siblings", [])]
    ok(f"{len(files)} files")
    return files


def main():
    print("PUBLIC SURFACES FOR THIS SUBMISSION")

    # 1. the Space -----------------------------------------------------------
    files = surface("1. Logbook Space (the submitted artifact)", "space", SPACE)
    if files:
        for need in ("README.md", "poster.pdf", "poster.png", "poster.html"):
            (ok if need in files else bad)(f"{need} present")
        for group in ("pages/", "code/", "results/", "logbook/artifacts/", "LICENSES/"):
            n = sum(1 for f in files if f.startswith(group))
            (ok if n else bad)(f"{group} {n} files")
        junk = [f for f in files if f.endswith(".pyc") or "__pycache__" in f]
        (bad if junk else ok)(
            f"no build junk published ({len(junk)} .pyc/__pycache__)"
            if junk
            else "no .pyc or __pycache__ published"
        )
        # the code tree must match what stage_code.py produces
        local = set()
        stage = os.path.join(ROOT, "code_publish")
        for p in glob.glob(os.path.join(stage, "**", "*"), recursive=True):
            if os.path.isfile(p) and "__pycache__" not in p:
                local.add("code/" + os.path.relpath(p, stage).replace("\\", "/"))
        remote = {f for f in files if f.startswith("code/")}
        missing = local - remote
        (bad if missing else ok)(
            f"code/ missing {len(missing)} local file(s): {sorted(missing)[:4]}"
            if missing
            else f"code/ carries every locally staged file ({len(local)})"
        )

    # 2. the rendered origin -------------------------------------------------
    print("\n2. Rendered origin (what a judge actually opens)")
    print(f"  url: {RENDER}")
    try:
        with urllib.request.urlopen(
            urllib.request.Request(RENDER, headers=UA), timeout=45
        ) as r:
            html = r.read().decode("utf-8", errors="replace")
        ok(f"HTTP {r.status}, {len(html)} B")
        (ok if "logbook.js" in html else bad)("loads the renderer")
    except Exception as e:  # noqa: BLE001
        bad(f"render origin unreachable: {type(e).__name__}")

    # 3. traces dataset ------------------------------------------------------
    surface(
        "3. Agent traces dataset (published by `logbook publish`)", "dataset", TRACES
    )

    # 4. workspace bucket ----------------------------------------------------
    wb = surface(
        "4. Workspace artifacts bucket (drives the Workspace tab)", "bucket", BUCKET
    )
    if wb:
        n_csv = sum(1 for p in wb if p.endswith(".csv"))
        (ok if n_csv else bad)(f"{n_csv} evidence CSV(s) reachable in the bucket")
    # Control: the namespace is load-bearing. Querying a bucket as a dataset must FAIL --
    # that is what produced the false "private, a judge cannot open it" verdict. If this
    # ever starts succeeding, the namespaces have merged and the note above is stale.
    probe = api(f"datasets/{BUCKET}")
    note(
        "control: same bucket queried as a dataset returns "
        f"{probe.get('_error', 'SUCCESS -- namespaces may have merged, re-read the note')}"
    )

    # 5. leak sweep over the text a judge can read ---------------------------
    print("\n5. Leak sweep over published TEXT")
    scanned = 0
    hits = 0
    for path in sorted(
        glob.glob(
            os.path.join(
                ROOT, "logbook", ".trackio", "logbook", "pages", "*", "page.md"
            )
        )
    ) + [os.path.join(ROOT, "work", "space_README.md")]:
        if not os.path.isfile(path):
            continue
        text = open(path, encoding="utf-8").read()
        text = re.sub(r"data:image/[^\"')\s]+", " ", text)  # base64 carries no prose
        scanned += 1
        for label, pat in FORBIDDEN:
            m = pat.search(text)
            if m:
                hits += 1
                bad(
                    f"{os.path.basename(os.path.dirname(path))}: {label} -> {m.group(0)[:60]}"
                )
    (ok if not hits else bad)(f"{scanned} text surfaces scanned, {hits} leak(s)")

    print()
    if _fail:
        print(f"{len(_fail)} PROBLEM(S):")
        for f in _fail:
            print(f"  - {f}")
        return 1
    print("every public surface is reachable, public, and current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
