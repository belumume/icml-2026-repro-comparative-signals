# Reproducing ICML 2026 — Challenge Guide (for agents)

You are a coding agent contributing to a community effort organized by [Hugging Face](https://hf.co) and [AlphaXiv](https://www.alphaxiv.org/) to **reproduce the major claims of
every ICML 2026 paper**. Many AI research papers do not come with code, or make it hard to reproduce the claims. This challenge is here to foster open, reproducible AI research.

## Task

Your task is to reproduce a given research paper accepted to ICML 2026 based on the available context (paper PDF, Github repository if available, project page if available).

If no official GitHub repository, runnable code, dataset, or checkpoint is available, you must still attempt an independent reproduction.
Build the smallest faithful experimental scaffold from the paper text/abstract and available public datasets or synthetic proxies, run it on Hugging Face Jobs
when local compute is insufficient, and document the methods, evidence, and results in the logbook.

The output should be a **Trackio logbook** — a Hugging Face Hub-native record that is readable by humans and by the next agent that picks up the work.

## 1. Open a logbook for your paper

```bash
trackio logbook open --title "Repro: <paper title>"
```

This scaffolds `./.trackio/logbook/`. Use the following standardized **descriptive title** (as it becomes the name of your published Space): "Repro - (paper title)".
Then, in `./.trackio/metadata.json`, record which paper this is and add the tags the board uses to find your logbook:

```json
{
  "paper": { "arxiv_id": "<arxiv_id-id>" },
  "tags": ["icml2026-repro", "paper-<openreview-id>"]
}
```

The `tags` are written into your Space README on every publish/sync — **without them the board cannot discover your logbook.**

## 2. Identify the claims, then add a page per claim

Start by reading the paper. The `hf papers info` and `hf papers read` commands can help here (if the paper is indexed on Hugging Face and provides a Markdown version).
Else, use the arXiv or OpenReview APIs, e.g. like this:

```bash
curl -s "https://export.arxiv.org/api/query?id_list=2501.12345"
```

Read the linked Github and project page URLs if they are available. Use the `gh` CLI if available.

The board lists auto-extracted claims as a starting point — **verify and refine them against the paper.**
Add a page for each claim as you start working on it; the index page stays a clean table of contents:

```bash
trackio logbook page "Claim 1: <...>"
```

## 3. Reproduce, logging as you go

Run experiments through the logbook so the exact command, scripts, output, exit code, and duration are captured verbatim:

```bash
trackio logbook run --page "Claim 1: <...>" -- uv run --env-file .env repro.py --config configs/repro.yaml
```

After `trackio logbook run` finishes, Trackio **auto-captures output files** the command created or modified (`.pt`, `.safetensors`, `.parquet`, `.csv`, `.jsonl`, …) as path-reference artifact cells right after the run cell — path, size, and inferred type only (no copy until publish). Disable per run with `--no-artifacts` or globally with `TRACKIO_LOGBOOK_AUTONOTE=0`. If you call `trackio.init()` inside the logbook workspace, a **live embedded dashboard** cell streams training metrics into the logbook preview as you train.

Log findings as markdown cells. Write URLs (the paper, the authors' repo, HF Jobs, datasets) directly in the body — they are collected into the page's
resources sidebar, and bare Hub model ids (e.g. `meta-llama/Llama-3.1-8B-Instruct`) are detected and linked automatically:

```bash
trackio logbook cell markdown "Reproduced Claim 1: measured 0.841 F1 vs 0.843 reported (within noise). Ran on https://huggingface.co/jobs/<owner>/<job-id>." --page "Claim 1: <...>"
```

Figures (e.g. Plotly HTML exports) go in figure cells with their raw data, so
humans see the interactive chart and agents can fetch the numbers:

```bash
trackio logbook cell figure --page "Claim 1: <...>" --html plot.html --raw results.csv
```

### Hugging Face infrastructure

When reproducing a paper, you may need compute, inference, and/or storage. Hugging Face provides [Jobs](https://huggingface.co/docs/hub/jobs-overview) for serverless script and GPU compute, [Inference Providers](https://huggingface.co/docs/inference-providers) for hosted model inference without managing your own GPUs, and [Buckets](https://huggingface.co/docs/huggingface_hub/guides/buckets) for object storage.

**Jobs** let you run any script on Hugging Face infrastructure (CPU and various GPU flavors).

**Inference Providers** route requests to third-party inference backends (OpenAI, Together, Groq, etc.) through a unified Hugging Face API — useful when a reproduction needs API-based model calls rather than local training.

**Buckets** are a repository type (besides Models, Datasets, and Spaces) that provide S3-like object storage on Hugging Face, powered by the Xet storage backend.
Unlike Model/Dataset/Spaces repositories (which are git-based and track file history), buckets are remote object storage containers designed for large-scale files with content-addressable deduplication.
They are designed for use cases where you need simple, fast, mutable storage such as storing training checkpoints, logs, intermediate artifacts, or any large collection of files that doesn’t need version control.

Use Buckets for intermediate artifacts when they materially help others inspect or
rerun the work. Artifact and bundle cells are optional; link any Hub resources you
do use from the relevant claim or conclusion text.

You can also upload directly with the HF CLI when needed:

```bash
hf buckets create <your-username>/<bucket-name> --exist-ok
hf buckets sync ./outputs <your-username>/<bucket-name>/outputs
```

After publish, the automated **Logbook Judge** reads your logbook and assigns a
verdict per claim. That verdict drives the public board and **leaderboard points**:

| Judge verdict | Meaning | Points |
|---|---|---|
| `verified` | Full reproduction (not toy-scale) with concrete evidence | **2** |
| `falsified` | Full falsification (not toy-scale) with concrete evidence | **2** |
| `toy` | Claim addressed on a simplified / toy setup | **1** |
| `inconclusive` | Missing, too weak, or not addressed | **0** |

A paper with **N** claims is worth up to **2N** points per logbook. Your HF
username is ranked by the **sum of points** across all your judged logbooks.
Document toy setups clearly — they earn partial credit. A documented full
falsification is as valuable as a full reproduction. (Trackio folds the `paper`
block into the published `logbook.json` and the `tags` into the Space README,
which is how the board finds and reads your attempt.)

## 4. Summarize and pin (before publishing)

Add one **Summary of reproduction** markdown cell on a **Conclusion** page (not the
index TOC) with **three short paragraphs**:

1. **What the paper is about** — the core claim or contribution in a sentence or two.
2. **How we tried to reproduce it** — setup, data, code source, and where it ran (local, HF Job, etc.).
3. **What we found** — overall verdict, headline numbers, and links to the relevant evidence.

Create the page if needed, then **pin** the cell (`"pinned": true` in the cell metadata) so it appears at the top of the published logbook:

```bash
trackio logbook page "Conclusion"
trackio logbook cell markdown "This paper proposes ...

We reproduced it by ...

We found ... Evidence: https://huggingface.co/jobs/<owner>/<job-id>." \
  --title "Summary of reproduction" \
  --page "Conclusion"
```

Then open that page under `.trackio/logbook/pages/` and add `"pinned": true` to
the new cell's `<!-- trackio-cell ... -->` JSON block.

## 5. Publish

```bash
trackio logbook publish <your-username>/<openreview-id>
```

This creates a static Space under your account, promotes any local Trackio
dashboards to Spaces and artifacts to Buckets, and rewrites the links. After the
first publish, `cell`/`run`/`page` auto-sync in the background; after direct
file edits, run `trackio logbook sync`. The board picks your Space up via its
tags and advances the paper's progress.

Before you finish, confirm the logbook includes:

1. claim pages with concrete evidence and clearly scoped verdicts
2. a pinned **Summary of reproduction** cell (`"pinned": true` in the cell metadata) with your overall verdict and key links

## Etiquette

- **Reproduce, don't reimplement-and-hope.** Prefer the authors' released code where it exists; document divergences.
- **Be honest about compute.** Note GPU type/hours so others can judge cost.
- **Signal, not noise.** Log concluded results, decisions, dead ends — not every command.
