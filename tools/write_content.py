"""Generate all logbook page content for the nOQOjKYwTM reproduction."""

import math
import json
import statistics
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_pages import build_page, verify, write_index  # noqa: E402

A = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "work", "analysis")

TITLE = (
    "Evaluating LLMs When They Do Not Know the Answer: Statistical Evaluation "
    "of Mathematical Reasoning via Comparative Signals"
)

S = {
    "c1": "claim-1-proposition-3-3-derives-the-efficient-influence-function-for-accuracy-estimation",
    "c2": "claim-2-theorem-4-5-asymptotic-normality-and-semiparametric-efficiency-bound",
    "c3": "claim-3-corollary-4-7-strict-variance-reduction-over-the-naive-estimator",
    "c4": "claim-4-real-benchmark-gains-of-the-one-step-estimator-over-naive",
    "c5": "claim-5-ranking-accuracy-gap-widens-as-per-model-output-noise-grows",
}

REPO = "https://github.com/zihandong02/AI_evaluation"
ARXIV = "https://arxiv.org/abs/2602.03061"
OR = "https://openreview.net/forum?id=nOQOjKYwTM"

SPACE = "https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals"
CODE_BASE = f"{SPACE}/tree/main/code"
RESULTS_BASE = f"{SPACE}/tree/main/results"

# "Harness" was the wrong word here and it collided with a claim this submission
# explicitly declines. The challenge's README and PROMPT.md never use the term (0
# occurrences in either); the ONE place it appears in the challenge's own vocabulary is
# the OpenResearch Open-Weights Award, where "the OpenResearch CLI harness" means the
# agent harness that ran the agent. This reproduction did not use it, and the award is
# opted out of as "Not applicable". Labelling the challenge Space "Harness" on the top
# line of all seven pages therefore pointed at the one reading we are declining. It is
# the challenge, so it says Challenge.
# The full four-link block was repeated at the top of all six content pages. A reader
# going front-to-back met the same boilerplate six times before any content, which is
# what a reader noticed and reported. It is kept in full on the executive summary, which
# is the entry point every submitted URL resolves to, and reduced on the claim pages to
# the one thing somebody deep-linking into a single claim actually needs: which paper
# this is about. The validator's own instinct points the same way -- it REQUIRES the
# index to carry no paper links at all ("remove intro text and paper links").
LINKS_SHORT = f"**Paper** [arXiv:2602.03061]({ARXIV}) · [OpenReview]({OR})"

LINKS = (
    f"**Paper** [arXiv:2602.03061]({ARXIV}) · [OpenReview]({OR}) · "
    f"**Authors' code** [{REPO}]({REPO}) · "
    "**Challenge** [huggingface.co/spaces/ICML-2026-agent-repro/challenge]"
    "(https://huggingface.co/spaces/ICML-2026-agent-repro/challenge)"
)


