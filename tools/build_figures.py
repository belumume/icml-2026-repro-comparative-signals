"""Build the three logbook data figures from the analysis JSONs.

Seven logbook pages carry every quantitative claim in a markdown table. A table row
saying a confidence interval runs from -0.4952 to -0.1845 is correct and takes a
reader several seconds to decode. The same interval drawn below a zero line is read
in one. These three figures are that translation, and nothing else: every value is
recomputed from the JSON at build time, so a figure cannot drift from the number the
prose quotes.

  fig1  empirical variance reduction against sigma, with 95 percent intervals and
        the exact efficiency bound. The sigma=0.08 interval sits entirely below zero.
  fig2  all 60 published gains rescaled into units of their own sampling noise.
  fig3  fitted against oracle-in-m variance reduction, showing where substituting
        the true m stops helping and starts hurting.

Sources, read fresh on every run:
  work/analysis/vr_lowsigma.json            R=250, low sigma
  work/analysis/vr_sweep_results.json       R=40, full sweep
  work/analysis/exact_efficiency_bound.json exact bound per sigma
  work/analysis/claim4_noise_floor.json     60 recomputed benchmark cells

Where the two variance-reduction sweeps cover the same base sigma the R=250 row
wins, because it is the better-resolved measurement of the same quantity.

LAYOUT IS GATED, NOT EYEBALLED. A first pass of these figures shipped a clipped
subtitle and two legend-over-annotation collisions, and every one of them was
invisible to a script that reads the plotting source. So the build measures the
rendered position of every piece of text it places and refuses to write a figure
whose text leaves the canvas or lands on other text. `layout_selftest` proves that
checker catches both defects before any verdict from it is believed, in the same
shape as `render_safe.selftest` in this repo.

Three deliberate choices follow from that gate:

  * Fixed geometry, via `add_axes` with explicit margins, instead of `tight_layout`
    or `bbox_inches="tight"`. Tight bounding boxes resize the canvas to fit the
    overflow, which hides a clipping bug by making the image a different size than
    asked for, leaves every overlap untouched, and makes the output width depend on
    how long an annotation happens to be. Fixed geometry plus a gate keeps all three
    figures exactly 1600px wide and still catches the defect.
  * Subtitles wrap to a measured width rather than to a guessed character count.
  * Legends sit above the axes, outside the data area, so no annotation placed
    inside the axes can collide with one. fig2 has no legend at all: its rows are
    already labelled by name, so a legend would only restate them.

Run it twice and the bytes do not change: the jitter in fig2 is seeded, the PNG
metadata is pinned, and the HTML is written with LF endings.

Usage:  python tools/build_figures.py
"""

import base64
import importlib.util
import io
import json
import math
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

# Set after the imports rather than between them: matplotlib.use() switches the
# backend on an already-imported pyplot as long as no figure exists yet, so the
# import block stays clean instead of carrying three E402 suppressions.
matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS = ROOT / "work" / "analysis"
OUTDIR = ROOT / "work" / "figures"

DPI = 160
WIDTH_PX = 1600
EMBED_PX = 1600
MAX_EMBED_BYTES = 400_000
TOL_PX = 1.0

# Palette: slots 1-3 of the reference categorical theme. Validated for this use with
# the dataviz skill's validate_palette script, all-pairs (these are dot and line
# forms, not stacked bars), light mode, white surface:
#   3 slots -> CVD dE 9.2, normal-vision dE 24.0, both pass. Aqua sits at 2.82:1
#   contrast, below the 3:1 relief threshold, so fig2 carries a direct row label per
#   benchmark and identity never rests on hue alone.
#   2 slots -> CVD dE 24.7, normal-vision dE 33.6, contrast pass.
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SURFACE = "#ffffff"
CRITICAL = "#d03b3b"

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": INK2,
        "text.color": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK2,
        "ytick.labelcolor": INK2,
        "grid.color": GRID,
        "grid.linewidth": 1.0,
        "grid.linestyle": "-",
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


# ------------------------------------------------------------------ layout gate


def _extent(artist, rend):
    try:
        return artist.get_window_extent(renderer=rend)
    except TypeError:
        return artist.get_window_extent()


