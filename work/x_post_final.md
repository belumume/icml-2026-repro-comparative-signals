# X post

```
arXiv 2602.03061 reports 60 benchmark comparisons where its accuracy estimator beats plain averaging, while giving no error bar (i.e., uncertainty interval) for any of them.

What I observed from running their code without modification: For models whose answers vary a lot, their simulator works. But making the model more consistent adds noise instead (33% more, 18% to 50% across 250 runs).

The above is one out of five claims in the paper that I checked. The other four held up.

My reproduction supports a different claim: that their estimator helps on average across all 60 comparisons, but not enough to show in any single one.

https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals
```
