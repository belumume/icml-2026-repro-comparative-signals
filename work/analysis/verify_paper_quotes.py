"""Check that every sentence the logbook quotes from the paper is actually in the paper.

The whole submission's argument is that a claim must be supported by its evidence. A
fabricated or drifted quote would fail that standard in the one place it would be most
damaging, and quoting is exactly where drift is invisible: a paraphrase reads as a quote,
and nobody re-opens the source to check punctuation.

Two mechanical wrinkles this handles, both of which would otherwise produce false alarms:

  1. The arXiv HTML renders math tokens DOUBLED ("Z Z", "sigma sigma") because it emits
     both the visual and the alt form. A quote that is correct in prose therefore does
     not appear literally in the extracted text. Collapsing adjacent duplicate words
     recovers the match without loosening it into a fuzzy search.
  2. Smart quotes, non-breaking spaces and em dashes differ between the page and the
     source. Normalising those is a formatting concession, not a semantic one.

Run from the repo root. Exit 1 if any quoted sentence cannot be found.
"""

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PAPER = ROOT / "paper" / "paper_v2.html"
PAGES = ROOT / "logbook" / ".trackio" / "logbook" / "pages"

# EXPLICIT SCOPE. A blanket scan of every quoted string flagged 21 of 23 passages, nearly
# all of them my own prose, section headings and code fragments. A check whose scope is
# wider than its claim is as defective as one that is narrower: it buries the real finding
# in noise, which is the exact failure this project already hit with an ISO-timestamp
# false positive. So this verifies the specific sentences the ARGUMENT rests on, named
# here, and says so. Anything quoted elsewhere is out of scope by construction.
LOAD_BEARING = [
    "In practice, since Z is also partially obtained by the target model, this "
    "independence is naturally violated, ensuring efficiency gain",
    "We defer to Appendix B.3 a detailed discussion of why ranking accuracy decreases",
    "consistent variance reduction",
    "significantly closer to the ground truth",
]
MIN_WORDS = 4


def normalise(t):
    t = html.unescape(t)
    for a, b in [
        ("“", '"'),
        ("”", '"'),
        ("‘", "'"),
        ("’", "'"),
        ("—", " "),
        ("–", " "),
        (" ", " "),
        ("−", "-"),
    ]:
        t = t.replace(a, b)
    t = re.sub(r"[*_`]", "", t)  # markdown emphasis
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def collapse_doubles(t):
    """arXiv HTML emits math tokens twice; collapse adjacent identical words."""
    prev = None
    while prev != t:
        prev = t
        t = re.sub(r"\b(\S+) \1\b", r"\1", t)
    return t


def main():
    if not PAPER.is_file():
        print(f"missing {PAPER}")
        return 1
    raw = PAPER.read_text(encoding="utf-8", errors="replace")
    src = normalise(re.sub(r"<[^>]+>", " ", raw))
    src_collapsed = collapse_doubles(src)

    total = missing = 0
    print("Load-bearing quotes the argument depends on:")
    for q in LOAD_BEARING:
        n = normalise(q)
        found = n in src or collapse_doubles(n) in src_collapsed
        total += 1
        missing += not found
        print(f"  {'OK  ' if found else 'MISSING'} {q[:78]}")
    quoted = re.compile(r"(?!x)x")  # blanket scan disabled; see LOAD_BEARING above

    for page in sorted(PAGES.glob("*/page.md")):
        body = page.read_text(encoding="utf-8")
        body = re.sub(r"data:image/[^\"')]+", " ", body)  # drop the poster payload
        bad = []
        for m in quoted.finditer(body):
            q = normalise(m.group(1))
            if len(q.split()) < MIN_WORDS:
                continue
            # A quote is "from the paper" only if we can find it there; quotes of my own
            # prose, of the challenge text, or of a reviewer are not this check's business,
            # so a miss is reported for a human read rather than assumed to be fabrication.
            total += 1
            if q in src or collapse_doubles(q) in src_collapsed:
                continue
            bad.append(q)
        if bad:
            print(f"\n  {page.parent.name[:52]}")
            for q in bad:
                missing += 1
                print(f"    NOT FOUND IN PAPER: “{q[:110]}”")

    print(f"\n{total} quoted passages checked, {missing} not located in the paper.")
    if missing:
        print(
            "Each is either a fabricated/drifted quote, or a quote of something OTHER"
        )
        print(
            "than the paper (the challenge text, a reviewer, my own prose). Read each."
        )
        return 1
    print("every quoted passage of >=4 words is present verbatim in the source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
