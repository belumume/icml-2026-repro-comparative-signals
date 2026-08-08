# Claim 2: Theorem 4.5: asymptotic normality and the efficiency bound


---
<!-- trackio-cell
{"type": "markdown", "id": "cell_c1ec2297f7a6", "created_at": "2026-08-08T23:40:05+00:00", "title": "Verdict: VERIFIED"}
-->

**Anchored claim** (the anchor cites this as Theorem 4.1; v2 numbers it 4.5, same statement). Theorem 4.5 shows the one-step estimator is asymptotically normal, `√N(θ̂_one-step − θ) →_d N(0, σ²_eff)`, and attains the semiparametric efficiency bound.

**Verdict: VERIFIED.**

**Paper** [arXiv:2602.03061](https://arxiv.org/abs/2602.03061) · [OpenReview](https://openreview.net/forum?id=nOQOjKYwTM)

### √N-consistency

If the estimator is √N-consistent, `sd(θ̂) × √N` is constant in N. Measured over 4,000 replicates per cell, with the true nuisances plugged in so that the theorem's own regularity conditions hold exactly:

| σ | N | mean θ̂ | true θ | sd × √N | KS p (normality) |
| --- | --- | --- | --- | --- | --- |
| 0.5 | 250 | 0.249680 | 0.2500 | 0.3177 | 0.084 |
| 0.5 | 1000 | 0.250111 | 0.2500 | 0.3169 | 0.677 |
| 0.5 | 4000 | 0.250078 | 0.2500 | 0.3227 | 0.256 |
| 1.0 | 250 | 1.001408 | 1.0000 | 0.9523 | 0.530 |
| 1.0 | 1000 | 1.000416 | 1.0000 | 0.9377 | 0.646 |
| 1.0 | 4000 | 1.000147 | 1.0000 | 0.9679 | 0.824 |

### Does it attain the efficiency bound?

The theorem has two halves and √N-consistency is only the first. The second is that the limiting variance **equals** the semiparametric bound, `σ²_eff = Var(ψ)`. Claim 1 measured `Var(ψ)` independently, so the two can be compared directly:

| σ | √Var(ψ) from Claim 1 (the bound) | measured sd × √N |
| --- | --- | --- |
| 0.5 | 0.3224 | 0.3177, 0.3169, 0.3227 |
| 1.0 | 0.9583 | 0.9523, 0.9377, 0.9679 |

The measured spread brackets the bound at both σ, so the estimator attains it rather than merely being √N-consistent. That comparison is what licenses the phrase "both halves".

**Two of the three values sit BELOW the bound at each σ, and that needs saying rather than leaving for the reader to notice.** A semiparametric efficiency bound is a **lower** bound on asymptotic variance, so a measurement under it is impossible in the limit and can only be sampling scatter. Both sides here are estimates: `sd × √N` is a finite-N Monte-Carlo quantity, and the bound it is compared against is itself the Monte-Carlo `Var(ψ)` from Claim 1, which matched its own identity to within 2%. The observed spread is 0.3169–0.3227 against 0.3224, and 0.9377–0.9679 against 0.9583: a range of about 1.8% and 3.2% of the bound, the same order as the error on the bound itself. Scattering to both sides is what attainment looks like at finite N; landing consistently **above** it would be the finding, and does not happen. The Claim 3 page applies this same rule in the opposite direction, where a value above its own ceiling did need explaining.

`sd × √N` is flat across a 16× range of N (0.3177 → 0.3227 at σ=0.5; 0.9523 → 0.9679 at σ=1.0), and Kolmogorov–Smirnov tests against the normal never reject (p between 0.084 and 0.824). Failing to reject is not proof of normality, and the smallest of those p-values is 0.084 at 4,000 replicates, which is weak; the claim here is only that normality survives a test that had the power to break it, not that it is established. Both halves of the theorem hold.

### Scope of this check

This verifies the theorem under its own assumptions, using true nuisance functions. It deliberately does **not** test what happens when `τ̂` is estimated from finite data; that is Claim 3's territory, and it is where the picture changes.

Reproduce: `python analysis/claims12_eif_check.py` · [code](https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals/tree/main/code) · [exact outputs](https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals/tree/main/results), both published with this logbook

