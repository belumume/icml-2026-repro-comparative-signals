# Author contact, DRAFT (not sent)

Operator sends this if they choose. No address was looked up. Sign-off name taken from
project memory; change it if wrong. Best route is the OpenReview thread for `nOQOjKYwTM`
or the contact address on the arXiv listing, whichever the operator prefers.

REWRITTEN 2026-08-03 after the nuisance ablation returned. The previous draft ASKED whether
the low-sigma result was a tuning artefact. That question is now answered by our own
measurement, so asking it would be disingenuous: a closed-form ridge nuisance removes the
excess variance entirely. Sending the old draft would have invited them to supply an answer
we already had. This version reports the finding instead, including the part that runs
against our own earlier framing.

Body is 251 whitespace-delimited words including the command line and the URL. Em dashes: 0.

---

**Subject:** Reproduction of arXiv 2602.03061, including a correction to our own finding

Hello,

I reproduced your paper for the ICML 2026 Agent Reproduction Challenge. Four of the five
claims I anchored held: the efficient influence function, asymptotic normality, Corollary
4.7 as an asymptotic statement, and the ranking claim, which survived a sigma sweep well
past your own grid. Your exact efficiency bound also sits above Figure 3's reference curve,
so the method has more headroom than that figure shows.

At sigma = 0.08 your unmodified `run_single_trial` gives the one-step estimator about 33%
more variance than the naive mean, where the exact bound offers an 8.5% reduction. I first
attributed that to the low-signal regime. That was wrong, and I have corrected the logbook.

Replacing only the nuisance regressor, leaving your feature construction, cross-fitting and
estimator algebra untouched, gives this at sigma = 0.08 (R = 60):

```
MLP, as shipped   VR = -0.5084  [-0.933, -0.176]
ridge, closed form      +0.0058  [-0.047, +0.055]
k-NN                    -0.0217  [-0.106, +0.048]
```

At sigma = 1.0 all three recover most of the bound. So the excess variance is specific to
the shipped MLP fit, which uses lr=0.001 and 50 epochs on a target roughly 150x smaller
than at sigma = 1, and not a property of your estimator. What does survive is narrower: at
sigma = 0.08 none of the three fits delivers the 8.5% that is available.

Logbook, code and the ablation: https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals

If any of this misreads your intent, I would rather correct it than leave it standing. If
you reply, I will publish your response verbatim alongside the logbook.

Thanks,
Ubaidullah
