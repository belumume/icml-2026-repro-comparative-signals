"""Extract Tables 1-3 of arXiv 2602.03061v2 directly from the HTML.

WHY THIS EXISTS (a correction to my own earlier work):
An earlier version of the Claim 4 analysis used a HAND transcription of these
tables and mislabelled two of them -- what was typed as "GPQA N=50" is actually
AIME (N=15) and what was typed as "AIME N=15" is actually GSM8K (N=100). The
error survived a positive control because that control searched for
"<model name> followed by <values>" ANYWHERE in the text, which succeeds no
matter which table the row came from. The control was structurally blind to the
one defect it needed to catch.

The fix is not a more careful transcription. It is to remove the human step: the
rows are parsed from the HTML and each table is bound to its caption by DOCUMENT
POSITION, so the benchmark label and N are read from the paper rather than
supplied by me.

Binding rule (verified against the source): in this arXiv HTML the caption sits
INSIDE the <figure> AFTER the table body, so a table's caption is the FIRST
"Table N:" string occurring after the table's start offset. Two independent
checks confirm the resulting assignment, both asserted below:
  * AIME has 30 problems, so every GT% in its table must be a multiple of 100/30
  * the N stated in each caption must match the N this script assigns
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "..", "..", "paper", "paper_v2.html")

# Benchmarks we care about, and the N each caption must state.
WANT = {1: ("GPQA", 50), 2: ("AIME", 15), 3: ("GSM8K", 100)}


def _text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def extract(html_path=HTML):
    h = open(html_path, encoding="utf-8", errors="replace").read()

    cap_num = {m.start(): int(m.group(1)) for m in re.finditer(r"Table\s+(\d+)\s*:", h)}
    cap_text = {
        m.start(): _text(h[m.start() : m.start() + 400])
        for m in re.finditer(r"Table\s+\d+\s*:", h)
    }

    tables = {}
    for m in re.finditer(r"<table.*?</table>", h, flags=re.S):
        body = _text(m.group(0))
        if "Improv" not in body or "GT%" not in body:
            continue
        # caption = FIRST "Table N:" strictly after this table's start
        later = [p for p in sorted(cap_num) if p > m.start()]
        if not later:
            continue
        cpos = later[0]
        num = cap_num[cpos]
        if num not in WANT:
            continue
        tables[num] = {
            "caption": cap_text[cpos],
            "body": body,
            "table_at": m.start(),
            "caption_at": cpos,
        }

    out = {}
    for num, (bench, n_expected) in WANT.items():
        if num not in tables:
            raise SystemExit(f"Table {num} ({bench}) not found in HTML")
        t = tables[num]
        cap = t["caption"]

        # --- check 1: caption names the benchmark we expect --------------
        assert bench.replace("GPQA", "GPQA").lower() in cap.lower(), (
            f"Table {num}: caption does not mention {bench}: {cap[:120]}"
        )
        # --- check 2: caption states the N we expect --------------------
        ns = [int(x) for x in re.findall(r"N\s*=\s*(\d+)", cap)]
        assert n_expected in ns, (
            f"Table {num} ({bench}): caption Ns {ns} do not include {n_expected}"
        )

        # --- parse the data rows ----------------------------------------
        # row shape: <model> <GT> <naive> <step1> <+imp1%> <step2> <+imp2%>
        rows = re.findall(
            r"([A-Za-z][\w.\-()]*(?:[ -][\w.\-()]+)*?)\s+"
            r"(\d+\.\d\d)\s+(\d+\.\d\d)\s+(\d+\.\d\d)\s+([+-]?\d+\.\d\d)%\s+"
            r"(\d+\.\d\d)\s+([+-]?\d+\.\d\d)%",
            t["body"],
        )
        parsed = []
        for model, gt, naive, s1, i1, s2, i2 in rows:
            # the first data row can absorb the trailing header token ("Improv.")
            # because the model pattern starts matching inside the header text
            model = re.sub(r"^(?:Improv\.?|One-step%?|Naive%?|GT%?)\s+", "", model.strip())
            assert not model.lower().startswith(("improv", "one-step", "naive", "gt%")), (
                f"model name still carries a header token: {model!r}"
            )
            parsed.append(
                {
                    "bench": bench,
                    "table": num,
                    "N": n_expected,
                    "model": model.strip(),
                    "GT": float(gt),
                    "naive": float(naive),
                    "step1": float(s1),
                    "imp1": float(i1),
                    "step2": float(s2),
                    "imp2": float(i2),
                }
            )
        assert len(parsed) == 10, (
            f"Table {num} ({bench}): parsed {len(parsed)} rows, expected 10"
        )
        out[bench] = parsed

    # --- check 3: AIME GT% must be multiples of 100/30 -------------------
    step = 100.0 / 30.0
    for r in out["AIME"]:
        k = r["GT"] / step
        assert abs(k - round(k)) < 0.02, (
            f"AIME row {r['model']} GT={r['GT']} is not a multiple of 100/30 "
            f"-- table/caption binding is wrong"
        )

    # --- check 4: GSM8K is the saturated benchmark, GPQA is not ---------
    gsm_min = min(r["GT"] for r in out["GSM8K"])
    gpqa_min = min(r["GT"] for r in out["GPQA"])
    assert gsm_min > gpqa_min + 20, (
        f"GSM8K min GT {gsm_min} vs GPQA min GT {gpqa_min}: profile does not match "
        f"a saturated vs hard benchmark -- binding suspect"
    )
    return out


def consistency(rows):
    """Recompute the paper's own Improv. metric and compare with what it printed.

    Improv = |naive - GT| - |one-step - GT|.  This is an internal check on the
    published tables, independent of any claim about the method.
    """
    bad = []
    for r in rows:
        for cfg, step, imp in ((1, r["step1"], r["imp1"]), (2, r["step2"], r["imp2"])):
            recomp = abs(r["naive"] - r["GT"]) - abs(step - r["GT"])
            if abs(recomp - imp) > 0.02:
                bad.append(
                    {
                        "bench": r["bench"],
                        "model": r["model"],
                        "cfg": cfg,
                        "printed": imp,
                        "recomputed": round(recomp, 2),
                        "delta": round(imp - recomp, 2),
                    }
                )
    return bad


if __name__ == "__main__":
    tabs = extract()
    allrows = [r for b in ("GPQA", "AIME", "GSM8K") for r in tabs[b]]
    print("=== table -> caption binding (parsed from HTML, not transcribed) ===")
    for b in ("GPQA", "AIME", "GSM8K"):
        r0 = tabs[b][0]
        print(f"  Table {r0['table']}  {b:<6} N={r0['N']:<4} rows={len(tabs[b])}")
    print(f"\n  total cells: {len(allrows)} models x 2 configs = {len(allrows) * 2}")
    print("  all 4 structural assertions passed (caption benchmark, caption N,")
    print("  AIME multiples of 100/30, saturated-vs-hard GT profile)")

    print("\n=== the three numbers the challenge anchor cites ===")
    anchors = [
        ("GPQA", "GPT-5.2", 1.60),
        ("AIME", "Claude-Sonnet-4.5", 4.00),
        ("GSM8K", "DeepSeek-R1-Distill-Llama-70B", 3.50),
    ]
    for bench, model, val in anchors:
        hit = [r for r in tabs[bench] if r["model"] == model]
        ok = hit and (
            abs(hit[0]["imp1"] - val) < 0.01 or abs(hit[0]["imp2"] - val) < 0.01
        )
        got = f"{hit[0]['imp1']:+.2f}/{hit[0]['imp2']:+.2f}" if hit else "NOT FOUND"
        print(
            f"  {'MATCH ' if ok else 'FAIL  '} {bench:<6} {model:<30} anchor {val:+.2f}  table {got}"
        )

    print("\n=== internal consistency of the paper's own Improv. column ===")
    bad = consistency(allrows)
    print(f"  cells checked: {len(allrows) * 2}   mismatches (>0.02pp): {len(bad)}")
    for b in bad:
        print(
            f"    {b['bench']:<6} {b['model']:<30} cfg{b['cfg']}  "
            f"printed {b['printed']:+.2f}  recomputed {b['recomputed']:+.2f}  "
            f"delta {b['delta']:+.2f}"
        )

    out = os.path.join(HERE, "tables_extracted.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(tabs, f, indent=1)
    print(f"\nwrote {out}")
