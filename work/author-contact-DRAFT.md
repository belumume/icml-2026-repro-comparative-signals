# Author contact, DRAFT (not sent)

Operator sends this if they choose. No address was looked up. Best route is the OpenReview
thread for `nOQOjKYwTM` or the contact address on the arXiv listing.

REVISION HISTORY, because this draft has been wrong twice and both corrections are the
point of sending it at all:
  v1 ASKED whether the low-sigma result was a tuning artefact. The ablation then answered
     that question ourselves, so asking would have invited them to supply what we held.
  v2 reported the ablation but quoted its R=60 numbers with no caveat. A stability run
     then showed R=60 is unreliable for a variance ratio: two R=60 runs of the identical
     configuration gave -0.5084 and +0.0394, while ten R=100 replicates ran -0.2565 to
     -0.1227 and were negative 10 of 10. Sending v2 would have handed them a magnitude we
     had already publicly qualified.
  v3 (this one) reports the contrast, which is what the ablation actually establishes, and
     states the magnitude caveat rather than leaving them to find it in the logbook.

Body is 268 words including the code block. Em dashes: 0.

---

**Subject:** Reproduction of arXiv 2602.03061, including two corrections to our own findings

Hello,

I reproduced your paper for the ICML 2026 Agent Reproduction Challenge. Four of the five
claims I anchored held: the efficient influence function, asymptotic normality, Corollary
4.7 as an asymptotic statement, and the ranking claim, which survived a sigma sweep well
past your own grid. Your exact efficiency bound also sits above Figure 3's reference curve,
so the method has more headroom than that figure shows.

At sigma = 0.08 your unmodified `run_single_trial` gives the one-step estimator more
variance than the naive mean, where the exact bound offers an 8.5% reduction. I first
attributed that to the low-signal regime. That was wrong, and I have corrected the logbook.

Replacing only the nuisance regressor, leaving your feature construction, cross-fitting and
estimator algebra untouched, gives this at sigma = 0.08:

```
MLP, as shipped   VR = -0.51
ridge, closed form      +0.006
k-NN                    -0.02
```

At sigma = 1.0 all three recover most of the bound. So the excess variance tracks the
shipped MLP fit, which uses lr=0.001 and 50 epochs on a target roughly 150x smaller than at
sigma = 1, rather than the estimator itself.

One caveat on my own numbers. Ten independent replicates at sigma = 0.08 were negative ten
times out of ten but ranged from -0.13 to -0.26, so the sign is solid and the magnitude
depends on the replication count more than a single run suggests. Read the table above as a
contrast between fits, not as three precise values.

What survives is narrower than my first claim: at sigma = 0.08 none of the three fits
delivers the 8.5% that is available.

Logbook, code and both experiments: https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals

If any of this misreads your intent I would rather correct it than leave it standing. If you
reply, I will publish your response verbatim alongside the logbook.

Thanks,
Ubaidullah