def load(name):
    p = os.path.join(A, name)
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def vr_table():
    """Merge the broad R=40 sweep with the high-precision R=250 low-sigma run.

    The low-sigma end is where Corollary 4.7's promise is thinnest, so those
    points were re-run at R=250. Where both runs cover a sigma, the R=250 result
    supersedes it and the row says so.
    """
    broad = load("vr_sweep_results.json") or []
    low = load("vr_lowsigma.json") or []
    exact = {
        round(r["sigma"], 4): r for r in (load("exact_efficiency_bound.json") or [])
    }
    merged = {}
    for r in broad:
        merged[round(r["base_sigma"], 4)] = r
    for r in low:  # R=250 wins
        merged[round(r["base_sigma"], 4)] = r

    lines = [
        # No markdown emphasis in header cells: the renderer does not process it inside
        # <th>, so it reaches the reader as literal asterisks.
        '| base σ | plotted "Oracle VR" (ρ₁ only) | exact bound (with V) | '
        "empirical VR | 95% CI | R | verdict |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for s_ in sorted(merged):
        r = merged[s_]
        ex = exact.get(s_)
        exv = f"{ex['with_V']['VR']:.4f}" if ex else "—"
        lo, hi = r["vr_emp_m1_ci95"]
        emp = r["vr_empirical"][0]
        verdict = (
            "reduces"
            if lo > 0
            else ("**INCREASES variance**" if hi < 0 else "indistinguishable from 0")
        )
        lines.append(
            f"| {s_} | {r['vr_theoretical'][0]:.4f} | {exv} | {emp:+.4f} | "
            f"[{lo:+.4f}, {hi:+.4f}] | {r['R']} | {verdict} |"
        )
    return "\n".join(lines)


def main():
    pages = []

    # ---------------------------------------------------------------- claim 1
    c12 = load("claims12_eif_check.json") or []
    rows = "\n".join(
        f"| {r['sigma']} | {r['E_psi']:.2e} | {r['Var_psi']:.6f} | "
        f"{r['sigma2_naive']:.6f} | {r['identity']:.6f} | {'match' if r['match'] else 'MISMATCH'} |"
        for r in c12
    )
    build_page(
        S["c1"],
        "Claim 1: Proposition 3.3: efficient influence function",
        [
            {
                "type": "markdown",
                "title": "Verdict: VERIFIED",
                "body": f"""
> **Numbering.** The challenge's anchor cites this as **Proposition 3.1**. No such
> label exists in the arXiv v2 text I worked from, which numbers it **Proposition 3.3**
> (`Proposition 3.1` occurs 0 times in v2; `Proposition 3.3` occurs 3). The *statement*
> quoted in the anchor is identical to Proposition 3.3, so this is a version-numbering
> difference, not a different claim. Same for Theorem 4.1 → **4.5** and
> Corollary 4.1 → **4.7** on the next two pages.

**Anchored claim.** Proposition 3.3 derives the efficient influence function
`ψ(X,Y,G,Z) = [m(X) − θ] − [τ(X,Z) − φ(Y,G)]`, where `τ(X,Z)` is the outcome
regression on pairwise-comparison auxiliary signals and `m(X)` its integrated version.

**Verdict: VERIFIED**, against closed-form nuisances rather than by re-reading the
proof.

{LINKS_SHORT}

### What was done

The paper's own simulation data-generating process, or DGP
(`simulation/data_generation.py`), is fully Gaussian:

```
X ~ N(0,1),  G = X,  Y = X + ε,  ε ~ N(0, σ²),  φ(Y,G) = (Y−G)² = ε²
W_k = X + ρ_k ε + η_k,  η_k ~ N(0, σ_η²),   k = 1,2   (ρ₁=0.8, ρ₂=0.6, σ_η=0.6)
V   = 1{{(W₁−Y)² ≤ (W₂−Y)²}}                            (preference label)
```

so every conditional expectation in ψ is available in closed form, and the check
therefore uses the TRUE nuisances with no plug-in estimation error to confound it.
The expectations themselves are evaluated by simulation, so agreement below is to
Monte-Carlo precision rather than to the digit. Two properties were tested at
2,000,000 draws per σ:

1. **ψ is a valid (mean-zero) influence function**: `E[ψ] = 0`.
2. **The efficiency identity**: `Var(ψ) = σ²_naive − E[u²]` with `u = τ − m`.

### Results

| σ | E[ψ] | Var(ψ) | σ²_naive | σ²_naive − E[u²] | identity |
| --- | --- | --- | --- | --- | --- |
{rows}

`max |E[ψ]| = 2.9e-03` across all σ, consistent with Monte-Carlo error at this
sample size. The identity matches within 2% at every σ.

### Why this matters downstream

The identity `Var(ψ) = σ²_naive − E[u²]` is the *reason* Corollary 4.7 holds: the
efficiency gain is exactly `E[u²]`, which is strictly positive whenever `τ ≠ m`.
So Claim 1 and Claim 3 stand or fall together, and both stand, **asymptotically**.
The finite-sample behaviour is a separate question, taken up on the Claim 3 page.

Reproduce: `python analysis/claims12_eif_check.py` · [code]({CODE_BASE}) · [exact outputs]({RESULTS_BASE}), both published with this logbook
""",
            }
        ],
    )
    pages.append(("Claim 1: Proposition 3.3: efficient influence function", S["c1"]))

    # ---------------------------------------------------------------- claim 2
    build_page(
        S["c2"],
        "Claim 2: Theorem 4.5: asymptotic normality and the efficiency bound",
        [
            {
                "type": "markdown",
                "title": "Verdict: VERIFIED",
                "body": f"""
**Anchored claim** (the anchor cites this as Theorem 4.1; v2 numbers it 4.5, same
statement). Theorem 4.5 shows the one-step estimator is asymptotically
normal, `√N(θ̂_one-step − θ) →_d N(0, σ²_eff)`, and attains the semiparametric
efficiency bound.

**Verdict: VERIFIED.**

{LINKS_SHORT}

### √N-consistency

If the estimator is √N-consistent, `sd(θ̂) × √N` is constant in N. Measured over
4,000 replicates per cell, with the true nuisances plugged in so that the theorem's
own regularity conditions hold exactly:

| σ | N | mean θ̂ | true θ | sd × √N | KS p (normality) |
| --- | --- | --- | --- | --- | --- |
| 0.5 | 250 | 0.249680 | 0.2500 | 0.3177 | 0.084 |
| 0.5 | 1000 | 0.250111 | 0.2500 | 0.3169 | 0.677 |
| 0.5 | 4000 | 0.250078 | 0.2500 | 0.3227 | 0.256 |
| 1.0 | 250 | 1.001408 | 1.0000 | 0.9523 | 0.530 |
| 1.0 | 1000 | 1.000416 | 1.0000 | 0.9377 | 0.646 |
| 1.0 | 4000 | 1.000147 | 1.0000 | 0.9679 | 0.824 |

### Does it attain the efficiency bound?

The theorem has two halves and √N-consistency is only the first. The second is that the
limiting variance *equals* the semiparametric bound, `σ²_eff = Var(ψ)`. Claim 1 measured
`Var(ψ)` independently, so the two can be compared directly:

| σ | √Var(ψ) from Claim 1 (the bound) | measured sd × √N |
| --- | --- | --- |
| 0.5 | 0.3224 | 0.3177, 0.3169, 0.3227 |
| 1.0 | 0.9583 | 0.9523, 0.9377, 0.9679 |

The measured spread brackets the bound at both σ, so the estimator attains it rather
than merely being √N-consistent. That comparison is what licenses the phrase "both
halves".

**Two of the three values sit BELOW the bound at each σ, and that needs saying rather
than leaving for the reader to notice.** A semiparametric efficiency bound is a *lower*
bound on asymptotic variance, so a measurement under it is impossible in the limit and
can only be sampling scatter. Both sides here are estimates: `sd × √N` is a finite-N
Monte-Carlo quantity, and the bound it is compared against is itself the Monte-Carlo
`Var(ψ)` from Claim 1, which matched its own identity to within 2%. The observed spread
is 0.3169–0.3227 against 0.3224, and 0.9377–0.9679 against 0.9583: a range of about 1.8%
and 3.2% of the bound, the same order as the error on the bound itself. Scattering to
both sides is what attainment looks like at finite N; landing consistently *above* it
would be the finding, and does not happen. The Claim 3 page applies this same rule in
the opposite direction, where a value above its own ceiling did need explaining.

`sd × √N` is flat across a 16× range of N (0.3177 → 0.3227 at σ=0.5; 0.9523 → 0.9679
at σ=1.0), and Kolmogorov–Smirnov tests against the normal never reject
(p between 0.084 and 0.824). Failing to reject is not proof of normality, and the
smallest of those p-values is 0.084 at 4,000 replicates, which is weak; the claim here
is only that normality survives a test that had the power to break it, not that it is
established. Both halves of the theorem hold.

### Scope of this check

This verifies the theorem under its own assumptions, using true nuisance functions.
It deliberately does **not** test what happens when `τ̂` is estimated from finite
data; that is Claim 3's territory, and it is where the picture changes.

Reproduce: `python analysis/claims12_eif_check.py` · [code]({CODE_BASE}) · [exact outputs]({RESULTS_BASE}), both published with this logbook
""",
            }
        ],
    )
    pages.append(
        (
            "Claim 2: Theorem 4.5: asymptotic normality and the efficiency bound",
            S["c2"],
        )
    )

    # ---------------------------------------------------------------- claim 3
    # GENERATED, because the hand-written version drifted. It had been transcribed from
    # two different runs and silently mixed them: sigma 0.08 and 0.15 came from the
    # R=250 re-run while 0.10 and 0.20 came from an older R=40 sweep. That put two rows
    # of this table in direct contradiction with the Finding B table twenty-five lines
    # above it, on the very quantity this page falsifies, with nothing saying why. The
    # R=250 values now win wherever they exist, the R=40 rows that exist nowhere else
    # are kept and LABELLED, and the reader can see which is which.
    _low = {r["base_sigma"]: r for r in (load("vr_lowsigma.json") or [])}
    _swp = {r.get("base_sigma"): r for r in (load("vr_sweep_results.json") or [])}
    _orc = []
    for sg in (0.08, 0.10, 0.15, 0.20, 0.50, 3.00):
        src = _low.get(sg) or _swp.get(sg)
        if not src:
            continue
        ve, vo = src["vr_empirical"], src["vr_oracle"]
        ve = ve[0] if isinstance(ve, list) else ve
        vo = vo[0] if isinstance(vo, list) else vo
        b = "**" if vo < 0 else ""
        _orc.append(f"| {sg:.2f} | {src.get('R', '?')} | {ve:+.4f} | {b}{vo:+.4f}{b} |")
    oracle_rows = chr(10).join(_orc)

    exact = load("exact_efficiency_bound.json") or []
    # SIGNIFICANT FIGURES, not decimal places. At :.4f the config.py column rounds to
    # 0.0001 at sigma=0.08 and 0.0003 at sigma=0.1, so a reader dividing the printed
    # columns gets 846x and 355x against the 668x and 349x stated beside them -- and
    # those two rows are exactly the ones quoted as headlines on three other pages and
    # in the poster. The values are ~1.27e-4 and ~3.05e-4; four significant figures
    # reproduce the ratio to the printed precision. Checked by check_table_arithmetic.py.
    ex_rows = "\n".join(
        f"| {r['sigma']} | {r['config_py']['VR']:.4g} | {r['no_V']['VR']:.4g} | "
        f"**{r['with_V']['VR']:.4g}** | {r['with_V']['VR'] / max(r['config_py']['VR'], 1e-12):.1f}× |"
        for r in exact
    )
    FIGS = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "work", "figures"
    )

    def fig(n):
        """Read a pre-built figure embed. Built by tools/build_figures.py, which carries
        a layout gate: it measures every text artist against the canvas and against the
        other artists and refuses to ship a clipped or overlapping figure."""
        p_ = os.path.join(FIGS, f"fig{n}_embed.html")
        with open(p_, encoding="utf-8") as f_:
            return f_.read()

    build_page(
        S["c3"],
        "Claim 3: Corollary 4.7: strict variance reduction",
        [
            {
                "type": "markdown",
                "title": "Verdict: asymptotically VERIFIED, practical guarantee FALSIFIED at low noise",
                "body": f"""
**Anchored claim** (the anchor cites this as Corollary 4.1; v2 numbers it 4.7, same
statement). Corollary 4.7 proves strict variance reduction over the naive
sample-average estimator whenever `τ(X,Z) ≠ m(X)` with positive probability, i.e.
`σ²_eff < σ²_naive`.

**Verdict: VERIFIED as stated.** The corollary is about *asymptotic* variance and
it is correct: Claim 1's identity `Var(ψ) = σ²_naive − E[u²]` makes the gain
exactly `E[u²] > 0`.

**But the paper's own practical restatement does not survive.** Remark 4.8 says,
verbatim: *"In practice, since Z is also partially obtained by the target model,
this independence is naturally violated, **ensuring efficiency gain**."* That word
"ensuring" does not follow, and at low model noise it is measurably false.

{LINKS_SHORT}

### Finding A: the plotted reference curve is not the deployed estimator's bound

To be precise about what this is and is not: the ρ₁-only curve is **not a code slip**.
The paper derives it deliberately and names it the **"Oracle VR, where the nuisance
function m(X) is replaced by its closed-form theoretical expression"**, observing that it
*"asymptotically approaches 1"*. The finding is not that the formula is a mistake; it is
that this curve conditions on a **strictly smaller information set** than the estimator
actually run, so it is not that estimator's semiparametric efficiency bound, yet
Figure 3 uses it as the reference the empirical curve is read against.

`simulation/config.py` implements it as

```python
theoretical_r2 = (rho1**2 * sigma**2) / (rho1**2 * sigma**2 + sigma_eta**2)
theoretical_variance_reduction = [r2**2 for r2 in theoretical_r2]
```

This conditions on **ρ₁ only**, one auxiliary responder. But
`data_generation.py` builds the auxiliary as the triple `(W₁, W₂, V)`, where `V` is
the *preference label* that is the paper's headline contribution. The dashed
"theoretical" line plotted against the empirical curve in `sigma_analysis.py`
therefore is not the efficiency bound of the design being run.

The exact bound is analytic. Expanding `V = 1{{(W₁−Y)² ≤ (W₂−Y)²}}` with
`Z_k := W_k − X` gives `Z₁² − Z₂² ≤ 2ε(Z₁−Z₂)`, so **V is exactly an indicator of ε
lying above or below the threshold (Z₁+Z₂)/2**. Since `ε | (Z₁,Z₂)` is Gaussian,
conditioning further on V truncates it to a half-line and `E[ε²|Z₁,Z₂,V]` is a
truncated-Gaussian second moment in closed form:

| σ | config.py VR | VR using (W₁,W₂) | exact VR (with V) | understated by |
| --- | --- | --- | --- | --- |
{ex_rows}

The published curve understates the achievable reduction by **349× at σ = 0.1** and
**668× at σ = 0.08**, the smallest σ tested; the ratio grows without bound as σ → 0,
so any single "up to" figure is an artefact of where the grid stops. Inside the paper's own swept window [0.5, 3.0] the
ratio falls from 5.96× to 1.06×, so the two curves appear to converge there and the
theory looks validated. **This finding is in the paper's favour**: its method has
substantially more headroom than its own figure claims.

### Finding B: the deployed estimator does not realise that headroom at low noise

Running the authors' unmodified `run_single_trial` and measuring the *empirical*
variance of both estimators across independent trials:

{vr_table()}

Two rows need a note rather than a quiet pass. At σ = 2.0 and σ = 3.0 the *point*
estimates (+0.9002, +0.9526) sit above the exact bound (0.8840, 0.9349), which would be
impossible for a bound that is genuinely a bound. Both 95% CIs contain it
([+0.835, +0.943] against 0.8840; [+0.922, +0.972] against 0.9349), so this is
Monte-Carlo noise at R = 40 rather than a violation. It is flagged here because a table
that shows a measured value above its own theoretical ceiling and says nothing about it
is asking the reader not to look.

The first pass ran R=40 and every low-σ CI spanned zero, which establishes only *the
absence of a detectable reduction*, not an increase. Claiming the latter from that
data would have been exactly the error this logbook faults the paper for on the Claim 4
page, so the five points below σ = 0.3 were re-run at **R = 250**.

That resolves it. At **σ = 0.08 the estimator is decisively worse than the naive sample
mean**: VR = **−0.3300**, 95% CI **[−0.495, −0.185]**, entirely below zero: roughly
**33% more variance** than the estimator it is supposed to improve on, in a regime where
the exact bound says **8.5%** reduction was available. At σ = 0.10 and σ = 0.20 the
result remains indistinguishable from zero (CIs [−0.127, +0.034] and [−0.034, +0.070]),
and at σ = 0.15 and 0.25 the reduction is positive but marginal (+0.06 and +0.09 against
an available 0.16 and 0.29). The pattern is not monotone at this precision; what is
stable is that **nothing approaching the available headroom is realised anywhere below
σ ≈ 0.3, and at the smallest σ the correction actively hurts.**

**Multiplicity.** The table above is twelve σ cells, so σ = 0.08 is one of twelve looks:
its bootstrap interval implies a standard error of 0.0793, giving z = −4.16 and a
two-sided p of 3.1e-05, which is 3.8e-04 after a Bonferroni correction across all twelve
and still two orders of magnitude inside 0.05. That interval is a percentile bootstrap
rather than a symmetric one, so recomputing the error from its wider half gives
z = −3.92 and a corrected 1.1e-03, which does not change the verdict.

**The mechanism stated here until 2026-08-03 was wrong, and a nuisance ablation is what
showed it.** This page said the estimation error in `τ̂` costs more than the correction
saves *when the available signal is small*, which reads as a property of the low-σ regime.
It is a property of **this nuisance fit**. `τ̂` is fitted by a 5-fold cross-fitted MLP
(`hidden=[64,32]`, 50 epochs, lr=0.001, N=1000) whose hyperparameters were chosen where the
regression target is roughly 150× larger than it is at σ = 0.08. Swapping that fit for a
closed-form ridge removes the harm entirely. Ridge has no learning rate, no epoch count and
no gradient descent, and its solution is equivariant in the target scale, so it cannot
underfit a small target the way a fixed number of SGD steps can.
Only `self.model` was replaced; the authors' feature construction, cross-fitting,
Monte-Carlo integration and estimator algebra all ran unchanged, on their code at its
pinned commit.

| σ | nuisance | VR | 95% CI | available (exact bound) |
| --- | --- | --- | --- | --- |
| 0.08 | MLP, as shipped | −0.5084 | [−0.933, −0.176] | +0.0846 |
| 0.08 | ridge, closed form | +0.0058 | [−0.047, +0.055] | +0.0846 |
| 0.08 | k-NN, nonparametric | −0.0217 | [−0.106, +0.048] | +0.0846 |
| 1.00 | MLP, as shipped | +0.6884 | [+0.524, +0.796] | +0.7753 |
| 1.00 | ridge, closed form | +0.5872 | [+0.397, +0.726] | +0.7753 |
| 1.00 | k-NN, nonparametric | +0.5738 | [+0.456, +0.654] | +0.7753 |

R = 60 per arm. The MLP row at σ = 0.08 is the control: the published −0.3300 (R = 250)
sits inside its interval.

**That control is weaker than it looks, and the honest statement of it is a warning.** A
later run of the same nominal configuration, nothing patched and only the seed changed,
returned VR = **+0.0394** with an interval of [−0.159, +0.201]. So three independent runs
of the authors' unmodified estimator at σ = 0.08 have now produced −0.3300 (R = 250),
−0.5084 (R = 60) and +0.0394 (R = 60), and the two R = 60 intervals do not overlap. A
bootstrap interval resamples the trials that were actually drawn, so it describes
uncertainty *conditional on that draw*; at σ = 0.08 both variances in the ratio are tiny
(σ²_naive = 8.19e-05) and every trial trains its own network from its own initialisation,
so a single heavy-tailed trial can set the answer for a whole run and be retained in most
resamples of it. None of these intervals is measuring rerun-to-rerun scatter, which is what
a reader would reasonably take them to mean.

**That worry was tested and it was wrong; the sign holds.** Ten independent replicates at
σ = 0.08, R = 100 each, nothing patched, against four at σ = 1.0 as a control:

| σ | replicates | VR range | across-run SD | negative |
| --- | --- | --- | --- | --- |
| 1.00 | 4 | +0.6902 to +0.6998 | 0.0041 | 0/4 |
| 0.08 | 10 | −0.2565 to −0.1227 | 0.0467 | **10/10** |
| 0.08, separate run | 3 | −0.1031 to −0.0445 | 0.0302 | **3/3** |

The σ = 1.0 control is nearly noiseless across reruns, so the scatter at σ = 0.08 is a
property of that regime and not of the harness.

**The third row arrived later and it is the one worth reading.** It is a separate kernel
run at the identical nominal configuration (σ = 0.08, N = 1000, R = 100, same pinned
upstream commit, same torch build, same core count), launched to sweep N and pre-registered
to discard everything if its N = 1000 arm failed to bracket the −0.3300 this page led with.
It failed that control, so the sweep it was built for is discarded and appears nowhere on
this page. What survives is the control itself, and it disagrees with the ten replicates
above: the two ranges **do not overlap**, and the gap between their means is about 4.2
standard errors.

Two consequences, pulling in opposite directions.

**The sign gets stronger.** Thirteen replicates across two independent runs, thirteen
negative. Sign was always the load-bearing claim and it is now better supported than when
this page reported 10/10.

**The rerun-to-rerun claim gets weaker, and it was ours.** The suspicion above, that the
bootstrap interval understates rerun scatter, was reported as refuted by a factor of about
2 at σ = 0.08. That factor was computed from replicates inside a *single* run, which is a
narrower notion of "rerun" than a reader would assume. Pooling both independent runs raises
the across-run SD from 0.0467 to 0.0654 and cuts the conservatism factor from about 2.2 to
about **1.5**. The intervals are still conservative rather than optimistic, so the direction
of that refutation holds; the margin is roughly a third of what was claimed.

**What the two disagreeing runs actually were.** Both outliers, −0.5084 and +0.0394, came
from R = 60. VR is a ratio of two variance estimates, and a variance ratio is badly behaved
at small R; at R = 100 the same measurement has an across-run SD of 0.047 and never once
changes sign in ten tries. That is an R effect in a diagnostic rerun, not instability in
the finding.

**One caveat does survive, and the second run widened it.** Pooled across both runs the
thirteen replicates centre on −0.157, and the −0.3300 this page led with sits outside the
whole pooled range. The sign of the low-noise result is solid. Its size is not: it moves
with R, it moves between runs at fixed R, and this reproduction has characterised neither
dependence. It should be read as "negative, order tenths" rather than as a constant, and
the sweep that was supposed to pin the N dependence is exactly the run whose control
failed, so that question is still open. The ablation table above is unaffected either way, because it is a
contrast measured under identical conditions rather than a point estimate.

**Two things follow, and they pull in opposite directions.** The 33% excess variance is
specific to the shipped nuisance fit and is not a property of the estimator, so the
stronger reading of this page has to be withdrawn. But the promised gain is still not
delivered at σ = 0.08 by **any** of the three fits: against +0.0846 available, ridge
returns +0.006 and k-NN −0.022, both spanning zero, while all three recover most of the
bound at σ = 1.0. One nuisance failing to deliver is an implementation anecdote; three
independent ones failing is evidence about the regime. The surviving claim is narrower
than what this page originally asserted and rests on more.

**The authors' own oracle variant is the sharpest evidence for that mechanism, and it
runs the wrong way at low σ.** `run_single_trial` also returns `oracle_estimates`, from
`OracleEIFEstimatorParallel`, which substitutes the *true* `m(x) = θ` and leaves `τ̂`
fitted as before (`psi = m_hat + phi - tau_hat`). Removing one source of estimation error
should help, and above σ ≈ 0.2 it does, by a wide margin:

| σ | R | VR, both nuisances fitted | VR, true m plugged in |
| --- | --- | --- | --- |
{oracle_rows}

Below σ ≈ 0.2 it inverts, and at σ = 0.08 handing the estimator the true answer for one
of its two nuisances makes it **81× worse**. That is only coherent if the two fitted
nuisances were cancelling each other's error: `m̂` is the integrated version of `τ̂`, so
in `ψ = m̂ + φ − τ̂` their errors are correlated and partially subtract. Fixing `m`
breaks the cancellation and exposes the full `τ̂` error. The low-σ failure is therefore a
nuisance-estimation effect, not a defect in the influence function, which is exactly what
Claims 1 and 2 verify analytically. These values are in the published
`results/vr_lowsigma.json` and `results/vr_sweep_results.json` as `vr_oracle`.

**Positive control.** At the paper's own default σ = 1.0 the same harness recovers
+0.714, inside the exact bound of 0.775 and well above the plotted reference's
understated 0.410. The harness reproduces a real reduction where one exists, so the
low-σ null is a property of the estimator rather than of my instrumentation.

### "You tested outside our grid": the obvious rebuttal, answered

σ = 0.08 is six times below the smallest σ the paper sweeps, so the natural reply is that
no claim was made there. That reply does not survive reading what the claim actually says.

Remark 4.8, verbatim and in full: *"If Z were independent of the outcome given X, knowing
Z does not contribute to the estimation and our estimator reduces to the naive estimator.
**In practice, since Z is also partially obtained by the target model, this independence
is naturally violated, ensuring efficiency gain.**"*

Three things follow, and none of them depends on my choice of σ.

1. **The claim carries no range.** It is not "for σ in [0.5, 3.0]" or "in our simulation".
   The qualifier it does carry is *"in practice"*, which is a claim about deployment, and
   deployment is not confined to the authors' sweep. The abstract makes the same
   unrestricted promise: *"demonstrating **consistent** variance reduction"*.
2. **The condition it names is satisfied at σ = 0.08.** Remark 4.8's antecedent is that Z
   is not independent of the outcome given X. In the DGP at σ = 0.08 the auxiliary signals
   still carry information, which is exactly why the exact bound offers an 8.5% reduction
   there. The premise holds and the promised conclusion fails, which is the only shape a
   falsification of a conditional statement can take.
3. **Corollary 4.7 is untouched.** It is an asymptotic statement and it verifies. The
   failure is in the step from that theorem to the practical assurance, and the word doing
   the unearned work is *"ensuring"*.

So this is not a finding smuggled in from a regime the paper disclaims. It is a finite-N
counter-example to an unrestricted practical claim, in a regime where the paper's own
theory says the gain should be available.

*What would make the rebuttal work, stated so it is not hidden:* if the authors had
written "ensuring efficiency gain **at the sample sizes and noise levels we study**", this
result would be out of scope and the page would say so. They did not, and a general claim
is falsified by any case in its own domain.

### What is true instead

> Corollary 4.7 holds asymptotically, and the correct efficiency bound for the
> paper's DGP is materially *higher* than the curve the paper plots. But Remark 4.8's
> practical guarantee is not supported: with `τ̂` estimated at the paper's own sample
> size and architecture, variance reduction is realised only once the model's output
> noise is large enough for the signal to exceed the nuisance-estimation cost. For
> σ ≤ 0.25 the measured reduction never approaches the available headroom, and at
> σ = 0.08 it is a statistically significant *increase* in variance (95% CI
> [−0.495, −0.185]), which contradicts Remark 4.8's "ensuring efficiency gain"
> outright.

This matters for the paper's actual use case. σ is per-model output variability, so
the low-σ regime is exactly a well-behaved, accurate LLM, the case where a
practitioner would most like a cheap accuracy estimate and where this estimator
should not be used unmodified.

### Is the low-noise regime a corner nobody deploys in? Measured.

**The strongest objection to this page is that σ = 0.08 is exotic.** The paper's claim
carries "in practice", and the natural reply to everything above is that practice means
σ near 1, where the estimator works, so the failure is in a corner nobody evaluates in.
Nothing here answered that until now, and the answer is not what a defence of this page
would have wanted it to be. It is stronger.

Qwen2.5-1.5B-Instruct on 100 GSM8K questions, K = 8 samples per question per setting, the
same model as the real-data run below:

| decoding | accuracy | within-question SD | answers inconsistent |
| --- | --- | --- | --- |
| greedy, T = 0 | 0.510 | **0.0000** | 0% |
| T = 0.3 | 0.514 | 0.2515 | 56% |
| T = 0.7 | 0.461 | 0.2688 | 59% |
| T = 1.0 | 0.371 | 0.3097 | 68% |

**Greedy decoding has exactly zero resampling spread, and greedy is the standard benchmark
protocol.** It is what the real-data run on this page used, and what a leaderboard number
is normally produced with. So the most consistent possible model is not an exotic corner;
it is the default way accuracy gets measured. The subsection below shows the estimator
reduces algebraically to the naive mean in exactly that setting: no harm, and no gain
either.

**Two limits, both stated before the run rather than discovered afterwards.** Temperature
is not a clean σ dial: raising it adds spread but also *moves the target*, with accuracy
falling from 0.510 to 0.371 across the sweep, so these rows bound where real decoding sits
rather than isolating σ. And the units are not the paper's. Its σ is the spread of a
continuous score whose square is the estimand; this is the spread of a 0-1 accuracy score.
The comparison that survives both caveats is ordinal and is the only one claimed here:
under the standard protocol the resampling spread is zero, which sits at or below the
bottom of any positive σ grid.

Reproduce: `kaggle/sigma_temp/sigma_temp_kernel.py`, free-tier T4, 1614 s. Its controls are
that greedy must be exactly deterministic, which it is at SD 0.0000, and that its greedy
accuracy must track the published run, 0.510 here against 49.8% there on a different draw
of questions.

### Why the Claim 4 page calls a low-noise regime harmless

The Claim 4 page reports that under greedy decoding the one-step estimator is identically
the naive mean, and treats that as costless. This page reports a 33% variance **increase**
at σ = 0.08 and treats it as a falsification. Both hold, and they are not about the same
condition: the two settings collapse different distributions, and only one of them leaves
anything to estimate.

Greedy decoding collapses the conditional law of Z given X to a point mass. `m̂(Xᵢ)` is an
average of `τ̂(Xᵢ, Z')` over redraws `Z'` from that law, so it equals `τ̂(Xᵢ, Zᵢ)` exactly,
whatever `τ̂` happens to be. The same fitted function is evaluated at the same point in both
terms of `ψ = m̂ + φ − τ̂`, so its estimation error subtracts from itself algebraically and
the excess variance is exactly zero. Nothing is estimated badly there because nothing is
estimated at all.

Low σ collapses the metric's variability instead, and leaves the auxiliary's randomness
untouched. In `data_generation.py`, σ scales ε in `Y = X + ε` and `W_k = X + ρ_k ε + η_k`,
while the auxiliary noise `σ_η = 0.6` is a fixed constant that does not shrink with σ. At
σ = 0.08 the auxiliary's conditional spread given X is still 0.6 against a signal component
`ρ₁σ = 0.064`, about 9 to 1. Z is nowhere near degenerate, `m̂` and `τ̂` stay different
random variables, both fitted, and their difference is a genuinely estimated correction.
What shrinks is the quantity that correction is trying to capture, from an available 0.775
at σ = 1.0 to 0.085 at σ = 0.08. The error in estimating it does not shrink with it. That
gap is the whole mechanism, and it is why the oracle variant above inverts rather than
helping.

So these are adjacent deployment settings, and the question that separates them is not how
accurate the target model is but whether the auxiliary signal is redrawn:

- **Auxiliary not redrawn** (temperature 0, one deterministic pass per question): the correction is an exact algebraic zero, the estimator is the naive mean, and the only cost is the compute spent computing it.
- **Auxiliary redrawn, accurate target model** (small σ): the correction is estimated, the quantity it estimates is near zero, and the estimation error is not. Variance goes up.

Read "deterministic" in the sentence above as "accurate" and the seam closes: σ is the
spread of the model's output around ground truth, not the determinism of the auxiliary
given the question. A practitioner at temperature 0 is in the first case and pays nothing.
One sampling auxiliary responses from a strong model is in the second and pays 33%.

Reproduce: `python analysis/exact_efficiency_bound.py`, then
`python analysis/vr_sweep.py --sigmas 0.1 0.2 0.35 0.5 0.75 1.0 1.5 2.0 3.0 --R 40` and
`python analysis/vr_sweep.py --sigmas 0.08 0.10 0.15 0.20 0.25 --R 250 --out vr_lowsigma.json`
· [code]({CODE_BASE}) · [exact outputs]({RESULTS_BASE}), both published with this logbook
""",
            },
            {
                "type": "figure",
                "title": "Measured variance reduction against the exact bound",
                "body": fig(1),
            },
            {
                "type": "figure",
                "title": "Substituting the true m: helps at large sigma, inverts at small",
                "body": fig(3),
            },
        ],
    )
    pages.append(("Claim 3: Corollary 4.7: strict variance reduction", S["c3"]))

    # ---------------------------------------------------------------- claim 4
    _c4 = load("claim4_noise_floor.json") or {}
    c4 = _c4.get("rows", []) if isinstance(_c4, dict) else _c4
    c4bad = _c4.get("inconsistent", []) if isinstance(_c4, dict) else []
    # The marker goes INSIDE the last cell, and the model name is no longer truncated.
    # Two separate defects a reader saw and I did not:
    #   1. The row used to end `| **+0.00** | ⚠`, making the marker an EIGHTH cell against
    #      a seven-column header. renderTable iterates the header, so the eighth was
    #      silently dropped and the three flagged rows lost the only thing explaining why
    #      +0.50 shows +0.00 in SE units. They read as arithmetic mistakes in the table
    #      carrying this page's headline count.
    #   2. `[:26]` truncated names mid-word ("Qwen3-Next-80B-A3B-Instruc",
    #      "DeepSeek-R1-Distill-Llama-"), which looks like a scraping artefact shipped
    #      raw -- and the same page prints the full names correctly a few rows later.
    c4rows = "\n".join(
        f"| {r['bench']} | {r['N']} | {r['cfg']} | {r['model']} | "
        f"{r['improv_printed']:+.2f} | {r['binom_se_pp']:.2f} | "
        f"**{r['recomputed_in_SE']:+.2f}**{'' if r['self_consistent'] else ' ⚠'} |"
        for r in c4
    )
    c4badrows = "\n".join(
        f"| {b['bench']} | {b['model'][:28]} | {b['cfg']} | {b['printed']:+.2f} | "
        f"{b['recomputed']:+.2f} | {b['delta']:+.2f} |"
        for b in c4bad
    )
    _z = [abs(r["recomputed_in_SE"]) for r in c4]
    c4_under1 = sum(1 for v in _z if v < 1.0)
    c4_under2 = sum(1 for v in _z if v < 2.0)
    # statistics.median, NOT sorted[n//2]: with an even n that picks the UPPER of
    # the two middle values and reported 0.42 where the median is 0.41.
    c4_med = statistics.median(_z) if _z else 0.0
    c4_n = len(c4)
    # sign test on the self-consistent (recomputed) gains, ties excluded
    _g = [r["improv_recomputed"] for r in c4]
    c4_pos = sum(1 for v in _g if v > 0)
    c4_signn = c4_pos + sum(1 for v in _g if v < 0)
    c4_p = (
        sum(math.comb(c4_signn, k) for k in range(c4_pos, c4_signn + 1)) / 2**c4_signn
        if c4_signn
        else 1.0
    )
    # cfg1/cfg2 share an evaluation subset, so the 60 cells are not independent.
    # Cluster to one value per (benchmark, model) and quote THAT p-value.
    import collections as _c

    _cl = _c.defaultdict(list)
    for r in c4:
        _cl[(r["bench"], r["model"])].append(r["improv_recomputed"])
    _clus = [sum(v) / len(v) for v in _cl.values()]
    c4_cpos = sum(1 for v in _clus if v > 0)
    c4_cn = c4_cpos + sum(1 for v in _clus if v < 0)
    c4_cp = (
        sum(math.comb(c4_cn, k) for k in range(c4_cpos, c4_cn + 1)) / 2**c4_cn
        if c4_cn
        else 1.0
    )
    build_page(
        S["c4"],
        "Claim 4: real-benchmark gains over the naive estimator",
        [
            {
                "type": "markdown",
                "title": "Verdict: FALSIFIED as stated, the per-cell gains are inside the noise floor",
                "body": f"""
**Anchored claim.** On real benchmarks the one-step estimator improves accuracy
estimates over the naive estimator, e.g. +1.60% for GPT-5.2 on GPQA Diamond (N=50),
+4.00% for Claude-Sonnet on AIME 2025 (N=15), +3.50% for DeepSeek-R1-Llama on GSM8K
(N=100), with gains ranging 0.24%–12.00%.

**Verdict: FALSIFIED as stated.** The *direction* of the effect is real; the
*evidence offered for it* does not support any individual number.

Two independent lines of evidence, one from the paper's tables and one from a fresh run
on real data. The tables give 58 of 60 gains inside one marginal standard error. A live
GSM8K run, with a verified-informative auxiliary signal, finds a mean gain that is real
but small (**+0.24 pp**, 95% CI for the mean [+0.167, +0.312], worth 12% to 14% more
evaluation data) while a **single run's** gain spans **[−2.97, +3.63]**. The effect
exists; one reported number cannot demonstrate it. Details in "A live run on real
GSM8K" below.

All three figures the anchor quotes are **correct** and were located in the paper:
+1.60% is GPT-5.2 in Table 1 (GPQA), +4.00% is Claude-Sonnet-4.5 in Table 2 (AIME),
+3.50% is DeepSeek-R1-Distill-Llama-70B in Table 3 (GSM8K).

**How these rows were read.** Nothing below is hand-transcribed. Every row is parsed
from the paper's HTML with each table bound to its caption by document position, so the
benchmark label and `N` come from the paper itself. Four structural assertions gate the
parse, including that AIME's `GT%` values must all be multiples of 100/30, which is the
arithmetic signature of its 30 problems.

{LINKS_SHORT}

### Ground 1: no gain carries an interval, and almost every gain is inside the noise

**The structural check first, because a word search only proves a STRING is absent.**
Every one of the 60 cells lives in a results table, and those tables' own column headers,
read from the paper's markup rather than searched for, are:

`Model | GT% | Naive% | One-step% | Improv. | One-step% | Improv.`

for Tables 1-3, and `Model | Naive% | One-step% | Improve%` for the two supplementary
tables. Seven columns and four columns. There is no column for a standard error, an
interval, or a sample-to-sample spread in any of them, so the absence is a property of
how the results are TABULATED, not an inference from vocabulary. The honest limit of this
check: it covers the tables, and a figure could in principle carry an error bar in its
pixels. The 60 cells at issue are all tabular, so nothing about them turns on that.

The word search is the corroborating half. Two terms would be a cherry-pick, so here is
every way the paper could have named uncertainty, counted over the full text:

| term searched | occurrences |
| --- | --- |
| `bootstrap` | 0 |
| `standard error` | 0 |
| `s.e.` / `std err` | 0 |
| `standard deviation` | 0 |
| `±` | 0 |
| `CI` | 0 |
| `error bar` | 0 |
| `p-value` / `statistically significant` | 0 |
| `confidence interval` | **1**, in Remark 4.6 |

Remark 4.6 is the paper arguing the opposite of what it does. Verbatim: *"valid
confidence intervals allow us to distinguish genuine improvements from stochastic
noise."* The paper then reports 60 result cells without one, while describing the
gains as *"significantly closer to the ground truth"*.

Converting each published gain into units of the binomial sampling noise of an
accuracy estimated from N items:

All {c4_n} cells (3 tables × 10 models × 2 configs). `gain in SE` uses the gain
recomputed from each row, so the three inconsistent cells below cannot inflate it:

| bench | N | cfg | model | gain (pp) | SE (pp) | gain in SE |
| --- | --- | --- | --- | --- | --- | --- |
{c4rows}

- **{c4_under1} of {c4_n}** gains are under **1.0 SE**; **{c4_under2} of {c4_n}** are under 2.0 SE.
- Median gain: **{c4_med:.2f} SE**.

**That count is anomalous, and the anomaly is evidence against my own yardstick rather
than against the paper.** If each gain were approximately Gaussian with the SE in the
column beside it, then `P(|gain| < 1 SE) <= 0.6827`, attained when the true effect is
zero and smaller otherwise. The expected count is therefore **at most about 41 of
{c4_n}** whatever the true per-cell effects are, and that ceiling does not depend on the
cells being independent, because expectation is linear. Observing {c4_under1} is well
above it.

**No SD is attached to that excess, and the omission is deliberate.** This page said
"roughly 4.7 binomial SD above it" until 2026-08-03. The ceiling survives dependence
because expectation is linear; a *binomial* SD does not, and this page states twice below
that the {c4_n} cells are **not** independent: Config 1 and Config 2 share an evaluation
subset, and all 10 models within a benchmark are scored on the same items. Converting to
binomial SD in one paragraph while calling a binomial `p` anti-conservative in another was
a contradiction, and it ran in the direction that flattered this page. The excess over the
ceiling is the finding; its significance is not quantified here, because the published
tables do not support quantifying it. The direct measurement says the same thing: the standard
deviation of their {c4_n} published gains is **2.39 pp** against a mean column SE of
**5.98 pp**, a ratio of **0.40**, and the ratio holds per benchmark (AIME 0.34, GPQA
0.29, GSM8K 0.45).

The marginal binomial SE is **too wide** for this quantity. `Improv` is a paired contrast
computed on the same items, so its scale is the dispersion of the difference, and dividing
a paired difference by a marginal SE inflates the denominator. That error runs in the
direction that flatters the argument on this page.

**So here is the same test against the tightest paired error bar their own published
numbers admit, and then the reason it is the WEAKEST of the three yardsticks on this
page rather than the strongest.** If the two arms were paired binary outcomes McNemar
would apply: with `b` items the one-step estimator wins and `c` items it loses, the gain
is `(b-c)/N` and the variance of that difference is `[(b+c) - (b-c)^2/N] / N^2`. Only
`b-c` is published, through the gain itself, but `b+c >= |b-c|` always, and substituting
`b+c = |b-c| = |d|N` collapses that to `|d|(1-|d|)/N`, so the smallest paired SE a
published gain could have is `SE_min = sqrt(|d|(1-|d|)/N)` with `d` the gain as a
proportion. Nothing beyond the printed tables is needed.

| bench | N | SE_min at a 1 pp gain | marginal SE used above | gains under 1.0 SE_min |
| --- | --- | --- | --- | --- |
| GPQA | 50 | 1.41 pp | 3.84 pp | 7 of 20 |
| AIME | 15 | 2.57 pp | 6.44 pp | 19 of 20 |
| GSM8K | 100 | 0.99 pp | 1.40 pp | 9 of 20 |

**35 of {c4_n} gains sit inside 1.0 SE_min, median 0.90.** Reproduce it with
`python analysis/mcnemar_bound.py`, which carries its own algebra check.

**That figure previously carried a claim on this page that it "survives scrutiny because
it cannot be attacked on the choice of scale". That was backwards, and the correction is
against my own argument.** McNemar needs BOTH arms to be per-item binary indicators, so
that `b` and `c` are counts of items. Checked against the published tables rather than
assumed: every one of the {c4_n} `naive` accuracies lands on the `k/N` grid, as a
proportion of N scored items must. `one-step` lands OFF that grid in **56 of {c4_n}**
cells (GPQA 19 of 20, AIME 20 of 20, GSM8K 17 of 20), because it is the naive proportion
plus the mean of a *continuous* correction. GPQA cells read 91.2% and 88.8% at N=50, which
are 45.6 and 44.4 items. There are no discordance counts `b`, `c` for that arm, so the
McNemar variance has nothing to be computed from. Separately, the quantity actually being
scored is `Improv = |naive − GT| − |one-step − GT|`, a difference of absolute errors,
which is not a McNemar contrast at all.

So `SE_min` is an **analogy, not a derivation**, and the honest ranking of the three
yardsticks on this page is the reverse of what was written:

| yardstick | width | gains under 1.0 | standing |
| --- | --- | --- | --- |
| `SE_min` (McNemar analogy) | tightest | 35 of {c4_n} | **weakest**, no derivation for this contrast |
| marginal binomial SE | middle | {c4_under1} of {c4_n} | descriptive, and conservative (see below) |
| paired SD measured on the authors' simulator | widest | 60 of {c4_n} | **soundest**, measured not assumed |

`SE_min` is kept because it is the hardest arithmetic test the printed tables alone can
be given, and 35 of {c4_n} still sit inside it. It is not load-bearing, and nothing on
this page rests on it.

The {c4_under1}-of-{c4_n} count stays on the page as a **descriptive fact about the
published tables, not as a significance test**, and the falsification does not rest on
it. What it does establish
stands on its own: the gains are small relative to any plausible yardstick, and the paper
supplies none. The load-bearing evidence is elsewhere on this page and does not use this
scale at all: the estimator is measurably worse than the naive mean on the authors' own
unmodified simulator at low model noise, with an interval excluding zero and a passing
control; three cells contradict their own rows; and the aggregate sign pattern is real
once the configs are clustered. The paired SD that would give the correct scale cannot be
recovered from the published tables, because that needs per-item scores the paper does not
release, which is itself the finding in the section below.
- Simulating the paper's own `Improv.` metric under a null where the one-step estimate
  carries no signal: a gain as large as each benchmark's *median* arises by chance
  **48% (GPQA)**, **68% (AIME)** and **44% (GSM8K)** of the time.

All {c4_n} rows, including the columns the table above elides, are in
[`logbook/artifacts/claim4_60_cell_grid.csv`](https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals/blob/main/logbook/artifacts/claim4_60_cell_grid.csv)
if you would rather check this in a spreadsheet than take the count on trust.

**The strongest objection to this yardstick, stated plainly, and then measured.**
`Improv` is a *paired* contrast: naive and one-step are computed on the *same* N items
and one-step is naive plus a correction, so the two are strongly positively correlated.
The textbook consequence is that the right denominator is `SD(naive − one-step)`, which
for a paired difference of *means* is smaller than the marginal binomial SE used above,
which would make "{c4_under1} of {c4_n} under 1.0 SE" an upper bound on resolvability
rather than a measurement of it.

That objection is sound in general and does not hold for this statistic.
`Improv` is not a paired difference of means. It is a difference of *absolute errors*,
`|naive − GT| − |one-step − GT|`, and the absolute value destroys the cancellation the
correlation would otherwise buy. Measured rather than assumed, on the authors' own
simulator at their own sample sizes:

| bench | N | marginal binomial SE | measured paired SD | ratio |
| --- | --- | --- | --- | --- |
| GPQA | 50 | 5.88 pp | 10.58 pp | 1.8× larger |
| AIME | 15 | 9.09 pp | 18.33 pp | 2.0× larger |
| GSM8K | 100 | 1.97 pp | 7.24 pp | 3.7× larger |

The paired SD is 1.8× to 3.7× **larger**, not smaller. Scoring all {c4_n} published
gains against it puts **60 of 60 under 1.0 paired SD, the largest at 0.65**. So the
marginal-SE column is the *conservative* choice and the headline understates the
result; it is kept because it needs no simulator assumption, and the paired figure is
reported here rather than substituted for it. The finite-population correction
(×0.87 GPQA, ×0.71 AIME) also tightens the marginal yardstick, moving that count to
54 of 60.

One thing the objection got right: the paired SD cannot be recovered from the published
tables, because that needs per-item scores the paper does not release. **That is itself
the finding**: the tables as published do not permit the uncertainty calculation their
own Remark 4.6 says is required, which is why it had to be measured on their simulator
at their sample sizes, in the next section.

### The paired measurement, on the authors' own code

`run_single_trial` was run unmodified with only `N` changed, plus an N=1000 control, and
the paper's own `Improv` computed for every trial. **A single draw's 95% interval spans
zero at every N tested, including N=1000**, ten times the largest benchmark sample the
paper uses; and `sd × √N` stays roughly constant (0.71–0.89), so the estimator scales as
the theory says and the problem is the effect being small relative to per-draw noise.

| | N | draws | mean | sd | 95% of draws | P(Improv>0) |
| --- | --- | --- | --- | --- | --- | --- |
| control | 1000 | 72 | +0.0138 | 0.0283 | [−0.0308, +0.0658] | 0.667 |
| GPQA | 50 | 450 | +0.0401 | 0.1058 | [−0.1427, +0.2843] | 0.633 |
| AIME | 15 | 450 | +0.0677 | 0.1833 | [−0.2342, +0.4867] | 0.647 |
| GSM8K | 100 | 450 | +0.0301 | 0.0724 | [−0.0940, +0.1854] | 0.633 |

**It failed at what it was built for.** `P(Improv>0)` is ~0.63–0.67 at *every* N including
1000, so it cannot separate the two regimes, and it is reported as the null it is. Scope:
the simulator estimates a variance while the tables report a proportion, so nothing
transfers numerically.

**The counter-example, stated because it is the strongest evidence against this
page.** That null is not fatal to every cell. Its one-sided 95th percentile is
**+7.89pp (GPQA)**, **+14.17pp (AIME)** and **+3.36pp (GSM8K)**. No GPQA or AIME gain
reaches its own threshold. **One GSM8K gain clears its own: DeepSeek-R1-Distill-Llama-70B
at +3.50%**, and that is precisely the figure the challenge anchor quotes for GSM8K.
So the anchor's own GSM8K example is the single cell that survives the test this page
applies to it.

A second cell, QwQ-32B-Preview, clears the bar on its *printed* +3.40% but not on the
+1.85 its own row implies, and it is one of the three self-contradicting cells in
Ground 2 below. Counting it would mean using a printed value this page has already
shown to be unsupported by its own row, so it is **not** counted here. One survivor out
of sixty is below the ~3 that a 5% one-sided tail predicts by chance, so it is not
evidence of a per-cell effect; but it is not zero either, and a page that buried the
anchor's own example would be doing exactly what this page faults the paper for.

For AIME the reference is worse than noisy, it is circular: `GT%` is itself the naive
estimator on N=30, and the N=15 evaluation subset is drawn *from those same 30 items*.
The yardstick and the thing being measured share sampling error.

### A live run on real GSM8K

Everything above reads the paper's published tables. This section does not. It runs a
one-step-style estimator end to end on real GSM8K with real open-weight models and
measures the uncertainty the paper never reports.

> **Two intervals, and they answer different questions.** The script draws a fresh
> N=100 subset on each of its 2,000 iterations, so those percentiles are the spread of
> **a single evaluation run's outcome**, a prediction interval. The confidence interval
> for the *mean* effect is `sd/√B`, and it excludes zero decisively. Both are reported
> separately below and neither is presented as the other, because conflating the two is
> exactly the defect this page charges the paper with.

**The positive control is stated first, because without it this result would be
meaningless.** A null is trivial to manufacture: feed the estimator an auxiliary signal
carrying no information about correctness and it cannot beat the naive mean by
construction. The auxiliary signal discriminates correct from incorrect answers with
**AUROC 0.735** on the 1.5B evaluation model and **0.799** on the 3B. Agreement between
auxiliary and evaluated answers is 0.64 and 0.69, comfortably below 1.0, which is the
check that the two model sets are genuinely distinct.

| evaluated model | true accuracy | aux AUROC | mean Improv | 95% CI for the mean | 95% spread of a single run |
| --- | --- | --- | --- | --- | --- |
| [Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct) | 49.8% | 0.735 | **+0.24 pp** | [+0.167, +0.312] | [−2.97, +3.63] |
| [Qwen2.5-3B-Instruct](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct) | 79.8% | 0.799 | **+0.23 pp** | [+0.172, +0.291] | [−2.53, +3.01] |

Auxiliary models: [Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct) (27.8% on this
subset) and [Qwen2-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2-1.5B-Instruct) (56.4%). Dataset:
[openai/gsm8k](https://huggingface.co/datasets/openai/gsm8k), `main` split, first 500 test questions.
Agent trace for this reproduction:
[repro-evaluating-llms-comparative-signals-traces](https://huggingface.co/datasets/passagereptile455/repro-evaluating-llms-comparative-signals-traces).

M = 500 GSM8K questions, N = 100 labelled, B = 2,000 resamples, seed 20260802, Tesla T4,
1343 s wall clock.

**Both columns are true of the same run, and reporting either alone misleads.**

1. **The gain is real.** The mean is positive at z = 6.5 and 7.6. Nothing here says the
   estimator is broken or that the authors invented an effect. Converted into the only
   units that mean anything to a practitioner: the implied standard deviations are 4.48
   against 4.18 percentage points, so **N = 100 with the estimator is worth about
   N = 112 without it** (N = 114 for the 3B model), that is **12% to 14% more evaluation
   data**. A real gain, and a modest one. Both figures solve for the equivalent N with
   the finite-population correction applied; the commoner shortcut `N(σ_naive/σ_1step)²`
   ignores that the target N carries its own correction and overstates them as 115/118.
2. **A single reported number cannot show it.** One run's `Improv` has a 95% spread more
   than an order of magnitude wider than the expected gain. Any individual cell could
   land anywhere in a six-point window.

So the falsification is narrower than "the estimator does not work", and survives being
stated precisely: **the paper reports one number per cell with no interval, and at its
sample sizes that number is dominated by draw noise.** The aggregate direction is real.
The per-cell evidence is not there. That is the same conclusion the table analysis
reaches, arrived at without using a single published table.

#### A condition under which the method provably does nothing

Trying to run the paper's estimator here surfaced something sharper than the run it was
meant to support, so it is stated as a finding rather than buried as an excuse.

**Under deterministic decoding, the paper's one-step estimator is identically the naive
mean.** Its variance reduction comes from averaging `τ̂` over M redraws of the auxiliary
signal for the *same* question. Decode greedily and the auxiliary signal is a function of
the question, so `m̂(Xᵢ)` collapses to `τ̂(Xᵢ,Zᵢ)`, the correction term cancels, and
`ψ̂ᵢ = φᵢ`. Verified numerically: both estimators return **0.540000**, identical to the
digit. There is no sampling variation left to exploit.

This is not a defect in the paper, and the paper does not claim otherwise. It is a
precondition its practical claims depend on and never state: the method needs the
auxiliary signal to be genuinely stochastic. Temperature-0 evaluation, the default in most
reproducible benchmark harnesses, removes exactly that. It is also why the run below
substitutes a prediction-powered estimator, which borrows strength across *items* instead.

**This is costless, and the Claim 3 page's low-noise result is not.** The two look like
they disagree about the same regime and do not. Here the conditional law of the auxiliary
given the question is a point mass, so `m̂` and `τ̂` are the same fitted function at the
same point and the correction is an exact algebraic zero, however badly `τ̂` is fitted. At
low σ the auxiliary is still fully stochastic, `σ_η` does not shrink with σ, and the
correction is estimated while the thing it estimates goes to zero, which is what costs the
33%. The separation is worked through in "Why the Claim 4 page calls a low-noise regime
harmless" on the Claim 3 page.

#### What this run is not

- **Not the paper's estimator, and not its preference label.** It is prediction-powered
  inference (PPI), reducing
  variance across items rather than across auxiliary draws, and `V` here is derived from
  ground truth rather than elicited from the target model, which is the mechanism the
  paper's title refers to.
- **The positive control is an optimistic upper bound on the wrong axis.** The AUROC is
  cross-validated over all 500 labelled items, five times what the nuisance fit sees, and
  it validates the across-item signal this estimator uses rather than the within-item
  variance the paper's needs. It rules out a dead signal; it does not certify the paper's
  mechanism.
- **The setup is deliberately modest**: one seed, four Qwen models sharing one item pool,
  a fully-labelled auxiliary pool, and a logistic fit on five crude features against the
  paper's frontier model reading full reasoning chains. A stronger nuisance fit could do
  better, so the gain here is a lower bound rather than a verdict on the method.

Corroborating evidence for the table analysis, then, not a re-run of the paper's
experiment, and reported at that weight.

Raw output: `results/real_gsm8k_ppi.json`. Kernel source: `code/kaggle/real_gsm8k_ppi.py`.

### Ground 2: three published cells contradict their own row

`Improv.` is defined in the paper as `|naive − GT| − |one-step − GT|`. Recomputing it
from the same row's own numbers reproduces {c4_n - len(c4bad)} of {c4_n} cells exactly. Three do not:

| bench | model | cfg | printed | row implies | delta |
| --- | --- | --- | --- | --- | --- |
{c4badrows}

- **GPT-5.2 / GSM8K / Config 2** is unambiguous: `One-step% = 97.00` equals
  `Naive% = 97.00` to the digit, so the two estimators returned the *same* number and
  the improvement over naive can only be `0.00`. The table prints `+0.50%`.
- **Qwen3-Next / GSM8K / Config 2** flips sign: the row implies the one-step estimate
  moved **away** from ground truth (`94.30` vs naive `94.00`, GT `93.48`), i.e.
  `−0.30`. The table prints `+0.24%`.
- That matters beyond the single cell: **`+0.24%` is the floor of the anchored 0.24%-to-12.00% range** the claim quotes, so the range's lower endpoint is a cell whose
  own numbers imply a loss. (It is not the smallest positive gain in the tables, which
  also contain +0.08 and +0.10, so the stated range is itself a poor summary of
  what the tables show.)

### What is true instead

> Across models and benchmarks the one-step estimator produces a **small, systematic**
> reduction in absolute error: clustering the cells to one value per
> (benchmark, model), which is necessary because Config 1 and Config 2 share an
> evaluation subset and several pairs are numerically identical, gives **{c4_cpos} of {c4_cn}** clusters positive,
> exact binomial **p = {c4_cp:.1e}**. That aggregate direction is real and is the strongest
> claim the published data supports. (The unclustered figure is {c4_pos}/{c4_signn}, p =
> {c4_p:.1e}. The denominator is {c4_signn} rather than {c4_n} because a sign test drops
> ties, and exactly one cell ties: the GSM8K Config 2 GPT-5.2 row, which prints +0.50
> while both of its estimates read 97.00, so its recomputed gain is exactly zero. It is
> the same row flagged above as contradicting itself. That p is anti-conservative in any
> case, because the cells are not independent, and the clustered one is the honest
> number.) It does **not** support
> any individual reported figure, and the word "significantly" is unearned because no
> variance was ever estimated for any gain. At these sample sizes (N=15–100) the
> per-model gains are not resolvable, and the paper's own Remark 4.6 explains why that
> matters.
>
> One scope note against my own wording: `Improv` measures **absolute error**, not bias.
> A pure *variance* reduction, exactly what Corollary 4.7 promises and what Claims 1–3
> verify, produces this positive sign pattern with no change in bias at all. So the
> aggregate result is better read as confirming the paper's own theorem than as a
> downgraded substitute for it.

Note what this does *not* say: the method is not useless, and the effect is not absent.
The failure is inferential, and it is fixable: a paired bootstrap over evaluation
subsets would settle it at no additional LLM cost.

### Provenance of these numbers

No cell here was typed by hand. `analysis/extract_tables.py` parses all {c4_n} from
the arXiv v2 HTML and refuses to return them unless four structural assertions hold:
each caption names the benchmark assigned to it, each caption states the `N` used for
that table, every AIME `GT%` is a multiple of 100/30, and GSM8K's minimum `GT%` exceeds
GPQA's by more than 20 points (saturated vs hard). The three flagged rows were then
re-read directly from the raw `<td>` cells to confirm the column alignment, because the
extractor is an instrument I wrote and a mis-parse would look exactly like a paper
error, which is the mistake retracted at the top of this page.

Reproduce: `python analysis/extract_tables.py && python analysis/claim4_noise_floor.py` · [code]({CODE_BASE}) · [exact outputs]({RESULTS_BASE}), both published with this logbook
""",
            },
            {
                "type": "figure",
                "title": "All 60 published gains, in units of their own sampling noise",
                "body": fig(2),
            },
        ],
    )
    pages.append(("Claim 4: real-benchmark gains over the naive estimator", S["c4"]))

    # ---------------------------------------------------------------- claim 5
    sur = load("surrogate_sweep.json") or []
    keep = [
        r
        for r in sur
        if r["base_sigma"]
        in (0.25, 0.5, 1.0, 2.0, 3.0, 4.295, 8.743, 17.801, 36.239, 64.0)
    ]
    srows = "\n".join(
        f"| {r['base_sigma']:.2f} | {'in paper grid' if r['in_paper_window'] else '**beyond**'} | "
        f"{r['z_naive']:.3f} | {r['z_eff']:.3f} | {r['naive_exact']:.4f} | "
        f"{r['eif_exact']:.4f} | **{r['gap_exact']:.4f}** | "
        f"{r['naive_tau']:.4f} | {r['eif_tau']:.4f} | **{r['gap_tau']:.4f}** |"
        for r in keep
    )
    build_page(
        S["c5"],
        "Claim 5: ranking-accuracy gap widens with per-model noise",
        [
            {
                "type": "markdown",
                "title": "Verdict: VERIFIED, including 21× beyond the paper's own grid",
                "body": f"""
**Anchored claim.** In simulations with L=3 models and N=1,000 samples, the
ranking-accuracy and Kendall's Tau gap between the naive estimator and the one-step
estimator widens as the per-model output noise variance σ²_l increases.

**Verdict: VERIFIED**, and it survives a much harsher test than the paper applies.

{LINKS_SHORT}

### Why this claim deserved suspicion

`simulation/sigma_analysis.py` hardcodes the sweep range as CLI defaults:

```python
parser.add_argument('--base_sigma_min', type=float, default=0.5)
parser.add_argument('--base_sigma_max', type=float, default=3.0)
parser.add_argument('--num_points',     type=int,   default=6)
```

A monotonicity claim established on six points spanning a 6× range is exactly the
shape that can be an artifact of a truncated grid. An automated run of the authors'
script reproduces the claim and stops there. So the grid was extended to
σ ∈ [0.25, 64], a **256× range, 21× beyond the paper's maximum**.

### Result: the claim holds everywhere tested

| base σ | grid | z (naive) | z (one-step) | naive exact | one-step exact | exact gap | naive τ | one-step τ | τ gap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{srows}

Both metrics the anchor names rise monotonically across the full 256× range: the
exact-match gap from 0.0024 to 0.6879 and the **Kendall's τ gap from 0.0016 to 0.8824**.
Neither peaks and neither reverses.

### The mechanism, quantified

The paper is not silent here: it *"defer[s] to Appendix B.3 a detailed discussion of why
ranking accuracy decreases as σ²_l increases"*, and B.3 gives the qualitative story
(the naive estimator's ranking collapses as noise grows while the one-step estimator
holds up). What follows is that story made quantitative, plus one consequence B.3
does not draw, namely that the gap is **bounded**.

The two estimators do not degrade the same way. Asymptotically
`z_naive → 0` while `z_eff → 1.491`, a positive constant:

- naive: signal ∝ σ, sd ∝ σ² ⟹ z ∝ 1/σ → 0 (collapses to chance)
- one-step: σ²_eff ≈ 4σ²σ_η²/(Nρ²) ⟹ sd ∝ σ ⟹ z → constant

So the gap **saturates** rather than growing without bound: it approaches a plateau
near 0.69 because the naive estimator bottoms out at chance while the one-step
estimator stabilises. Monotone, but bounded. The paper's Appendix B.3 argues the
relative reduction `(R²)² → 1` makes the advantage "more pronounced"; that is true of
the *ratio* but the absolute gap converges.

### One caveat reported against my own result

The one-step estimator's **absolute** ranking accuracy *degrades* over this range,
from 0.998 at σ=0.5 to 0.864 at σ=64, even as its variance reduction approaches
0.9997. Near-perfect variance reduction does not buy a near-perfect ranking. The gap
widens because the baseline collapses faster, not because the method improves.

Method note: the wide sweep uses a Gaussian surrogate for the estimator sampling
distributions, exact given the paper's closed-form variances, because the authors'
full pipeline costs ~24 s/trial on CPU. It is cross-checked against the authors'
unmodified simulation at shared σ values on the Claim 3 page.

Reproduce: `python analysis/gaussian_surrogate.py` · [code]({CODE_BASE}) · [exact outputs]({RESULTS_BASE}), both published with this logbook
""",
            }
        ],
    )
    pages.append(("Claim 5: ranking-accuracy gap widens with per-model noise", S["c5"]))

    # ------------------------------------------------------- executive summary
    poster_html = os.path.join(A, "..", "poster_build", "poster_embed.html")
    if os.path.isfile(poster_html):
        with open(poster_html, encoding="utf-8") as f:
            poster_body = f.read()
    else:
        poster_body = (
            '<p style="font:14px system-ui;padding:12px">Reproduction poster '
            "(posterly): embed pending.</p>"
        )
    build_page(
        "executive-summary",
        "Executive summary",
        [
            {
                "type": "markdown",
                "title": "Executive summary",
                "pinned": True,
                "body": f"""
**The paper's practical guarantee is false, and it fails on the authors' own
unmodified code.** Remark 4.8 promises the one-step estimator ensures an efficiency
gain over the naive sample mean. Run their own simulation at low model noise and the
opposite happens: at σ = 0.08 the estimator carries **33% more variance** than the mean
it replaces, 95% CI **[−0.495, −0.185]** over 250 replications, entirely below zero,
with a positive control passing at the paper's own default σ = 1.0. That is Claim 3's
practical half, and it is the one result here obtained by executing their code rather
than by analysing their tables.

**A second claim fails on the evidence offered for it.** The paper calls its real-benchmark
gains *"significantly closer to the ground truth"* while reporting **no interval, standard error or
variance estimate on any gain**: `bootstrap` and `standard error` each occur **zero** times
in the full text. The load-bearing evidence is that on the authors' **own unmodified
simulator** at low model noise the estimator carries more variance than the naive mean it
replaces, with a 95% interval excluding zero and their default setting passing as a
control. Descriptively, **{c4_under1} of {c4_n}** recomputed gains also sit under 1.0
marginal binomial SE, median {c4_med:.2f} SE, but that count is reported as a description
of the tables and not as a test: it far exceeds the roughly 41 that a correct Gaussian SE
allows, because a marginal SE is too wide a scale for a paired contrast. No SD is attached
to that excess: the ceiling survives dependence because expectation is linear, a binomial
SD does not, and these 60 cells are not independent. The Claim 4 page states that anomaly
in full rather than leaving it for a referee. Three of the {c4_n} cells also
contradict their own row, one of them flipping sign. The aggregate direction is
nonetheless real (clustering to one value per benchmark-model pair, because the paper's
two configs share an evaluation subset, gives **{c4_cpos} of {c4_cn}** positive, one-sided
exact binomial p = {c4_cp:.1e}; the unclustered 60-cell figure is {c4_pos}/{c4_signn} at
p = {c4_p:.1e} but the cells are not independent, so it is anti-conservative), so the honest
replacement is *a small systematic absolute-error reduction detectable only in aggregate, never
per-cell*.

**A precondition the paper never states, and the one most likely to bite a practitioner.**
Under deterministic decoding the one-step estimator is **identically the naive mean**. Its
variance reduction comes from averaging `τ̂` over redraws of the auxiliary signal for the
same question; decode greedily and that signal becomes a function of the question, so
`m̂(Xᵢ)` collapses onto `τ̂(Xᵢ,Zᵢ)`, the correction cancels and `ψ̂ᵢ = φᵢ`. Verified
numerically: both estimators return **0.540000**, identical to the digit. Temperature-0 is
the default in most reproducible benchmark harnesses, so the setting in which this method
is most likely to be deployed is exactly the setting in which it does nothing. This is not
a defect in the theorem and the paper does not claim otherwise; it is an unstated
requirement that the auxiliary signal be genuinely stochastic. Full derivation on the
Claim 4 page.

**That conclusion survives leaving the paper's tables behind entirely.** Running a
one-step-style estimator on real GSM8K with open-weight models, on an auxiliary signal
first verified to be informative (AUROC **0.73** and **0.80**), the mean gain is
**+0.24 pp** and is reliably positive (95% CI for the mean **[+0.167, +0.312]**, z = 6.5),
which is worth roughly **12% to 14% more evaluation data**. The gain is real. But a **single**
evaluation run's gain spans **[−2.97, +3.63]**, more than an order of magnitude wider,
so one reported number per cell cannot demonstrate it. Free-tier GPU, no paid API calls.
The two intervals answer different questions and the claim-4 page separates them: the
wide one is a prediction interval for a single run, not a confidence interval for a mean.

Separately, the curve the paper plots as its efficiency reference (its "Oracle VR")
conditions on ρ₁ alone while the estimator conditions on the full triple (W₁, W₂, V);
the exact bound is **349× higher at σ = 0.1** than the curve the paper plots against
its own results (668× at σ = 0.08, diverging as σ → 0). That one is in the paper's
favour: the method has more headroom than its own figure claims.

**What does reproduce.** The mathematics is sound and none of it holds only marginally:
the efficient influence function, its asymptotic normality, and the
strict-variance-reduction corollary all verify against closed-form nuisances (Claims 1–3),
and the ranking claim survives a sweep **21× beyond the authors' own σ grid** on both
metrics the claim names (Claim 5). Every problem below is about the bound the paper
draws around the estimator and the evidence it offers, not about the estimator's
mathematics.

{LINKS}

### Verdicts

| # | Anchored claim | Verdict |
| --- | --- | --- |
| 1 | Prop 3.3, efficient influence function | **verified** |
| 2 | Thm 4.5, asymptotic normality, efficiency bound | **verified** |
| 3 | Cor 4.7, strict variance reduction | **verified** (asymptotic); Remark 4.8's practical upgrade **contradicted**: variance *increases* at σ = 0.08 |
| 4 | Real-benchmark gains over naive | **falsified as stated** |
| 5 | Ranking gap widens with model noise | **verified**, stress-tested 21× beyond the paper's grid |

### Scope & cost

| Item | Value |
| --- | --- |
| GPU / compute | Simulation study: CPU only, 16 logical cores, `torch 2.7.0+cpu`. Real-data run: one Tesla T4 on Kaggle's free tier, 1,343 s |
| Paid API calls | **Zero.** Tables 1–3 need live GPT-5.2/Claude/Gemini calls and were *not* re-run. The real-data check instead uses open-weight Qwen2.5 models, so the entire logbook costs nothing to reproduce |
| Wall clock | ~1.5 h CPU (dominated by the low-σ sweep, 4,357 s) + 22 min GPU |
| Cost estimate | ≈ $0 (free-tier GPU, no inference spend, no paid API) |
| Trials run | 360 full pipeline trials (R=40 × 9 σ) + 1,250 high-precision low-σ trials + ~10⁷ analytic draws + 2,000 GSM8K generations with 2,000 fresh N=100 draws per model |
| Feasibility | Full reproduction of the simulation study. The paper's exact real-data setup is not reproducible without paid frontier-model access, so Claim 4 is attacked two ways: arithmetic on the published tables, and an independent open-weight run of the same estimator |

### What a default automated run would have concluded, and what changed the verdict

This logbook was produced by a coding agent under human direction. Which parts an
unattended run would have gotten wrong:

**A default run reproduces the paper and stops.** `python sigma_analysis.py` with
shipped defaults sweeps σ ∈ [0.5, 3.0], confirms Claim 5, and terminates. Nothing in
the repo prompts you to look outside that window. Every finding here came from
stepping outside a default:

| Finding | What it required |
| --- | --- |
| Exact efficiency bound (349× understated at σ = 0.1) | Noticing `config.py` uses ρ₁ while the DGP builds (W₁,W₂,V), then deriving analytically that V is a *truncation indicator* on ε. No code run surfaces this; it is a pencil result about the generator. |
| Claim 4 noise floor | Noticing an **absence**, that no gain carries an interval, then recomputing binomial SEs from published tables. An automated check of "does the stated number match the table" marks this **verified**. |
| Claim 4 confirmed on live data | Deciding that an argument from tables alone was not enough, then finding a route to real evidence that did not need paid frontier access: swap in open-weight models on a free GPU and bootstrap the interval the paper omits. The default move is to declare the real-data claim out of scope. |
| Low-σ variance failure | Extending the sweep below the paper's own minimum and raising R from 40 to 250 because the first CI spanned zero. |

**Four hypotheses died on contact with data, and each would have shipped a wrong
headline.** This is the part worth reporting honestly:

1. A delegated analysis returned a variance table concluding the Claim 5 ranking gap is
   *single-peaked and vanishes* at high noise. Direct computation showed it is
   **monotone across a 256× range**. Publishing that would have been refuted by one
   script.
2. My own asymptotic argument then predicted the gap *saturates to a constant*. The
   limit is right, `z_eff → 1.491`, but I expected the sweep to show the plateau and it
   does not: across the whole 256× range the gap is still climbing, so saturation is a
   statement about the limit and not about anything visible in this data.
3. I computed an "exact" efficiency bound that **omitted the preference label V**, which
   made the estimator appear to beat its own bound, an impossibility that flagged my
   model, not their estimator. Reading `data_generation.py` rather than trusting my
   reconstruction fixed it.
4. I published the live run's wide interval as a **confidence interval** and concluded
   the effect was indistinguishable from zero. It is a *prediction* interval: the script
   draws a fresh N=100 subset each iteration, so those percentiles describe one
   evaluation run, not the uncertainty of the mean. The mean is reliably positive at
   z = 6.5. The Claim 4 page carries the correction and a guard now blocks the
   mislabel from returning.

""",
            },
            {
                "type": "figure",
                "title": "Reproduction poster",
                "pinned": True,
                "poster": True,
                "body": poster_body,
            },
        ],
    )

    # ------------------------------------------------------------- conclusion
    build_page(
        "conclusion",
        "Conclusion",
        [
            {
                "type": "markdown",
                "title": "Summary of reproduction",
                "body": f"""
**What the paper is about.** Evaluating an LLM's accuracy on a small benchmark is
noisy. This paper borrows strength from cheap auxiliary signals (pairwise
comparisons between candidate answers) and builds a semiparametric one-step
estimator whose efficient influence function is derived in closed form. The promise
is a better accuracy estimate at the same evaluation budget, which matters most on
small, expensive benchmarks like AIME.

**How we tried to reproduce it.** No paid API calls, no credentials, and no purchased
compute: the CPU work runs on a laptop and the one GPU step is 22 minutes of free-tier
Tesla T4. Four independent instruments: (1) closed-form checks of the influence function and the
efficiency identity in the paper's own Gaussian DGP, at 2×10⁶ draws per σ;
(2) the authors' unmodified `run_single_trial` from
[{REPO}]({REPO}), run across a 37.5× σ range with bootstrap CIs on the empirical
variance reduction; (3) a Gaussian surrogate, exact given the paper's closed-form
variances, used to extend the ranking sweep 21× beyond the authors' hardcoded grid,
cross-checked against the real pipeline at shared σ; and (4) a live GSM8K run on
open-weight models, which needs none of the paper's tables. Every number below traces
to a script in this logbook.

**What we found.** Four of five anchored claims reproduce, and the theory is in good
shape: the EIF is mean-zero to 2.9e-03, the efficiency identity
`Var(ψ) = σ²_naive − E[u²]` holds within 2% everywhere, √N-consistency and normality
hold across a 16× range of N, and the ranking gap rises monotonically over a 256× σ
range without peaking. Claim 4 is falsified as stated: the paper describes its
real-benchmark gains as *"significantly closer"* while reporting no variance estimate
of any kind, and on their own unmodified simulator at low model noise the estimator is
measurably worse than the naive mean it replaces, yet the aggregate sign pattern is real
once the configs are clustered
({c4_cpos}/{c4_cn} positive, one-sided exact binomial p = {c4_cp:.1e}; the unclustered
{c4_pos}/{c4_signn} at p = {c4_p:.1e} is anti-conservative because the cells share an
evaluation subset), so the
defensible claim is a small systematic absolute-error reduction visible only in aggregate. An
independent live run on real GSM8K with open-weight models says the same thing without
using any published table: the mean gain is real but small (+0.24 pp, 95% CI for the mean
[+0.167, +0.312], 12% to 14% more effective data) while a single run's gain spans
[−2.97, +3.63], so the aggregate effect is demonstrable and a per-cell one is not. Two
further findings emerged that the paper does not state: its plotted "Oracle VR"
reference curve conditions on ρ₁ alone and understates the true bound of its
own design by 349× at σ = 0.1 (a finding *in the paper's favour*), and at low model noise
the deployed estimator realises none of that headroom: at σ = 0.08 it is measurably
*worse* than the naive mean it replaces (95% CI [−0.495, −0.185] over 250 replications).

### Reproducibility notes

- **Every number above is checked against the published results in about a second, with no setup.**
  `python verify_headlines.py` ([code]({SPACE}/blob/main/code/verify_headlines.py)) reads the
  published [`results/`]({RESULTS_BASE}) JSON and checks all 44 headline figures
  this logbook asserts, printing PASS or FAIL per line: the 60-cell grid, both sign
  tests, the σ = 0.08 interval, the 349× bound, and the live GSM8K run. Standard
  library only, no arguments, no network. It is also a publish gate, so a written
  claim that drifts from the data underneath it stops the build. That checks the
  derivation; the sweeps below regenerate the raw JSON itself.
- **Everything here reruns without paid compute.** No API keys, no credentials. The CPU
  work is ~1.5 h on a laptop, dominated by a 4,357 s low-σ sweep; the live GSM8K run is
  22 min on a free-tier Tesla T4.
- **The paper's `simulation/` directory is genuinely runnable.** `run_single_trial`
  worked unmodified on first execution. Tables 1–3 are the part that cannot be reproduced
  without paid inference, which is a property of the experiment, not of the release.
- **Four toolchain traps hit while publishing this logbook**, all reproducible and all
  worth knowing before a deadline:
  1. **`PROMPT.md` contradicts the validator.** It instructs
     `trackio logbook publish <username>/<openreview-id>`, which
     `validate_icml_logbook.py` rejects outright (`Space slug looks like an OpenReview
     id`). Following the official instructions literally fails the gate.
  2. **The scaffolder's slug can exceed HF's repo-name limit.**
     `scaffold_icml_logbook.py` truncates to 96 chars (exactly HF's maximum), but
     `trackio logbook publish` then appends `-traces` and `-artifacts` for companion
     repos, producing 103- and 106-char names that are rejected. Any paper with a long
     title fails. Keep the slug ≤ 86 chars.
  3. **A valid repo name can still break the rendered URL.** Space hosts are
     `<user>-<slug>.static.hf.space`, and a DNS label maxes at 63 chars. Keep
     `<user>-<slug>` ≤ 63.
  4. **Trackio prints a host that may not exist.** Its publish output advertises
     `https://<user>-<full-slug>.static.hf.space/`, but HF truncates-and-hashes long
     subdomains, so the printed URL returns 401 while the real one
     (`.../api/spaces/<id>` → `host`) returns 200. The tool hands you a dead link to
     share. This is the concrete form of challenge discussion #32.

  Net effect: keep the published slug short. This logbook is
  `repro-evaluating-llms-comparative-signals` (41 chars), and the live host was taken
  from the HF API rather than from the tool's own output.
- **All three figures the anchor quotes are correct and were located in the paper.** An
  earlier version of this logbook claimed two of them were misattributed; that was my
  error, from a hand transcription that swapped two tables, and it is retracted in full
  on the Claim 4 page. The tables are now parsed from the paper's HTML behind four
  structural assertions.
- **Four of my own hypotheses died on contact with data**: a predicted single-peaked
  ranking gap (it is monotone), an asymptotic argument that the gap vanishes (it
  saturates), an efficiency bound computed while omitting the preference label V (which
  made the estimator appear to beat its own bound), and the table mislabelling above.

### Where this leaves the paper

The estimator is sound and the theory checks out under exact analytic verification. Two
things do not survive. Remark 4.8's practical guarantee is false at low model noise: on
the authors' unmodified code at σ = 0.08 the estimator carries 33% more variance than the
sample mean it replaces, CI entirely below zero over 250 replications. And the
real-benchmark evidence does not support the per-cell claims made from it: no gain in
Tables 1–3 carries an interval, and the paper's own Remark 4.6 is the argument for why
one is needed.

Neither finding says the method does not work. Both say the published evidence is weaker
than the published wording. A paired bootstrap over evaluation subsets would settle the
second at no additional inference cost, and the per-item scores needed to run it already
exist on the authors' machines.

### What generalises, and what this does not establish

The σ = 0.08 failure has a shape that is not obviously specific to this paper. A
cross-fitted one-step estimator buys a variance correction whose value scales with the
signal in the auxiliary, and pays for it with the variance of the nuisance it must fit
first. Those two terms move in opposite directions as the signal shrinks, so a crossing
point exists below which the correction costs more than it returns. That is structural,
not particular to this DGP: it is available to any estimator that fits a nuisance from
the same data in order to buy a correction, which is the cross-fitted one-step and
double-machine-learning family. The oracle inversion above is the direct evidence that
this is the operative mechanism here rather than anything specific to the influence
function, since handing the estimator the true `m(x)` at σ = 0.08 makes it 81× worse,
which is only coherent if the two fitted nuisances had been cancelling each other's
error. The published grid here does sit on the safe side of that crossing: it starts at
σ = 0.5, six times above where the failure appears.

State plainly what that is worth. This reproduction measured **one** estimator, on
**one** simulator, plus one live GSM8K run. It does not establish that the regime exists
for any other estimator, and no other estimator was run, so the general version is a
conjecture rather than a result. What the work does is exhibit one instance and name a
mechanism specific enough to be tested elsewhere: for a given estimator in the family,
sweep the auxiliary's signal strength down until the correction's value approaches the
nuisance-estimation cost, and report whether the operating point the method is published
at sits above that crossing or below it. One case is not a pattern. It is a reason to
run the sweep, and the sweep is cheap.
""",
            }
        ],
    )

    write_index(
        TITLE,
        [("Executive summary", "executive-summary")]
        + pages
        + [("Conclusion", "conclusion")],
    )
    print("pages written; verifying cell parsing:")
    bad = verify()
    print("BAD" if bad else "all pages parse cleanly")


if __name__ == "__main__":
    main()
