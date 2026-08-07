"""Strip markdown emphasis from table HEADER cells in the generator.

Trackio's renderer does not process markdown inside `<th>`, so `**exact**` and `` `Improv` ``
in a header row reach the reader as literal asterisks and backticks. Nine headers shipped
that way and it looks like a rough draft, which is exactly what it is.

Header cells are already styled (uppercase, bold) by the theme, so the emphasis was
redundant even where it rendered. Body cells are left alone: markdown works there.

A header row is identified structurally, as the line immediately preceding a `| --- |`
separator, rather than by guessing which lines look like headers.
"""

import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "write_content.py"
SEP = re.compile(r"^\s*\|[\s:|-]+\|\s*$")


def clean_header(line):
    """Remove ** and ` from a markdown table header row, keeping structure."""
    cells = line.split("|")
    out = []
    for c in cells:
        c = c.replace("**", "")
        c = c.replace("`", "")
        out.append(c)
    return "|".join(out)


def main():
    # --check reports without writing, so this can run as a publish gate. The whole
    # reason this file exists is that I verified file CONTENTS for hours and never
    # opened the rendered page; the operator found it in a screenshot. A defect the
    # reader can see must be caught by something that runs every time, not by me
    # remembering to look.
    check_only = "--check" in sys.argv
    text = SRC.read_text(encoding="utf-8")
    lines = text.split("\n")
    changed = []
    for i, line in enumerate(lines):
        if i == 0 or not SEP.match(line):
            continue
        header = lines[i - 1]
        if "|" not in header:
            continue
        cleaned = clean_header(header)
        if cleaned != header:
            changed.append((i, header.strip()[:76], cleaned.strip()[:76]))
            lines[i - 1] = cleaned

    if not changed:
        print("no table headers carry markdown emphasis")
        return 0

    if check_only:
        print(f"{len(changed)} header row(s) carry markdown the renderer shows literally:")
        for ln, before, _ in changed:
            print(f"  line {ln}: {before}")
        print("Run tools/fix_table_headers.py (no --check) to strip it.")
        return 1

    for ln, before, after in changed:
        print(f"  line {ln}")
        print(f"    -  {before}")
        print(f"    +  {after}")

    SRC.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"\ncleaned {len(changed)} header row(s)")

    # the generator also builds one header row programmatically, in vr_table()
    residual = [
        m.group(0)
        for m in re.finditer(
            r"^\s*['\"]\|[^\n]*\*\*[^\n]*$", SRC.read_text(encoding="utf-8"), re.M
        )
    ]
    if residual:
        print("\nPROGRAMMATIC header rows still carrying emphasis, fix by hand:")
        for r in residual:
            print("   ", r.strip()[:100])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
