"""Winner-consideration submission form for the ICML-2026 Open Reproductions challenge.

Participants who want to be considered for a prize submit this form. To be
eligible they must have publicly shared their logbook or poster (a link to a
LinkedIn / X / equivalent post is required). They can also opt in to the three
special awards, each of which requires a public logbook Space (with traces) we
can inspect:

  - Highest-Quality, Human-in-the-Loop Reproduction Award
  - Best Falsification / Negative Result Award
  - Best Open-Weights Reproduction with OpenResearch

Submissions are appended to a PRIVATE dataset under the abidlabs namespace, so
only the organizers can see them (same pattern as the credit-request form).
"""

import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from huggingface_hub import HfApi, hf_hub_download

DATASET_ID = os.getenv("SUBMISSIONS_DATASET", "abidlabs/icml-2026-winner-submissions")
SUBMISSIONS_FILE = "submissions.jsonl"
HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN")
CHALLENGE_URL = "https://huggingface.co/spaces/ICML-2026-agent-repro/challenge"
DISCUSSIONS_URL = f"{CHALLENGE_URL}/discussions"
OPENRESEARCH_URL = "https://openresearch.sh/"
SUBMISSION_DEADLINE = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
SUBMISSION_DEADLINE_LABEL = (
    "Sunday, August 2, 2026 at 11:59 PM Anywhere on Earth (AoE)"
)
MAX_EXPLANATION_CHARS = 1500

app = FastAPI(
    title="ICML 2026 Open Reproductions — winner submission",
    description="Form for participants who want to be considered for a prize.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_hf = HfApi(token=HF_TOKEN)


def _valid_username(username: str) -> bool:
    return bool(
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,94}[A-Za-z0-9])?", username or "")
    )


def _valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or ""))


def _valid_url(value: str) -> bool:
    return bool(re.fullmatch(r"https?://[^\s]+\.[^\s]+", (value or "").strip()))


def _submissions_open(now: datetime | None = None) -> bool:
    return (now or datetime.now(timezone.utc)) < SUBMISSION_DEADLINE


def _normalize_space_url(value: str) -> tuple[str, str]:
    value = (value or "").strip()
    if not value:
        return "", ""
    match = re.search(r"huggingface\.co/spaces/([^/\s]+/[^/\s?#]+)", value)
    if match:
        space_id = match.group(1)
        return space_id, f"https://huggingface.co/spaces/{space_id}"
    if re.fullmatch(r"[^/\s]+/[^/\s]+", value):
        return value, f"https://huggingface.co/spaces/{value}"
    return "", value


def _current_jsonl() -> str:
    try:
        path = hf_hub_download(
            repo_id=DATASET_ID,
            filename=SUBMISSIONS_FILE,
            repo_type="dataset",
            token=HF_TOKEN,
            force_download=True,
        )
    except Exception:
        return ""
    return Path(path).read_text()