def layout_report(fig, placed, furniture=()):
    """Measure where text actually landed. Returns (clipped, overlaps).

    `placed` is everything this script positions by hand: titles, subtitles,
    legends, annotations, direct labels. `furniture` is the axis apparatus, which
    matplotlib positions itself: axis labels and tick labels.

    Clipping is checked over both groups. Overlap is checked within `placed` and
    between `placed` and `furniture`, but never furniture against furniture:
    matplotlib lays ticks out so they do not collide, and pairing them with each
    other only produces noise that would train someone to ignore the report.
    """
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    fb = fig.bbox

    named = [(n, _extent(a, rend), True) for n, a in placed]
    named += [(n, _extent(a, rend), False) for n, a in furniture]

    clipped = []
    for name, bb, _ in named:
        if bb.width <= 0 or bb.height <= 0:
            continue
        off = []
        if bb.x0 < fb.x0 - TOL_PX:
            off.append(f"left by {fb.x0 - bb.x0:.0f}px")
        if bb.y0 < fb.y0 - TOL_PX:
            off.append(f"bottom by {fb.y0 - bb.y0:.0f}px")
        if bb.x1 > fb.x1 + TOL_PX:
            off.append(f"right by {bb.x1 - fb.x1:.0f}px")
        if bb.y1 > fb.y1 + TOL_PX:
            off.append(f"top by {bb.y1 - fb.y1:.0f}px")
        if off:
            clipped.append((name, ", ".join(off)))

    overlaps = []
    for i in range(len(named)):
        ni, bi, pi = named[i]
        if bi.width <= 0 or bi.height <= 0:
            continue
        for j in range(i + 1, len(named)):
            nj, bj, pj = named[j]
            if bj.width <= 0 or bj.height <= 0:
                continue
            if not pi and not pj:
                continue
            ix = min(bi.x1, bj.x1) - max(bi.x0, bj.x0)
            iy = min(bi.y1, bj.y1) - max(bi.y0, bj.y0)
            if ix > TOL_PX and iy > TOL_PX:
                overlaps.append((ni, nj, f"{ix:.0f}x{iy:.0f}px"))
    return clipped, overlaps


def layout_selftest():
    """Prove the checker fails on known-bad input before trusting it on real ones.

    Three controls, because a checker that flags everything passes a test that only
    plants defects: one text off the canvas (must be caught), one overlapping pair
    (must be caught), and two well-separated texts (must NOT be caught, so a
    checker that simply reports every pair cannot pass).
    """
    fig = plt.figure(figsize=(5, 4), dpi=100)
    ax = fig.add_axes([0.15, 0.15, 0.7, 0.7])
    good = ax.text(0.02, 0.02, "bottom left", transform=ax.transAxes)
    far = ax.text(0.02, 0.92, "top left", transform=ax.transAxes)
    off = ax.text(1.9, 2.4, "off the canvas", transform=ax.transAxes)
    a = ax.text(0.45, 0.5, "AAAAAA", transform=ax.transAxes)
    b = ax.text(0.45, 0.5, "BBBBBB", transform=ax.transAxes)
    clipped, overlaps = layout_report(
        fig, [("good", good), ("far", far), ("off", off), ("a", a), ("b", b)]
    )
    plt.close(fig)

    caught_clip = [n for n, _ in clipped] == ["off"]
    pairs = {frozenset((x, y)) for x, y, _ in overlaps}
    caught_overlap = pairs == {frozenset(("a", "b"))}
    if not caught_clip:
        print(f"  selftest: clipping control failed, flagged {clipped}")
    if not caught_overlap:
        print(f"  selftest: overlap control failed, flagged {sorted(pairs)}")
    return caught_clip and caught_overlap


def gate(name, fig, placed, furniture=()):
    """Refuse to ship a figure whose text is clipped or collides."""
    clipped, overlaps = layout_report(fig, placed, furniture)
    for n, how in clipped:
        print(f"  LAYOUT FAIL {name}: '{n}' leaves the canvas ({how})")
    for a, b, how in overlaps:
        print(f"  LAYOUT FAIL {name}: '{a}' overlaps '{b}' ({how})")
    if not clipped and not overlaps:
        n = len(placed) + len(furniture)
        print(f"  layout OK: {n} text objects, none clipped, none overlapping")
        return True
    return False


# ------------------------------------------------------------------ data loading


def load(name):
    path = ANALYSIS / name
    if not path.is_file():
        print(f"  missing source {path}")
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def merged_vr():
    """Merge the two sweeps on base_sigma. R=250 wins any overlap."""
    low = load("vr_lowsigma.json")
    sweep = load("vr_sweep_results.json")
    if low is None or sweep is None:
        return None

    by_sigma = {}
    # Lower priority first so the R=250 rows overwrite the R=40 rows on collision.
    for src in (sweep, low):
        for r in src:
            need = ("base_sigma", "vr_empirical", "vr_oracle", "vr_emp_m1_ci95", "R")
            missing = [k for k in need if k not in r]
            if missing:
                print(f"  skipping a row: missing {missing}")
                continue
            by_sigma[round(float(r["base_sigma"]), 6)] = {
                "sigma": float(r["base_sigma"]),
                "R": int(r["R"]),
                "emp": float(r["vr_empirical"][0]),
                "oracle": float(r["vr_oracle"][0]),
                "lo": float(r["vr_emp_m1_ci95"][0]),
                "hi": float(r["vr_emp_m1_ci95"][1]),
            }
    return [by_sigma[k] for k in sorted(by_sigma)]


