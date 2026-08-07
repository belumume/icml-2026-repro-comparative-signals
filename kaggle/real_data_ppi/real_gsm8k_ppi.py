"""Claim 4 on REAL LLM data: the confidence interval the paper never reports.

WHY THIS EXISTS
---------------
The paper's Table 3 reports per-model accuracy gains on GSM8K at N=100 and calls
them "significantly closer to the ground truth", while reporting no uncertainty
anywhere ("bootstrap" and "standard error" each occur zero times in the full
text). The logbook's Claim 4 page shows analytically that a gain of the reported
size is inside binomial sampling noise at N=100.

This script tests the same question with FIRST-HAND DATA instead of an argument
about the published table. It rebuilds the paper's evaluation setting on real
GSM8K with real LLM generations, runs a one-step / prediction-powered estimator
of accuracy, and does the one thing the paper omits: it BOOTSTRAPS over which
N-item subset happens to be labelled, and reports the resulting interval on the
paper's own `Improv` metric.

SETTING (mirrors the paper's Section 5 evaluation, not its Gaussian simulation)
------------------------------------------------------------------------------
  theta          = a model's true accuracy on GSM8K
  phi(Y,G)       = 1{model's answer is correct}      (per-item score)
  X              = the question
  Z = (W1,W2,V)  = two cheap auxiliary models' answers, plus a preference label
  M items        carry auxiliary signals (cheap: no ground truth needed)
  N subset of M  carry ground-truth labels (expensive)

  naive     = mean(phi) over the N labelled items
  one-step  = mean(tau_hat) over all M  +  mean(phi - tau_hat) over the N
              i.e. the standard one-step / PPI correction, with tau_hat a
              cross-fitted model of phi given the auxiliary signal.
  Improv    = |naive - GT| - |one-step - GT|      (the paper's own metric)

GT is computed on the FULL evaluated set, so it is a real reference rather than
a circular one (unlike the paper's AIME table, where GT% is the naive estimator
on N=30 and the N=15 subset is drawn from those same 30 items).

POSITIVE CONTROL (reported alongside every result; NOT enforced in code -- the
  informative flag is recorded, not used as a gate, so a reader must check it
  rather than assume the script refused to report on a dead signal)
------------------------------------------------------------------
tau_hat must actually carry signal: its cross-fitted AUROC/accuracy for
predicting correctness from the auxiliary signal must beat the base rate. If the
auxiliary signal is uninformative, a null result says nothing about the paper's
method and the run reports that instead.

Outputs /kaggle/working/real_gsm8k_ppi.json
"""

import json
import os
import re
import sys
import time

import numpy as np

OUT = "/kaggle/working" if os.path.isdir("/kaggle/working") else "."
SEED = 20260802
rng = np.random.default_rng(SEED)

# Evaluated models (theta = each one's accuracy) and the two auxiliary responders.
EVAL_MODELS = [
    "Qwen/Qwen2.5-1.5B-Instruct",
    "Qwen/Qwen2.5-3B-Instruct",
]
AUX_MODELS = [
    "Qwen/Qwen2.5-0.5B-Instruct",
    "Qwen/Qwen2-1.5B-Instruct",
]

# AUX_MODELS must stay DISJOINT from EVAL_MODELS. Decoding is greedy, so a model
# appearing in both lists reproduces its own answers as an "auxiliary" signal,
# putting phi itself into the feature matrix. That drives AUROC to 1.0, makes the
# one-step estimate reproduce GT exactly, and manufactures a positive Improv with
# a CI excluding zero -- an artifact, not a finding. Qwen2-1.5B is a different
# model generation from Qwen2.5-1.5B, so it is a genuine third-party signal.
assert not (set(EVAL_MODELS) & set(AUX_MODELS)), (
    "aux/eval overlap would leak phi into the feature matrix"
)
M_ITEMS = 500  # items carrying auxiliary signals
N_LABELLED = 100  # the paper's Table 3 sample size
B_BOOT = 2000  # bootstrap resamples over which N items are labelled
MAX_NEW = 320


# ----------------------------------------------------------------- generation
def build_prompts(questions, tok):
    out = []
    for q in questions:
        msgs = [
            {
                "role": "system",
                "content": "Solve the math problem. Reason briefly, then give the final "
                "numeric answer on its own last line as: #### <number>",
            },
            {"role": "user", "content": q},
        ]
        out.append(
            tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        )
    return out


