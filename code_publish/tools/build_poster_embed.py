"""Rebuild poster_embed.html from the current render.

The embed is a self-contained figure: the poster as a base64 webp, wrapped in links to
the full-resolution assets, with a figcaption that states the gate results. It is pinned
into the logbook's executive summary, so it is the poster most readers actually see.

Rebuilt by script rather than by hand because it has to stay consistent with three things
that move independently: the rendered PNG, the measured column spread, and the alt text
that carries the poster's claims for anyone who cannot see the image. Hand-editing kept
one of those stale each time.
"""

import base64
import io
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "work" / "poster_build"
PNG = BUILD / "poster_full.png"
OUT = BUILD / "poster_embed.html"
GATES = BUILD / "poster_gates.json"
BASE = (
    "https://huggingface.co/spaces/passagereptile455/"
    "repro-evaluating-llms-comparative-signals/resolve/main"
)
WIDTH = 2400


def alt_text():
    """Build the alt text from the source JSONs rather than hardcoding it.

    This was a hardcoded string carrying six numeric claims plus a description of the
    hero scoreboard. When the scoreboard was reordered to lead with the +33% result, the
    alt went on describing the old layout and never mentioned the new lead at all, so the
    ONLY description a screen-reader user or a text extraction receives was describing a
    poster that no longer existed. Same class as the polish caption below: a claim about
    a measured thing, written by hand, with nothing tying it to the thing.
    """
    A = ROOT / "work" / "analysis"

    def j(name):
        return json.loads((A / name).read_text(encoding="utf-8"))

    grid = j("claim4_noise_floor.json")["rows"]
    under1 = sum(1 for r in grid if abs(r["recomputed_in_SE"]) < 1.0)
    low = next(r for r in j("vr_lowsigma.json") if abs(r["base_sigma"] - 0.08) < 1e-9)
    vr, (lo, hi) = low["vr_empirical"][0], low["vr_emp_m1_ci95"]
    eb = {r["sigma"]: r for r in j("exact_efficiency_bound.json")}
    # TRUNCATE, do not round. The true ratio is 349.5462 and every other artifact prints
    # 349; rounding here emitted 350 and put two derivations of one number in
    # disagreement inside the same submission. Truncation is also the conservative
    # direction for a finding that runs in the paper's favour.
    ratio = int(eb[0.1]["with_V"]["VR"] / eb[0.1]["config_py"]["VR"])
    kag = json.loads(
        (ROOT / "kaggle" / "real_data_ppi" / "out" / "real_gsm8k_ppi.json").read_text(
            encoding="utf-8"
        )
    )
    m0 = kag["models"][0]
    se = m0["improv_sd_pp"] / math.sqrt(kag["config"]["B"])
    slo, shi = m0["improv_ci95_pp"]
    return (
        "Reproduction poster. Headline: at sigma = 0.08 the one-step estimator carries "
        f"{abs(vr) * 100:.0f} percent MORE variance than the naive mean it replaces, 95 "
        f"percent CI {lo:.3f} to {hi:.3f}, on the authors' unmodified code. "
        f"{under1} of {len(grid)} gains recomputed from the paper's own tables sit within "
        "one standard error of binomial sampling noise. The curve the paper plots as its "
        f"efficiency reference understates the estimator's true bound by {ratio:.0f}x at "
        "sigma = 0.1, a finding in the paper's favour. Four of five claims verified, one "
        f"falsified. On live GSM8K the mean gain is +{m0['improv_mean_pp']:.2f} "
        f"percentage points, 95 percent CI of the mean "
        f"+{m0['improv_mean_pp'] - 1.96 * se:.2f} to +{m0['improv_mean_pp'] + 1.96 * se:.2f}, "
        f"while a single evaluation run's gain spans {slo:.2f} to +{shi:.2f}."
    )


def spread():
    """Read the measured column spread from the gate report, never from memory."""
    if not GATES.is_file():
        return None
    m = re.search(r"spread\s*=\s*([\d.]+)\s*px", GATES.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def polish_phrase():
    """Describe the polish gate from the report, because the caption links to it.

    This sentence used to be hardcoded as "passes with no warnings". A reword pushed
    the warning count to 1 and the caption kept asserting 0, one click from the gate
    report that said otherwise -- a false claim in the one place a reader can check in
    a single click. The spread beside it was already derived; this now is too.
    """
    if not GATES.is_file():
        return "was run; see the gate report"
    # Parse the JSON and index the POLISH gate. A plain regex over the whole file
    # matched preflight's "warnings: 0" first and reported no warnings while polish
    # had one -- the same wrong-field read this function exists to prevent, committed
    # inside the fix for it. Read the structure, not the first thing that looks right.
    try:
        gates = json.loads(GATES.read_text(encoding="utf-8"))["gates"]["polish"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return "was run; see the gate report"
    m = None
    for line in gates.get("metrics", []):
        m = re.search(r"warnings\s*:\s*(\d+)", str(line)) or m
    if not m:
        return "was run; see the gate report"
    n = int(m.group(1))
    if n == 0:
        return "passes with no warnings"
    return f"passes with {n} typographic warning" + ("s" if n != 1 else "")


def main():
    if not PNG.is_file():
        print(f"missing {PNG}; render first")
        return 1
    try:
        from PIL import Image
    except ImportError:
        print("Pillow not importable by this interpreter; cannot build the embed")
        return 1

    img = Image.open(PNG)
    h = round(img.height * WIDTH / img.width)
    img = img.convert("RGB").resize((WIDTH, h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=92, method=6)
    payload = base64.b64encode(buf.getvalue()).decode("ascii")
    print(f"  webp {WIDTH}x{h}, {len(buf.getvalue()):,} B -> {len(payload):,} B base64")

    sp = spread()
    if not sp:
        print(
            "could not read the column spread from the gate report; refusing to guess"
        )
        return 1
    print(f"  column spread from gate report: {sp} px")
    polish = polish_phrase()
    print(f"  polish, from gate report: {polish}")

    html = f"""<figure style="margin:0">
  <a href="{BASE}/poster.png" target="_blank" rel="noopener">
    <img src="data:image/webp;base64,{payload}"
         alt="{alt_text()}"
         style="width:100%;height:auto;border:1px solid #d0d7de;border-radius:6px" />
  </a>
  <figcaption style="font-size:0.85em;color:#57606a;margin-top:.5em">
    60&nbsp;&times;&nbsp;36&nbsp;in conference poster, built with the <code>posterly</code> skill.
    Click for full resolution (9000&nbsp;&times;&nbsp;5400&nbsp;px PNG) &middot;
    <a href="{BASE}/poster.pdf">print-ready PDF</a> &middot;
    <a href="{BASE}/poster.html">source</a> &middot;
    <a href="{BASE}/poster_gates.json">gate report</a>.
    Hard gates all pass: <code>preflight</code>, <code>style</code>, <code>measure</code>
    (column alignment spread {sp}&nbsp;px, target &lt;5) and <code>verify-final</code>
    (1 page, 60.00&nbsp;&times;&nbsp;36.00&nbsp;in). <code>polish</code> is advisory and
    {polish}. The <code>asset</code> gate did not run: this poster embeds no
    external figures, so a green result covers the gates that ran, not that one.
    The QR was generated offline and decoded back to the OpenReview URL with two independent
    decoders (pyzbar and OpenCV) from the rendered poster.
  </figcaption>
</figure>
"""
    OUT.write_text(html, encoding="utf-8", newline="\n")
    print(f"  wrote {OUT.name} ({len(html):,} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