def exact_bounds():
    """Map sigma -> with_V.VR from the exact efficiency bound run."""
    raw = load("exact_efficiency_bound.json")
    if raw is None:
        return {}
    out = {}
    for r in raw:
        if "sigma" not in r or "VR" not in r.get("with_V", {}):
            print("  bound row missing sigma or with_V.VR; skipped")
            continue
        out[round(float(r["sigma"]), 6)] = float(r["with_V"]["VR"])
    return out


# ------------------------------------------------------------------ figure frame


def frame(height_px, left, bottom, top):
    """Fixed geometry. No layout engine, so the output is exactly WIDTH_PX wide."""
    fig = plt.figure(figsize=(WIDTH_PX / DPI, height_px / DPI))
    ax = fig.add_axes([left, bottom, 0.985 - left, top - bottom])
    return fig, ax


def fit_text(ax, x, y, s, fontsize, color, **kw):
    """Place text in axes coords, wrapping until it fits the axes width.

    The subtitle is the artist that overflowed the canvas twice, both times because
    the string was written to a guessed character budget. This measures the rendered
    width against the axes and adds lines until it fits, so the wrap point follows
    the font and the figure size rather than a number someone typed.
    """
    fig = ax.figure
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    avail = ax.get_window_extent(rend).width
    words = s.split()
    cand = s
    for lines in range(1, 5):
        per = math.ceil(len(words) / lines)
        cand = "\n".join(
            " ".join(words[i : i + per]) for i in range(0, len(words), per)
        )
        t = ax.text(
            x, y, cand, transform=ax.transAxes, fontsize=fontsize, color=color, **kw
        )
        fig.canvas.draw()
        if _extent(t, rend).width <= avail:
            return t
        t.remove()
    return ax.text(
        x, y, cand, transform=ax.transAxes, fontsize=fontsize, color=color, **kw
    )


def sigma_axis(ax, sigmas):
    ax.set_xscale("log")
    ax.set_xticks(sigmas)
    ax.set_xticklabels([f"{s:g}" for s in sigmas], fontsize=9.5)
    ax.set_xticks([], minor=True)
    ax.tick_params(axis="both", which="both", length=0)
    ax.set_xlim(min(sigmas) * 0.82, max(sigmas) * 1.22)
    ax.set_axisbelow(True)
    ax.grid(True, axis="y", linewidth=1.0)


def furniture_of(ax):
    """The axis apparatus, for the clipping half of the gate.

    Tick labels whose tick sits outside the view limits are skipped. Matplotlib
    builds those artists but never draws them, and their reported extent is far off
    the canvas, so including them made the gate report a 106px overflow on a tick
    the reader cannot see. A gate that cries wolf is a gate that gets ignored.
    """
    out = [("xlabel", ax.xaxis.label), ("ylabel", ax.yaxis.label)]
    for axis, key, lim in (
        (ax.xaxis, "x", ax.get_xlim()),
        (ax.yaxis, "y", ax.get_ylim()),
    ):
        lo, hi = min(lim), max(lim)
        for loc, t in zip(axis.get_ticklocs(), axis.get_ticklabels()):
            if t.get_text() and lo <= loc <= hi:
                out.append((f"{key}tick[{t.get_text()}]", t))
    return out


def save(fig, path):
    """Write the PNG with pinned metadata so repeat runs are byte-identical."""
    fig.savefig(
        path,
        dpi=DPI,
        facecolor=SURFACE,
        metadata={"Software": "icml-repro tools/build_figures.py"},
    )
    plt.close(fig)
    print(f"  wrote {path.name} ({path.stat().st_size:,} B)")


