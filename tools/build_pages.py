"""Write trackio logbook page.md files with correctly-formed cell blocks.

The validator parses cells out of `---\n<!-- trackio-cell\n{json}\n-->\n<body>`
blocks and silently SKIPS any cell whose JSON does not parse -- so a malformed
poster cell is an invisible validation failure. This builder emits the JSON with
json.dumps so that cannot happen, and asserts the round-trip afterwards.
"""

import hashlib
import json
import os
from datetime import datetime, timezone

import render_safe

ROOT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "logbook",
    ".trackio",
    "logbook",
    "pages",
)


def _cid(page, i, title):
    h = hashlib.sha1(f"{page}|{i}|{title}".encode()).hexdigest()[:12]
    return f"cell_{h}"


def build_page(slug, heading, cells):
    """cells: list of dicts {type, title, body, pinned?, poster?, lang?}"""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = [f"# {heading}\n"]
    for i, c in enumerate(cells):
        meta = {
            "type": c["type"],
            "id": _cid(slug, i, c["title"]),
            "created_at": now,
            "title": c["title"],
        }
        if c.get("pinned"):
            meta["pinned"] = True
            meta["pinned_at"] = now
        if c.get("poster"):
            meta["poster"] = True
        body = c["body"]
        if c["type"] == "figure":
            body = f"````html\n{body}\n````"
        else:
            # The renderer is line-oriented and has no italic. Normalising HERE, at
            # the single point every cell body passes through, is what makes that
            # impossible to forget in one page's prose. Figure cells are the poster's
            # raw HTML payload and must not be touched.
            body = render_safe.normalise(body)
        out.append(
            "\n---\n<!-- trackio-cell\n" + json.dumps(meta) + "\n-->\n" + body + "\n"
        )
    text = "\n".join(out)
    d = os.path.join(ROOT, slug)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "page.md")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return p


def write_index(title, pages):
    """pages: ordered list of (label, slug)."""
    lines = [f"# Reproduction: {title}", "", "## Pages", "", "| Page |", "| --- |"]
    lines += [f"| [{label}](#/{slug}) |" for label, slug in pages]
    lines.append("")
    p = os.path.join(ROOT, "index.md")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    return p


def verify():
    """Re-parse every page exactly as the validator does; fail loudly on drift."""
    import re

    cell_re = re.compile(
        r"(^|\n)---\n<!-- trackio-cell\n([\s\S]*?)\n-->\n([\s\S]*?)"
        r"(?=\n---\n<!-- trackio-cell\n|\s*$)"
    )
    bad = 0
    for d in sorted(os.listdir(ROOT)):
        pd = os.path.join(ROOT, d, "page.md")
        if not os.path.isfile(pd):
            continue
        text = open(pd, encoding="utf-8").read()
        n_blocks = text.count("<!-- trackio-cell")
        parsed = 0
        for m in cell_re.finditer(text):
            try:
                json.loads(m.group(2))
                parsed += 1
            except json.JSONDecodeError:
                bad += 1
                print(f"  BAD JSON in {d}")
        status = "OK" if parsed == n_blocks else "MISMATCH"
        if parsed != n_blocks:
            bad += 1
        print(f"  {status:<9} {d:<70} cells parsed {parsed}/{n_blocks}")
    return bad
