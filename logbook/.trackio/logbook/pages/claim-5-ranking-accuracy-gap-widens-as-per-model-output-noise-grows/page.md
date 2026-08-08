# Claim 5: ranking-accuracy gap widens with per-model noise


---
<!-- trackio-cell
{"type": "markdown", "id": "cell_7da16a09d7d1", "created_at": "2026-08-08T01:32:15+00:00", "title": "Verdict: VERIFIED, including 21\u00d7 beyond the paper's own grid"}
-->

**Anchored claim.** In simulations with L=3 models and N=1,000 samples, the ranking-accuracy and Kendall's Tau gap between the naive estimator and the one-step estimator widens as the per-model output noise variance σ²_l increases.

**Verdict: VERIFIED**, and it survives a much harsher test than the paper applies.

**Paper** [arXiv:2602.03061](https://arxiv.org/abs/2602.03061) · [OpenReview](https://openreview.net/forum?id=nOQOjKYwTM)

### Why this claim deserved suspicion

`simulation/sigma_analysis.py` hardcodes the sweep range as CLI defaults:

```python
parser.add_argument('--base_sigma_min', type=float, default=0.5)
parser.add_argument('--base_sigma_max', type=float, default=3.0)
parser.add_argument('--num_points',     type=int,   default=6)
```

A monotonicity claim established on six points spanning a 6× range is exactly the shape that can be an artifact of a truncated grid. An automated run of the authors' script reproduces the claim and stops there. So the grid was extended to σ ∈ [0.25, 64], a **256× range, 21× beyond the paper's maximum**.

### Result: the claim holds everywhere tested

| base σ | grid | z (naive) | z (one-step) | naive exact | one-step exact | exact gap | naive τ | one-step τ | τ gap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.25 | **beyond** | 5.612 | 5.658 | 1.0000 | 1.0000 | **0.0000** | 1.0000 | 1.0000 | **0.0000** |
| 0.50 | in paper grid | 2.991 | 3.173 | 0.9953 | 0.9978 | **0.0024** | 0.9969 | 0.9985 | **0.0016** |
| 1.00 | in paper grid | 1.540 | 2.031 | 0.8673 | 0.9550 | **0.0877** | 0.9105 | 0.9700 | **0.0594** |
| 2.00 | in paper grid | 0.780 | 1.640 | 0.5707 | 0.8983 | **0.3276** | 0.6649 | 0.9318 | **0.2669** |
| 3.00 | in paper grid | 0.523 | 1.559 | 0.4314 | 0.8811 | **0.4496** | 0.4986 | 0.9200 | **0.4215** |
| 64.00 | **beyond** | 0.025 | 1.491 | 0.1763 | 0.8642 | **0.6879** | 0.0260 | 0.9085 | **0.8824** |

Both metrics the anchor names rise monotonically across the full 256× range: the exact-match gap from 0.0024 to 0.6879 and the **Kendall's τ gap from 0.0016 to 0.8824**. Neither peaks and neither reverses.

### The mechanism, quantified

The paper is not silent here: it "defer[s] to Appendix B.3 a detailed discussion of why ranking accuracy decreases as σ²_l increases", and B.3 gives the qualitative story (the naive estimator's ranking collapses as noise grows while the one-step estimator holds up). What follows is that story made quantitative, plus one consequence B.3 does not draw, namely that the gap is **bounded**.

The two estimators do not degrade the same way. Asymptotically `z_naive → 0` while `z_eff → 1.491`, a positive constant:

- naive: signal ∝ σ, sd ∝ σ² ⟹ z ∝ 1/σ → 0 (collapses to chance)
- one-step: σ²_eff ≈ 4σ²σ_η²/(Nρ²) ⟹ sd ∝ σ ⟹ z → constant

So the gap **saturates** rather than growing without bound: it approaches a plateau near 0.69 because the naive estimator bottoms out at chance while the one-step estimator stabilises. Monotone, but bounded. The paper's Appendix B.3 argues the relative reduction `(R²)² → 1` makes the advantage "more pronounced"; that is true of the **ratio** but the absolute gap converges.

### One caveat reported against my own result

The one-step estimator's **absolute** ranking accuracy **degrades** over this range, from 0.998 at σ=0.5 to 0.864 at σ=64, even as its variance reduction approaches 0.9997. Near-perfect variance reduction does not buy a near-perfect ranking. The gap widens because the baseline collapses faster, not because the method improves.

Method note: the wide sweep uses a Gaussian surrogate for the estimator sampling distributions, exact given the paper's closed-form variances, because the authors' full pipeline costs ~24 s/trial on CPU. It is cross-checked against the authors' unmodified simulation at shared σ values on the Claim 3 page.

Reproduce: `python analysis/gaussian_surrogate.py` · [code](https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals/tree/main/code) · [exact outputs](https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals/tree/main/results), both published with this logbook

