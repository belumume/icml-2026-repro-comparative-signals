# Post brief — ICML 2026 reproduction logbook

**You write every sentence. I supply substance, verified numbers, and the gate.**

That division is not stylistic caution, it is the measured method as of 2026-08-02.
Pangram now serves **4.0** and the old 3.3.2 verdicts do not transfer. The cleanest
measurement in our corpus, taken 2026-08-02:

| text | words | who composed | verdict |
|---|---|---|---|
| your own rewrite (Reactorfield Q2) | 56 | you | **Human 100%** |
| an agent assembly built from *your own mined phrasings* | 52 | the agent | **AI** |

Same length band, your vocabulary in both, one variable: who built the sentences.
So a polished draft from me is the path that *measurably fails*. No agent sentence
should survive into the final bytes — one is enough to flag the whole post.

---

## Eligibility requirement (why this post exists)

The winner-submission form requires, verbatim: *"A link to a LinkedIn, X, or equivalent
post where you shared at least 1 verified logbook or poster you created. Sharing your
work publicly is required to be eligible."* No post, no prize consideration — including
both $500 special awards.

## The links

- Rendered logbook (**use this one**): https://passagereptile455-repro-evaluating-llms-comparat-44a478e.static.hf.space/
- Space page: https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals
- Paper: https://arxiv.org/abs/2602.03061 · OpenReview `nOQOjKYwTM`
- Authors' code: https://github.com/zihandong02/AI_evaluation

## Verified facts you can draw on (every number checked; do not round them)

- Paper: *"Evaluating LLMs When They Do Not Know the Answer"*, ICML 2026. It builds a
  semiparametric one-step estimator that borrows strength from cheap pairwise
  comparisons so a small eval set gives a better accuracy estimate.
- **4 of 5 anchored claims reproduce.** The theory is genuinely sound — influence
  function, asymptotic normality, efficiency bound all check out analytically.
- **The falsification:** the paper calls its real-benchmark gains *"significantly
  closer to the ground truth"* while **no gain carries an interval, standard error or
  variance estimate**. Searched the full text: `bootstrap` **0** occurrences,
  `standard error` **0** occurrences. (It does have robustness re-runs varying seed,
  subset size and rubric, so do not say "no uncertainty of any kind" — that overstates
  it and is easy to rebut.)
  **58 of 60** recomputed gains sit under **1.0 standard error** of binomial noise;
  median **0.42 SE**; all 60 under 2.0 SE.
- **The part that is not an argument about tables, and is probably the most postable
  thing here.** I ran a one-step-style estimator live on real GSM8K with open-weight
  models on a free Kaggle T4, 22 minutes, zero paid API calls. Two numbers, both true of
  the same run, and you need both or it misleads:
  - The **mean** gain is **+0.24 pp** and is reliably positive (CI for the mean
    **[+0.167, +0.312]**). In useful units that is worth **12% to 14% more evaluation
    data**. So the effect is real.
  - A **single** evaluation run's gain spans **[−2.97, +3.63]**, more than an order of
    magnitude wider. So one reported number cannot show the effect.
  Second model, same story: +0.23 pp mean, [+0.172, +0.291], single-run [−2.53, +3.01].
  Before trusting any of it I checked the auxiliary signal was actually informative
  (AUROC **0.73** and **0.80**), because a dead signal produces a null for free.
  The one-line version, if you want it: *the effect is real in aggregate and invisible in
  any one number, and the paper reports only single numbers.*
  **If you write about this, do not call the wide interval a confidence interval.** I did,
  in the first published version, and an independent review caught it. It is the spread of
  a single run. The logbook now carries that correction openly, which is worth more to us
  than the cleaner-sounding original claim.
- **Three of the 60 cells contradict their own row.** `Improv.` is defined in the paper
  as `|naive − GT| − |one-step − GT|`; recomputing it from each row's own numbers
  reproduces 57 of 60. The clearest: GPT-5.2 on GSM8K prints **+0.50%** where its
  one-step estimate equals the naive one to the digit (97.00 vs 97.00), so the gain can
  only be zero. Another flips sign — **+0.24%** printed where the row implies **−0.30%**
  — and +0.24% happens to be the stated floor of the paper's own "0.24–12.00%" range.
