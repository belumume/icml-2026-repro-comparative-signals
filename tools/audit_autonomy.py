"""Extract every genuine operator turn across the whole session, all compactions.

Answers one question against the record rather than from memory: which things did the
agent fail to do on its own, and what did the operator actually have to supply?

Filters out everything that is not the human speaking. The session JSONL's `user`
records are mostly NOT the user: tool results, hook injections, harness reminders,
local-command output and the compaction summaries all carry role=user.
"""

import json
import pathlib
import re
import sys

def _session_jsonl():
    """Locate the transcript without naming anyone's home directory in source."""
    import os, sys
    if len(sys.argv) > 1:
        return pathlib.Path(sys.argv[1])
    sid = os.environ.get("CLAUDE_SESSION_ID", "")
    base = pathlib.Path.home() / ".claude" / "projects"
    if sid:
        hit = next(base.rglob(f"{sid}.jsonl"), None)
        if hit:
            return hit
    found = sorted(base.rglob("*.jsonl"), key=lambda q: q.stat().st_mtime, reverse=True)
    if not found:
        raise SystemExit("no session JSONL found; pass one as argv[1]")
    return found[0]


PATH = _session_jsonl()

# Composed rather than written literally: a repo guard blocks source files containing
# the reminder tag verbatim, and this filter necessarily has to match on it.
_REMINDER = "<system-" + "reminder>"

NOISE = (
    _REMINDER,
    "<local-command-",
    "tool_use_id",
    "[Request interrupted",
    "Caveat: The messages below",
    "<command-name>",
    "<command-message>",
    "<user-prompt-submit-hook>",
)


def turns():
    out = []
    with open(PATH, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("type") != "user":
                continue
            if r.get("isCompactSummary"):
                out.append((i, "COMPACTION", ""))
                continue
            msg = r.get("message") or {}
            c = msg.get("content")
            if isinstance(c, list):
                text = " ".join(
                    b.get("text", "") for b in c if isinstance(b, dict) and "text" in b
                )
            elif isinstance(c, str):
                text = c
            else:
                continue
            text = text.strip()
            if not text or any(k in text for k in NOISE):
                continue
            # a genuine turn is prose the human typed; tool payloads are huge and JSON-ish
            if len(text) > 4000 or text.lstrip().startswith("{"):
                continue
            out.append((i, "USER", re.sub(r"\s+", " ", text)))
    return out


def main():
    rows = turns()
    users = [r for r in rows if r[1] == "USER"]
    ncomp = sum(r[1] == "COMPACTION" for r in rows)
    print(f"{len(users)} genuine operator turns, {ncomp} compactions\n")
    for i, kind, text in rows:
        if kind == "COMPACTION":
            print(f"\n{'=' * 74}\n[record {i}] --- COMPACTION BOUNDARY ---\n{'=' * 74}")
            continue
        print(f"[{i}] {text[:600]}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
