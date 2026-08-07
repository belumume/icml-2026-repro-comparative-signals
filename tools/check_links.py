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
import time
import sys
import urllib.error
import urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SOURCES = [
    os.path.join(ROOT, "work", "space_README.md"),
    *glob.glob(
        os.path.join(ROOT, "logbook", ".trackio", "logbook", "pages", "*", "page.md")
    ),
]
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
