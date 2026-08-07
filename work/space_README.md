---
title: "Reproduction: Evaluating LLMs When They Do Not Know the Answer: Statistical Evaluation of Mathematical Reasoning via Comparative Signals"
emoji: 🎯
colorFrom: yellow
colorTo: red
sdk: static
pinned: false
tags:
 - trackio
 - trackio-logbook
 - open-experiment
 - icml2026-repro
 - paper-nOQOjKYwTM
 - arxiv:2602.03061
---

# Reproduction: *Evaluating LLMs When They Do Not Know the Answer*

An ICML 2026 Agent Reproduction Challenge logbook for **arXiv 2602.03061** / OpenReview
`nOQOjKYwTM`. Five anchored claims, checked one at a time. Published with
[Trackio](https://github.com/gradio-app/trackio).

**[Read the rendered logbook](https://passagereptile455-repro-evaluating-llms-comparat-44a478e.static.hf.space/)**
· [poster PNG](https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals/resolve/main/poster.png) · [print PDF](https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals/resolve/main/poster.pdf)
· [code](https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals/tree/main/code) · [exact outputs](https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals/tree/main/results)

## Verdicts

| Claim | Verdict |
| --- | --- |
| 1. Proposition 3.3, efficient influence function | VERIFIED by exact analytic check |
| 2. Theorem 4.5, asymptotic normality and the efficiency bound | VERIFIED, both halves shown |
| 3. Corollary 4.7, strict variance reduction | VERIFIED asymptotically. **The practical guarantee fails at low noise** |
| 4. Real-benchmark gains over the naive estimator | **FALSIFIED as stated** |
| 5. Ranking gap widens with output noise | VERIFIED, stress-tested 21x past the authors' grid |

The mathematics is sound. What does not hold is a practical guarantee in Remark 4.8 and
the evidence offered for the real-benchmark claim.

## The three findings

**The estimator can be worse than the mean it replaces.** Remark 4.8 says the one-step
estimator ensures an efficiency gain. Running the authors' own unmodified simulation at
low model noise, at sigma = 0.08 it carries **33% more variance** than the naive sample
mean, 95% CI [-0.495, -0.185] over 250 replications, entirely below zero, with a positive
control passing at the paper's own default sigma = 1.0.

**The real-benchmark gains are inside their own noise floor, and a live run agrees.**
The paper calls its gains "significantly closer to the ground truth" while reporting no
interval, standard error or variance estimate for any of them; `bootstrap` and
`standard error` each occur zero times in the full text. 58 of 60 gains recomputed from
the paper's own numbers sit under one standard error of binomial noise. Running a one-step-style estimator live on
real GSM8K with open-weight models, on an auxiliary signal verified informative first
(AUROC 0.73 and 0.80), the mean gain is **+0.24 pp** and is reliably positive (95% CI for
the mean [+0.167, +0.312]), worth 12% to 14% more evaluation data. The gain is real.
But a **single** run's gain spans **[-2.97, +3.63]**, more than an order of magnitude
wider, so one number per cell cannot demonstrate it. The honest replacement claim is a
small systematic absolute-error reduction detectable in aggregate and never per cell.

**One finding in the paper's favour.** The curve it plots as its efficiency reference
conditions on a strictly smaller information set than the estimator actually run, so it
understates the true bound by **349x at sigma = 0.1**. The method has more headroom than
its own figure claims.

## Reproducing this

Everything here reproduces from a fresh clone with no paid API access and no credentials.
See [`code/README.md`](https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals/blob/main/code/README.md) for the full procedure, the pinned
authors' commit, and the environment. The heaviest step is a 73 minute low-σ sweep on CPU; the GPU
run is 22 minutes.

The paper's own HTML is vendored at `paper/paper_v2.html` with its source URL, retrieval
date and sha256 recorded, so the table analysis reproduces even if the arXiv page moves.
It remains the authors' work under the arXiv perpetual non-exclusive licence.

**To check a verdict without running anything**, open
[`logbook/artifacts/`](https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals/tree/main/logbook/artifacts): the evidence behind each claim as
flat CSV, one file per table, including the full 60-cell grid the Claim 4 falsification
rests on. They are generated from the result JSON and re-verified against it cell by cell
on every publish, so they cannot drift from the pages that cite them. The same files are
listed under the **Workspace** tab.

## Provenance and licences of the tooling

The poster was built with the `posterly` skill, which is **AGPL-3.0**, and its layout
tokenization is vendored and adapted from
[ARIS](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep) under **MIT**
(c) 2026 wanshuiyin. The poster HTML renders math with **MathJax** (Apache-2.0). All
three licence texts ship in [`LICENSES/`](https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals/tree/main/LICENSES), because the poster
source carries an attribution that pointed at a licence file this Space was not
publishing. The paper HTML in `paper/` remains the authors' work under the arXiv
perpetual non-exclusive licence.

Agent traces for this reproduction are public at
[`passagereptile455/repro-evaluating-llms-comparative-signals-traces`](https://huggingface.co/datasets/passagereptile455/repro-evaluating-llms-comparative-signals-traces).
