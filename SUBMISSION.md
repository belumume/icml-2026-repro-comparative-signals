---
audience: internal
public: false
---

<!-- Internal working doc. The ONLY outward-facing text is the fenced
     `fals-explanation` block, which is audited separately: 0 em dashes,
     ASCII-only, no flagged vocabulary, within the 1500-char limit. -->

# Winner-submission packet

Form: https://huggingface.co/spaces/ICML-2026-agent-repro/winner-submission
**Deadline: Sunday 2 August 2026, 11:59 PM Anywhere-on-Earth = 11:59 UTC on 3 August.**

---

## Fields

| field | value |
| --- | --- |
| `username` | `passagereptile455` |
| `email` | **you fill this** — I will not guess your address |
| `social` | **you fill this** — the post URL, once you have posted it (see `POST-BRIEF.md`) |

### Award opt-ins

**☑ Best Falsification / Negative Result Award** — opt in.

`fals-url`:
```
https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals
```

`fals-explanation` (634 chars; the live form's own `maxlength` is 1500, verified by
reading `main.py` in the form Space rather than trusting this note). The form asks for
"2-3 sentences, in your own words" covering the falsified claim, the evidence, and the
different claim the work supports, and this covers those three in that order:

```
arXiv 2602.03061 reports 60 benchmark comparisons where its accuracy estimator beats plain averaging, while giving no error bar (i.e., uncertainty interval) for any of them.

What I observed from running their code without modification: For models whose answers vary a lot, their simulator works. But making the model more consistent adds noise instead (33% more, 18% to 50% across 250 runs).

The above is one out of five claims in the paper that I checked. The other four held up.

My reproduction supports a different claim: that their estimator helps on average across all 60 comparisons, but not enough to show in any single one.
```

**☐ Highest-Quality, Human-in-the-Loop Reproduction Award** — **do not opt in.**
It requires explaining *why an automated agent could not reproduce the claims
autonomously and what you had to do*. This reproduction ran autonomously; you logged
into Hugging Face and nothing else. Claiming it would be false.

**☐ OpenResearch Open-Weights Award** — **do not opt in.** Requires an open-weights
model as the main agent via the OpenResearch CLI harness. Not applicable.

---

## What the submission points at

- **Rendered logbook:** https://passagereptile455-repro-evaluating-llms-comparat-44a478e.static.hf.space/
- **Space:** https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals
- **Poster:** [PNG 9000×5400](https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals/resolve/main/poster.png) · [print PDF](https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals/resolve/main/poster.pdf)
- **Code:** `/tree/main/code` · **exact outputs:** `/tree/main/results`
- **Agent traces:** public dataset `passagereptile455/repro-evaluating-llms-comparative-signals-traces`. Re-audited against the LIVE dataset after publish, not against the local file: 0 occurrences of the Windows profile name, the OS account name, the real name, or the Kaggle handle; 0 real email addresses; and 0 strings matching the documented shape of a Google, Anthropic, OpenAI, HuggingFace, Firecrawl, AWS, GitHub or Slack credential. An earlier version of this line claimed 0 occurrences of the username and was FALSE: the sanitizer scrubbed the Windows profile name but not the OS account name in `ls -la` owner columns, and its audit was blind to the same gap because it only re-checked patterns already in its own substitution list. Both are fixed in `code/tools/sanitize_trace.py`, which now derives identifiers at runtime rather than hardcoding them.
- **Paper:** arXiv 2602.03061 · OpenReview `nOQOjKYwTM`

## Verdicts

| claim | verdict |
| --- | --- |
| 1 — efficient influence function (Prop 3.3) | VERIFIED |
| 2 — asymptotic normality + efficiency bound (Thm 4.5) | VERIFIED |
| 3 — strict variance reduction (Cor 4.7) | VERIFIED asymptotically; **not realised at low noise** |
| 4 — real-benchmark gains over naive | **FALSIFIED as stated** |
| 5 — ranking gap widens with output noise | VERIFIED, stress-tested 21× past the authors' grid |

Plus one finding in the paper's favour: the curve it plots as its efficiency reference
(its "Oracle VR", a deliberate derivation, not a slip) conditions on ρ₁ alone while the
estimator conditions on the full triple (W₁, W₂, V), so it understates the true bound by
**349× at σ = 0.1** and 668× at σ = 0.08, diverging as σ → 0. The method has more
headroom than its own figure claims.

Plus a live run that needs none of the paper's tables: a one-step-style estimator on real
GSM8K with open-weight models has a mean gain of **+0.24 pp** that is reliably positive
(95% CI for the mean [+0.167, +0.312], z = 6.5), worth 12% to 14% more evaluation data,
while a **single** run's gain spans **[−2.97, +3.63]**. The effect is real; one reported
number cannot show it. Positive control passed first (auxiliary AUROC 0.73 and 0.80).
Free-tier GPU, no paid API calls. The two intervals answer different questions and the
claim-4 page separates them: the wide one is a prediction interval for a single run, not
a confidence interval for a mean.

## Order of operations

1. Write the post (`POST-BRIEF.md`) — every sentence yours.
2. Send me the exact bytes; I run Pangram on them and report which spans flag.
3. Post it, copy the URL.
4. Fill the form: username, email, post URL, tick **Falsification** only, paste the
   Space URL and the explanation above.
