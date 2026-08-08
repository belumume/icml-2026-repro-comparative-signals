# Reproduction code — ICML 2026 Agent Reproduction Challenge

Reproduces every number in the logbook for **nOQOjKYwTM** / arXiv 2602.03061,
*Evaluating LLMs When They Do Not Know the Answer: Statistical Evaluation of
Mathematical Reasoning via Comparative Signals*.

Rendered logbook: https://passagereptile455-repro-evaluating-llms-comparat-44a478e.static.hf.space/

Everything below is CPU only. No GPU, no API keys, no paid calls.

---

## Check the numbers first, in one second

The full reproduction below takes about 40 minutes, most of it in two simulator
sweeps. You almost certainly want this first:

```bash
python verify_headlines.py
```

No arguments, no dependencies beyond the standard library, no setup, no network.
It reads the published `results/*.json` and checks all 45 headline numbers the
logbook asserts (the 60-cell grid, both sign tests, the σ=0.08 confidence
interval, the efficiency bound, and the live GSM8K run), printing PASS or FAIL per
line against what the prose claims. It runs as a publish gate too, so if a written
claim ever drifts from the data underneath it, the logbook does not ship.

That verifies the *derivation*. Everything below re-derives the raw JSON itself,
from the authors' unmodified code, which is the part that takes 40 minutes.

---

## Cold start

Four steps. **Step 1 ends in `code/`, and every command in this file, setup
included, runs from there.** That is the only working directory this README
uses.

### 1. Get this repository

```bash
git clone https://huggingface.co/spaces/passagereptile455/repro-evaluating-llms-comparative-signals
cd repro-evaluating-llms-comparative-signals/code
```

Some of the logbook page directories under `pages/` have long names. On Windows,
cloning into an already-deep directory can fail the checkout with `Filename too
long`; clone somewhere shallow, or set `git config --global core.longpaths true`
first. Nothing in the reproduction path reads `pages/`, but the checkout has to
succeed to get the rest.

### 2. Get the authors' code

`analysis/vr_sweep.py` and `analysis/claim4_at_reported_N.py` run the authors'
own simulation unmodified, so their package has to be on disk at
`code/AI_evaluation/`. The scripts locate it relative to their own file, so the
exact directory name matters.

```bash
git clone https://github.com/zihandong02/AI_evaluation.git AI_evaluation
git -C AI_evaluation checkout aa03c3064e532a13dc65e0d58aa62a1a5402260f
```

That commit is pinned because it is the state the results here were produced
against. As of 2026-08-02 it is also the only commit on `main` (authored
2026-05-29), so a plain clone lands on it, but the checkout is written out so
the pin survives any later push by the authors.

Nothing in `code/AI_evaluation/` is edited. `vr_sweep.py` imports
`SimulationConfig` and `run_single_trial` from it as published.

### 3. Get the paper HTML

`analysis/extract_tables.py` parses the paper's Tables 1-3 out of the arXiv
HTML rendering, which must sit at `paper/paper_v2.html` (that is one level up
from `code/`, at the root of this repository).

A copy is already published here, so a fresh clone of this repository has it and
you can skip ahead. To re-fetch it from the source instead:

```bash
python -c "import urllib.request; \
open('../paper/paper_v2.html','wb').write(urllib.request.urlopen( \
urllib.request.Request('https://arxiv.org/html/2602.03061v2', \
headers={'User-Agent':'Mozilla/5.0'})).read())"
```

Either way the file must hash to:

```
sha256  786287c822be49f23f209af7534a6e218039e95befc6a50ca6073e52a2744c65
bytes   694941
```

```bash
python -c "import hashlib;print(hashlib.sha256(open('../paper/paper_v2.html','rb').read()).hexdigest())"
```

Provenance: fetched from `https://arxiv.org/html/2602.03061v2` on 2026-08-02,
which returned exactly those bytes. The document's own watermark reads
`arXiv:2602.03061v2 [cs.LG] 20 Jul 2026`, and it carries the arXiv.org
perpetual non-exclusive license. It is vendored here only so the table
extraction has a fixed, hashable input; the paper itself belongs to its authors.

`paper/.gitattributes` marks this file `-text` so that git's `core.autocrlf`,
which is on by default on Windows, does not rewrite its line endings on checkout
and change the hash. Without that the checked-out file hashes to
`ed92e536...` on Windows and to the value above everywhere else. Verified: with
`core.autocrlf=true`, a fresh clone now checks out the pinned bytes.