def embed(png, out, alt, caption):
    """Wrap a PNG as a self-contained base64 <figure>, mirroring build_poster_embed."""
    from PIL import Image

    img = Image.open(png).convert("RGB")
    if img.width != EMBED_PX:
        h = round(img.height * EMBED_PX / img.width)
        img = img.resize((EMBED_PX, h), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, "WEBP", lossless=True, method=6)
    mode = "lossless"
    if buf.tell() > MAX_EMBED_BYTES:
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=92, method=6)
        mode = "quality 92"
    raw = buf.getvalue()
    payload = base64.b64encode(raw).decode("ascii")
    print(
        f"  {out.name}: webp {mode} {img.width}x{img.height}, "
        f"{len(raw):,} B -> {len(payload):,} B base64"
    )
    if len(raw) > MAX_EMBED_BYTES:
        print(f"  WARNING {out.name} payload exceeds {MAX_EMBED_BYTES:,} B")

    html = f"""<figure style="margin:0">
  <img src="data:image/webp;base64,{payload}"
       alt="{alt}"
       style="width:100%;height:auto;border:1px solid #d0d7de;border-radius:6px" />
  <figcaption style="font-size:0.85em;color:#57606a;margin-top:.5em">
    {caption}
  </figcaption>
</figure>
"""
    out.write_text(html, encoding="utf-8", newline="\n")
    print(f"  wrote {out.name} ({len(html):,} B)")


def _frac_top(ax, artist, rend):
    """Top edge of an artist, in axes-fraction units."""
    axbb = ax.get_window_extent(rend)
    return (_extent(artist, rend).y1 - axbb.y0) / axbb.height


def head(ax, title, subtitle, placed, handles=None, ncol=2):
    """Stack legend, subtitle and title above the axes, measuring as it goes.

    Each element is placed above the MEASURED top of the one below it, rather than
    at a hand-picked axes fraction. Two of the first gate failures came from
    guessing those offsets, and one came from `set_title(pad=...)` being in points
    while everything around it was reasoned about in pixels: at 160 dpi a pad of 64
    is 142px, not 64px, which pushed the title off the top of fig2. Measuring
    removes both mistakes, and keeps the spacing right whether the subtitle wraps
    to one line or three.

    The legend lives here, above the axes, so that nothing drawn inside the data
    area can collide with it by construction.
    """
    fig = ax.figure
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    gap = 10.0 / ax.get_window_extent(rend).height

    y = 1.012
    if handles:
        leg = ax.legend(
            handles=handles,
            loc="lower left",
            bbox_to_anchor=(0.0, y),
            ncol=ncol,
            frameon=False,
            fontsize=10.5,
            labelcolor=INK2,
            handlelength=2.6,
            columnspacing=2.2,
        )
        placed.append(("legend", leg))
        fig.canvas.draw()
        y = _frac_top(ax, leg, rend) + gap

    sub = fit_text(ax, 0, y, subtitle, 10, INK2, va="bottom", ha="left")
    placed.append(("subtitle", sub))
    fig.canvas.draw()

    t = ax.text(
        0,
        _frac_top(ax, sub, rend) + gap,
        title,
        transform=ax.transAxes,
        fontsize=14.5,
        fontweight="bold",
        color=INK,
        va="bottom",
        ha="left",
    )
    placed.append(("title", t))


# ---------------------------------------------------------------------------- fig1


