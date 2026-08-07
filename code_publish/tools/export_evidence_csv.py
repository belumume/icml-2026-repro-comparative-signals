"""Emit the evidence tables as flat CSV, derived from the result JSON.

WHY
---
Two separate reasons, and the second one is the reason this is not decoration.

1. A reviewer who wants to check a verdict should not have to run anything. The
   headline claim is "58 of 60 recomputed gains land inside one binomial standard
   error". That is a statement about a 60-row table, and a 60-row table belongs in a
   spreadsheet, not in a JSON blob a reader has to parse to read.

2. The logbook's Workspace tab was EMPTY -- "0 files, 0 B" to anyone who clicked it.
   Trackio builds that tab by walking the directory that contains `.trackio` (here,
   `logbook/`) for files whose extension is in its model/dataset map. `.json` is not in
   that map and none of the results lived under `logbook/` anyway, so the tab had
   nothing to show. CSV under `logbook/artifacts/` satisfies both the reader and the
   tab, with the same bytes.

The CSVs are DERIVED, never hand-maintained: every value is read from the JSON that the
analysis wrote, and the check below re-reads each emitted file and compares it back
against that JSON cell by cell. A CSV that drifts from its source is worse than no CSV,
because it silently contradicts the page that cites it.

Run from the repo root:  python tools/export_evidence_csv.py [--check]
"""

import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "work" / "analysis"
KAGGLE = ROOT / "kaggle" / "real_data_ppi" / "out" / "real_gsm8k_ppi.json"
OUT = ROOT / "logbook" / "artifacts"


def load(name):
    return json.loads((SRC / name).read_text(encoding="utf-8"))


def flatten_sigma_sweep(rows):
    """vr_sweep rows carry parallel per-sigma lists; emit one row per sigma."""
    per_sigma = [
        "sigma_list",
        "true_theta",
        "vr_theoretical",
        "vr_empirical",
        "vr_oracle",
        "var_naive",
        "var_eif",
        "mse_naive",
        "mse_eif",
    ]
    out = []
    for row in rows:
        n = len(row["sigma_list"])
        for i in range(n):
            item = {"base_sigma": row["base_sigma"], "R": row["R"]}
            for key in per_sigma:
                value = row.get(key)
                if isinstance(value, list) and len(value) == n:
                    item[key.replace("sigma_list", "sigma")] = value[i]
            out.append(item)
    return out


def build():
    """Return {filename: (rows, one-line description)} with every value from JSON."""
    noise = load("claim4_noise_floor.json")
    tables = load("tables_extracted.json")
    extracted = tables["GPQA"] + tables["AIME"] + tables["GSM8K"]
    vr = flatten_sigma_sweep(load("vr_sweep_results.json") + load("vr_lowsigma.json"))

    built = {
        "claim4_60_cell_grid.csv": (
            noise["rows"],
            "Every cell of the paper's three result tables: the printed one-step gain, "
            "the gain recomputed from the paper's own printed numbers, and whether each "
            "falls inside one binomial standard error at that cell's N.",
        ),
        "paper_tables_as_printed.csv": (
            extracted,
            "The paper's Tables 1-3 transcribed verbatim, before any recomputation.",
        ),
        "claim4_at_reported_N.csv": (
            load("claim4_at_reported_N.json"),
            "Distribution of the one-step gain at each benchmark's reported N. The "
            "spread columns describe single runs (a prediction interval), NOT the "
            "uncertainty of the mean.",
        ),
        "surrogate_sweep.csv": (
            load("surrogate_sweep.json"),
            "Variance reduction and both z-statistics across the surrogate-noise sweep, "
            "flagging which rows sit inside the paper's own sigma window.",
        ),
        "variance_reduction_by_sigma.csv": (
            vr,
            "Theoretical, empirical and oracle variance reduction per noise level, "
            "one row per (base_sigma, sigma) pair.",
        ),
        "eif_identity_check.csv": (
            load("claims12_eif_check.json"),
            "Efficient-influence-function identity check behind Claims 1 and 2: "
            "Var(psi) against sigma^2_naive - E[u^2] at each noise level.",
        ),
    }
    if KAGGLE.is_file():
        # The kernel JSON is a nested record (config / env / per-model results), not a
        # table. Dumping it whole produced one CSV row holding Python dict reprs -- a
        # JSON blob under a .csv extension, which is worse than omitting it, because a
        # reviewer opening it in a spreadsheet gets a single unreadable cell. Only the
        # per-model results are tabular, so only those are emitted, with the scalar run
        # parameters repeated per row so each row stands alone.
        real = json.loads(KAGGLE.read_text(encoding="utf-8"))
        cfg = real.get("config", {})
        rows = []
        for m in real.get("models", []):
            lo, hi = m.get("improv_ci95_pp", ["", ""])
            rows.append(
                {
                    "model": m.get("model"),
                    "GT_pct": m.get("GT_pct"),
                    "aux_auroc": m.get("aux_auroc"),
                    "aux_informative": m.get("aux_informative"),
                    "improv_mean_pp": m.get("improv_mean_pp"),
                    "improv_sd_pp": m.get("improv_sd_pp"),
                    "single_run_p2.5_pp": lo,
                    "single_run_p97.5_pp": hi,
                    "frac_improv_positive": m.get("frac_improv_positive"),
                    "M": cfg.get("M"),
                    "N": cfg.get("N"),
                    "B": cfg.get("B"),
                    "seed": cfg.get("seed"),
                    "gpu": real.get("env", {}).get("gpu"),
                }
            )
        if rows:
            built["real_data_gsm8k_ppi.csv"] = (
                rows,
                "The live GSM8K run, one row per evaluated model. The two single_run "
                "columns are the spread of ONE evaluation run, not a CI for the mean.",
            )
    return built