- **The honest other half** (this is what makes it a real result rather than a dunk):
  the aggregate effect *is* real. Clustering to one value per benchmark-model pair,
  because the paper's two configs share an evaluation subset, gives **27 of 30**
  positive, exact binomial **p = 4.2e-06**. Quote that one, not the unclustered
  53-of-59 / 8.8e-11: the cells are not independent, so the unclustered p is
  anti-conservative. The true claim is a small systematic bias reduction visible only
  in aggregate, never per-cell. The method is not useless; the inference was
  unsupported.
- **The counter-example against my own finding, which the logbook states rather than
  hides:** exactly **one** of the 60 gains clears a no-signal null (GSM8K, +3.50%
  against a +3.36pp bar), and it is the very figure the challenge's own anchor quotes.
  One survivor out of sixty is fewer than the ~3 a 5% tail predicts by chance, so it
  does not rescue the per-cell claim, but omitting it would have been exactly the sin
  the logbook accuses the paper of. (An earlier draft said two; the second, +3.40%,
  clears only on a printed value its own row contradicts, so counting it would mean
  relying on a number this logbook has already shown to be unsupported.) Only mention
  this if you want to; it is the most honest thing in there.
- **I got something wrong and fixed it in public.** My first pass hand-transcribed the
  three result tables and swapped two of their identities, which made me wrongly claim
  the challenge's own anchored numbers were misattributed. They were correct; I was not.
  The logbook carries the retraction on the claim-4 page. The fix was to delete the
  human step: the tables are now parsed from the paper's HTML with each bound to its
  caption by document position, behind four structural assertions. Worth mentioning only
  if you want to — it is the most honest thing in the logbook, but it is your call.
- **A finding in the paper's favour:** the curve it plots as its efficiency reference
  (its "Oracle VR", a deliberate derivation and not a coding slip) conditions on ρ₁
  alone while the estimator uses the full auxiliary triple, so it understates the true
  bound by **349× at σ=0.1** and 668× at σ=0.08.
- **At low model noise the estimator makes things worse:** at σ=0.08, variance is
  **+33%** vs the naive mean (250 replications, 95% CI [−0.495, −0.185], entirely below
  zero). This contradicts Remark 4.8's *"ensuring efficiency gain"*. Between σ=0.10 and
  0.20 the reduction is statistically indistinguishable from zero.
- **Cost: no paid API calls at all.** The simulation study is CPU only; the live GSM8K
  run used 22 minutes on one free-tier Kaggle T4. All 750 challenge GPU-credit slots
  were gone before you joined, and none were needed.
- **Everything is rerunnable:** the analysis code, the exact result JSONs, the poster
  source and the full agent trace are all published in the same Space.
- Their `simulation/` code ran unmodified on the first try, which is rarer than it
  should be and worth saying.

## Content requirements

1. Link the logbook (the rendered URL above).
2. Say it is the ICML 2026 reproduction challenge (HF + alphaXiv).
3. Carry **both halves** of the falsification — the failure *and* that the aggregate
   effect is real. A one-sided "paper is wrong" post would be inaccurate and you would
   have to walk it back.
4. Somewhere ≥ 50 words, or Pangram cannot score it. 60–120 is the sweet spot.

## Hard don'ts

- No arrogance. You deleted the Built-with-Claude LinkedIn post over the
  *"I actually thought I'd get in"* closer — tone, not outcome, was the reason.
- Don't claim you disproved the paper. You didn't; you falsified one claim as stated and
  verified four.
- Don't say "significantly" about your own result either.
- No em dashes, no "delve/leverage/comprehensive", no "Excited to share".

## Register anchors — your own posted words

X (lowercase, direct, stakes on a checkable fact):
> got into Built with Claude: Life Sciences (@AnthropicAI + cerebral valley, with the
> gladstone institutes). 500 picked, one week, going solo.
> getting in was the part i was confident about. whether that was the delusional part,
> we find out by the 13th.

> still early, would genuinely love eyes on it.

LinkedIn (sentence case, fuller, fragment closers allowed):
> Most agents either run the dangerous command or sit blocked until you're back at the
> keyboard. A call reaches you wherever you are.

## Then

Send me the exact bytes. I run Pangram on them, report which spans flag, and you
restructure only those spans. I do not rewrite them for you — that is what puts the
verdict back to AI.