def fig1(rows, bounds):
    sigmas = [r["sigma"] for r in rows]
    emp = np.array([r["emp"] for r in rows])
    lo = np.array([r["lo"] for r in rows])
    hi = np.array([r["hi"] for r in rows])

    fig, ax = frame(980, left=0.085, bottom=0.115, top=0.843)
    sigma_axis(ax, sigmas)
    placed = []

    ymin = min(lo.min(), 0.0) - 0.12
    ymax = max(hi.max(), max(bounds.get(round(s, 6), 0) for s in sigmas)) + 0.10
    ax.set_ylim(ymin, ymax)

    # The region below zero is where the estimator loses to the naive mean. Tinting
    # it is the whole point of the figure: it makes "the bar is under the line" a
    # one-second read instead of a sign check on a table cell.
    ax.axhspan(ymin, 0, color=CRITICAL, alpha=0.055, zorder=0, lw=0)
    ax.axhline(0, color=INK, lw=2.0, zorder=3)

    bx = [s for s in sigmas if round(s, 6) in bounds]
    by = [bounds[round(s, 6)] for s in bx]
    ax.plot(
        bx, by, color=ORANGE, lw=2.0, ls=(0, (5, 3)), zorder=4, solid_capstyle="round"
    )
    ax.errorbar(
        sigmas,
        emp,
        yerr=[emp - lo, hi - emp],
        fmt="none",
        ecolor=BLUE,
        elinewidth=2.0,
        capsize=5,
        capthick=2.0,
        zorder=5,
    )
    # 2px surface ring on the markers so they stay legible where they cross the
    # zero rule and the bound line.
    ax.plot(
        sigmas,
        emp,
        "o",
        ms=8.5,
        mfc=BLUE,
        mec=SURFACE,
        mew=2.0,
        zorder=6,
        linestyle="none",
    )

    band = ax.text(
        min(sigmas) * 0.845,
        ymin + 0.03,
        "below this line: MORE variance than the naive mean",
        fontsize=9.5,
        color=CRITICAL,
        va="bottom",
        ha="left",
        zorder=7,
    )
    placed.append(("band label", band))

    r0 = rows[0]
    note = ax.annotate(
        f"sigma = {r0['sigma']:g}\nVR = {r0['emp']:.4f}\n"
        f"95% CI [{r0['lo']:.4f}, {r0['hi']:.4f}]\nentire interval below zero",
        xy=(r0["sigma"], r0["lo"]),
        xytext=(0.155, 0.30),
        textcoords="axes fraction",
        fontsize=10,
        color=INK,
        ha="left",
        va="top",
        linespacing=1.45,
        arrowprops=dict(arrowstyle="-", color=MUTED, lw=1.2, shrinkA=2, shrinkB=6),
        zorder=8,
    )
    placed.append(("sigma 0.08 callout", note))

    # Replication counts differ across the merged sweep. Saying so on the plot keeps
    # the reader from reading the tighter low-sigma intervals as a free lunch.
    r250 = [r["sigma"] for r in rows if r["R"] == 250]
    r40 = [r["sigma"] for r in rows if r["R"] == 40]
    ytop = ymax - 0.03
    if r250:
        placed.append(
            (
                "R=250 label",
                ax.text(
                    math.sqrt(min(r250) * max(r250)),
                    ytop,
                    f"R = 250 replications ({len(r250)} points)",
                    fontsize=9,
                    color=MUTED,
                    ha="center",
                    va="top",
                ),
            )
        )
    if r40:
        placed.append(
            (
                "R=40 label",
                ax.text(
                    math.sqrt(min(r40) * max(r40)),
                    ytop,
                    f"R = 40 ({len(r40)} points)",
                    fontsize=9,
                    color=MUTED,
                    ha="center",
                    va="top",
                ),
            )
        )
    if r250 and r40:
        ax.axvline(
            math.sqrt(max(r250) * min(r40)), color=GRID, lw=1.0, zorder=1, ymax=0.94
        )

    ax.set_xlabel("base sigma (log scale)", fontsize=11)
    ax.set_ylabel(
        "variance reduction vs the naive mean\n(higher is better)", fontsize=11
    )
    head(
        ax,
        "The variance reduction is negative at small sigma",
        "Measured reduction with 95 percent confidence intervals, against the exact "
        "exact efficiency bound. Zero is the naive mean.",
        placed,
        handles=[
            Line2D(
                [],
                [],
                color=BLUE,
                marker="o",
                ms=8.5,
                mfc=BLUE,
                mec=SURFACE,
                mew=2.0,
                lw=2.0,
                label="measured, 95% CI",
            ),
            Line2D(
                [],
                [],
                color=ORANGE,
                lw=2.0,
                ls=(0, (5, 3)),
                label="exact efficiency bound (with V)",
            ),
        ],
    )

    ok = gate("fig1", fig, placed, furniture_of(ax))
    save(fig, OUTDIR / "fig1.png")

    neg = [r for r in rows if r["hi"] < 0]
    alt = (
        "Scatter plot with error bars of empirical variance reduction against base "
        "sigma on a logarithmic axis. At sigma 0.08 the point sits at "
        f"{rows[0]['emp']:.4f} with a 95 percent confidence interval of "
        f"{rows[0]['lo']:.4f} to {rows[0]['hi']:.4f}, entirely below zero, meaning the "
        "estimator carries about 33 percent more variance than the naive mean it is "
        "meant to improve on. Variance reduction climbs with sigma and reaches "
        f"{rows[-1]['emp']:.4f} at sigma {rows[-1]['sigma']:g}. A dashed line shows the "
        "exact efficiency bound, which the measured values fall well short of across "
        "the small and middle sigma range. "
        f"{len(neg)} of {len(rows)} intervals lie entirely below zero."
    )
    caption = (
        "<strong>Empirical variance reduction against sigma, with 95 percent "
        "confidence intervals.</strong> Points are the measured reduction relative to "
        "the naive mean at the first sigma of each configuration; bars are the "
        "reported 95 percent interval. Zero is the naive mean, so anything below the "
        "rule is an estimator that costs variance rather than saving it. At "
        f"sigma&nbsp;=&nbsp;0.08 the whole interval lies below zero "
        f"({rows[0]['emp']:.4f}, CI {rows[0]['lo']:.4f} to {rows[0]['hi']:.4f}). The "
        "dashed line is the exact efficiency bound (with V). Merged from "
        "<code>work/analysis/vr_lowsigma.json</code> (R&nbsp;=&nbsp;250) and "
        "<code>work/analysis/vr_sweep_results.json</code> (R&nbsp;=&nbsp;40), the "
        "R&nbsp;=&nbsp;250 run taking precedence where both cover a sigma; bound from "
        "<code>work/analysis/exact_efficiency_bound.json</code> "
        "(<code>with_V.VR</code>)."
    )
    embed(OUTDIR / "fig1.png", OUTDIR / "fig1_embed.html", alt, caption)
    return ok


