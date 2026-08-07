"""Publish gate: render every page the way the reader's browser will, then read it.

Every other gate in this repo inspects the markdown SOURCE. That is how 42 literal
asterisks and a shredded blockquote reached the live Claim 4 page while seven gates
reported green -- the source was exactly what I wrote, and what I wrote was not what
the renderer can display.

This gate runs `render_safe.render()`, a transcription of the renderer's own block
dispatch, over the generated pages and fails on anything a reader would see as raw
markup. It is the source-side half of the browser check; the browser is still the
authority, and `tools/check_live_render.py` goes and asks it.
"""

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_safe  # noqa: E402

PAGES = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "logbook",
    ".trackio",
    "logbook",
    "pages",
    "*",
    "page.md",
)


def main():
    if not render_safe.selftest():
        print("render_safe failed its own control; this gate's verdict means nothing")
        return 1
    print()
    total = 0
    pages = sorted(glob.glob(PAGES))
    if not pages:
        print(f"no pages found under {PAGES} -- wrong root?")
        return 1
    for path in pages:
        body = open(path, encoding="utf-8").read()
        problems = render_safe.check(body)
        name = path.replace("\\", "/").split("/")[-2][:52]
        print(f"  {'FAIL' if problems else 'OK  '} {name:54} {len(problems)} defect(s)")
        for kind, sample in problems[:4]:
            print(f"        {kind}: {sample}")
        total += len(problems)

    print()
    if total:
        print(f"{total} construct(s) would render as raw markup for the reader.")
        print("The renderer supports **bold**, `code`, [text](url) and bare URLs only.")
        return 1
    print(f"{len(pages)} pages render clean: no literal markup reaches the reader")
    return 0


if __name__ == "__main__":
    sys.exit(main())
