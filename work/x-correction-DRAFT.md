# X follow-up: correction to the 3 Aug post (DRAFT, not sent)

Reply to https://x.com/ubaidmume/status/2084225563976155540

Why this is worth posting rather than leaving alone: the original attributes the low-noise
excess variance to their ESTIMATOR. The ablation shows it is their nuisance FIT. That is
the difference between indicting a method and indicting an implementation, and the people
most affected by the wrong version are the authors, who have no way to know. It is also a
result rather than an announcement, which is the shape worth posting.

The rest of the original stands. Four of five claims did reproduce; the estimator does help
on average and not per-cell, and the ablation makes that part stronger rather than weaker.

Numbers verified against results/ before drafting: ridge +0.0058, MLP -0.5084, kNN -0.0217
at sigma=0.08; exact available bound +0.0846; ten R=100 replicates mean -0.1835, range
-0.2565 to -0.1227, negative 10/10; published point -0.3300 at R=250.

Em dashes: 0. No self-flagellation, no hedging, no closer.

---

Correction. I said their estimator adds noise when the model is more consistent. That was
wrong about the cause.

I swapped their nuisance regressor for a closed-form ridge and changed nothing else in
their pipeline. The harm disappears: -0.51 becomes +0.006. Their MLP is fit at lr=0.001
for 50 epochs on a target roughly 150x smaller than where those settings were chosen, so it
underfits. That is their tuning, not their estimator.

The size moved too. Ten reruns at R=100 centre on 18%, not the 33% I quoted. Both extreme
values I first hit were at R=60, where a ratio of two variances misbehaves.

What survives is narrower and rests on more. With a consistent model none of three nuisance
fits (their MLP, ridge, k-NN) delivers the 8.5% that is theoretically available, while all
three deliver it when the model varies. One fit failing is an implementation anecdote.
Three failing is a property of the regime.

The logbook now carries the ablation, the replication, and this correction.