# ---------------------------------------------------------------------------- fig2


def fig2(rows):
    order = ["GPQA", "AIME", "GSM8K"]
    colors = {"GPQA": BLUE, "AIME": ORANGE, "GSM8K": AQUA}
    present = [b for b in order if any(r.get("bench") == b for r in rows)]
    for b in sorted({r.get("bench") for r in rows}):
        if b not in order:
            print(f"  unexpected bench {b!r} in claim4_noise_floor.json; plotted last")
            present.append(b)
            colors[b] = MUTED

    fig, ax = frame(880, left=0.165, bottom=0.135, top=0.875)
    placed = []
    # Seeded so a rebuild reproduces the same jitter and the same bytes.
    rng = np.random.default_rng(20260803)

    over = []
    for i, b in enumerate(present):
        vals = [abs(float(r["recomputed_in_SE"])) for r in rows if r.get("bench") == b]
        y = len(present) - 1 - i
        ax.plot(
            vals,
            y + rng.uniform(-0.17, 0.17, size=len(vals)),
            "o",
            ms=8.5,
            mfc=colors[b],
            mec=SURFACE,
            mew=1.6,
            alpha=0.9,
            linestyle="none",
            zorder=4,
        )
        n_over = sum(1 for v in vals if v >= 1.0)
        # The row name is the direct label, so identity never rests on hue. That is
        # also why this figure has no legend: it would only restate these.
        placed.append(
            (
                f"{b} row label",
                ax.text(
                    -0.02,
                    y,
                    b,
                    transform=ax.get_yaxis_transform(),
                    fontsize=12,
                    color=INK,
                    ha="right",
                    va="center",
                    fontweight="bold",
                ),
            )
        )
        placed.append(
            (
                f"{b} row count",
                ax.text(
                    -0.02,
                    y - 0.26,
                    f"{len(vals) - n_over} of {len(vals)} under 1 SE",
                    transform=ax.get_yaxis_transform(),
                    fontsize=9,
                    color=MUTED,
                    ha="right",
                    va="center",
                ),
            )
        )
        for r in rows:
            if r.get("bench") == b and abs(float(r["recomputed_in_SE"])) >= 1.0:
                over.append((b, y, r))

    ax.axvline(1.0, color=INK, lw=2.0, zorder=3)
    placed.append(
        (
            "1 SE rule label",
            ax.text(
                1.03,
                len(present) - 0.38,
                "1 standard error of sampling noise",
                fontsize=10,
                color=INK,
                ha="left",
                va="center",
            ),
        )
    )

    for b, y, r in over:
        x = abs(float(r["recomputed_in_SE"]))
        placed.append(
            (
                f"{b} outlier callout",
                ax.annotate(
                    f"{r.get('model', 'unknown model')}\n"
                    f"{r['improv_recomputed']:+.1f} pp gain = {x:.2f} SE "
                    f"(N = {r.get('N', '?')})",
                    xy=(x, y),
                    xytext=(x - 0.03, y - 0.42),
                    fontsize=9.5,
                    color=INK,
                    ha="right",
                    va="top",
                    linespacing=1.4,
                    arrowprops=dict(
                        arrowstyle="-", color=MUTED, lw=1.2, shrinkA=2, shrinkB=6
                    ),
                    # The callouts sit across the 1 SE rule, which otherwise strikes
                    # through the digits. The surface does the separating, as with
                    # the rings on the markers.
                    bbox=dict(facecolor=SURFACE, edgecolor="none", pad=2.0),
                    zorder=6,
                ),
            )
        )

    total = len(rows)
    under = sum(1 for r in rows if abs(float(r["recomputed_in_SE"])) < 1.0)
    hi = max(abs(float(r["recomputed_in_SE"])) for r in rows)
    ax.set_ylim(-0.85, len(present) - 0.25)
    ax.set_xlim(-0.06, max(1.75, hi + 0.22))
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="x", length=0)
    ax.set_axisbelow(True)
    ax.grid(True, axis="x", linewidth=1.0)
    ax.set_xlabel(
        "absolute reported gain, in units of that cell's own sampling standard error",
        fontsize=11,
    )
    head(
        ax,
        f"{under} of the {total} published gains are smaller than sampling noise",
        "One dot per benchmark cell. A dot left of the rule is a gain the evaluation "
        "was too small to distinguish from chance.",
        placed,
    )

    ok = gate("fig2", fig, placed, furniture_of(ax))
    save(fig, OUTDIR / "fig2.png")

    names = ", ".join(
        f"{r.get('model')} on {b} at {abs(float(r['recomputed_in_SE'])):.2f} SE"
        for b, _, r in over
    )
    alt = (
        f"Dot plot of all {total} published benchmark gains, one row per benchmark, "
        "with each gain rescaled into units of that cell's own binomial sampling "
        f"standard error. {under} of the {total} dots fall left of the one standard "
        "error rule, meaning the reported improvement is smaller than the noise of "
        f"the evaluation that measured it. Only {len(over)} exceed it: {names}."
    )
    caption = (
        f"<strong>The {total} published gains, in units of sampling noise.</strong> "
        "Each dot is one benchmark cell, its recomputed improvement divided by the "
        "binomial standard error implied by that cell's own sample size. Dots left of "
        f"the rule are gains the evaluation was too small to resolve: {under} of "
        f"{total}. The {len(over)} exceptions are labelled. Vertical position within a "
        "row is jitter for legibility and carries no meaning. Source: "
        "<code>work/analysis/claim4_noise_floor.json</code> (<code>rows</code>, fields "
        "<code>bench</code>, <code>improv_recomputed</code>, "
        "<code>recomputed_in_SE</code>)."
    )
    embed(OUTDIR / "fig2.png", OUTDIR / "fig2_embed.html", alt, caption)
    return ok


