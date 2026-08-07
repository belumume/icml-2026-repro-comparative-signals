"""Measure slop, bloat, and prize-criteria compliance instead of asserting them.

Answers four questions with numbers:
  1. Is there slop or bloat in the poster or the pages?
  2. Are the Special Prize #2 criteria met, verbatim from the organizers' own wording?
  3. Does the logbook match the REQUIRED structure from the challenge instructions?
  4. Is every Hub model / dataset / repo linked, which the instructions require explicitly?

Run from the repo root.
"""

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PAGES = ROOT / "logbook" / ".trackio" / "logbook" / "pages"
POSTER = ROOT / "work" / "poster_build" / "poster.html"
SUB = ROOT / "SUBMISSION.md"

# --- slop markers, from ~/.claude/rules/anti-slop.md ------------------------
FLAGGED = [
    "actionable",
    "comprehensive",
    "subsequent",
    "leverage",
    "delve",
    "tapestry",
    "facilitate",
    "utilize",
    "enhance",
    "streamline",
    "robust",
]
CLOSERS = [
    "hope this helps",
    "feel free",
    "don't hesitate",
    "happy to discuss",
    "let me know if",
    "looking forward to",
]
TEMPLATED = [
    r"In this (section|paper|article|report)",
    r"We (present|propose|introduce) a (novel|new)",
    r"it is worth noting",
    r"it should be noted",
    r"to the best of our knowledge",
    r"it is well[- ]known",
    r"our (key|main|primary|novel) contribution",
]
# editorial bloat: internal process leaking into a public artifact
BLOAT = [
    (r"\b(?:ADR|DECISION|RFC-INT)-?\d+\b", "internal decision id"),
    # NOT (?<![A-Za-z]): that still matches the "T22" of an ISO timestamp
    # (2026-08-02T22:35), which produced 14 false positives on the first run.
    (r"(?<![A-Za-z0-9])T\d{2,4}\b", "internal task id"),
    (r"\b[a-zA-Z_][a-zA-Z0-9_]*\.py:\d+", "file:line citation"),
    (
        r"\b(?:per|after|pre-?|post-?)\s*(?:session\s*\d+|compact(?:ion)?)",
        "session ref",
    ),
    (r"(?i)\b(?:TODO|FIXME|rewrite per agent)\b", "dev chatter"),
    (r"(?i)\bverified empirically\b", "process-revealing"),
]

fails = []


def note(ok, label, detail=""):
    print(f"  {'OK  ' if ok else 'FLAG'} {label}{(' -- ' + detail) if detail else ''}")
    if not ok:
        fails.append(label)


def strip_html(t):
    # Comments first. An HTML/CSS comment is invisible to a reader, so slop rules that
    # exist to protect the READER do not apply there. Counting them produced a flag on
    # "text identity - no venue logo fabricated", which is a source note recording a
    # deliberate decision, not prose anyone sees.
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    # Decode entities. Without this the counter reads the SOURCE while the slop rules
    # exist to protect the READER: the poster carried three em dashes and this audit
    # reported one, because two were written &mdash; and a literal-character count
    # cannot see an entity. Same shape as every other defect found today, where a gate
    # inspected the input and the defect lived in the output.
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t)


def scan(name, text):
    print(f"\n--- {name} ({len(text.split()):,} words) ---")
    em = text.count("—")
    # The poster title uses one as a separator between paper name and venue, which is
    # conventional for a title and inside the "max 1-2 in long-form" allowance. Body
    # prose stays at zero. Changing it would reflow a title tuned to fit one line.
    allowed = 1 if name == "poster.html" else 0
    note(em <= allowed, f"em dashes = {em} (allowed {allowed})")
    for w in FLAGGED:
        n = len(re.findall(rf"\b{w}\b", text, re.I))
        if n:
            note(False, f"flagged vocab '{w}' x{n}")
    for c in CLOSERS:
        if c in text.lower():
            note(False, f"empty closer '{c}'")
    for pat in TEMPLATED:
        m = re.search(pat, text, re.I)
        if m:
            note(False, f"templated opener: {m.group(0)[:40]!r}")
    for pat, label in BLOAT:
        hits = re.findall(pat, text)
        if hits:
            note(False, f"editorial bloat ({label}) x{len(hits)}", str(hits[:3]))


