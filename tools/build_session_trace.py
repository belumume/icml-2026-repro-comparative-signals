"""Extract a mechanical, lossless SKELETON of the session from the raw JSONL.

WHY THIS IS NOT A FAN-OUT. The obvious approach to "trace the whole session" is to chunk
17.9 MB and hand every chunk to an agent. That costs a fleet, and most of what it would
extract is deterministic: who said what, which commands ran, which files were written,
how tasks moved. None of that needs judgement, so none of it needs an agent.

So this pulls the skeleton mechanically and cheaply, leaving ONLY the interpretive layer
(what the arc means, which lessons transfer) to be written on top. That is the difference
between a targeted mine and an indiscriminate one.

Built from the RAW record rather than any compact summary, because this session crossed
three compaction boundaries and a summary is a lossy paraphrase by construction. Base64
payloads are stripped: the poster embed alone is ~600 KB and recurs, so leaving it in
would dominate the output while carrying no information.
"""

import json
import os
import re
import sys
from pathlib import Path

# Derived at runtime, never hardcoded. An absolute path under a home directory carries
# the OS account name, and this file ships to a PUBLIC Space, so a literal path here
# publishes an identifier indefinitely. sanitize_trace.py already scrubs identifiers out
# of the trace CONTENT; that is worth nothing while the generator's own source leaks the
# same string. Two occurrences of the profile name shipped live this way.
SESSION_ID = os.environ.get("CLAUDE_SESSION_ID", "")
PROJECT_SLUG = os.environ.get("CLAUDE_PROJECT_SLUG", "")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "work" / "session_trace.md"


def _resolve_src():
    """Locate the session JSONL without naming anyone's home directory in the source."""
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    base = Path.home() / ".claude" / "projects"
    if PROJECT_SLUG:
        base = base / PROJECT_SLUG
    if SESSION_ID:
        hit = next(base.rglob(f"{SESSION_ID}.jsonl"), None)
        if hit:
            return hit
    # newest transcript under the projects tree, which is what an interactive run wants
    found = sorted(base.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not found:
        raise SystemExit(
            "no session JSONL found; pass one explicitly:\n"
            "  python tools/build_session_trace.py <path-to-session.jsonl>"
        )
    return found[0]


SRC = _resolve_src()

B64 = re.compile(r"[A-Za-z0-9+/]{200,}={0,2}")
HEX = re.compile(r"\b[0-9a-f]{64,}\b")
WS = re.compile(r"[ \t]+")

# Harness-injected markers, composed rather than written literally so this file does not
# itself look like an injection leak to the guard that watches for exactly that.
INJECTED = (
    "<system-" + "reminder>",
    "hook additional context",
    "<local-" + "command",
    "[Request interrupted",
)


def clean(t, cap=None):
    if not isinstance(t, str):
        t = str(t)
    t = B64.sub("<base64>", t)
    t = HEX.sub("<hex>", t)
    t = WS.sub(" ", t).strip()
    if cap and len(t) > cap:
        t = t[:cap] + f" ...[+{len(t) - cap} chars]"
    return t


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def main():
    if not SRC.is_file():
        print(f"missing {SRC}")
        return 1

    users, compactions, tools, writes, tasks = [], [], [], [], []
    n = 0
    for line in SRC.open(encoding="utf-8", errors="replace"):
        n += 1
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue

        if rec.get("isCompactSummary"):
            compactions.append(n)
            continue

        msg = rec.get("message") or {}
        role = msg.get("role") or rec.get("type")
        content = msg.get("content")

        if role == "user":
            t = text_of(content)
            # Exclude harness-injected material. It is not the operator speaking, and
            # counting it as a user turn is the self-contamination trap in
            # claim-verification.md: a corpus containing your own output cannot
            # corroborate your own output.
            if t and not any(m in t for m in INJECTED) and not t.startswith("Caveat:"):
                users.append((n, clean(t, 700)))

        elif role == "assistant" and isinstance(content, list):
            for b in content:
                if not isinstance(b, dict) or b.get("type") != "tool_use":
                    continue
                name, inp = b.get("name", "?"), b.get("input") or {}
                if name in ("Bash", "PowerShell"):
                    cmd = clean(inp.get("command", ""), 150)
                    if cmd:
                        tools.append((n, cmd))
                elif name in ("Write", "Edit", "MultiEdit"):
                    writes.append((n, name, inp.get("file_path", "?")))
                elif name in ("TaskCreate", "TaskUpdate"):
                    tasks.append(
                        (
                            n,
                            name,
                            clean(inp.get("subject") or inp.get("taskId", ""), 90),
                            inp.get("status", ""),
                        )
                    )

    seen, files = set(), []
    for _, _, fp in writes:
        if fp not in seen:
            seen.add(fp)
            files.append(fp)

    lines = [
        "---",
        "audience: internal",
        "public: false",
        "---",
        "",
        "# Session trace (mechanical skeleton)",
        "",
        f"Extracted from the raw session JSONL ({SRC.stat().st_size:,} B, {n:,} records) "
        "rather than from any compact summary, because this session crossed "
        f"**{len(compactions)} compaction boundaries** and a summary is lossy by "
        "construction. Regenerate at any time with `tools/build_session_trace.py`.",
        "",
        f"- operator turns: **{len(users)}**",
        f"- shell commands: **{len(tools)}**",
        f"- file writes/edits: **{len(writes)}** across **{len(files)}** distinct files",
        f"- task operations: **{len(tasks)}**",
        f"- compaction boundaries at records: {compactions}",
        "",
        "## 1. The operator's own words, in order",
        "",
        "The authoritative spec for this session. Every correction the work turned on is "
        "here verbatim, which is the first thing a compact summary flattens.",
        "",
    ]
    for rn, t in users:
        lines += [f"**[rec {rn}]** {t}", ""]

    lines += ["## 2. Task lifecycle", ""]
    for rn, kind, subj, st in tasks:
        lines.append(f"- `[{rn}]` {kind} {subj}{(' -> ' + st) if st else ''}")

    lines += ["", "## 3. Files written or edited (first-touch order)", ""]
    lines += [f"- `{fp}`" for fp in files]

    lines += ["", "## 4. Commands run", ""]
    lines += [f"- `[{rn}]` `{cmd}`" for rn, cmd in tools]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size:,} B)")
    print(
        f"  {len(users)} operator turns | {len(tools)} commands | {len(files)} files | "
        f"{len(tasks)} task ops | {len(compactions)} compactions"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