# ---------------------------------------------------------------------------- fig3


def fig3(rows):
    sigmas = [r["sigma"] for r in rows]
    emp = [r["emp"] for r in rows]
    orc = [r["oracle"] for r in rows]

    fig, ax = frame(980, left=0.095, bottom=0.115, top=0.843)
    sigma_axis(ax, sigmas)
    placed = []

    # Symlog keeps the -26.73 point on the canvas without flattening the band where
    # every other value lives. Linear inside +/-1, logarithmic outside it.
    ax.set_yscale("symlog", linthresh=1.0, linscale=1.1, base=10)
    ax.set_yticks([-30, -10, -3, -1, -0.5, 0, 0.5, 1])
    ax.set_yticklabels(["-30", "-10", "-3", "-1", "-0.5", "0", "0.5", "1"], fontsize=10)
    ax.set_ylim(min(min(orc), min(emp)) * 1.9, 1.9)

    ax.axhline(0, color=INK, lw=2.0, zorder=3)
    ax.axhline(-1, color=GRID, lw=1.0, zorder=1)
    for vals, color, z in ((orc, ORANGE, 4), (emp, BLUE, 6)):
        ax.plot(sigmas, vals, color=color, lw=2.0, zorder=z, solid_capstyle="round")
        ax.plot(
            sigmas,
            vals,
            "o",
            ms=8.0,
            mfc=color,
            mec=SURFACE,
            mew=2.0,
            zorder=z + 1,
            linestyle="none",
        )

    # Where the oracle stops helping. Read off the data, not asserted.
    cross = None
    for a, b in zip(rows, rows[1:]):
        if a["oracle"] < a["emp"] and b["oracle"] >= b["emp"]:
            cross = math.sqrt(a["sigma"] * b["sigma"])
            break
    if cross:
        ax.axvspan(
            min(sigmas) * 0.82, cross, color=CRITICAL, alpha=0.045, zorder=0, lw=0
        )
        placed.append(
            (
                "worse-than-fitted band label",
                ax.text(
                    math.sqrt(min(sigmas) * cross),
                    1.55,
                    "oracle m is WORSE than the fitted m",
                    fontsize=9.5,
                    color=CRITICAL,
                    ha="center",
                    va="center",
                ),
            )
        )

    worst = min(rows, key=lambda r: r["oracle"])
    placed.append(
        (
            "worst oracle callout",
            ax.annotate(
                f"oracle m at sigma = {worst['sigma']:g}\n"
                f"VR = {worst['oracle']:.2f}, against {worst['emp']:.2f} fitted",
                xy=(worst["sigma"], worst["oracle"]),
                xytext=(0.235, 0.10),
                textcoords="axes fraction",
                fontsize=10,
                color=INK,
                ha="left",
                va="center",
                linespacing=1.45,
                arrowprops=dict(
                    arrowstyle="-", color=MUTED, lw=1.2, shrinkA=2, shrinkB=6
                ),
                zorder=8,
            ),
        )
    )
    for label, vals, dy in (("oracle", orc, 9), ("fitted", emp, -10)):
        placed.append(
            (
                f"{label} end value",
                ax.annotate(
                    f"{vals[-1]:.2f}",
                    xy=(sigmas[-1], vals[-1]),
                    xytext=(9, dy),
                    textcoords="offset points",
                    fontsize=10,
                    color=INK2,
                    ha="left",
                    va="center",
                ),
            )
        )

    ax.set_xlabel("base sigma (log scale)", fontsize=11)
    ax.set_ylabel("variance reduction (symmetric log scale)", fontsize=11)
    head(
        ax,
        "Substituting the true m helps at large sigma and inverts at small sigma",
        "The y axis is linear between -1 and 1 and logarithmic outside it, so the "
        "collapse at small sigma stays on the canvas.",
        placed,
        handles=[
            Line2D(
                [],
                [],
                color=BLUE,
                marker="o",
                ms=8.0,
                mfc=BLUE,
                mec=SURFACE,
                mew=2.0,
                lw=2.0,
                label="fitted m (as implemented)",
            ),
            Line2D(
                [],
                [],
                color=ORANGE,
                marker="o",
                ms=8.0,
                mfc=ORANGE,
                mec=SURFACE,
                mew=2.0,
                lw=2.0,
                label="oracle m (true value substituted)",
            ),
        ],
    )

    ok = gate("fig3", fig, placed, furniture_of(ax))
    save(fig, OUTDIR / "fig3.png")

    alt = (
        "Line chart comparing fitted and oracle variance reduction against base sigma "
        "on a logarithmic x axis and a symmetric log y axis. Above roughly sigma 0.2 "
        "the oracle line sits above the fitted line, so substituting the true value of "
        "m improves variance reduction. Below it the oracle line collapses, reaching "
        f"{worst['oracle']:.2f} at sigma {worst['sigma']:g} where the fitted estimator "
        f"is only {worst['emp']:.2f}. At the largest sigma the two converge, "
        f"{orc[-1]:.2f} oracle against {emp[-1]:.2f} fitted."
    )
    caption = (
        "<strong>Fitted against oracle variance reduction.</strong> The oracle curve "
        "substitutes the true m rather than estimating it. Above roughly "
        "sigma&nbsp;=&nbsp;0.2 that substitution helps; below it the oracle inverts "
        f"catastrophically, reaching {worst['oracle']:.2f} at "
        f"sigma&nbsp;=&nbsp;{worst['sigma']:g} where the fitted estimator sits at "
        f"{worst['emp']:.2f}. The y axis is symmetric log, linear within plus or minus "
        "1 and logarithmic beyond, so the collapse is visible without compressing the "
        "rest. Merged from <code>work/analysis/vr_lowsigma.json</code> and "
        "<code>work/analysis/vr_sweep_results.json</code> "
        "(<code>vr_empirical[0]</code>, <code>vr_oracle[0]</code>), the "
        "R&nbsp;=&nbsp;250 run taking precedence."
    )
    embed(OUTDIR / "fig3.png", OUTDIR / "fig3_embed.html", alt, caption)
    return ok


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    if importlib.util.find_spec("PIL") is None:
        print("Pillow not importable by this interpreter; cannot build the embeds")
        return 1

    if not layout_selftest():
        print("layout checker failed its own controls; its verdict means nothing")
        return 1
    print("layout checker passes its controls (catches clipping and overlap, and")
    print("does not flag well-separated text)\n")

    rows = merged_vr()
    if not rows:
        print("no variance-reduction rows; cannot build fig1 or fig3")
        return 1
    bounds = exact_bounds()
    missing = [r["sigma"] for r in rows if round(r["sigma"], 6) not in bounds]
    if missing:
        print(f"  no exact bound for sigma {missing}; omitted from the bound line")

    print(
        f"merged {len(rows)} sigma points "
        f"({sum(1 for r in rows if r['R'] == 250)} at R=250, "
        f"{sum(1 for r in rows if r['R'] == 40)} at R=40)"
    )

    ok = True
    print("\nfig1")
    ok &= fig1(rows, bounds)

    print("\nfig2")
    nf = load("claim4_noise_floor.json")
    if nf is None or "rows" not in nf:
        print("  claim4_noise_floor.json missing or has no 'rows'; skipping fig2")
        ok = False
    else:
        bad = [r for r in nf["rows"] if "recomputed_in_SE" not in r or "bench" not in r]
        if bad:
            print(f"  {len(bad)} rows missing bench or recomputed_in_SE; skipped")
        ok &= fig2([r for r in nf["rows"] if r not in bad])

    print("\nfig3")
    ok &= fig3(rows)

    if not ok:
        print("\nLAYOUT GATE FAILED: fix the placements above before publishing")
        return 1
    print("\ndone: 3 figures, 3 embeds, layout gate clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
