"""Score the submission texts with Pangram, using the key from Proton Pass.

The key is read from Pass at runtime and never printed. Async task API:
  POST https://text.external-api.pangram.com/task   -> {"id": ...}
  GET  .../task/<id>  until stage is STAGE_SUCCESS
"""

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

PASS = "C:/Users/<user>/AppData/Local/Programs/ProtonPass/pass-cli.exe"
BASE = "https://text.external-api.pangram.com"


def key():
    out = subprocess.run(
        [
            PASS,
            "item",
            "view",
            "--vault-name",
            "Personal",
            "--item-title",
            "pangram.com",
            "--field",
            "password",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    k = (out.stdout or "").splitlines()
    k = k[0].strip() if k else ""
    if not k:
        print("could not read the api key from Pass", file=sys.stderr)
        sys.exit(2)
    return k


def call(method, path, api_key, payload=None):
    req = urllib.request.Request(
        BASE + path,
        method=method,
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        data=json.dumps(payload).encode() if payload else None,
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def score(name, text, api_key):
    try:
        t = call("POST", "/task", api_key, {"text": text})
    except urllib.error.HTTPError as e:
        print(
            f"  {name}: POST failed {e.code} {e.read()[:200].decode(errors='replace')}"
        )
        return None
    tid = t.get("id") or t.get("task_id") or t.get("taskId")
    if not tid:
        print(f"  {name}: no task id in {list(t)[:6]}")
        return None
    for _ in range(40):
        time.sleep(3)
        try:
            r = call("GET", f"/task/{tid}", api_key)
        except urllib.error.HTTPError as e:
            print(f"  {name}: poll failed {e.code}")
            return None
        stage = r.get("stage", "")
        if stage in ("STAGE_SUCCESS", "STAGE_FAILED"):
            return r
    print(f"  {name}: timed out polling")
    return None


TEXTS = {
    "X POST": """arXiv 2602.03061 proposes an estimator that measures LLM accuracy more precisely than a plain average, and reports it winning in all 60 model-benchmark cells while giving an uncertainty interval for none of them. The words "bootstrap" and "standard error" do not appear anywhere in it, so there is nothing to check those sixty numbers against.

I ran their own simulator unmodified. At low model noise the variance reduction comes out at -0.33, which is 33% more variance than the plain average rather than less, with a 95% CI of [-0.495, -0.185] over 250 runs and their default setting passing as a control.

Four of their five claims survived. The small aggregate effect their Corollary 4.7 predicts is there in the data; the sixty per-cell wins are not, and with no intervals reported there was never a way to tell those apart.""",
    "FORM": """The paper claims its estimator measures an LLM's benchmark accuracy more precisely than a simple average, and it reports a win in all 60 model-benchmark cells without giving an uncertainty interval for a single one. Running their own simulator unmodified, at low model noise the variance reduction comes out negative: -0.33, so the estimator carries 33% more variance than the average it replaces, 95% CI [-0.495, -0.185] over 250 runs with their default setting passing as a control. What survives is the weaker claim their own Corollary 4.7 predicts, that the effect is real in aggregate but not resolvable in any one cell, and a live GSM8K run on open-weight models agrees. Every number in the logbook re-derives from the published results in about a second, with no GPU, no API key and nothing to install.""",
}


def main():
    k = key()
    print(f"key loaded ({len(k)} chars), never printed\n")
    for name, t in TEXTS.items():
        w = len(t.split())
        print(f"{name}  ({w} words){'  <-- under the 50-word floor' if w < 50 else ''}")
        r = score(name, t, k)
        if not r:
            continue
        print(f"  stage      : {r.get('stage')}")
        print(f"  prediction : {r.get('prediction')}")
        for f in (
            "ai_likelihood",
            "fraction_ai",
            "fraction_ai_assisted",
            "fraction_human",
        ):
            if f in r:
                print(f"  {f:22}: {r[f]}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