If you re-fetch and the hash differs, arXiv has re-rendered the HTML. The
extractor asserts its own structural expectations and will fail loudly rather
than parse a changed page silently, so a mismatch is worth investigating before
trusting anything downstream of it. The line endings do not affect the parse
either way, since the extractor reads the file in text mode; the hash is pinned
so that the input is identifiable, not because the parser is fragile.

### 4. Python environment

```bash
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Verified on Python 3.13.7 with numpy 2.2.2, scipy 1.15.2, joblib 1.4.2 and
torch 2.7.0+cpu. On Linux, use the CPU wheel index for the same torch build:
`pip install torch==2.7.0 --index-url https://download.pytorch.org/whl/cpu`.

That is the whole setup. Everything below runs from this same `code/`.

---

## Layout after setup

```
repro-evaluating-llms-comparative-signals/
├── paper/paper_v2.html          <- step 3
├── results/                     <- copies of the outputs published with the logbook
└── code/                        <- the one working directory
    ├── requirements.txt
    ├── analysis/*.py            <- the reproduction scripts
    ├── kaggle/real_gsm8k_ppi.py <- the live GSM8K run, GPU, off this path
    ├── tools/                   <- logbook page generator, provenance only
    └── AI_evaluation/           <- step 2, the authors' unmodified package
```

---

## What each script establishes

| script | claim | what it does |
| --- | --- | --- |
| `analysis/claims12_eif_check.py` | 1, 2 | exact analytic check of the efficient influence function: `E[psi]=0` and the efficiency identity `Var(psi) = sigma^2_naive - E[u^2]`, plus sqrt(N)-consistency and KS normality |
| `analysis/exact_efficiency_bound.py` | 3 | derives the exact efficiency bound *including* the preference label `V` via truncated-Gaussian second moments, and compares it with the curve `simulation/config.py` actually plots |
| `analysis/vr_sweep.py` | 3 | runs the authors' unmodified `run_single_trial` across a sigma grid with a bootstrap CI on the variance reduction; includes an explicit positive control at the paper's own default sigma=1.0 |
| `analysis/extract_tables.py` | 4 | parses Tables 1-3 out of the arXiv HTML, binding each table to its caption by document position, behind four structural assertions |
| `analysis/claim4_noise_floor.py` | 4 | expresses all 60 published gains in units of binomial sampling noise at the reported N, simulates the paper's own `Improv.` metric under a no-signal null, and runs the aggregate sign test |
| `analysis/claim4_at_reported_N.py` | 4 | asks the same question on the authors' own simulator instead of analytically: runs `run_single_trial` with N set to each benchmark's reported size and reports the distribution of the paper's own `Improv` metric, behind a positive control at N=1000 |
| `analysis/gaussian_surrogate.py` | 5 | extends the ranking-gap sweep to sigma in [0.25, 64], 21x past the authors' own grid |

`vr_sweep.py` and `claim4_at_reported_N.py` are the two that import the authors'
package, so they are the two that need step 2. The other five are self-contained.

---

## The live GSM8K run

`kaggle/real_gsm8k_ppi.py` is the eighth script and the only one not on the
reproduction path above. It tests Claim 4 against first-hand LLM data instead of
against the paper's published table: it rebuilds the Section 5 evaluation setting
on real GSM8K, runs the one-step estimator, and bootstraps over which N-item
subset is labelled to produce the interval the paper never reports. Eight of the
45 checks in `verify_headlines.py` rest on its output.

It was reachable from the Claim 4 page and from nothing in this README, which is
why it is written down here: a script nothing links to is a script a reader
cannot find.

**You do not need to run it to check its result.** It wrote
`results/real_gsm8k_ppi.json`, that file is published, and `verify_headlines.py`
checks all eight of its figures in under a second with no GPU and no network; the
interval for the mean is recomputed, the rest are compared against the published
endpoints.
Running it yourself is the stronger form of verification, not the required one.

**What it needs, if you do run it.** Not pinned in `requirements.txt`, because
none of it is required for the reproduction path and pinning it would imply
otherwise. The versions below are read from the `env` block of
`results/real_gsm8k_ppi.json`, which the run recorded itself:

| package | version in the published run |
| --- | --- |
| torch | 2.10.0+cu128 |
| transformers | 5.0.0 |
| datasets | 5.0.0 |
| numpy | imported; version not recorded in the `env` block |
| scikit-learn | imported; version not recorded in the `env` block |
| vllm | **not installed in the published run.** See below. |