def generate(model_name, questions):
    """Greedy-decode answers. vLLM if present, else batched transformers."""
    t0 = time.time()
    try:
        from vllm import LLM, SamplingParams
        from transformers import AutoTokenizer

        tok = AutoTokenizer.from_pretrained(model_name)
        llm = LLM(
            model=model_name,
            dtype="half",
            gpu_memory_utilization=0.85,
            max_model_len=1024,
            enforce_eager=True,
        )
        outs = llm.generate(
            build_prompts(questions, tok),
            SamplingParams(temperature=0.0, max_tokens=MAX_NEW),
        )
        texts = [o.outputs[0].text for o in outs]
        del llm
        import gc, torch

        gc.collect()
        torch.cuda.empty_cache()
    except Exception as e:
        print(
            f"  [vllm unavailable: {type(e).__name__}] falling back to transformers",
            flush=True,
        )
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tok = AutoTokenizer.from_pretrained(model_name, padding_side="left")
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        mdl = AutoModelForCausalLM.from_pretrained(
            model_name, torch_dtype=torch.float16, device_map="cuda"
        ).eval()
        prompts = build_prompts(questions, tok)
        texts, BS = [], 32
        for i in range(0, len(prompts), BS):
            enc = tok(
                prompts[i : i + BS],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=768,
            ).to("cuda")
            with torch.no_grad():
                g = mdl.generate(
                    **enc,
                    max_new_tokens=MAX_NEW,
                    do_sample=False,
                    pad_token_id=tok.pad_token_id,
                )
            texts += tok.batch_decode(
                g[:, enc["input_ids"].shape[1] :], skip_special_tokens=True
            )
            print(f"    {min(i + BS, len(prompts))}/{len(prompts)}", flush=True)
        del mdl
        import gc

        gc.collect()
        torch.cuda.empty_cache()
    print(
        f"  {model_name}: {len(texts)} generations in {time.time() - t0:.0f}s",
        flush=True,
    )
    return texts


_NUM = re.compile(r"-?\d[\d,]*\.?\d*")


def extract(text):
    if "####" in text:
        tail = text.split("####")[-1]
        m = _NUM.search(tail)
        if m:
            return m.group(0).replace(",", "").rstrip(".")
    m = _NUM.findall(text)
    return m[-1].replace(",", "").rstrip(".") if m else None


def correct(pred, gold):
    if pred is None:
        return 0
    try:
        return int(abs(float(pred) - float(gold)) < 1e-4)
    except ValueError:
        return 0


