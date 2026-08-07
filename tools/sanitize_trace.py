"""Sanitize a Claude Code session JSONL before it is published publicly.

The challenge requires PUBLIC agent traces. Trackio's attach step scrubs secrets
(tokens/keys) but NOT personal identifiers, and a raw Claude Code transcript is full of
shell output carrying the operator's identity. Publishing it verbatim leaks that.

This rewrites identifiers to neutral placeholders while leaving the technical content,
which is the whole evidentiary value of the trace, completely intact.

TWO DEFECTS THIS FILE HAS ALREADY SHIPPED, both fixed here, both worth stating because
they are the failure modes a sanitizer is prone to:

1. It scrubbed the Windows *profile* name but not the OS *account* name, which appears
   in every `ls -la` line as the file-owner column. 125 occurrences reached a public
   dataset. The audit did not catch it because the audit only re-checked the patterns
   the substitution list already knew about, so it was structurally blind to exactly
   the identifier that was missing. An audit that can only confirm what the fixer
   already handles is not an audit.

2. It hardcoded the operator's username as a module constant, so publishing the
   sanitizer published the identifier it exists to remove.

Both are fixed by deriving identifiers at RUNTIME from the environment rather than
naming them in source, and by auditing against a broad identity pattern rather than
against the substitution list.
"""

import argparse
import getpass
import json
import os
import re
import sys
from pathlib import Path


def identifiers(extra):
    """Every string that identifies this operator, longest first.

    Longest-first matters: scrubbing a short name before a longer one containing it
    corrupts the longer one into a half-redacted string that still leaks.
    """
    found = set()
    for cand in [
        getpass.getuser(),
        Path.home().name,
        os.environ.get("USERNAME", ""),
        os.environ.get("USER", ""),
        *extra,
    ]:
        cand = (cand or "").strip()
        if len(cand) >= 4:  # avoid scrubbing generic short tokens
            found.add(cand)
    return sorted(found, key=len, reverse=True)


EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Public, project-relevant, and carrying no personal address.
EMAIL_ALLOW = re.compile(r"(noreply|users\.noreply\.github\.com|example\.com)", re.I)


# re.I is load-bearing and was missing: without it a lowercase `c:\users\jdoe` from
# shell output passed the audit untouched. The self-test below caught that on its first
# run, which is the entire argument for having one.
HOME_SEG = re.compile(r"[A-Za-z]:[\\/]{1,4}Users[\\/]{1,4}([A-Za-z0-9._-]+)", re.I)
KNOWN_SEGMENTS = {"user", "public", "default", "all users"}


def stray_home_segments(text, allow=()):
    """Home-path segments that are NOT an expected placeholder.

    Narrowed once, deliberately, and the reason matters. The trace being sanitized is a
    transcript of the work, and this session DISCUSSED this very check, so the sentence
    "a stray `C:/Users/r...`" got recorded into the transcript and the audit then flagged
    its own investigation. The capture there is a one-letter stub plus an ellipsis, not
    an account name.

    So a capture is ignored only when its alphanumeric core is too short to be an
    account name at all. Anything of real-username length still trips the gate, which
    `_self_test` below proves rather than assumes: a narrowing that is not shown to
    still fire is indistinguishable from having disabled the check.
    """
    out = set()
    for m in HOME_SEG.finditer(text):
        seg = m.group(1)
        core = re.sub(r"[^A-Za-z0-9]", "", seg)
        if len(core) < 3:
            continue  # e.g. "r..." from prose about this check
        if seg.lower() in KNOWN_SEGMENTS or seg.lower() in {a.lower() for a in allow}:
            continue
        out.add(seg)
    return out


def _self_test():
    """Positive control. Refuses to run the audit until it can prove it still bites.

    The fixtures are COMPOSED at runtime rather than written as literals, and that is
    not stylistic. This tool sanitizes a transcript of the very session that runs it, so
    any example path spelled out in this file gets recorded into that transcript and the
    audit then flags its own test data as a leak. Building the strings from parts keeps
    the control honest without poisoning the corpus it inspects. The same reasoning is
    why the failure output prints segments but the substitution list never prints names.
    """
    stem = "C:" + "/" + "Users" + "/"
    for seg in ["a" + "cct1", "s" + "omebody", "j" + "smith"]:
        for path in (stem + seg + "/DEV", stem.replace("/", "\\") + seg + "\\DEV"):
            assert stray_home_segments(path), "control failed: real-length name missed"
    # lowercase drive and dir, the case a missing re.I silently let through
    assert stray_home_segments("c:" + "\\" + "users" + "\\" + "n" + "ame7" + "\\x")

    for path in [stem + "user/DEV", stem + "Public/x", stem + "r..."]:
        assert not stray_home_segments(path), f"over-correction: caught {path!r}"


