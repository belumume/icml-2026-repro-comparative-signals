"""Regenerate the poster gate report with repo-relative paths only.

The published `poster_gates.json` was written by the gate tool with absolute local paths,
so it carried the operator's Windows username 17 times onto a public Space. It was also
stale: its timestamp predated the poster rebuild that added the real-data panel, so it
was simultaneously a privacy leak and wrong evidence.

Deleting it would have been simpler and worse: the gate results are the reproducible
evidence that the poster meets its own layout and style bars. So this re-runs the gates
now and records the outcome with every path made relative to the repo root, which is the
only form that means anything to someone who cloned it anyway.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "work" / "posterly" / "tools" / "poster_check.py"
POSTER = ROOT / "work" / "poster_build" / "poster.html"
OUT = ROOT / "work" / "poster_build" / "poster_gates.json"

# Gate invocations, verified against each tool's own --help rather than assumed.
# My first version guessed: it passed "style" to poster_check.py (which has no such
# subcommand -- style lives in a SEPARATE style_check.py) and called verify-final without
# --from-html (which it refuses, by design, so the expected canvas size cannot silently
# default to something wrong). Both came back FAIL and neither was the poster's fault.
CHECKER = ROOT / "work" / "posterly" / "tools" / "poster_check.py"
STYLE = ROOT / "work" / "posterly" / "tools" / "style_check.py"
PDF = ROOT / "work" / "poster_build" / "poster.pdf"

GATES = [
    ("preflight", [str(CHECKER), "preflight", str(POSTER)]),
    ("style", [str(STYLE), str(POSTER)]),
    ("measure", [str(CHECKER), "measure", str(POSTER)]),
    ("polish", [str(CHECKER), "polish", str(POSTER)]),
    ("verify-final", [str(CHECKER), "verify-final", str(PDF), "--from-html", str(POSTER)]),
]
# Numbers worth keeping in the report, pulled from each gate's own stdout.
WANTED = re.compile(
    r"(spread\s*=\s*[\d.]+\s*px|warnings\s*:\s*\d+|\d+\s*x\s*\d+\s*pt|"
    r"\[\w[\w-]*\]\s*(PASS|FAIL)|\d+\s+problems?,\s*\d+\s+warnings?)",
    re.I,
)


def relativise(text):
    """Strip anything that identifies this machine, leaving repo-relative paths."""
    t = text.replace("\\\\", "/").replace("\\", "/")
    t = t.replace(str(ROOT).replace("\\", "/"), ".")
    # any surviving absolute path, including the interpreter's
    t = re.sub(r"[A-Za-z]:/[^\s\"',]*/", lambda m: "<path>/", t)
    return t


def main():
    if not CHECKER.is_file() or not POSTER.is_file():
        print("poster or gate tool missing; nothing to regenerate")
        return 1

    report = {"poster": "poster.html", "gates": {}}
    ok = True
    for gate, argv in GATES:
        p = subprocess.run(
            [sys.executable] + argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=ROOT,
        )
        out = (p.stdout or "") + (p.stderr or "")
        metrics = sorted({relativise(m.group(0)).strip() for m in WANTED.finditer(out)})
        report["gates"][gate] = {
            "status": "PASS" if p.returncode == 0 else "FAIL",
            "exit_code": p.returncode,
            "metrics": metrics,
        }
        ok &= p.returncode == 0
        print(f"  {gate:14} {'PASS' if p.returncode == 0 else 'FAIL'}  {metrics}")

    report["all_gates_pass"] = ok
    report["note"] = (
        "Paths are repo-relative by construction. An earlier published version of this "
        "file recorded absolute local paths and leaked the author's username; it was "
        "also stale relative to the poster it described."
    )

    blob = json.dumps(report, indent=2)
    leftover = re.findall(r"[A-Za-z]:[\\/]{1,2}Users[\\/]{1,2}([A-Za-z0-9._-]+)", blob)
    if leftover:
        print(f"REFUSING to write: home-path segments survived {sorted(set(leftover))}")
        return 1

    OUT.write_text(blob + "\n", encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)} ({len(blob)} B), all gates pass: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