# -------------------------------------------------------------- the estimator
def one_step(phi, feats, labelled_idx, n_splits=5, seed=0):
    """One-step / PPI estimate of mean(phi) using auxiliary features.

    tau_hat is cross-fitted ON THE LABELLED SUBSET ONLY (the honest setting:
    ground truth is what is expensive), then applied to all M items.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold

    M = len(phi)
    lab = np.asarray(labelled_idx)
    y = phi[lab]
    X = feats[lab]
    tau_all = np.full(M, y.mean(), dtype=float)
    oof = np.full(len(lab), y.mean(), dtype=float)

    if len(np.unique(y)) > 1:
        k = min(n_splits, int(min(np.bincount(y.astype(int)))) or 1)
        if k >= 2:
            skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=seed)
            models = []
            for tr, te in skf.split(X, y):
                m = LogisticRegression(max_iter=1000, C=1.0).fit(X[tr], y[tr])
                oof[te] = m.predict_proba(X[te])[:, 1]
                models.append(m)
            tau_all = np.mean([m.predict_proba(feats)[:, 1] for m in models], axis=0)

    naive = float(y.mean())
    onestep = float(tau_all.mean() + (y - oof).mean())
    return naive, onestep, oof, y


def preflight():
    """Record the exact environment and fail fast on an unusable GPU.

    A Pascal (sm_60) card is BELOW the minimum of recent PyTorch builds, which
    surfaces as an opaque 'no kernel image is available for execution on the
    device' only after several GB of model weights have already downloaded.
    Checking the arch list up front turns that into a two-second failure and
    pins the versions the reported numbers were produced with.
    """
    import datasets as _ds
    import torch
    import transformers

    info = {
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "datasets": _ds.__version__,
        "cuda_available": bool(torch.cuda.is_available()),
    }
    if torch.cuda.is_available():
        cap = torch.cuda.get_device_capability(0)
        arches = list(torch.cuda.get_arch_list())
        info.update(
            gpu=torch.cuda.get_device_name(0),
            capability=f"sm_{cap[0]}{cap[1]}",
            gpu_count=torch.cuda.device_count(),
            torch_arch_list=arches,
        )
        if f"sm_{cap[0]}{cap[1]}" not in arches:
            raise SystemExit(
                f"FATAL: {info['gpu']} is sm_{cap[0]}{cap[1]}, absent from this "
                f"PyTorch build's arch list {arches}. Re-push with a supported "
                f"accelerator (machine_shape) instead of burning a download."
            )
    print("preflight: " + json.dumps(info), flush=True)
    return info


def dump(results):
    p = os.path.join(OUT, "real_gsm8k_ppi.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
    print(f"wrote {p} ({len(results['models'])} model rows)", flush=True)


def main():
    from datasets import load_dataset

    print("=" * 78, flush=True)
    print("REAL-DATA CHECK: the CI the paper never reports", flush=True)
    print("=" * 78, flush=True)

    t_start = time.time()
    env = preflight()

    ds = load_dataset("openai/gsm8k", "main", split="test")
    idx = rng.choice(len(ds), size=M_ITEMS, replace=False)
    qs = [ds[int(i)]["question"] for i in idx]
    golds = [
        ds[int(i)]["answer"].split("####")[-1].strip().replace(",", "") for i in idx
    ]
    print(f"GSM8K test subset: M={M_ITEMS} items", flush=True)

    # auxiliary responders -> W1, W2 (generated once, shared across evaluated models)
    aux_pred = {}
    for am in AUX_MODELS:
        aux_pred[am] = [extract(t) for t in generate(am, qs)]

    w_corr = {
        am: np.array([correct(p, g) for p, g in zip(aux_pred[am], golds)])
        for am in AUX_MODELS
    }
    a1, a2 = AUX_MODELS
    agree = np.array(
        [
            int(aux_pred[a1][i] is not None and aux_pred[a1][i] == aux_pred[a2][i])
            for i in range(M_ITEMS)
        ]
    )
    # V: preference label, which auxiliary is closer to the truth
    V = (w_corr[a1] >= w_corr[a2]).astype(int)
    qlen = np.array([len(q.split()) for q in qs], dtype=float)
    qlen = (qlen - qlen.mean()) / (qlen.std() + 1e-9)

    results = {
        "config": {
            "M": M_ITEMS,
            "N": N_LABELLED,
            "B": B_BOOT,
            "seed": SEED,
            "eval_models": EVAL_MODELS,
            "aux_models": AUX_MODELS,
        },
        "env": env,
        "aux_accuracy_pct": {am: float(w_corr[am].mean() * 100.0) for am in AUX_MODELS},
        "models": [],
    }

    for em in EVAL_MODELS:
        phi = np.array(
            [correct(extract(t), g) for t, g in zip(generate(em, qs), golds)]
        )
        GT = float(phi.mean())
        feats = np.column_stack([w_corr[a1], w_corr[a2], agree, V, qlen]).astype(float)

        # --- positive control: does the auxiliary signal predict correctness? ---
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import cross_val_predict
        from sklearn.metrics import roc_auc_score

        try:
            pp = cross_val_predict(
                LogisticRegression(max_iter=1000),
                feats,
                phi,
                cv=5,
                method="predict_proba",
            )[:, 1]
            auroc = float(roc_auc_score(phi, pp))
        except Exception:
            auroc = float("nan")
        informative = auroc > 0.55

        boot = []
        for b in range(B_BOOT):
            lab = rng.choice(M_ITEMS, size=N_LABELLED, replace=False)
            nv, os_, _, _ = one_step(phi, feats, lab, seed=b)
            boot.append((abs(nv - GT) - abs(os_ - GT)) * 100.0)  # percentage points
        boot = np.array(boot)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        # Auditable evidence that no auxiliary vector IS phi (the leakage the
        # aux/eval disjointness assert prevents). Near-1.0 agreement here would
        # mean the "auxiliary" signal is really the ground-truth label.
        aux_phi_agreement = {am: float((w_corr[am] == phi).mean()) for am in AUX_MODELS}

        row = {
            "model": em,
            "GT_pct": GT * 100.0,
            "aux_auroc": auroc,
            "aux_informative": bool(informative),
            "aux_phi_agreement": aux_phi_agreement,
            "improv_mean_pp": float(boot.mean()),
            "improv_sd_pp": float(boot.std(ddof=1)),
            "improv_ci95_pp": [float(lo), float(hi)],
            "frac_improv_positive": float((boot > 0).mean()),
            "ci_spans_zero": bool(lo < 0 < hi),
        }
        results["models"].append(row)
        print(f"\n  {em}", flush=True)
        print(f"    GT accuracy on M={M_ITEMS}: {row['GT_pct']:.2f}%", flush=True)
        print(
            f"    auxiliary signal AUROC for correctness: {auroc:.3f} "
            f"({'informative' if informative else 'UNINFORMATIVE - control fails'})",
            flush=True,
        )
        print(
            f"    Improv at N={N_LABELLED}: mean {row['improv_mean_pp']:+.3f}pp  "
            f"sd {row['improv_sd_pp']:.3f}pp",
            flush=True,
        )
        print(
            f"    95% bootstrap CI: [{lo:+.3f}, {hi:+.3f}] pp   "
            f"P(Improv>0) = {row['frac_improv_positive']:.3f}",
            flush=True,
        )
        print(
            f"    -> CI {'SPANS ZERO' if row['ci_spans_zero'] else 'excludes zero'}",
            flush=True,
        )
        # Bank after every evaluated model: a run killed by a timeout during the
        # second model still leaves the first model's result on disk.
        dump(results)

    results["wall_clock_sec"] = round(time.time() - t_start, 1)
    dump(results)
    print(f"\ntotal wall clock: {results['wall_clock_sec']:.0f}s", flush=True)


if __name__ == "__main__":
    sys.exit(main())