def build_subs(names):
    subs = []
    for n in names:
        e = re.escape(n)
        subs += [
            (
                re.compile(rf"[Cc]:[\\/]{{1,2}}Users[\\/]{{1,2}}{e}", re.I),
                "C:/Users/user",
            ),
            (re.compile(rf"/c/Users/{e}", re.I), "/c/Users/user"),
            (re.compile(rf"\\\\Users\\\\{e}", re.I), r"\\\\Users\\\\user"),
            # PLAIN substring, deliberately NOT \b...\b. In a JSON-escaped transcript a
            # captured output line is preceded by the two characters backslash and n, so
            # the character immediately before an identifier is the WORD character "n"
            # and a word boundary never matches. That is exactly where an `ls -l` owner
            # column sits. Both this substitution and the audit below used \b, so both
            # were blind to the same cases, and 16 occurrences survived a run that
            # printed CLEAN. Over-scrubbing an identifier is harmless; missing one is
            # the entire failure mode.
            (re.compile(e, re.I), "user"),
        ]
    subs.append((EMAIL, "<email-redacted>"))
    return subs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument(
        "--also",
        action="append",
        default=[],
        help="additional identifier to scrub (repeatable). Use for names that do not "
        "appear in the environment, e.g. a third-party account handle.",
    )
    ap.add_argument(
        "--allow-segment",
        action="append",
        default=[],
        help="a home-path segment that is NOT a real identity and may pass the audit "
        "(repeatable). Every use is printed, so nothing is silently ignored. This "
        "exists because the transcript being sanitized records this tool's own test "
        "fixtures, and an append-only history cannot be edited after the fact. Never "
        "use it for a segment you have not personally confirmed is synthetic.",
    )
    args = ap.parse_args()

    _self_test()  # the audit must be shown to bite before it is trusted
    names = identifiers(args.also)
    if not names:
        print("no identifiers resolved; refusing to run", file=sys.stderr)
        return 1
    # Deliberately does NOT print the names: this output can be pasted anywhere.
    print(f"scrubbing {len(names)} identifier(s), longest first")
    subs = build_subs(names)

    def scrub(text):
        for pat, rep in subs:
            text = pat.sub(rep, text)
        return text

    n_in = n_out = 0
    with (
        open(args.src, encoding="utf-8", errors="replace") as fi,
        open(args.dst, "w", encoding="utf-8", newline="\n") as fo,
    ):
        for line in fi:
            n_in += 1
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError:
                continue
            cleaned = scrub(line)
            try:
                json.loads(cleaned)
            except json.JSONDecodeError:
                print(
                    f"line {n_in}: substitution broke JSON, dropping", file=sys.stderr
                )
                continue
            fo.write(cleaned if cleaned.endswith("\n") else cleaned + "\n")
            n_out += 1

    print(f"records in={n_in} out={n_out}")

    # ---- audit the OUTPUT ---------------------------------------------------
    # Checks the identifiers AND a generic home-path shape, so a future identifier
    # the substitution list has never heard of still trips the gate.
    text = open(args.dst, encoding="utf-8", errors="replace").read()
    fails = 0

    for n in names:
        # plain substring, for the same escaped-newline reason as build_subs
        hits = len(re.findall(re.escape(n), text, re.I))
        print(f"  identifier {'CLEAN' if not hits else f'FAIL ({hits})'}")
        fails += bool(hits)

    if args.allow_segment:
        print(
            f"  allowing {len(args.allow_segment)} reviewed segment(s): "
            f"{sorted(args.allow_segment)}"
        )
    unexpected = sorted(stray_home_segments(text, allow=args.allow_segment))
    print(f"  home paths {'CLEAN' if not unexpected else f'FAIL {unexpected[:5]}'}")
    fails += bool(unexpected)

    emails = [h for h in EMAIL.findall(text) if not EMAIL_ALLOW.search(h)]
    print(f"  emails     {'CLEAN' if not emails else f'FAIL ({len(emails)})'}")
    fails += bool(emails)

    if fails:
        print("\nSANITIZATION INCOMPLETE. Do not publish.", file=sys.stderr)
        return 1
    print("\nsanitized trace is clean; safe to attach and publish publicly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
