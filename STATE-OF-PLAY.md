# State of play — read this first

Updated 2026-08-08. Self-contained: everything below is either stated here or named by path,
and every figure carries the command that re-derives it. Recompute rather than quote.

---

## 0. What is still running

**One kernel has not landed.** `icml-repro-vr-nsweep-r100`, started 22:36 UTC 2026-08-07 with a
9h budget, so it ends by ~07:36 UTC 2026-08-08.

```
python -m kaggle kernels status ubaidullahshuaib/icml-repro-vr-nsweep-r100
python -m kaggle kernels output ubaidullahshuaib/icml-repro-vr-nsweep-r100 -p kaggle/vr_nsweep_r100/out
```

If that reports `No module named kaggle.__main__`, `python` has resolved to a virtualenv
without the CLI. Use the interpreter that has it rather than installing anything; on this
machine that is the Python 3.13 under `AppData/Local/Programs/Python`. This is not a footnote:
the same drift made `check_all_surfaces_synced.py` report `0 on Kaggle` and name every live
kernel as missing, because a failed subprocess produced empty output that was counted as a
zero. The check now resolves an interpreter and says *could not list* when it cannot look.

When it lands, in this order:

1. **Check the pull file count.** An earlier pull silently truncated at 194 files with the
   results JSON absent; a clean re-pull into a fresh directory got 294 including it. A missing
   file after a pull is not evidence the kernel produced nothing.
2. **Read `control_ok` first.** It is true only if the published -0.3300 falls inside the
   N=1000 interval. If false, discard every row, exactly as the earlier mechanism run's rows
   were discarded. A single row means nothing without it.
3. If it passes, integrate through `tools/write_content.py` — not the generated page, which is
   overwritten — then `python tools/publish_all.py`, then commit on a branch and open a PR.

Everything else is done. Git is clean, no open PRs, all surfaces synced.

---

## 1. What this is

A reproduction of **arXiv 2602.03061** for the ICML 2026 Agent Reproduction Challenge,
submitted for Best Falsification / Negative Result on 2026-08-03 before the 11:59 UTC deadline.

**Judging is frozen.** The challenge FAQ, verbatim: *"Logbooks published or updated after that
moment are not judged: verdicts already on the board at the deadline stay frozen, and later
edits do not change them."* The judged state is the 08:02 UTC publish of 03 Aug. Everything
since improves the artifact and does not move the score. Both halves are true; stating only one
of them is dishonest.

**Four of the five anchored claims reproduce. The fifth does not.** The interesting part is that
the published explanation for the fifth was wrong twice before measurement settled it.

---

## 2. The findings, each with its re-derive command

### The falsification as it stands

At sigma = 0.08 the one-step estimator does not deliver the +0.0846 the exact bound offers.
**None of three independent nuisance fits delivers it**, and the paper's own fit is actively
harmful. One fit failing is an implementation anecdote; three failing is a property of the regime.

### Nuisance ablation — the harm is the fit, not the estimator

```
python -c "import json;d=json.load(open('results/vr_ablation_results.json'));[print(r) for r in d['rows']]"
```

At sigma=0.08: MLP as shipped **-0.5084**, ridge **+0.0058**, kNN **-0.0217**. At sigma=1.0 all
three recover most of the bound (+0.6884 / +0.5872 / +0.5738 against +0.7753).

Ridge is closed-form, so there is no learning rate, no epoch count and no SGD, and it is
equivariant in target scale. It cannot underfit a small target the way the shipped MLP does at
lr=0.001 and 50 epochs on a target roughly 150x smaller than where those settings were chosen.
Only `self.model` is swapped, so the authors' feature construction, cross-fitting, MC integration
and estimator algebra all still run.

### Stability — the sign holds, and my own alarm was wrong

```
python -c "import json;d=json.load(open('results/vr_stability_results.json'));[print(a['sigma'],a.get('across_replicate_sd'),a.get('understatement_factor'),a.get('n_negative')) for a in d['arms']]"
```

sigma=0.08, ten replicates at R=100: **negative 10 of 10**, range -0.2565 to -0.1227, SD 0.0467.
sigma=1.0 control: SD 0.0041, near-noiseless. Understatement factor 0.46x and 0.09x, both below
1, so the bootstrap intervals are conservative rather than optimistic.

**The magnitude caveat survives.** R=100 centres on -0.18 and the published -0.3300 sits outside
that range. The sign is solid; the size depends on R in a way this reproduction has not
characterised, which is what the still-running kernel above is for. The page says "negative,
order tenths", not a constant.

### Sigma against decoding temperature — the low-noise regime is the default protocol

```
python -c "import json;d=json.load(open('results/sigma_temp_results.json'));[print(r) for r in d['rows']]"
```

Qwen2.5-1.5B, 100 GSM8K questions, K=8. Greedy at T=0: accuracy 0.510, within-question SD
**0.0000**. At T=0.3 / 0.7 / 1.0: SD 0.2515 / 0.2688 / 0.3097, accuracy 0.514 / 0.461 / 0.371.