def main():
    print("=" * 70)
    print("1. SLOP / BLOAT")
    print("=" * 70)
    for p in sorted(PAGES.glob("*/page.md")):
        body = p.read_text(encoding="utf-8")
        # the exec summary embeds a base64 poster; strip it or word counts are fiction
        body = re.sub(r"data:image/[^\"')]+", "<embedded-image>", body)
        scan(p.parent.name[:44], body)
    if POSTER.is_file():
        scan("poster.html", strip_html(POSTER.read_text(encoding="utf-8")))

    print()
    print("=" * 70)
    print("2. SPECIAL PRIZE #2 CRITERIA (organizers' verbatim wording)")
    print("=" * 70)
    sub = SUB.read_text(encoding="utf-8")
    m = re.search(r"`fals-explanation` \(.*?```\n(.*?)\n```", sub, re.S)
    expl = m.group(1).strip() if m else ""
    print(
        f'  criterion: "a significant claim could not be reproduced and what is true instead"'
    )
    note(len(expl) > 0, "explanation present", f"{len(expl)} chars / 1500")

    # ------------------------------------------------------------------
    # Criterion-shaped, NOT phrase-keyed.
    #
    # The previous design was three lists of literal phrasings, grown by one entry
    # every time the field was rewritten. Across one session it reported a required
    # element as MISSING seven times, and on every one of those occasions the element
    # was present and the WORDING had changed. A check keyed to one wording does not
    # verify the criterion; it verifies that nobody edited the text, and it argues
    # against every improvement. The comment trail below those lists was itself the
    # evidence: six successive "added after the field was rewritten" apologies.
    #
    # These test the SHAPE a satisfied criterion must have in ANY wording:
    #
    #   (a) ORIGINAL CLAIM  = a reference to the paper  AND a verb of assertion
    #   (b) EVIDENCE        = two or more quantitative facts, OR an explicit
    #                         statement that no uncertainty was reported
    #   (c) REPLACEMENT     = a contrast marker  AND a verb of support
    #
    # The controls after them drive the real functions against texts that genuinely
    # lack one element (must read absent) and against texts that carry the element in
    # wording nobody here has used (must read present). The second half is what proves
    # these are criterion-shaped rather than a longer list of my own sentences.
    # ------------------------------------------------------------------
    # `\btheir\b` is deliberately broad: a possessive reference to the authors, paired
    # with an assertion verb, IS a statement of the paper's own claim however it is
    # phrased. The first version required "their paper" or "their X claims" and the
    # positive control caught it -- "Their method is advertised as strictly better"
    # read as ABSENT, which is exactly the failure this rebuild exists to remove.
    PAPER_REF = r"arXiv\s*\d{4}\.\d{4,5}|\bthe paper\b|\btheir\b|\bthe authors\b"
    ASSERT_VB = (
        r"\b(?:reports?|claims?|states?|says?|proposes?|promises?|shows?|advertis\w+)\b"
    )
    QUANT = r"[-+]?\d+(?:\.\d+)?\s*%|\[[-+]?\d|\b\d+\s+of\s+\d+\b|\b\d{2,}\s+(?:runs|comparisons|cells|items|models)\b"
    ABSENCE = r"\bno (?:error bar|uncertainty|interval)|without .{0,25}(?:error bar|interval|uncertainty)|zero (?:times|occurrences)|\bfor none of them\b"
    CONTRAST = r"\binstead\b|\bdifferent\b|\brather than\b|\bwhat (?:holds|survives|is true)\b|\bnot enough to\b"
    SUPPORT_VB = r"\b(?:supports?|holds?|helps?|remains?|survives?|predicts?|is real\b)"

    def crit_a(t):
        return bool(re.search(PAPER_REF, t, re.I) and re.search(ASSERT_VB, t, re.I))

    def crit_b(t):
        return len(re.findall(QUANT, t, re.I)) >= 2 or bool(re.search(ABSENCE, t, re.I))

    def crit_c(t):
        return bool(re.search(CONTRAST, t, re.I) and re.search(SUPPORT_VB, t, re.I))

    CRITS = [
        (crit_a, "(a) explains the ORIGINAL claim"),
        (crit_b, "(b) gives the EVIDENCE against it"),
        (crit_c, "(c) states a NEW claim believed true instead"),
    ]
    for fn, label in CRITS:
        note(fn(expl), label)

    # Controls. Each criterion gets one text that genuinely LACKS its element (must
    # read absent, or the check has been loosened into always-true and certifies
    # nothing) and one that carries the element in wording used nowhere in this repo
    # (must read present, or the check is still keyed to my sentences).
    NEG = {
        "(a)": "Running the simulator unmodified gives 33% more variance, 95% CI "
        "[-0.495, -0.185] over 250 runs. My reproduction supports a different "
        "claim: the effect is real on average but not resolvable per cell.",
        "(b)": "arXiv 2602.03061 reports that its estimator beats plain averaging. "
        "My reproduction supports a different claim instead: the gain holds "
        "only when pooled.",
        "(c)": "arXiv 2602.03061 reports 60 benchmark comparisons where its "
        "estimator beats plain averaging. Running their code gives 33% more "
        "variance, 18% to 50% across 250 runs.",
    }
    POS = {
        "(a)": "Their method is advertised as strictly better than the sample mean.",
        "(b)": "Not one of the sixty entries is given without an error bar missing; "
        "in fact no uncertainty interval accompanies any of them.",
        "(c)": "What is true instead: the improvement is real in aggregate and holds "
        "nowhere individually.",
    }
    for (fn, label), key in zip(CRITS, ("(a)", "(b)", "(c)")):
        if fn(NEG[key]):
            note(False, f"CONTROL {key}: reads PRESENT on a text that lacks it")
        if not fn(POS[key]):
            note(
                False, f"CONTROL {key}: reads ABSENT on unfamiliar wording that has it"
            )

    print()
    print("=" * 70)
    print("3. REQUIRED LOGBOOK STRUCTURE (from the challenge instructions)")
    print("=" * 70)
    want = [
        "executive-summary",
        "claim-1",
        "claim-2",
        "claim-3",
        "claim-4",
        "claim-5",
        "conclusion",
    ]
    have = [p.parent.name for p in sorted(PAGES.glob("*/page.md"))]
    for w in want:
        note(any(h.startswith(w) for h in have), f"page present: {w}")
    exec_p = next(
        (p for p in PAGES.glob("*/page.md") if p.parent.name == "executive-summary"),
        None,
    )
    if exec_p:
        t = exec_p.read_text(encoding="utf-8")
        note(
            "Scope & cost" in t or "Scope &amp; cost" in t,
            "exec summary has Scope & cost table",
        )
        note("poster" in t.lower(), "exec summary has the pinned poster")

    print()
    print("=" * 70)
    print("4. 'Link every Hub model, dataset, Job, Bucket, and GitHub repo'")
    print("=" * 70)
    alltext = "\n".join(p.read_text(encoding="utf-8") for p in PAGES.glob("*/page.md"))
    raw = ROOT / "kaggle" / "real_data_ppi" / "out" / "real_gsm8k_ppi.json"
    models = []
    if raw.is_file():
        cfg = json.load(open(raw, encoding="utf-8"))["config"]
        models = cfg["eval_models"] + cfg["aux_models"]
    for mdl in models:
        linked = f"huggingface.co/{mdl}" in alltext
        note(linked, f"Hub model linked: {mdl}")
    note(
        "github.com/zihandong02/AI_evaluation" in alltext, "authors' GitHub repo linked"
    )
    note(
        "-traces" in alltext or "traces" in alltext.lower(), "traces dataset referenced"
    )

    print()
    print("=" * 70)
    print(f"{len(fails)} FLAG(S)" if fails else "NO FLAGS")
    for f in fails:
        print("   -", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