Hardware: 2x Tesla T4 (`sm_75`), Kaggle GPU kernel, internet enabled to pull the
models and the dataset. Models: Qwen2.5-1.5B-Instruct and Qwen2.5-3B-Instruct
evaluated, Qwen2.5-0.5B-Instruct and Qwen2-1.5B-Instruct as the auxiliary pair.

The vllm row is worth reading twice. The script prefers vllm for generation and
falls back to transformers when it is absent. In the run that produced the
published JSON it was absent every time, logged four times as
`[vllm unavailable: ModuleNotFoundError] falling back to transformers`. So the
published numbers came from the transformers path, and listing vllm as a
dependency of the result would describe a code path that did not execute. It is
an optional accelerator, and the fallback is what ran.

Two things do not carry version pins above, and neither is an oversight: numpy
and scikit-learn are imported by the script but were not written into the `env`
block it records, so no version for them exists in the published evidence.
Inventing one here would be worse than the gap.

---

## Running it

All from `code/`. Runtimes are measured, on CPU.

```bash
# Claims 1 and 2                                                    ~6 s
python analysis/claims12_eif_check.py

# Claim 3, analytic half                                           ~13 s
python analysis/exact_efficiency_bound.py

# Claim 4 (the second script imports the first, so keep the order)  ~1 s
python analysis/extract_tables.py && python analysis/claim4_noise_floor.py

# Claim 5                                                           ~5 s
python analysis/gaussian_surrogate.py

# Claim 3, simulation half. Slow: it re-runs the authors' trial loop.
python analysis/vr_sweep.py --sigmas 0.1 0.2 0.35 0.5 0.75 1.0 1.5 2.0 3.0 --R 40
python analysis/vr_sweep.py --sigmas 0.08 0.10 0.15 0.20 0.25 --R 250 --out vr_lowsigma.json

# Claim 4, simulator half. Also slow, for the same reason.       ~22 min
python analysis/claim4_at_reported_N.py
```

The two `vr_sweep.py` runs took roughly 21 minutes and 74 minutes respectively
on 14 workers; per-sigma timings are in `results/vr_sweep.log` and
`results/vr_lowsigma.log`. Use `--jobs N` to match your core count. The per-trial
seed is a function of the sigma index and the trial index only, so `--jobs` does
not change the numbers.

`claim4_at_reported_N.py` above is shown with its defaults. The published run
used different draw counts: the `draws` field in each row of
`results/claim4_at_reported_N.json` records what it actually used, and
`results/reported_N.log` records its per-block timings, which total about 22
minutes. Set `--reps` and `--control-reps` to match those draw counts if you
want to reproduce that run rather than a default one.

To sanity-check the wiring from step 2 before committing to a long run, one
sigma at low `R` takes about a minute and still prints the positive control:

```bash
python analysis/vr_sweep.py --sigmas 1.0 --R 8 --jobs 8 --out smoke.json
```

---

## Where the output lands, and what `results/` is

`results/` in this repository holds the exact outputs that the published logbook
quotes, so a reviewer can diff instead of only re-running. They are **copies**.
Nothing in the reproduction path writes into `results/`: the scripts below write
beside themselves, and the copies are made by `tools/stage_results.py`, which
globs the live outputs and refuses to stage an incomplete set.

That last clause used to read "the copies were made by hand", and it was true
when written. It stopped being true when staging was automated, which is the
same silent drift the staging exists to end, so it is corrected here rather than
left as a sentence that still reads plausibly.

| script | writes | to |
| --- | --- | --- |
| `analysis/claims12_eif_check.py` | `claims12_eif_check.json` | `code/analysis/` |
| `analysis/exact_efficiency_bound.py` | `exact_efficiency_bound.json` | `code/analysis/` |
| `analysis/extract_tables.py` | `tables_extracted.json` | `code/analysis/` |
| `analysis/claim4_noise_floor.py` | `claim4_noise_floor.json` | `code/analysis/` |
| `analysis/claim4_at_reported_N.py` | `claim4_at_reported_N.json` | `code/analysis/` |
| `analysis/gaussian_surrogate.py` | `surrogate_sweep.json` | `code/analysis/` |
| `analysis/vr_sweep.py` (default `--out`) | `vr_sweep_results.json` | `code/`, the working directory |
| `analysis/vr_sweep.py --out vr_lowsigma.json` | `vr_lowsigma.json` | `code/`, the working directory |
| `kaggle/real_gsm8k_ppi.py` | `real_gsm8k_ppi.json` | `/kaggle/working/`, on the GPU kernel |

