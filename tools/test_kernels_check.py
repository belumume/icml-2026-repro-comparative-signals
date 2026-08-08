"""Control for the kaggle-listing check: could-not-list must not read as listed-none.

WHY THIS EXISTS
---------------
On 2026-08-08 `check_all_surfaces_synced.py` reported `7 local, 0 on Kaggle` and named
all six live icml-repro kernels as missing. Every one was published, and one was
mid-flight at that moment. The cause was interpreter drift: the gate ran
`sys.executable -m kaggle`, `python` resolved to a virtualenv with no runnable kaggle
module, the subprocess died, and empty stdout became a count of zero.

Nothing errored. The gate printed a confident, specific, entirely wrong finding.

The fix is only worth anything if it can still FAIL, so this drives both branches: a
working interpreter must produce a real count, and a broken one must say it could not
look rather than reporting nothing found. The second case is the whole point; without it
this file would prove only that the check went green today.

    python tools/test_kernels_check.py
"""

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "check_all_surfaces_synced.py"


def load_target():
    """Load the gate by path, so this control does not depend on sys.path shape."""
    spec = importlib.util.spec_from_file_location("_surfaces_gate", TARGET)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {TARGET}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


checks = 0
failures = 0


def expect(label, cond):
    global checks, failures
    checks += 1
    if not cond:
        failures += 1
    print(f"  {'OK  ' if cond else 'FAIL'} {label}")


def main():
    m = load_target()
    real = m._kaggle_interpreters

    # 1. no interpreter can run kaggle -> must say so, must NOT report a zero count
    m._kaggle_interpreters = lambda: ["definitely-not-an-interpreter-xyz"]
    ok, msg = m.kernels_match()
    expect("broken interpreter reports COULD NOT LIST", "COULD NOT LIST" in msg)
    expect("broken interpreter does NOT claim a count", "0 on Kaggle" not in msg)
    expect("broken interpreter fails the check", ok is False)

    # 2. the real path still produces a genuine count, so the fix did not merely
    #    silence the check to make it quiet
    m._kaggle_interpreters = real
    ok, msg = m.kernels_match()
    expect("working interpreter yields a real count", "on Kaggle" in msg)
    expect("working interpreter found kernels", "0 on Kaggle" not in msg)

    # 3. mutation control: without the guard clause, case 1 goes back to reporting a
    #    zero. Assert the guard is present so a future edit that drops it fails here
    #    rather than silently restoring the original defect.
    src = TARGET.read_text(encoding="utf-8")
    guard = 'return False, "COULD NOT LIST kaggle kernels'
    expect("the guard clause is present in the source", guard in src)

    print(f"\n{checks - failures}/{checks} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
