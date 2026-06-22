"""LLM-as-judge baseline: does the impl accomplish the task intent? A semantic
foil for coupling. Reads ANTHROPIC_API_KEY from env or .env; stdlib only."""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

_MODEL = "claude-sonnet-4-6"
_URL = "https://api.anthropic.com/v1/messages"
_PROMPT = (
    "You are checking whether a Dafny method body correctly accomplishes a task.\n"
    "Task: {nl}\n"
    "Specification (ensures): {spec}\n"
    "Implementation body: {impl}\n"
    "Ignore whether the specification is complete. Does the body correctly "
    "accomplish the task? Answer with exactly one word: CORRECT or WRONG."
)


def _key() -> str | None:
    k = os.environ.get("ANTHROPIC_API_KEY")
    if k:
        return k
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None


def judge(nl: str, spec: list[str], impl: str, model: str = _MODEL, key: str | None = None):
    """Return 'wrong' | 'correct' | None (no key / API error / unparsed)."""
    key = key or _key()
    if not key:
        return None
    payload = json.dumps({
        "model": model,
        "max_tokens": 5,
        "messages": [{"role": "user", "content": _PROMPT.format(
            nl=nl, spec=" && ".join(spec) or "(none)", impl=impl)}],
    }).encode()
    req = urllib.request.Request(_URL, data=payload, headers={
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = json.loads(resp.read())["content"][0]["text"].strip().upper()
    except Exception:
        return None
    if "WRONG" in text:
        return "wrong"
    if "CORRECT" in text:
        return "correct"
    return None
