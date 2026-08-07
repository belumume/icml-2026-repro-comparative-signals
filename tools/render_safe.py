"""Make the generated markdown safe for the logbook renderer, and prove it.

THIS MODULE'S `render()` IS NOT THE RENDERER, AND IS NOT AUTHORITATIVE
---------------------------------------------------------------------
`render()` below is a PORT of logbook.js's block loop, written by inference from its
behaviour. A checker that re-implements its consumer agrees with ITSELF rather than with
the consumer, and this one did exactly that through three defects that shipped live and
were found by a human opening the page, never by this file:

  * a table inside a `> ` blockquote, which this port folded onto one line;
  * the same table after a partial fix, still unrenderable because a table CANNOT exist
    in a blockquote at all -- the renderer's table branch requires the line to start
    with `|`, and `> |` never does;
  * numbered items separated onto their own lines but with no blank line between them,
    which the renderer joins into a single run-on paragraph.

The AUTHORITATIVE structural gate is `check_renderer_contract.py`, whose rules are
transcribed from logbook.js itself and which is the one that must be trusted on whether
a construct renders. Keep this module for what it can honestly do: NORMALISE the source
(one logical block per line, emphasis the renderer can express) and catch the two purely
lexical residues below. Do not add structural detection here; add it there.

WHAT WENT WRONG
---------------
Every gate in this repo read the markdown SOURCE. None of them read the rendered
page, and the renderer is not a markdown implementation -- it is about forty lines
of regex in `trackio/frontend_templates/logbook/logbook.js`. Opening the live Space
in a browser and counting DOM nodes gave the verdict in one line:

    253 <strong> tags,  0 <em> tags.

So the renderer supports `**bold**`, `` `code` ``, `[link](url)` and bare URLs, and
NO italic in any form. Every `*emphasis*` written into these pages reached the reader
as literal asterisks -- 42 of them, in the argument prose where emphasis carries the
meaning. Worse, it is LINE-ORIENTED (`renderBlocks` dispatches on each line's prefix):

  * a `- ` bullet collects only lines that themselves start with `- `, so a wrapped
    continuation line breaks out of the bullet and becomes a separate paragraph;
  * each `> ` line becomes its OWN <blockquote> element, so a hard-wrapped quote
    renders as a ragged column of one-line quote bars;
  * `inline()` runs per line, so `**bold**` opened on one line and closed on the next
    matches nothing and both delimiters print literally.

All four defects hit the Claim 4 self-criticism blockquote at once -- the strongest
passage in the submission, rendered as twelve separate bars full of loose asterisks.

THE FIX
-------
`normalise()` rewrites each logical block onto ONE source line (which is what a
line-oriented renderer needs) and converts emphasis to something it can render.
Fenced code, tables and headings are passed through untouched.

`render()` is a faithful port of the renderer's own block dispatch, and `check()`
runs it to assert the OUTPUT is clean. That is the part that matters: a normaliser
verified against my model of the renderer proves nothing, because my model of the
renderer is exactly what was wrong. It is verified against the renderer's algorithm,
transcribed from its source, and the self-test drives the real defect through it.
"""

import re
import sys

# The renderer's complete inline vocabulary, from logbook.js lines 41-44.
RE_CODE = re.compile(r"`([^`]+)`")
RE_BOLD = re.compile(r"\*\*([^*]+)\*\*")
RE_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

FENCE = re.compile(r"^\s*(```|````)")
# A line the renderer dispatches on its own: heading, table row, horizontal rule,
# or a cell delimiter. None of these may be joined to a neighbour.
# The `(?:>\s*)?` is load-bearing and was missing. Without it this matched a bare table
# row but NOT a row inside a blockquote, because that row starts with "> ". normalise()
# then folded the whole quote -- table rows included -- onto one logical line, and the
# renderer printed the row separators literally:
#   | bench | N | ... | | --- | --- | ... | | GPQA | 50 | ...
# That shipped live on the Claim 4 page, in the paragraph carrying the strongest
# technical rebuttal in the submission, and no gate saw it.
STANDALONE = re.compile(r"^\s*(?:>\s*)?(#{1,6}\s|\||---\s*$|<!--)")
NUMBERED = re.compile(r"^\d+\.\s")


def _protect_code(text):
    """Hide inline-code spans so emphasis rewriting cannot touch `rho1**2`."""
    spans = []

    def stash(m):
        spans.append(m.group(0))
        return f"\x00{len(spans) - 1}\x00"

    return RE_CODE.sub(stash, text), spans


def _restore(text, spans):
    return re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], text)


