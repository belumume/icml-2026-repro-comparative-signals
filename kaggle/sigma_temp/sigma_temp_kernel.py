"""Does the low-sigma regime OCCUR? Measure a real model's spread across decoding temperature.

THE QUESTION, AND WHY IT IS THE STRONGEST OPEN OBJECTION TO OUR OWN FALSIFICATION
--------------------------------------------------------------------------------
The claim-3 page argues that the paper's Corollary 4.7 claim carries no range and says
"in practice", so testing outside the authors' sweep is fair. The authors' best available
reply is the one thing this reproduction has never measured:

    "in practice means sigma around 1, where our method works. You tested sigma = 0.08,
     a corner nobody deploys in."

Nothing in the logbook answers that. The nuisance ablation established WHY the estimator
fails at low sigma; it says nothing about WHETHER low sigma occurs. Different questions,
and only the first was settled.

This was deferred twice on reasoning that did not survive checking: that it needed an order
of magnitude more compute (the published GSM8K kernel ran in 1343 s on free-tier T4s), and
that the ablation had settled the question it addresses (it had not).

WHAT IS ACTUALLY MEASURED, as an OPERATIONALISATION rather than as "sigma"
-------------------------------------------------------------------------
In the authors' simulator an item's score is CONTINUOUS: Y = X + eps, eps ~ N(0, sigma^2).
A real LLM on GSM8K scores each item 0 or 1, and a Bernoulli's spread is pinned by its
mean, so no free sigma can be read off a single greedy pass.

The analogue that IS free is resampling spread. Ask the same question K times at
temperature T, take the per-question mean score in [0, 1], and measure how that varies.
At T = 0 decoding is deterministic and the spread is zero by construction. As T rises the
answers scatter, which is what sigma parameterises.

Reported per temperature: mean accuracy, the MEAN WITHIN-QUESTION SD of the per-question
score (the direct analogue of sigma), and the fraction of questions answered inconsistently.

HONEST LIMITS, stated before the run rather than after:
  * Temperature moves several things at once. It is a realistic knob, not a clean sigma
    dial, so this bounds where real decoding sits rather than isolating sigma.
  * The simulator's sigma is on the scale of the estimated metric; this spread is on a
    0-1 accuracy scale. Analogous, not identical units. The valid comparison is ORDINAL:
    does realistic decoding sit near the bottom of the authors' 0.5-to-3.0 grid, or far
    below it where the failure was found?
  * One benchmark, one model family. It cannot characterise every deployment.

GENERATION USES TRANSFORMERS, NOT vLLM, AND THAT IS DELIBERATE
--------------------------------------------------------------
The published GSM8K run's own log carries "vllm unavailable: ModuleNotFoundError, falling
back to transformers" FOUR times, so every published number here came from the transformers
path. A first draft of this kernel imported vLLM directly with no fallback and would have
crashed on start, burning a session slot. Checking the prior run's log rather than assuming
the dependency is what caught it.

CONTROL: the T = 0 arm must be exactly deterministic (within-question SD identically 0),
and its accuracy must sit near the published run's for this model. If either fails the
harness differs from the published one and no other row is readable.
"""

import gc
import json
import os
import re
import time

import numpy as np
import torch

OUT = "/kaggle/working" if os.path.isdir("/kaggle/working") else "."
SEED = 20260808
MODEL = "Qwen/Qwen2.5-1.5B-Instruct"  # the eval model of the published GSM8K run
N_Q = 100  # matches that run's labelled sample size
K = 8  # samples per question at nonzero temperature
TEMPS = [0.0, 0.3, 0.7, 1.0]
MAX_NEW = 320
BATCH = 32
BUDGET_S = 7.0 * 3600

ANS = re.compile(r"(-?\d[\d,]*\.?\d*)")


def gold(text):
    return text.split("####")[-1].strip().replace(",", "")


def pred(text):
    m = ANS.findall(text.replace(",", ""))
    return m[-1].rstrip(".") if m else None