def to_csv(rows):
    """Union of keys, in first-seen order, so a sparse row cannot silently drop one."""
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in fields})
    return buf.getvalue()


def verify(name, text, rows):
    """Re-read the emitted CSV and compare every cell back to the source JSON.

    csv gives back strings, so compare numerically where the source is numeric and
    textually otherwise. A mismatch here means the CSV is lying about the JSON, which
    is the single failure mode that would make publishing these worse than not.
    """
    got = list(csv.DictReader(io.StringIO(text)))
    if len(got) != len(rows):
        return [f"{name}: {len(got)} rows written, {len(rows)} in source"]
    problems = []
    for i, (a, b) in enumerate(zip(got, rows)):
        for key, want in b.items():
            have = a.get(key)
            if isinstance(want, bool):
                ok = have == str(want)
            elif isinstance(want, (int, float)):
                try:
                    ok = have is not None and float(have) == float(want)
                except ValueError:
                    ok = False
            elif want is None:
                ok = have == ""
            else:
                ok = have == str(want)
            if not ok:
                problems.append(f"{name} row {i} {key}: csv={have!r} json={want!r}")
    return problems


def main():
    check_only = "--check" in sys.argv
    built = build()
    OUT.mkdir(parents=True, exist_ok=True)

    problems = []
    stale = []
    index = []
    for name, (rows, description) in sorted(built.items()):
        text = to_csv(rows)
        problems += verify(name, text, rows)
        path = OUT / name
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current != text:
            stale.append(name)
            if not check_only:
                path.write_text(text, encoding="utf-8", newline="")
        index.append((name, len(rows), len(text), description))

    if problems:
        print("CSV DOES NOT MATCH ITS SOURCE JSON:")
        for p in problems[:20]:
            print("   ", p)
        return 1

    if check_only:
        if stale:
            print("evidence CSVs are stale relative to the analysis JSON:")
            for name in stale:
                print("   ", name)
            print("Run tools/export_evidence_csv.py to regenerate.")
            return 1
        print(f"{len(built)} evidence CSVs match the analysis JSON")
        return 0

    readme = ["# Evidence tables\n"]
    readme.append(
        "Flat CSV derived from the result JSON in `work/analysis/`, so a reviewer can "
        "check any verdict in a spreadsheet without running the analysis. Regenerated "
        "by `tools/export_evidence_csv.py`, which re-reads each file and compares every "
        "cell back to its source; the publish gate fails if they drift.\n"
    )
    for name, nrows, nbytes, description in index:
        readme.append(f"- **`{name}`** ({nrows} rows) {description}\n")
    (OUT / "README.md").write_text("\n".join(readme), encoding="utf-8", newline="\n")

    for name, nrows, nbytes, _ in index:
        print(f"  {name:34s} {nrows:4d} rows  {nbytes:7,d} B")
    print(
        f"\n{len(built)} evidence CSVs written to {OUT.relative_to(ROOT).as_posix()}/"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
