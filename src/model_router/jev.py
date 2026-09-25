"""The Jev routing call, via Jev directly (jev_api_key) or via OpenRouter (openrouter_api_key)."""

import json

from ._http import request_json
from .errors import RouterError

JEV_ROUTE_URL = "https://www.jevai.org/api/v1/decisions/model-route"
OPENROUTER_DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
OPENROUTER_JEV_MODEL = "~typesafe/jev-latest"

# ponytail: only the head of the task is sent for routing. It keeps routing cheap;
# token and cost limits still use the full task.
ROUTING_CHARS = 8000
# Jev rejects bodies over 32 KiB; leave headroom for JSON escaping.
MAX_BODY_BYTES = 30_000
# Description lengths to try, longest first, until every candidate fits under MAX_BODY_BYTES.
DESCRIPTION_CHARS = (200, 100, 40, 0)

INSTRUCTIONS = (
    "Which model is the most efficient fit for this task? Each option lists live input/output prices "
    "per 1M tokens, context window, max output tokens and the estimated cost of this task. "
    "Use a cheap, fast model for simple tasks (short answers, translation, formatting, extraction) "
    "and a stronger, pricier model only when the task needs deep reasoning, long-form writing, "
    "or serious coding."
)


def _header(in_tokens, limits):
    return f"(~{in_tokens} input tokens, ~{limits.output_tokens} output tokens expected)"


def _describe(m, in_tokens, limits, desc_chars):
    line = (
        f"{m.id} | ${m.prompt_price * 1e6:.2f}/M in, ${m.completion_price * 1e6:.2f}/M out"
        f" | context {m.context_length} | max output {m.max_output_tokens or 'n/a'}"
        f" | est. ${m.cost(in_tokens, limits.output_tokens):.6f} for this task"
    )
    return f"{line} | {m.description[:desc_chars]}" if desc_chars else line


def _fit(build, n_candidates):
    """Build the request with the longest descriptions that still fit Jev's body limit."""
    for chars in DESCRIPTION_CHARS:
        body = build(chars)
        if len(json.dumps(body).encode()) <= MAX_BODY_BYTES:
            return body
    raise RouterError(
        f"{n_candidates} candidate models don't fit in one Jev request (32 KiB). "
        "Pass fewer providers or an explicit models=[...] list."
    )


def choose_via_jev(api_key, task, in_tokens, candidates, limits, *, timeout=60):
    """jevai.org model-route preset. Returns the chosen model id."""
    res = request_json(
        JEV_ROUTE_URL,
        api_key,
        _fit(
            lambda chars: {
                "task": f"{_header(in_tokens, limits)}\n{task[:ROUTING_CHARS]}",
                "candidates": [
                    {"id": m.id, "description": _describe(m, in_tokens, limits, chars)} for m in candidates
                ],
                "priorities": [
                    "Lowest cost that still does the task well",
                    "Strong reasoning or coding quality only when the task needs it",
                ],
            },
            len(candidates),
        ),
        timeout=timeout,
    )
    decision = (res.get("data") or {}).get("decision")
    if res.get("code") != 0 or decision not in {m.id for m in candidates}:
        raise RouterError(f"Unexpected Jev response: {res}")
    return decision


def choose_via_openrouter(api_key, task, in_tokens, candidates, limits, *, timeout=60):
    """OpenRouter decisions API running Jev. Returns the chosen model id."""
    # Aliases keep criteria keys plain; model ids contain "/" and ".".
    alias = {f"m{i}": m for i, m in enumerate(candidates)}
    res = request_json(
        OPENROUTER_DECISIONS_URL,
        api_key,
        _fit(
            lambda chars: {
                "model": OPENROUTER_JEV_MODEL,
                "state": f"Task {_header(in_tokens, limits)}:\n{task[:ROUTING_CHARS]}",
                "questions": {
                    "model": {
                        "type": "choice",
                        "instructions": INSTRUCTIONS,
                        "criteria": {a: _describe(m, in_tokens, limits, chars) for a, m in alias.items()},
                    }
                },
            },
            len(candidates),
        ),
        timeout=timeout,
    )
    picked = ((res.get("answers") or {}).get("model") or {}).get("choice")
    if picked not in alias:
        raise RouterError(f"Unexpected Jev response: {res}")
    return alias[picked].id