def main():
    t0 = time.time()
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer

    rng = np.random.default_rng(SEED)
    ds = load_dataset("gsm8k", "main", split="test")
    idx = rng.choice(len(ds), size=N_Q, replace=False)
    qs = [ds[int(i)]["question"] for i in idx]
    gs = [gold(ds[int(i)]["answer"]) for i in idx]

    tok = AutoTokenizer.from_pretrained(MODEL, padding_side="left")
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    prompts = [
        tok.apply_chat_template(
            [
                {
                    "role": "user",
                    "content": q + "\n\nSolve step by step. End with the final number.",
                }
            ],
            tokenize=False,
            add_generation_prompt=True,
        )
        for q in qs
    ]

    mdl = AutoModelForCausalLM.from_pretrained(
        MODEL, torch_dtype=torch.float16, device_map="cuda"
    ).eval()

    results = {
        "model": MODEL,
        "n_questions": N_Q,
        "k_samples": K,
        "seed": SEED,
        "generation": "transformers (vLLM is absent on this image; see module docstring)",
        "operationalisation": (
            "per-question mean score over K samples at temperature T; the reported spread "
            "is the mean WITHIN-QUESTION SD of that score. Not the simulator's sigma in "
            "the same units; comparable ordinally."
        ),
        "rows": [],
    }

    def bank():
        results["secs"] = round(time.time() - t0, 1)
        with open(f"{OUT}/sigma_temp_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    def run(temperature, k):
        """k generations per prompt. Returns [n_questions][k] decoded strings."""
        per_q = [[] for _ in prompts]
        for rep in range(k):
            torch.manual_seed(SEED + rep)
            for i in range(0, len(prompts), BATCH):
                enc = tok(
                    prompts[i : i + BATCH],
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=768,
                ).to("cuda")
                with torch.no_grad():
                    g = mdl.generate(
                        **enc,
                        max_new_tokens=MAX_NEW,
                        do_sample=temperature > 0.0,
                        temperature=temperature if temperature > 0.0 else None,
                        top_p=1.0 if temperature > 0.0 else None,
                        pad_token_id=tok.pad_token_id,
                    )
                dec = tok.batch_decode(
                    g[:, enc["input_ids"].shape[1] :], skip_special_tokens=True
                )
                for j, txt in enumerate(dec):
                    per_q[i + j].append(txt)
            print(f"    T={temperature} rep {rep + 1}/{k}", flush=True)
        return per_q

    print(f"model {MODEL}, {N_Q} questions, K={K}, temps {TEMPS}\n", flush=True)
    for T in TEMPS:
        if time.time() - t0 > BUDGET_S:
            print(f"  budget reached before T={T}; banked rows are on disk")
            results["truncated_at"] = T
            bank()
            break
        t = time.time()
        # K=1 at T=0: greedy decoding is deterministic, so K samples would be K identical
        # strings and the SD would be 0 by construction rather than by measurement.
        # Saying so beats spending 8x the compute to rediscover it.
        k = 1 if T == 0.0 else K
        texts = run(T, k)

        scores = [
            [1.0 if pred(c) == g else 0.0 for c in cs] for cs, g in zip(texts, gs)
        ]
        means = np.array([np.mean(s) for s in scores])
        within = np.array([np.std(s, ddof=1) if len(s) > 1 else 0.0 for s in scores])
        row = {
            "temperature": T,
            "k": k,
            "mean_accuracy": float(means.mean()),
            "mean_within_question_sd": float(within.mean()),
            "across_question_sd": float(means.std(ddof=1)),
            "frac_inconsistent": float(np.mean([0 < np.mean(s) < 1 for s in scores])),
            "secs": round(time.time() - t, 1),
        }
        results["rows"].append(row)
        bank()
        print(
            f"  T={T:<4} acc={row['mean_accuracy']:.3f}  within-q SD="
            f"{row['mean_within_question_sd']:.4f}  inconsistent="
            f"{row['frac_inconsistent']:.2f}  ({row['secs']}s)",
            flush=True,
        )

    z = next((r for r in results["rows"] if r["temperature"] == 0.0), None)
    results["control_determinism_ok"] = bool(z and z["mean_within_question_sd"] == 0.0)
    results["control_note"] = (
        "Compare mean_accuracy at T=0 against this model's accuracy in "
        "results/real_gsm8k_ppi.json. A mismatch beyond sampling means the harness "
        "differs from the published run and no row here is readable."
    )
    print(f"\ncontrol, greedy is deterministic: {results['control_determinism_ok']}")
    bank()

    del mdl
    gc.collect()
    torch.cuda.empty_cache()
    print(f"wrote {OUT}/sigma_temp_results.json ({results['secs']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