**Greedy has exactly zero resampling spread, and greedy is the standard benchmark protocol.** So
the most consistent possible model is not an exotic corner of the space; it is how accuracy is
normally measured. That answers the authors' strongest objection, that in practice sigma is near
1. Two limits were stated before the run and confirmed by it: temperature moves the target as
well as the spread, since accuracy falls from 0.510 to 0.371, and the units are not the paper's,
so only the ordinal comparison is claimed.

### McNemar bound, corrected

`work/analysis/mcnemar_bound.py` returned `sqrt(|d|/n)`; the correct expression is
`sqrt(|d|(1-|d|)/n)`. Materiality is nil here (35/60 both ways, zero flips) but the dropped term
made the bar wider, which flattered our own conclusion. The self-test had certified the error and
was fixed alongside it.

---

## 3. Five premises that measurement killed

A later reader can rebuild a result from `results/`. A refutation cannot be rebuilt, so these are
the entries that matter most.

1. **"The repo is frozen, so findings are disclosure and not repair."** Invented. There is no
   no-edit rule anywhere. The real FAQ sentence is about judging; I widened it into a prohibition
   on editing, asserted it for hours, and wrote it into a nine-agent audit brief, so every finding
   came back classified disclosure-only. One of them was a live Windows username on the public
   Space.
2. **"The low-signal regime causes the excess variance."** Wrong, and it was the published
   explanation. The ablation refutes it.
3. **"The bootstrap CI understates rerun scatter."** Refuted by measurement, and it was my own
   alarm. Conservative at 0.46x and 0.09x.
4. **"Publishing to GitHub would tie the pseudonymous handle to a real name."** Wrong. The 03 Aug
   X post is under the same handle and links the Space; they were already linked.
5. **"The temperature sweep needs an order of magnitude more compute, and the ablation settled its
   question."** Both false. It ran in 1614 s on a free T4, and the ablation settled *why* the
   estimator fails, not *whether* low sigma occurs. It was deferred twice, once while its
   justification was described as having got stronger. It turned out to be the most valuable open
   item.

---

## 4. Where everything lives

- **GitHub:** https://github.com/belumume/icml-2026-repro-comparative-signals
- **Hugging Face Space:** `passagereptile455/repro-evaluating-llms-comparative-signals`
- **Rendered logbook:** https://passagereptile455-repro-evaluating-llms-comparat-44a478e.static.hf.space/
- **Kaggle:** seven kernels under `ubaidullahshuaib/icml-repro-*`

`python tools/check_all_surfaces_synced.py` answers "is anything stale anywhere" across all nine
checks in one command.

---

## 5. The gates, and what they said on this run

Run 2026-08-08. Exit codes were captured before any pipe, so these are the commands' own
statuses rather than a pager's.

| command | result |
|---|---|
| `python tools/check_all_surfaces_synced.py` | 9 checks; the only open item is the in-flight kernel in section 0 |
| `python tools/check_findings_closed.py` | exit 0; disposition of all 18 findings re-derived from the repo |
| `python code_publish/verify_headlines.py` | exit 0; **all 36 checks pass**, about 1s, stdlib only |
| `python tools/check_links.py` | exit 0; **31 distinct links, 0 relative, every one resolves** |
| `python tools/test_kernels_check.py` | 6/6; the control for the check below |

`HANDOFF.md` carries the fuller record. `tools/` holds every gate, and each one's docstring says
what it exists to prevent and names the incident that produced it.

**The ledger is the source of truth for what is open, not recollection.** It reported two settled
findings as open for three days because it was keyed to a cancelled kernel. Re-derive; do not
recall.

---

## 6. Traps that cost real time here

- **Kaggle pulls can truncate silently.** See section 0.
- **Monkeypatching a class and then reusing loky workers contaminates later trials.** The
  abandoned mechanism kernel patched `fit` and `predict` but not `predict_integrated`, mixing
  scales, and never restored the class, so "unpatched" trials running in a reused worker were
  still patched. It produced VR = -1038 and -6793. Its control read -0.1312 against a published
  -0.3300 and caught it. `vr_ablation` does this correctly, with `_orig_fit` and a restore.
- **A budget guard above the session wall is not a guard.** That same kernel guarded at 9.5h
  against a 9h wall, so it was killed before the guard could fire, destroying 11.5h of
  computation because it wrote its JSON only at the end. Bank after every unit.
- **Verify a remote job's dependencies from a prior run's log, not from expectation.** vLLM is
  not installed on Kaggle: the published GSM8K log carries `vllm unavailable:
  ModuleNotFoundError` four times. A first draft of the temperature kernel imported it with no
  fallback and would have crashed on start.
- **`hash()` is randomised per process**, so a seed derived from it is not reproducible across
  runs. Use an explicit table.
- **A subprocess whose failure nobody checks becomes a confident zero.** The surface-sync gate
  ran `sys.executable -m kaggle`, `python` resolved to a virtualenv without the CLI, and empty
  stdout was counted as a listing: `7 local, 0 on Kaggle`, naming six live kernels as missing
  while one of them was still running. A verdict identical across every item is evidence about
  the instrument before it is evidence about the world. `tools/test_kernels_check.py` now drives
  both branches, and it earned its keep immediately: it caught that the first version of the fix
  crashed on a nonexistent interpreter instead of falling through to the next one.