def fix_emphasis(text):
    """Single-asterisk emphasis has no renderer support at all. Two cases.

    A span already wrapped in quotation marks -- *"significantly closer"* -- gets the
    asterisks dropped, because the quotes were always doing the work and bolding a
    quotation of someone else's words would misrepresent how it was said.

    Everything else becomes bold, which is the only emphasis that exists here. That is
    a real change in weight, and it is the honest one: the alternative is deleting
    emphasis the argument depends on ("the *direction* of the effect is real; the
    *evidence offered for it* does not").
    """
    text, spans = _protect_code(text)
    # Quoted span first, so it is not caught by the general rule below. The inner
    # alternation matters: three spans survived the first pass because the quotation
    # itself contains a nested **bold** -- *"...this independence is naturally
    # violated, **ensuring efficiency gain**."* -- and a [^"*]+ class cannot cross one.
    # Permitting a literal ** inside keeps the emphasis on the paper's own wording.
    q = r'(?:[^"*]|\*\*)+?'
    text = re.sub(rf'(?<!\*)\*("{q}")\*(?!\*)', r"\1", text)
    text = re.sub(rf"(?<!\*)\*(“{q}”)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"**\1**", text)
    return _restore(text, spans)


def normalise(body):
    """One source line per logical block; emphasis the renderer can render."""
    lines = body.split("\n")
    out = []
    fence = None
    buf = None  # (kind, prefix, text)

    def flush():
        nonlocal buf
        if buf is not None:
            kind, prefix, text = buf
            out.append(prefix + fix_emphasis(" ".join(text.split())))
            buf = None

    for raw in lines:
        if fence:
            out.append(raw)
            if FENCE.match(raw):
                fence = None
            continue
        if FENCE.match(raw):
            flush()
            out.append(raw)
            fence = raw.strip()[:4]
            continue

        stripped = raw.strip()
        if not stripped:
            flush()
            out.append("")
            continue
        if STANDALONE.match(raw):
            flush()
            out.append(fix_emphasis(raw))
            continue

        # A bare ">" separates quote paragraphs in the source, and the renderer has no
        # branch for it -- it falls through to the paragraph collector and would print
        # a stray ">". Treat it as a block break and drop it.
        if stripped == ">":
            flush()
            continue

        if NUMBERED.match(stripped):
            # The renderer has no ordered-list branch, so "1." / "2." / "3." fall through
            # to `para.push(trimmed)` and are joined with a space by flushPara().
            #
            # The previous comment here claimed that "keeping each on its own line makes
            # them three <p>s". That is FALSE, and it was reasoning about the renderer
            # instead of reading it: only a BLANK line flushes a paragraph. Four numbered
            # points on four consecutive lines rendered as one ~1,100-character wall of
            # text with inline "1." "2." "3." "4." markers, on the executive summary and
            # the conclusion -- the two pages a judge is most likely to skim.
            flush()
            if out and out[-1] != "":
                out.append("")
            buf = ("p", "", stripped)
        elif stripped.startswith("- "):
            flush()
            buf = ("li", "- ", stripped[2:])
        elif stripped.startswith("> "):
            if buf and buf[0] == "bq":
                buf = ("bq", "> ", buf[2] + " " + stripped[2:])
            else:
                flush()
                buf = ("bq", "> ", stripped[2:])
        elif buf is not None:
            # a wrapped continuation of whatever block is open
            buf = (buf[0], buf[1], buf[2] + " " + stripped)
        else:
            buf = ("p", "", stripped)
    flush()
    return "\n".join(out)


def render(body):
    """Port of the renderer's block dispatch, from logbook.js renderBlocks().

    Returns the visible text a reader would see. Only fidelity to the FAILURE modes
    matters here: per-line inline(), per-line blockquotes, bullets that only collect
    lines starting with "- ".
    """

    def inline(t):
        t = RE_CODE.sub(lambda m: m.group(1), t)
        t = RE_BOLD.sub(lambda m: m.group(1), t)
        t = RE_LINK.sub(lambda m: m.group(1), t)
        return t

    seen = []
    lines = body.split("\n")
    i = 0
    fence = None
    while i < len(lines):
        line = lines[i]
        if fence:
            if FENCE.match(line):
                fence = None
            i += 1
            continue
        if FENCE.match(line):
            fence = True
            i += 1
            continue
        t = line.strip()
        if t.startswith("|") or t.startswith("<!--") or t == "---":
            i += 1
            continue
        if t.startswith("> "):
            seen.append(inline(t[2:]))
        elif t.startswith("- "):
            seen.append(inline(t[2:]))
        elif t:
            seen.append(inline(t))
        i += 1
    return "\n".join(seen)


def check(body):
    """Problems a reader would SEE, found by rendering rather than by inspection."""
    problems = []
    for line in render(body).split("\n"):
        for m in re.finditer(r"\*\*|(?:^|[\s(])\*(?=\S)", line):
            problems.append(("literal asterisk", line.strip()[:96]))
            break
        if line.strip() == ">":
            problems.append(("stray blockquote marker", line))
        # A collapsed table. Its signature is unmistakable and cannot occur in prose: a
        # separator row's dashes appear INSIDE a line that also carries other cells,
        # because the rows were folded together. Detecting the rendered shape rather
        # than the source is the point; the source looked like a perfectly normal table.
        if re.search(r"\|\s*-{3,}\s*\|", line) and line.count("|") > 6:
            problems.append(
                ("collapsed table (rows folded onto one line)", line.strip()[:96])
            )
    return problems


def selftest():
    """Drive the real defect through it. A normaliser nobody has seen fail is a guess."""
    broken = (
        "> **The limitation of this yardstick, stated plainly because it is the strongest\n"
        "> objection to this page.** `Improv` is a *paired* contrast: naive and one-step\n"
        "> are computed on the *same* N items.\n"
        ">\n"
        '> The paper calls its gains *"significantly closer"* while reporting none.\n'
        "\n"
        "- Simulating the paper's own `Improv.` metric under a null where the estimate\n"
        "  carries no signal: a gain as large as the *median* arises by chance.\n"
        "\n"
        "```python\n"
        "theoretical_r2 = (rho1**2 * sigma**2) / (rho1**2 * sigma**2 + sigma_eta**2)\n"
        "```\n"
    )
    fixed = normalise(broken)

    # The blockquoted table, copied from the Claim 4 page as it actually shipped broken.
    # It is here verbatim rather than minimised: this normaliser is dead if this case
    # stops firing, and a minimised repro drifts away from the real source shape.
    quoted_table = (
        "> Measured rather than assumed, on the authors' own simulator at their own\n"
        "> sample sizes:\n"
        ">\n"
        "> | bench | N | marginal binomial SE | measured paired SD | ratio |\n"
        "> | --- | --- | --- | --- | --- |\n"
        "> | GPQA | 50 | 5.88 pp | 10.58 pp | 1.8x larger |\n"
        "> | AIME | 15 | 9.09 pp | 18.33 pp | 2.0x larger |\n"
        "> | GSM8K | 100 | 1.97 pp | 7.24 pp | 3.7x larger |\n"
        ">\n"
        "> The paired SD is 1.8x to 3.7x larger, not smaller.\n"
    )
    qt_fixed = normalise(quoted_table)
    qt_rows = [ln for ln in qt_fixed.split("\n") if ln.startswith("> |")]

    cases = [
        ("the defect must be detected before the fix", bool(check(broken))),
        # --- the blockquoted table, live-defect controls ---
        (
            "a blockquoted table keeps one row per line",
            len(qt_rows) == 5,
        ),
        (
            "...and the separator row is not folded into a data row",
            all(ln.count("|") == 6 for ln in qt_rows),
        ),
        (
            "...so check() reports nothing on the fixed form",
            not check(qt_fixed),
        ),
        (
            "check() DOES fire on a collapsed table (detector is load-bearing)",
            any(
                p[0].startswith("collapsed table")
                for p in check(
                    "> | bench | N | SE | | --- | --- | --- | | GPQA | 50 | 5.88 pp |"
                )
            ),
        ),
        (
            "...and does NOT fire on an ordinary separator row",
            not check("| --- | --- |"),
        ),
        ("no literal asterisk survives the fix", not check(fixed)),
        (
            "bold no longer spans a line break",
            "**The limitation of this yardstick, stated plainly because it is the "
            "strongest objection to this page.**" in fixed,
        ),
        (
            "the wrapped quote is now ONE blockquote line",
            sum(1 for ln in fixed.split("\n") if ln.startswith("> ")) == 2,
        ),
        (
            "the bullet keeps its continuation",
            any(
                ln.startswith("- Simulating") and "arises by chance" in ln
                for ln in fixed.split("\n")
            ),
        ),
        (
            "quoted span loses the asterisks, keeps the quotes",
            '"significantly closer"' in fixed and '*"significantly' not in fixed,
        ),
        ("word emphasis becomes bold", "**paired**" in fixed and "**median**" in fixed),
        (
            "code fence is untouched, rho1**2 intact",
            "theoretical_r2 = (rho1**2 * sigma**2) / (rho1**2 * sigma**2 + sigma_eta**2)"
            in fixed,
        ),
        ("stray '>' separator is dropped", "\n>\n" not in fixed),
    ]

    # The three that survived the first pass: a quotation carrying a nested **bold**.
    nested = normalise(
        'Remark 4.8 says, verbatim: *"In practice, this independence is naturally\n'
        'violated, **ensuring efficiency gain**."* That word does not follow.\n'
    )
    cases += [
        ("quote with nested bold loses its outer asterisks", not check(nested)),
        (
            "...and keeps the nested bold intact",
            "**ensuring efficiency gain**" in nested,
        ),
    ]

    # Numbered arguments must not collapse into one run-on paragraph.
    numbered = normalise(
        '1. The claim carries no range. It is not "for sigma in [0.5, 3.0]" or\n'
        '   "in our simulation".\n'
        "2. The condition it names is satisfied at sigma = 0.08.\n"
    )
    cases += [
        (
            "numbered points stay separate blocks",
            len([ln for ln in numbered.split("\n") if ln.strip()]) == 2,
        ),
        (
            "...with their own continuations joined in",
            any(
                "in our simulation" in ln and ln.startswith("1.")
                for ln in numbered.split("\n")
            ),
        ),
    ]
    ok = True
    for label, passed in cases:
        print(f"  {'OK  ' if passed else 'FAIL'} {label}")
        ok &= passed
    return ok


if __name__ == "__main__":
    sys.exit(0 if selftest() else 1)