def _append_submission(record: dict) -> None:
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN is not configured on this Space.")
    _hf.create_repo(
        repo_id=DATASET_ID,
        repo_type="dataset",
        private=True,
        exist_ok=True,
        token=HF_TOKEN,
    )
    existing = _current_jsonl()
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    payload = (existing.rstrip("\n") + "\n" if existing.strip() else "") + line + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tmp:
        tmp.write(payload)
        tmp_path = tmp.name
    try:
        _hf.upload_file(
            path_or_fileobj=tmp_path,
            path_in_repo=SUBMISSIONS_FILE,
            repo_id=DATASET_ID,
            repo_type="dataset",
            token=HF_TOKEN,
            commit_message="Add winner-consideration submission",
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.get("/", response_class=HTMLResponse)
async def form():
    return (
        _PAGE.replace("__CHALLENGE_URL__", CHALLENGE_URL)
        .replace("__DISCUSSIONS_URL__", DISCUSSIONS_URL)
        .replace("__OPENRESEARCH_URL__", OPENRESEARCH_URL)
        .replace("__SUBMISSION_DEADLINE__", SUBMISSION_DEADLINE_LABEL)
    )


@app.post("/submit")
async def submit(payload: dict):
    if not _submissions_open():
        return {
            "ok": False,
            "error": f"Winner submissions closed on {SUBMISSION_DEADLINE_LABEL}.",
        }

    username = (payload.get("hf_username") or "").strip()
    email = (payload.get("email") or "").strip()
    social_post_url = (payload.get("social_post_url") or "").strip()
    if not _valid_username(username):
        return {"ok": False, "error": "Enter a valid Hugging Face username."}
    if not _valid_email(email):
        return {"ok": False, "error": "Enter a valid email address."}
    if not _valid_url(social_post_url):
        return {
            "ok": False,
            "error": "Add a public link to your post (LinkedIn, X, or equivalent).",
        }

    want_hitl = bool(payload.get("interested_hitl"))
    want_falsification = bool(payload.get("interested_falsification"))
    want_openresearch = bool(payload.get("interested_openresearch"))

    hitl_id, hitl_url = _normalize_space_url(payload.get("hitl_space_url") or "")
    fals_id, fals_url = _normalize_space_url(payload.get("falsification_space_url") or "")
    hitl_explanation = (payload.get("hitl_explanation") or "").strip()
    falsification_explanation = (
        payload.get("falsification_explanation") or ""
    ).strip()
    openresearch_id, openresearch_url = _normalize_space_url(
        payload.get("openresearch_space_url") or ""
    )
    openresearch_explanation = (
        payload.get("openresearch_explanation") or ""
    ).strip()

    if want_hitl and not hitl_url:
        return {
            "ok": False,
            "error": "Add the public Space URL of your Human-in-the-Loop logbook.",
        }
    if want_falsification and not fals_url:
        return {
            "ok": False,
            "error": "Add the public Space URL of your Falsification logbook.",
        }
    if want_hitl and not hitl_explanation:
        return {
            "ok": False,
            "error": "Explain how your logbook fits the Human-in-the-Loop award in 2–3 sentences.",
        }
    if want_falsification and not falsification_explanation:
        return {
            "ok": False,
            "error": "Explain how your logbook fits the Falsification award in 2–3 sentences.",
        }
    if want_openresearch and not openresearch_url:
        return {
            "ok": False,
            "error": "Add the public Space URL of your OpenResearch logbook.",
        }
    if want_openresearch and not openresearch_explanation:
        return {
            "ok": False,
            "error": "Name the open-weights main model and explain how you used the OpenResearch CLI harness.",
        }
    if len(hitl_explanation) > MAX_EXPLANATION_CHARS:
        return {
            "ok": False,
            "error": "Keep the Human-in-the-Loop explanation under 1,500 characters.",
        }
    if len(falsification_explanation) > MAX_EXPLANATION_CHARS:
        return {
            "ok": False,
            "error": "Keep the Falsification explanation under 1,500 characters.",
        }
    if len(openresearch_explanation) > MAX_EXPLANATION_CHARS:
        return {
            "ok": False,
            "error": "Keep the OpenResearch explanation under 1,500 characters.",
        }

    record = {
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "hf_username": username,
        "email": email,
        "social_post_url": social_post_url,
        "interested_hitl": want_hitl,
        "hitl_space_id": hitl_id if want_hitl else "",
        "hitl_space_url": hitl_url if want_hitl else "",
        "hitl_explanation": hitl_explanation if want_hitl else "",
        "interested_falsification": want_falsification,
        "falsification_space_id": fals_id if want_falsification else "",
        "falsification_space_url": fals_url if want_falsification else "",
        "falsification_explanation": (
            falsification_explanation if want_falsification else ""
        ),
        "interested_openresearch": want_openresearch,
        "openresearch_space_id": openresearch_id if want_openresearch else "",
        "openresearch_space_url": openresearch_url if want_openresearch else "",
        "openresearch_explanation": (
            openresearch_explanation if want_openresearch else ""
        ),
    }
    try:
        _append_submission(record)
    except Exception as exc:
        return {"ok": False, "error": f"Could not save your submission yet: {exc}"}
    return {
        "ok": True,
        "message": "Submission received. The organizers will review your logbooks directly — thanks for sharing your work publicly!",
    }


_PAGE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>ICML 2026 — Winner Submission</title>
    <style>
      :root {
        --paper: #fdfcf9;
        --panel: #ffffff;
        --ink: #1f2937;
        --muted: #6b7280;
        --line: #e5e7eb;
        --accent: #f97316;
        --accent-strong: #ea580c;
        --accent-soft: #fff7ed;
        --grid-line: rgba(31, 41, 55, 0.045);
        --mono: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
        --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        --serif: ui-serif, "Iowan Old Style", "Palatino Linotype", Georgia, serif;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        background-color: var(--paper);
        background-image:
          linear-gradient(var(--grid-line) 1px, transparent 1px),
          linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
        background-size: 26px 26px;
        color: var(--ink);
        font-family: var(--sans);
        font-size: 16px;
        line-height: 1.5;
        -webkit-font-smoothing: antialiased;
      }
      .wrap { max-width: 980px; margin: 0 auto; padding: 0 20px 44px; }
      .hero {
        background: linear-gradient(180deg, #17181c 0%, #1e2027 100%);
        color: #fff;
        border-radius: 0 0 16px 16px;
        padding: 28px 32px 30px;
        margin: 0 -20px 26px;
      }
      .logos { display: flex; gap: 18px; align-items: center; flex-wrap: wrap; margin-bottom: 24px; color: #b7b9c2; font-size: 14px; }
      .logos span { display: inline-flex; align-items: center; gap: 6px; }
      .hero h1 {
        font-family: var(--serif);
        font-size: 34px;
        line-height: 1.1;
        margin: 0 0 10px;
      }
      .hero p { color: #c3c4cb; font-size: 15px; line-height: 1.55; max-width: 760px; margin: 0; }
      .hero .deadline { color: #fed7aa; margin-top: 12px; font-size: 14px; }
      .hero a, footer a { color: #fdba74; font-weight: 700; text-decoration: none; }
      .prizes { margin: 0 0 24px; }
      .prizes-head h2 { font-family: var(--serif); font-size: 20px; margin: 0 0 5px; }
      .prizes-head p { color: var(--muted); font-size: 15px; line-height: 1.55; margin: 0 0 14px; }
      .prize-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
      .prize {
        position: relative;
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 10px;
        padding: 14px 14px 15px 16px;
        overflow: hidden;
      }
      .prize::before {
        content: "";
        position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
        background: var(--accent);
      }
      .prize.gold::before { background: linear-gradient(180deg, #f4c04e, #d99a15); }
      .prize.silver::before { background: linear-gradient(180deg, #ccd0d8, #9aa1ad); }
      .prize-top { display: flex; align-items: baseline; justify-content: space-between; gap: 6px; margin-bottom: 3px; }
      .medal { font-size: 18px; line-height: 1; }
      .prize .amount { font-family: var(--serif); font-size: 20px; font-weight: 700; color: var(--accent-strong); line-height: 1; }
      .prize.gold .amount { color: #b8860b; }
      .prize h3 { font-family: var(--serif); font-size: 15px; line-height: 1.3; margin: 4px 0; }
      .prize .crit { color: var(--muted); font-size: 14px; line-height: 1.45; margin: 0; }
      .prizes-note { color: var(--muted); font-size: 14px; line-height: 1.5; margin: 14px 0 0; }
      .credit-award {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 16px;
        align-items: center;
        margin-top: 12px;
        padding: 16px 18px;
        border: 1px solid #bae6d3;
        border-radius: 10px;
        background: #f0fdf7;
      }
      .credit-amount {
        font-family: var(--serif);
        font-size: 22px;
        font-weight: 700;
        color: #047857;
        white-space: nowrap;
      }
      .credit-award h3 { font-family: var(--serif); font-size: 17px; margin: 0 0 3px; }
      .credit-award p { color: var(--muted); font-size: 14px; line-height: 1.5; margin: 0; }
      .credit-award a { color: #047857; font-weight: 700; text-decoration: none; }
      form {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 10px 30px rgba(30, 20, 80, 0.06);
      }
      .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; align-items: start; }
      .field { display: grid; align-content: start; gap: 7px; margin-bottom: 16px; }
      label {
        font-family: var(--mono);
        font-size: 12px;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        font-weight: 700;
      }
      input[type="text"], input[type="email"], input[type="url"], textarea {
        width: 100%;
        min-height: 50px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--paper);
        color: var(--ink);
        padding: 11px 12px;
        font: inherit;
      }
      textarea { min-height: 86px; resize: vertical; line-height: 1.45; }
      input:focus, textarea:focus { outline: 2px solid var(--accent); border-color: transparent; }
      .hint { color: var(--muted); font-size: 14px; line-height: 1.45; margin: -2px 0 0; }
      .divider { height: 1px; background: var(--line); margin: 8px 0 20px; }
      .section-title { font-family: var(--serif); font-size: 20px; margin: 0 0 4px; }
      .section-sub { color: var(--muted); font-size: 15px; line-height: 1.5; margin: 0 0 18px; }
      .opt {
        border: 1px solid var(--line);
        border-radius: 10px;
        padding: 16px 18px;
        margin-bottom: 14px;
        background: var(--paper);
      }
      .opt.checked { border-color: var(--accent); background: var(--accent-soft); }
      .check {
        display: flex;
        gap: 12px;
        align-items: flex-start;
        cursor: pointer;
        font-family: var(--sans);
        font-size: 16px;
        font-weight: 400;
        letter-spacing: normal;
        text-transform: none;
      }
      .check input { margin-top: 3px; width: 18px; height: 18px; accent-color: var(--accent-strong); flex: 0 0 auto; }
      .check-body strong { display: block; font-size: 16px; line-height: 1.35; margin-bottom: 3px; }
      .check-body span { color: var(--muted); font-size: 14px; line-height: 1.5; }
      .reveal { display: none; margin: 14px 0 0; }
      .opt.checked .reveal { display: block; }
      button {
        border: 0;
        border-radius: 8px;
        background: var(--accent-strong);
        color: #fff;
        cursor: pointer;
        font-family: var(--mono);
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        padding: 12px 16px;
        white-space: nowrap;
      }
      .status {
        display: none;
        margin-top: 16px;
        border-radius: 8px;
        padding: 12px 14px;
        background: var(--accent-soft);
        border: 1px solid #fed7aa;
        color: var(--ink);
      }
      .status.err { background: #fef2f2; border-color: #fecaca; }
      footer { color: var(--muted); font-size: 13px; text-align: center; margin-top: 18px; }
      footer a { color: var(--accent-strong); }
      @media (max-width: 720px) {
        .grid { grid-template-columns: 1fr; }
        .prize-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .hero { padding: 24px 22px; }
        .credit-award { grid-template-columns: 1fr; gap: 5px; }
      }
    </style>
  </head>
  <body>
    <div class="wrap">
      <section class="hero">
        <div class="logos">
          <span>🎯 Trackio</span>
          <span>🤗 Hugging Face</span>
          <span>📈 alphaXiv</span>
        </div>
        <h1>Submit for winner consideration</h1>
        <p class="deadline"><strong>Submission deadline:</strong> __SUBMISSION_DEADLINE__.</p>
      </section>

      <section class="prizes">
        <div class="prizes-head">
          <h2>Prizes</h2>
          <p>The top two places are set by verified leaderboard points; the three special
          awards are decided by the organizers reviewing logbooks. For consideration, you
          must <b>publicly share your logbook or poster and link to that social media post below</b>. Either way,
          every winner is verified from the actual logbooks, so make sure yours
          is public and inspectable.</p>
        </div>
        <div class="prize-grid">
          <div class="prize gold">
            <div class="prize-top"><span class="medal">🥇</span><span class="amount">$2,000</span></div>
            <h3>First place</h3>
            <p class="crit">Most verified points on the leaderboard.</p>
          </div>
          <div class="prize silver">
            <div class="prize-top"><span class="medal">🥈</span><span class="amount">$1,000</span></div>
            <h3>Second place</h3>
            <p class="crit">Second-most verified points on the leaderboard.</p>
          </div>
          <div class="prize">
            <div class="prize-top"><span class="medal">⭐</span><span class="amount">$500</span></div>
            <h3>Best Human-in-the-Loop</h3>
            <p class="crit">A logbook that shows a most rigorous, fully verified reproduction needing human intervention.</p>
          </div>
          <div class="prize">
            <div class="prize-top"><span class="medal">🔬</span><span class="amount">$500</span></div>
            <h3>Best Falsification</h3>
            <p class="crit">A logbook that shows a strongest negative result and produces a <em>different</em> claim that is true.</p>
          </div>
        </div>
        <div class="credit-award">
          <div class="credit-amount">$500</div>
          <div>
            <h3>OpenResearch Open-Weights Award</h3>
            <p>For the best reproduction that uses an <b>open-weights model as the main agent</b>
            with the <a href="__OPENRESEARCH_URL__" target="_blank" rel="noopener">OpenResearch CLI (<code>orx</code>)</a>
            harness. The winner receives $500.</p>
          </div>
        </div>
        <p class="prizes-note">All award decisions are entirely at the organizers' discretion.
        The four prizes above are Hugging Face GPU credits. Everyone with at least one
        verified logbook also receives a certificate of participation.</p>
      </section>

      <form id="winner-form">
        <div class="grid">
          <div class="field">
            <label for="username">Hugging Face username</label>
            <input id="username" name="username" type="text" placeholder="e.g. abidlabs" autocomplete="username" required />
          </div>
          <div class="field">
            <label for="email">Email address</label>
            <input id="email" name="email" type="email" placeholder="you@example.com" autocomplete="email" required />
          </div>
        </div>

        <div class="field">
          <label for="social">Public post about your logbook or poster</label>
          <input id="social" name="social" type="url" placeholder="https://www.linkedin.com/posts/... or https://x.com/..." required />
          <p class="hint">A link to a LinkedIn, X, or equivalent post where you shared at least 1 verified logbook or poster you created. Sharing your work publicly is required to be eligible.</p>
        </div>

        <div class="divider"></div>

        <h2 class="section-title">Special prizes (optional)</h2>
        <p class="section-sub">Opt in to any special award below. For each one you must link a
          <b>public</b> logbook Space that <b>includes the agent traces</b> so we can inspect it.
          Each special award is based on a single high-quality logbook, regardless of how many
          logbooks you submitted.</p>

        <div class="opt" id="opt-hitl">
          <label class="check">
            <input type="checkbox" id="hitl" />
            <span class="check-body">
              <strong>Highest-Quality, Human-in-the-Loop Reproduction Award ($500)</strong>
              <span>Consider me for the most rigorous, fully verified end-to-end reproduction that required human intervention.</span>
            </span>
          </label>
          <div class="reveal">
            <div class="field" style="margin-bottom:0">
              <label for="hitl-url">Logbook Space URL</label>
              <input id="hitl-url" type="url" placeholder="https://huggingface.co/spaces/username/logbook" />
              <p class="hint">Must be public and include the agent traces for the reproduction.</p>
            </div>
            <div class="field" style="margin:14px 0 0">
              <label for="hitl-explanation">Why does this reproduction fit the award?</label>
              <textarea id="hitl-explanation" rows="3" maxlength="1500" placeholder="In 2–3 sentences, describe why an automated agent was not able to reproduce the claim without human intervention, and what intervention you made."></textarea>
              <p class="hint">Explain in your own words how this Space meets the award criteria (2–3 sentences).</p>
            </div>
          </div>
        </div>

        <div class="opt" id="opt-fals">
          <label class="check">
            <input type="checkbox" id="fals" />
            <span class="check-body">
              <strong>Best Falsification / Negative Result Award ($500)</strong>
              <span>Consider me for the best logbook explaining why a claim could not be reproduced and what is true instead.</span>
            </span>
          </label>
          <div class="reveal">
            <div class="field" style="margin-bottom:0">
              <label for="fals-url">Logbook Space URL</label>
              <input id="fals-url" type="url" placeholder="https://huggingface.co/spaces/username/logbook" />
              <p class="hint">Must be public and include traces showing the failed claim and the different claim that holds.</p>
            </div>
            <div class="field" style="margin:14px 0 0">
              <label for="fals-explanation">Why does this reproduction fit the award?</label>
              <textarea id="fals-explanation" rows="3" maxlength="1500" placeholder="In 2–3 sentences, describe the falsified claim, the evidence, and the different claim your work supports."></textarea>
              <p class="hint">Explain in your own words how this Space meets the award criteria (2–3 sentences).</p>
            </div>
          </div>
        </div>

        <div class="opt" id="opt-openresearch">
          <label class="check">
            <input type="checkbox" id="openresearch" />
            <span class="check-body">
              <strong>OpenResearch Open-Weights Award ($500)</strong>
              <span>Consider me for the best reproduction using an open-weights model as the main agent with the OpenResearch CLI harness.</span>
            </span>
          </label>
          <div class="reveal">
            <div class="field" style="margin-bottom:0">
              <label for="openresearch-url">Logbook Space URL</label>
              <input id="openresearch-url" type="url" placeholder="https://huggingface.co/spaces/username/logbook" />
              <p class="hint">Must be public and include inspectable agent traces from the reproduction.</p>
            </div>
            <div class="field" style="margin:14px 0 0">
              <label for="openresearch-explanation">Model and OpenResearch setup</label>
              <textarea id="openresearch-explanation" rows="3" maxlength="1500" placeholder="In 2–3 sentences, name the open-weights model used as the main agent and describe how the reproduction used the OpenResearch CLI harness."></textarea>
              <p class="hint">Identify the main model and briefly explain the role of <code>orx</code> in the reproduction.</p>
            </div>
          </div>
        </div>

        <button type="submit">Submit for consideration</button>
        <div id="status" class="status"></div>
      </form>

      <footer>
        <a href="__CHALLENGE_URL__" target="_blank" rel="noopener">Back to the challenge</a>
        ·
        <a href="__DISCUSSIONS_URL__" target="_blank" rel="noopener">Questions?</a>
      </footer>
    </div>

    <script>
      const form = document.getElementById("winner-form");
      const statusBox = document.getElementById("status");
      const hitl = document.getElementById("hitl");
      const fals = document.getElementById("fals");
      const optHitl = document.getElementById("opt-hitl");
      const optFals = document.getElementById("opt-fals");
      const openresearch = document.getElementById("openresearch");
      const optOpenresearch = document.getElementById("opt-openresearch");
      const hitlUrl = document.getElementById("hitl-url");
      const hitlExplanation = document.getElementById("hitl-explanation");
      const falsUrl = document.getElementById("fals-url");
      const falsExplanation = document.getElementById("fals-explanation");
      const openresearchUrl = document.getElementById("openresearch-url");
      const openresearchExplanation = document.getElementById("openresearch-explanation");

      function showStatus(message, isError) {
        statusBox.textContent = message;
        statusBox.className = "status" + (isError ? " err" : "");
        statusBox.style.display = "block";
      }
      function syncOpt(checkbox, container, fields) {
        container.classList.toggle("checked", checkbox.checked);
        fields.forEach((field) => { field.required = checkbox.checked; });
      }
      hitl.addEventListener("change", () => syncOpt(hitl, optHitl, [hitlUrl, hitlExplanation]));
      fals.addEventListener("change", () => syncOpt(fals, optFals, [falsUrl, falsExplanation]));
      openresearch.addEventListener("change", () => syncOpt(openresearch, optOpenresearch, [openresearchUrl, openresearchExplanation]));

      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const payload = {
          hf_username: document.getElementById("username").value.trim(),
          email: document.getElementById("email").value.trim(),
          social_post_url: document.getElementById("social").value.trim(),
          interested_hitl: hitl.checked,
          hitl_space_url: hitl.checked ? hitlUrl.value.trim() : "",
          hitl_explanation: hitl.checked ? hitlExplanation.value.trim() : "",
          interested_falsification: fals.checked,
          falsification_space_url: fals.checked ? falsUrl.value.trim() : "",
          falsification_explanation: fals.checked ? falsExplanation.value.trim() : "",
          interested_openresearch: openresearch.checked,
          openresearch_space_url: openresearch.checked ? openresearchUrl.value.trim() : "",
          openresearch_explanation: openresearch.checked ? openresearchExplanation.value.trim() : "",
        };
        showStatus("Saving...", false);
        try {
          const res = await fetch("/submit", {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify(payload),
          });
          const data = await res.json().catch(() => ({ ok: false, error: "Unexpected response" }));
          showStatus(data.ok ? data.message : data.error, !data.ok);
          if (data.ok) form.querySelector("button").disabled = true;
        } catch (err) {
          showStatus("Network error — please try again.", true);
        }
      });
    </script>
  </body>
</html>"""
