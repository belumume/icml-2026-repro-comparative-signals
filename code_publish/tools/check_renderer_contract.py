"""Validate every page against the REAL renderer's block contract, read from its source.

WHY THIS EXISTS, AND WHY THE PREVIOUS CHECKER DID NOT CATCH ANYTHING
--------------------------------------------------------------------
`render_safe.py` contains a PORT of the renderer's block dispatch, written by inference.
A checker that re-implements its consumer's rules agrees with itself, not with the
consumer, so it certified pages that were visibly broken to a reader. Three defects
shipped live on the Claim 4 page under a green gate, and each was found by a human
opening the page, never by the gate.

This file instead transcribes the contract from `logbook.js`, the actual renderer the
static Space loads. Verbatim, its block loop is:

    ""                       -> flush paragraph
    /^(`{3,}|~{3,})/         -> code fence, consumes to the closing fence
    "---"                    -> <hr>
    /^(#{1,4})\\s+/           -> h1..h4        <-- FOUR levels only, ##### is NOT a heading
    "|" + next line is a     -> table, consumes consecutive lines starting with "|"
       separator row                           <-- top level ONLY; "> |" never matches
    "> "                     -> ONE <blockquote> per line, inline() only
                                                <-- no table/list/fence/heading can live in one
    /^`[^`]+`$/              -> div.ts
    "- "                     -> list, consumes consecutive lines starting with "- "
    else                     -> paragraph collector

Everything this file reports is a construct the author clearly INTENDED as structure and
which the renderer will print as literal text instead.

Run:  python tools/check_renderer_contract.py
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
FENCE = re.compile(r"^(`{3,}|~{3,})")
SEPARATOR = re.compile(r"^\|?[\s:|-]*-{2,}[\s:|-]*\|?$")


def scan(text):
    """Walk the source the way the renderer walks it and report what will not render."""
    problems = []
    lines = text.split("\n")
    i = 0
    in_fence = False
    fence_close = None
    while i < len(lines):
        raw = lines[i]
        t = raw.strip()

        if in_fence:
            if fence_close and fence_close.match(t):
                in_fence = False
            i += 1
            continue
        m = FENCE.match(t)
        if m:
            in_fence = True
            fence_close = re.compile(
                "^" + m.group(1)[0] + "{" + str(len(m.group(1))) + ",}\\s*$"
            )
            i += 1
            continue

        # --- inside a blockquote nothing but inline text survives -------------
        if t.startswith("> "):
            inner = t[2:].strip()
            if inner.startswith("|"):
                problems.append((i + 1, "table row inside a blockquote", inner[:88]))
            elif inner.startswith("- "):
                problems.append((i + 1, "bullet inside a blockquote", inner[:88]))
            elif re.match(r"^#{1,6}\s", inner):
                problems.append((i + 1, "heading inside a blockquote", inner[:88]))
            elif FENCE.match(inner):
                problems.append((i + 1, "code fence inside a blockquote", inner[:88]))
            i += 1
            continue

        # --- headings deeper than h4 are not headings -------------------------
        if re.match(r"^#{5,}\s", t):
            problems.append(
                (i + 1, "h5+ renders as plain text (renderer stops at h4)", t[:88])
            )
            i += 1
            continue

        # --- a table only renders if the NEXT line is a separator row ---------
        if t.startswith("|"):
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if not SEPARATOR.match(nxt):
                problems.append(
                    (i + 1, "table row with no separator row after it", t[:88])
                )
                i += 1
                continue

            # renderTable iterates the HEADER's cells, so any row with more cells than
            # the header loses the extras with no warning. Three rows carried a trailing
            # warning marker as an eighth cell against a seven-column header; the marker
            # never rendered and those rows read as arithmetic errors.
            def ncells(s):
                s = s.strip()
                body = s[1:-1] if s.endswith("|") else s[1:]
                return len(body.split("|"))

            width = ncells(lines[i])
            start = i
            while i < len(lines) and lines[i].strip().startswith("|"):
                if i != start + 1 and ncells(lines[i]) != width:
                    problems.append(
                        (
                            i + 1,
                            f"row has {ncells(lines[i])} cells against a {width}-cell "
                            "header; the extras are dropped silently",
                            lines[i].strip()[:88],
                        )
                    )
                i += 1
            continue

        i += 1
    return problems


def selftest():
    """Prove each detector fires on the shape it exists for, and stays quiet otherwise.

    Case 1 is the table that shipped broken on the Claim 4 page, verbatim. This checker
    is dead if that case stops firing.
    """
    cases = [
        (
            "the shipped blockquoted table is caught",
            "> Measured on their own simulator:\n"
            "> | bench | N | SE |\n"
            "> | --- | --- | --- |\n"
            "> | GPQA | 50 | 5.88 pp |\n",
            "table row inside a blockquote",
        ),
        (
            "a bullet inside a blockquote is caught",
            "> - this never becomes a list\n",
            "bullet inside a blockquote",
        ),
        (
            "an h5 is caught",
            "##### not a heading\n",
            "h5+ renders as plain text (renderer stops at h4)",
        ),
        (
            "a table with no separator row is caught",
            "| a | b |\n| 1 | 2 |\n",
            "table row with no separator row after it",
        ),
        (
            "the shipped trailing-marker row is caught",
            "| bench | N | gain |\n| --- | --- | --- |\n| GSM8K | 100 | **+0.00** | warn\n",
            "row has 4 cells against a 3-cell header; the extras are dropped silently",
        ),
    ]
    ok = True
    for label, src, want in cases:
        got = [p[1] for p in scan(src)]
        good = want in got
        ok &= good
        print(f"  {'OK  ' if good else 'FAIL'} selftest: {label}")

    # must-NOT-fire: the valid forms, or this checker would flag the whole logbook
    clean = (
        "## A real heading\n\n"
        "| bench | N |\n| --- | --- |\n| GPQA | 50 |\n\n"
        "> A single-line quote with `code` and **bold**.\n\n"
        "- a bullet\n- another\n\n"
        "```python\n"
        "> | this is inside a fence | and must be ignored |\n"
        "```\n"
    )
    good = not scan(clean)
    ok &= good
    print(
        f"  {'OK  ' if good else 'FAIL'} selftest: valid markdown produces no findings"
    )
    if not good:
        for p in scan(clean):
            print("      unexpected:", p)
    return ok


def main():
    if not selftest():
        print("this checker failed its own control; its verdict below means nothing")
        return 1
    print()
    total = 0
    for path in PAGES:
        name = os.path.basename(os.path.dirname(path))
        found = scan(open(path, encoding="utf-8").read())
        if found:
            print(f"{name}")
            for ln, kind, snip in found:
                print(f"  line {ln:>5}  {kind}")
                print(f"              {snip}")
            total += len(found)
    print(f"\n{len(PAGES)} pages, {total} construct(s) the renderer will print as text")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
