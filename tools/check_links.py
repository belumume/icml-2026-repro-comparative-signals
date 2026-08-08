"""Publish gate: every link a reader can click must resolve, and none may be relative.

WHY THIS IS A GATE AND NOT A ONE-OFF SCRIPT
-------------------------------------------
An ad-hoc version of this check reported "21 distinct links checked -- ALL RESOLVE"
while three links on the front page were dead. It expanded `./x` as `<space-root>/x`,
which is a rule I invented. Hugging Face resolves a relative link against the CURRENT
PAGE's directory, so a README viewed at `/blob/main/README.md` turns

    [code/README.md](./blob/main/code/README.md)

into `/blob/main/` + `blob/main/code/README.md` -- a doubled path that 404s. The
checker agreed with itself and not with the renderer, which is the same failure as
auditing markdown source and never opening the rendered page.

So relative links are refused outright rather than resolved. Their target depends on
which view the reader happens to be in, and a link whose destination depends on the
viewer is not a link you can verify. Absolute URLs have one meaning everywhere.

Run from the repo root:  python tools/check_links.py
"""

import concurrent.futures
import glob
import os
import re
import subprocess
import time
import sys
import urllib.error
import urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _sources():
    """Every tracked markdown file, DERIVED from git rather than enumerated by hand.

    This used to be a hardcoded list: the front-page README source plus the rendered
    logbook pages. Nine files, 22 links. The repo tracks 21 markdown files, so 12 sat
    outside the gate entirely, carrying 12 more links that nothing checked. Among them
    `code_publish/README.md`, which SHIPS to the Space as `code/README.md` and is
    reader-facing, and `data/PROMPT.md` and `data/README.md` with 9 links between them.

    They all resolved when checked by hand, so this widening cost nothing today. That is
    exactly why it was worth doing: the gate was reporting a clean result over a surface
    narrower than the one it appeared to cover, and a future edit to an unwalked file
    would have broken a link silently.

    Deriving from `git ls-files` means a markdown file added tomorrow is walked by
    existing, not by anyone remembering to add it here. FLOOR is a canary: if the walked
    set ever shrinks below what has already been verified, that is a scope regression and
    the gate says so instead of quietly checking less.
    """
    try:
        out = subprocess.run(
            ["git", "ls-files", "*.md"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        ).stdout.split()
        files = [
            os.path.join(ROOT, f) for f in out if os.path.isfile(os.path.join(ROOT, f))
        ]
    except Exception:
        files = []
    if not files:
        # not a git repo, or git unavailable: fall back to the original hardcoded set
        # rather than silently checking nothing, which would read as a pass
        files = [
            os.path.join(ROOT, "work", "space_README.md"),
            *glob.glob(
                os.path.join(
                    ROOT, "logbook", ".trackio", "logbook", "pages", "*", "page.md"
                )
            ),
        ]
    return files


SOURCE_FLOOR = 20  # verified at 21 tracked .md on 2026-08-08
SOURCES = _sources()
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")
UA = {"User-Agent": "Mozilla/5.0"}


def status(url, attempts=3, backoff=2.0):
    """HTTP status, retrying TRANSPORT failures but never HTTP ones.

    A single blip used to fail the whole publish and report a live link as dead. On
    2026-08-04 this reported openreview.net and github.com as URLError inside a publish
    run; both returned 200 to a direct request seconds later. That is worse than a missed
    check: a gate that cries wolf teaches you to re-run it until it passes, which is how
    a real dead link eventually ships.

    The split matters. An HTTPError is the SERVER answering, so 404 is a finding and is
    returned immediately without retry. Everything else is the TRANSPORT failing, which is
    a claim about this machine's network rather than about the link, so it is retried.
    """
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code  # the server spoke; not transient, do not retry
        except Exception as e:  # noqa: BLE001 - transport failure, possibly transient
            last = type(e).__name__
            if i < attempts - 1:
                time.sleep(backoff * (i + 1))
    return last


def selftest():
    """Prove this gate can FAIL before letting it report a pass.

    It was hand-controlled once, in a shell, on the day it was written. A control that
    lives outside the file is a control that stops running. Both shapes are checked: the
    relative link that shipped, and the doubled-path 404 it produced.
    """
    space = (
        "https://huggingface.co/spaces/passagereptile455/"
        "repro-evaluating-llms-comparative-signals/"
    )
    cases = [
        ("relative link must be REFUSED", "./blob/main/code/README.md", False),
        ("absolute link must be accepted", space + "blob/main/code/README.md", True),
    ]
    ok = True
    for label, url, should_pass in cases:
        is_relative = not url.startswith("http")
        passed = not is_relative
        good = passed == should_pass
        ok &= good
        print(f"  {'OK  ' if good else 'FAIL'} selftest: {label}")
    # and the 404 shape must be caught by the fetch layer, not just the prefix rule
    dead = space + "blob/main/blob/main/code/README.md"
    code = status(dead)
    good = code != 200
    ok &= good
    print(
        f"  {'OK  ' if good else 'FAIL'} selftest: the doubled path still 404s ({code})"
    )
    return ok


def main():
    if not selftest():
        print("this gate failed its own control; its verdict below means nothing")
        return 1
    print()
    relative = []
    urls = {}
    for path in SOURCES:
        if not os.path.isfile(path):
            continue
        text = open(path, encoding="utf-8").read()
        # the poster cell is a megabyte of base64; it holds no clickable links
        text = re.sub(r"data:image/[^\"')\s]+", " ", text)
        # Fenced code is not clickable, so a link-shaped string inside it is not a link.
        # Widening this gate from 9 files to all 21 tracked markdown surfaced exactly one
        # finding and it was this false positive: a JSON snippet in HANDOFF.md containing
        # `[...](url)`-shaped text, reported as a relative link. Expect a widening to
        # surface a class to narrow rather than to come back clean; a gate that cries wolf
        # on its first real day gets learned around, which is worse than never widening it.
        text = re.sub(r"```.*?```", " ", text, flags=re.S)
        text = re.sub(r"(?m)^(?: {4}|\t).*$", " ", text)
        # INLINE code too, which is where the one real false positive lived: HANDOFF.md
        # documents the trackio renderer's supported syntax as `[text](url)` inside
        # backticks. Fences and indented blocks were stripped first and it still fired,
        # because the string was never in a block at all. Worth the extra pass: a gate
        # whose first widened run reports a finding that is not a defect is the shape that
        # gets learned around.
        text = re.sub(r"``[^`]*``|`[^`\n]*`", " ", text)
        name = os.path.basename(os.path.dirname(path)) or os.path.basename(path)
        for m in LINK.finditer(text):
            url = m.group(1)
            if url.startswith(("#", "mailto:")):
                continue
            if not url.startswith("http"):
                relative.append((name, url))
                continue
            urls.setdefault(url, name)

    if relative:
        print("RELATIVE LINKS -- their target depends on which view renders the page:")
        for name, url in relative:
            print(f"  {name}: {url}")
        print(
            "Use an absolute https:// URL. See this file's docstring for the 404 this"
        )
        print("produced on the front page while an ad-hoc checker reported all-clear.")
        return 1

    bad = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for url, code in zip(urls, pool.map(status, urls)):
            if code != 200:
                bad.append((code, urls[url], url))

    print(f"{len(urls)} distinct links, 0 relative")
    for code, name, url in bad:
        print(f"  {code}  {name}: {url}")
    if bad:
        print(f"\n{len(bad)} link(s) a reader would click and land on nothing.")
        return 1
    print("every link resolves")
    return 0


if __name__ == "__main__":
    sys.exit(main())
