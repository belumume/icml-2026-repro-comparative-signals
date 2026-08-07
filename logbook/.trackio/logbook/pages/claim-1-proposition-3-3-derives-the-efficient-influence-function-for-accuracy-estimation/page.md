# Claim 1: Proposition 3.3: efficient influence function


---
<!-- trackio-cell
{"type": "markdown", "id": "cell_627a28fb7311", "created_at": "2026-08-04T11:55:30+00:00", "title": "Verdict: VERIFIED"}
-->

> **Numbering.** The challenge's anchor cites this as **Proposition 3.1**. No such label exists in the arXiv v2 text I worked from, which numbers it **Proposition 3.3** (`Proposition 3.1` occurs 0 times in v2; `Proposition 3.3` occurs 3). The **statement** quoted in the anchor is identical to Proposition 3.3, so this is a version-numbering difference, not a different claim. Same for Theorem 4.1 → **4.5** and Corollary 4.1 → **4.7** on the next two pages.

**Anchored claim.** Proposition 3.3 derives the efficient influence function `ψ(X,Y,G,Z) = [m(X) − θ] − [τ(X,Z) − φ(Y,G)]`, where `τ(X,Z)` is the outcome regression on pairwise-comparison auxiliary signals and `m(X)` its integrated version.

**Verdict: VERIFIED**, against closed-form nuisances rather than by re-reading the proof.

**Paper** [arXiv:2602.03061](https://arxiv.org/abs/2602.03061) · [OpenReview](https://openreview.net/forum?id=nOQOjKYwTM)

### What was done

The paper's own simulation data-generating process, or DGP (`simulation/data_generation.py`), is fully Gaussian:

```
X ~ N(0,1),  G = X,  Y = X + ε,  ε ~ N(0, σ²),  φ(Y,G) = (Y−G)² = ε²
W_k = X + ρ_k ε + η_k,  η_k ~ N(0, σ_η²),   k = 1,2   (ρ₁=0.8, ρ₂=0.6, σ_η=0.6)
V   = 1{(W₁−Y)² ≤ (W₂−Y)²}                            (preference label)
```

so every conditional expectation in ψ is available in closed form, and the check therefore uses the TRUE nuisances with no plug-in estimation error to confound it. The expectations themselves are evaluated by simulation, so agreement below is to Monte-Carlo precision rather than to the digit. Two properties were tested at 2,000,000 draws per σ:

1. **ψ is a valid (mean-zero) influence function**: `E[ψ] = 0`.

2. **The efficiency identity**: `Var(ψ) = σ²_naive − E[u²]` with `u = τ − m`.

### Results

| σ | E[ψ] | Var(ψ) | σ²_naive | σ²_naive − E[u²] | identity |
| --- | --- | --- | --- | --- | --- |
| 0.1 | -2.05e-06 | 0.000200 | 0.000200 | 0.000200 | match |
| 0.25 | 8.71e-05 | 0.007652 | 0.007821 | 0.007650 | match |
| 0.5 | -1.36e-04 | 0.103967 | 0.124819 | 0.103761 | match |
| 1.0 | -6.10e-04 | 0.918306 | 2.011695 | 0.923142 | match |
| 2.0 | -1.04e-03 | 5.078655 | 31.980468 | 5.066238 | match |
| 3.0 | -2.94e-03 | 12.221987 | 162.008196 | 12.114535 | match |

`max |E[ψ]| = 2.9e-03` across all σ, consistent with Monte-Carlo error at this sample size. The identity matches within 2% at every σ.

### Why this matters downstream

The identity `Var(ψ) = σ²_naive − E[u²]` is the **reason** Corollary 4.7 holds: the efficiency gain is exactly `E[u²]`, which is strictly positive whenever `τ ≠ m`. So Claim 1 and Claim 3 stand or fall together, and both stand, **asymptotically**. The finite-sample behaviour is a separate question, taken up on the Claim 3 page.

Reproduce: `python analysis/claims12_eif_check.py` · [code](https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals/tree/main/code) · [exact outputs](https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals/tree/main/results), both published with this logbook