`vr_sweep.py` is the one asymmetry: its `--out` is resolved against the working
directory, while every other script writes next to its own file. It prints the
absolute path it wrote, so you never have to guess.

`results/vr_sweep.log`, `results/vr_lowsigma.log` and `results/reported_N.log`
are captured stdout from those runs, not separate artifacts.

To diff a fresh run against what was published:

```bash
python - <<'EOF'
import json
for f in ["claims12_eif_check","exact_efficiency_bound","tables_extracted",
          "claim4_noise_floor","surrogate_sweep"]:
    a = json.load(open(f"analysis/{f}.json", encoding="utf-8"))
    b = json.load(open(f"../results/{f}.json", encoding="utf-8"))
    print(f"{f:28s} identical={a == b}")
EOF
```

---

## What is bit-reproducible and what is not

Claims 1, 2 and 5 reproduce exactly, end to end. Claims 3 and 4 each have an
analytic half that reproduces exactly and a simulator half that does not.

Verified on 2026-08-02: a fresh clone made by exactly the steps above, then the
five fast scripts run in order, produced five output files byte-identical to the
published `results/`.

| claim | script | reproducibility |
| --- | --- | --- |
| 1, 2 | `claims12_eif_check.py` | bit-identical, fixed seeds, numpy only |
| 3 (analytic) | `exact_efficiency_bound.py` | bit-identical, closed form |
| 4 (analytic) | `extract_tables.py`, `claim4_noise_floor.py` | bit-identical, given the pinned paper hash |
| 5 | `gaussian_surrogate.py` | bit-identical, fixed seeds, numpy only |
| 3 (simulation) | `vr_sweep.py` | **not** bit-identical across environments |
| 4 (simulator) | `claim4_at_reported_N.py` | **not** bit-identical across environments |

The two scripts that drive the authors' simulator are the exceptions, and the
reason is the estimator itself. Each trial trains a 5-fold cross-fitted MLP in
torch. Both scripts seed numpy and torch per trial, which pins the data and the
initialisation, but CPU floating-point reduction order in a torch build depends
on the BLAS/MKL it was compiled against and on threading, so a different torch
version or a different machine will land on slightly different weights and
therefore slightly different numbers out the far end. Both set
`torch.set_num_threads(1)` to remove the threading half of that, which is also
why the joblib worker count does not change the result, but the build half
remains.

Treat the confidence intervals those two write into `results/` as endpoints that
will not match to the digit. What should reproduce is the qualitative reading,
and each script states its own test for that. `vr_sweep.py` prints a positive
control at the paper's default sigma=1.0, where the empirical variance reduction
must track the theoretical 0.4096. `claim4_at_reported_N.py` prints one at
N=1000, where mean `Improv` must come out clearly positive. If either control
fails, the harness is wrong rather than the paper, and nothing downstream of it
should be believed.

---

## `code/tools/`

`tools/write_content.py` and `tools/build_pages.py` generate the logbook pages
from the JSON in `results/`. They are published for provenance, so the pages can
be traced to the numbers, and they are not part of the reproduction path above.
They expect the author's working repository layout, in which the analysis
outputs sit at `../work/analysis` relative to `tools/`. This repository is
flattened for publication and has no `work/` directory, so they will not run
here as-is. Everything the reproduction actually needs is in `analysis/`.

---

## Pins, in one place

| thing | value |
| --- | --- |
| paper | arXiv:2602.03061v2 [cs.LG], 20 Jul 2026 |
| paper HTML source | `https://arxiv.org/html/2602.03061v2`, fetched 2026-08-02 |
| paper HTML sha256 | `786287c822be49f23f209af7534a6e218039e95befc6a50ca6073e52a2744c65` (694941 bytes) |
| authors' code | `https://github.com/zihandong02/AI_evaluation` |
| authors' commit | `aa03c3064e532a13dc65e0d58aa62a1a5402260f` (2026-05-29) |
| OpenReview | `https://openreview.net/forum?id=nOQOjKYwTM` |
| python | 3.13.7 |
| packages | numpy 2.2.2, scipy 1.15.2, joblib 1.4.2, torch 2.7.0+cpu |
| live GSM8K run, separate environment | Kaggle, 2x Tesla T4, torch 2.10.0+cu128, transformers 5.0.0, datasets 5.0.0 |
| live GSM8K run, models | eval Qwen2.5-1.5B-Instruct and Qwen2.5-3B-Instruct; auxiliary Qwen2.5-0.5B-Instruct and Qwen2-1.5B-Instruct |
