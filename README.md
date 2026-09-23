<p align="center">
  <img src="https://raw.githubusercontent.com/TheCoder30ec4/model_router_python/main/docs/logo.svg" alt="model-router-python logo" width="120">
</p>

<h1 align="center">model-router-python</h1>

<p align="center">
  <strong>Send every prompt to the cheapest model that can actually do the job.</strong><br>
  Limit-aware LLM routing powered by <a href="https://www.jevai.org">Jev</a>. Zero dependencies.
</p>

<p align="center">
  <a href="https://github.com/TheCoder30ec4/model_router_python/actions/workflows/ci.yml"><img src="https://github.com/TheCoder30ec4/model_router_python/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/model-router-python/"><img src="https://img.shields.io/pypi/v/model-router-python?cacheSeconds=3600" alt="PyPI"></a>
  <a href="https://pypi.org/project/model-router-python/"><img src="https://img.shields.io/pypi/pyversions/model-router-python?cacheSeconds=3600" alt="Python versions"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT license"></a>
  <a href="https://thecoder30ec4.github.io/model_router_python/"><img src="https://img.shields.io/badge/docs-website-0f766e" alt="Docs"></a>
</p>

<p align="center"><a href="https://thecoder30ec4.github.io/model_router_python/"><strong>Read the docs →</strong></a></p>

---

## What is this?

`model-router-python` is a small Python library that answers one question for every LLM call: **which model should handle this?**

You list the models or providers you can use. For each prompt, the router:

1. **Filters** out models that can't handle it: the context window is too small, the model can't produce enough output tokens, or it would cost more than your budget.
2. **Asks [Jev](https://www.jevai.org)** to choose among the models that are left, using **live** prices, context sizes and limits: a cheap, fast model for easy work and a strong, expensive one only when the task needs it.
3. **Returns the model id** (e.g. `"openai/gpt-6-luna"`). Your code then calls that model the way it already does.

```python
router.route("Translate 'good morning' into French.")                          # -> "openai/gpt-6-luna"
router.route("Design a lock-free hash map in Rust and prove it's linearizable.") # -> "anthropic/claude-opus-5.5"
```

## Why?

Most apps and agents send **every** request to one flagship model. Most of those requests are routine (extract a field, rephrase a sentence, answer an FAQ) and don't need it. Frontier models cost **up to 40× more per token** than small ones. So a single fixed model means overpaying on easy work, or under-serving hard work if you pick a cheap one.

Choosing the model by hand for each call doesn't scale. Hard-coded rules ("under 500 characters goes to the small model") break the moment a short prompt turns out to be hard. This library makes the choice **per request**, using what the task actually asks for and what each model actually costs today.

## Where to use it

- **AI agents**: route each step separately. Planning and debugging go to a strong model; summarizing, formatting and tool-output parsing go to a cheap one.
- **Chatbots and support assistants**: most messages are simple, and the few hard ones get escalated automatically.
- **Batch and ETL pipelines**: extraction, classification and tagging over thousands of documents, with a hard cost cap on each call.
- **Multi-provider apps**: you have OpenAI, Anthropic and Google keys and want the best-value model across all of them, not one vendor's lineup.
- **Cost-sensitive products**: free tiers and high-volume endpoints where a fraction of a cent per request adds up.

## How it helps

| | Without a router | With model-router-python |
|---|---|---|
| **Cost** | Every call at flagship prices | Easy calls at cheap-model prices. **58–92% saved** in the scenarios [below](#real-world-use-cases-estimates) |
| **Quality** | Cheap model everywhere means hard tasks fail | Hard tasks still reach a strong model |
| **Context overflow** | Found out when the provider returns an error | Caught before any call is made |
| **Cut-off answers** | Paid for, then retried | Models whose output cap is too small are excluded upfront |
| **Budgets** | Checked after the bill arrives | `max_cost_usd` enforced on every call |
| **New models and price changes** | Edit your code | Picked up automatically from live data |

## Install

```bash
pip install model-router-python
# or
uv add model-router-python
```

Requires Python 3.12+ and has no dependencies. To install from source:

```bash
git clone https://github.com/TheCoder30ec4/model_router_python.git
cd model_router_python
pip install -e .
```

You pass every key in code, so no `.env` file or environment variable is required.

## Configure: pick one of two setups

| | **Option A: Jev key + your provider keys** | **Option B: OpenRouter key** |
|---|---|---|
| Key used for routing | `jev_api_key` from [jevai.org/agent/keys](https://www.jevai.org/agent/keys) | `openrouter_api_key` from [openrouter.ai/keys](https://openrouter.ai/keys) |
| Where Jev runs | jevai.org model-route API | OpenRouter's decisions API (`~typesafe/jev-latest`) |
| How you pick candidate models | provider names with their API keys (`{"openai": "sk-..."}`), provider names only (`["openai"]`), or exact `models=[...]` | provider names (`["openai", "anthropic"]`) or exact `models=[...]` |
| How you call the chosen model | directly with that provider's key: `router.api_key_for(model)` | through OpenRouter with the same key, for any provider |
| Best when | you already pay OpenAI, Anthropic and others directly | you want one key and one bill for everything |

### Option A: Jev key plus the providers you use

```python
from model_router import Router

router = Router(
    jev_api_key="jev_...",
    providers={  # the providers you have keys for
        "openai": "sk-...",
        "anthropic": "sk-ant-...",
    },
)

model = router.route("Translate 'good morning' into French.")  # e.g. "openai/gpt-6-luna"
key = router.api_key_for(model)  # -> "sk-..." (your OpenAI key)
```

Don't want the router to hold your provider keys? Pass the names only: `providers=["openai", "anthropic"]`.

### Option B: one OpenRouter key

```python
from model_router import Router

router = Router(
    openrouter_api_key="sk-or-...",
    providers=["openai", "anthropic", "google"],  # which providers are allowed
)
```

OpenRouter can call every provider's models, so this one key covers both routing and running the chosen model.

### Choosing candidate models

- `providers=[...]` sends **every current model** from those providers to Jev. Batch and free variants such as `:batch` are skipped, and so are models OpenRouter has scheduled for retirement. `models_per_provider=N` keeps only each provider's newest N. Provider names are OpenRouter's prefixes: `openai`, `anthropic`, `google`, `mistralai`, `meta-llama`, `x-ai`, `deepseek`, …
- `models=[...]` sets the exact list and replaces the automatic pick. It works with either option:

```python
router = Router(
    jev_api_key="jev_...",
    providers={"openai": "sk-...", "anthropic": "sk-ant-...", "google": "AIza..."},
    models=["anthropic/claude-opus-5.5", "openai/gpt-6-luna", "google/gemini-3.5-flash-lite"],
)
```

If you pass both `jev_api_key` and `openrouter_api_key`, routing goes through Jev directly.

### Live model data

Every candidate goes to Jev with **live** data from OpenRouter's public model list:

```
anthropic/claude-opus-5.5 | $4.00/M in, $20.00/M out | context 1000000 | max output 128000 | est. $0.020500 for this task | Claude Opus 5.5 is Anthropic's flagship…
```

- **Fetched once, not per request.** The list is downloaded when the first `Router` is created, then shared by every `Router` in the process for 24 hours. Call `refresh_catalog()` to force a new download. An existing `Router` keeps the data it was created with.
- **Where prices come from.** Providers' own APIs (Anthropic, OpenAI, …) list models but don't publish prices, so prices, context sizes and output limits come from OpenRouter's list. It needs no key and works the same with either option.
- **Fits Jev's 32 KiB request limit.** Descriptions shrink automatically when there are many candidates. Prices, context and cost are always kept. If the list still won't fit, `route()` raises `RouterError` and asks you to narrow `providers` or pass `models=[...]`. Three full providers (102 models) fit in about 24 KB.

## Quick start

```python
from model_router import Router, Limits

router = Router(
    openrouter_api_key="sk-or-...",  # or jev_api_key="jev_..."
    models=["anthropic/claude-opus-5.5", "openai/gpt-6-luna", "google/gemini-3.5-flash-lite"],
)

router.route("Translate 'good morning' into French.")
# -> "openai/gpt-6-luna"

router.route("Design a lock-free concurrent hash map in Rust and prove it is linearizable.")
# -> "anthropic/claude-opus-5.5"

# Per-call limits: expected output size and a hard cost cap in USD
router.route("Summarize this paragraph.", Limits(output_tokens=500, max_cost_usd=0.001))
```

These are real outputs from `examples/basic.py`.

### API

| Call | What it does |
|---|---|
| `Router(*, jev_api_key=None, openrouter_api_key=None, providers=None, models=None, limits=Limits(), models_per_provider=None)` | All arguments are keyword-only. Loads live prices, context sizes and output limits (cached for 24h, no key needed). Raises `UnknownModelError` for unknown model ids or providers. |
| `refresh_catalog()` | Clears the cached model list, so the next `Router` downloads fresh prices. |
| `router.api_key_for(model_id) -> str \| None` | The key you passed in `providers={...}` for this model's provider. |
| `router.route(task, limits=None) -> str` | Returns the best model id for `task`. |
| `router.fitting(task, limits=None) -> list[ModelInfo]` | Returns the models that pass the limits, without calling Jev (free). |
| `Limits(output_tokens=1024, max_cost_usd=None)` | The output size you expect and an optional cost cap for each call. |

`Limits` validates its arguments when created: `output_tokens` must be an integer of at least 1,
and `max_cost_usd` must be `None` (no cost cap) or a nonnegative `int` or `float` (zero is allowed).
Booleans and NaN are rejected. Invalid limits raise `ValueError` with the field name and required range.

Routing errors (all subclasses of `RouterError`):
- `NoModelFitsError`: no model passes the limits. The message gives the reason for each model.
- `UnknownModelError`: a model id isn't on OpenRouter.
- `RouterError`: no routing key, a network or HTTP failure, or an error returned by Jev (e.g. a rate limit).

### Using it in an agent

Route **every** LLM call separately. A planner step and a formatting step rarely need the same model. [examples/agent.py](examples/agent.py) shows:

- **Plan and execute** with a total budget shared across the steps
- **Multi-turn chat**, where each turn is routed on the whole conversation so far. When the talk turns hard, it switches to a stronger model:

```
[openai/gpt-6-luna]          user: Hi! What's the capital of Australia?
[anthropic/claude-opus-5.5]  user: Now write a Python function that finds the longest
                                   palindromic substring in O(n) time and explain it.
```

- **Fallback** to a default model if Jev is unreachable, so the agent never stalls:

```python
def pick(router, prompt, limits):
    try:
        return router.route(prompt, limits)
    except NoModelFitsError:
        raise  # input too large for every model: shrink it
    except RouterError:
        return "openai/gpt-6-luna"  # Jev down or rate limited
```

## What it costs

### The router itself

| Item | Cost |
|---|---|
| Loading the model list | Free (public endpoint, once per `Router`) |
| Limit filtering | Free (runs locally) |
| Only one model passes the limits | Free (Jev is skipped) |
| One routing call via OpenRouter, `models=[...]` with 3 models | **$0.000027** measured (636 input + 42 output tokens) |
| One routing call via OpenRouter, `providers=["openai", "anthropic", "google"]` (102 models) | **$0.00045** measured (about 10,600 input + 929 output tokens) |
| 1,000 routing calls | about **$0.027** (3 models) or **$0.45** (102 models) |

**Routing cost grows with the number of candidates.** Sending every model from three providers costs about 17× more than a short list, because Jev reads each model's price and limits every time. For high-volume traffic, pass a short `models=[...]` list. The use-case numbers below assume 3 models.

Routing cost also grows with prompt length, up to a cap. The measured call works out to about **$0.04 per million tokens**, and only the first 8,000 characters of a task (about 2,000 tokens) are sent. So a routing call costs at most about **$0.0001**, however long the prompt. For comparison, just sending a 4,000-token prompt to Claude Opus 5.5 costs $0.016.

These figures were measured through OpenRouter (Option B). Jev's own pricing for Option A isn't published on this page. Check your jevai.org account.

### The models it picks between (OpenRouter prices, September 2026)

| Model | Input $/1M tokens | Output $/1M tokens | Context |
|---|---|---|---|
| `anthropic/claude-opus-5.5` | $4.00 | $20.00 | 1M |
| `google/gemini-3.5-flash-lite` | $0.30 | $2.50 | 1M |
| `openai/gpt-6-luna` | $0.10 | $0.50 | 1M |

Opus costs **40× more** than gpt-6-luna for the same tokens. The router saves money by not paying that premium for tasks that don't need it.

## How it saves tokens and money

- **Cheaper tokens, not fewer tokens.** Your prompt is the same size either way. The saving comes from sending easy prompts to models that charge up to 40× less per token.
- **No wasted calls on context overflow.** A prompt that won't fit a model's context window is rejected before any call is made, instead of failing at the provider after the request has already been sent.
- **No truncated answers.** Models whose output cap is below your `output_tokens` are filtered out, so you don't pay for a cut-off answer and then pay again to retry.
- **Hard cost caps.** `max_cost_usd` rules out any model whose estimated cost for this call is over budget. An agent can spread a total budget across its steps (see `examples/agent.py`).
- **Free when there's no choice.** If only one model passes the limits, Jev isn't called.

## Real-world use cases (estimates)

These use the prices above plus the Jev routing cost. **The share of easy vs. hard tasks is an assumption.** Measure it on your own traffic before relying on these numbers.

### 1. Customer support bot
100,000 messages a month, each about 800 input and 300 output tokens. Assumes 85% are routine (order status, FAQs) and 15% need careful reasoning (disputes, refunds).

| Setup | Cost per message | Monthly |
|---|---|---|
| Everything on Claude Opus 5.5 | $0.0092 | **$920** |
| Routed: 85% gpt-6-luna, 15% Opus, plus routing | $0.0016 | **$160** |
| **Saving** | | **~$760/month (83%)** |

### 2. Coding agent
20,000 LLM steps a month, each about 4,000 input and 800 output tokens. Assumes 40% are hard (design, debugging) and 60% are mechanical (summarizing files, writing commit messages, reformatting).

| Setup | Cost per step | Monthly |
|---|---|---|
| Everything on Claude Opus 5.5 | $0.032 | **$640** |
| Routed: 40% Opus, 60% gpt-6-luna, plus routing | $0.0134 | **$268** |
| **Saving** | | **~$372/month (58%)** |

### 3. Document extraction pipeline
50,000 documents a month, each about 3,000 input and 200 output tokens (pulling fields out of invoices and contracts). Assumes 95% are clean and 5% are messy enough to need a strong model.

| Setup | Cost per doc | Monthly |
|---|---|---|
| Everything on Claude Opus 5.5 | $0.016 | **$800** |
| Routed: 95% gpt-6-luna, 5% Opus, plus routing | $0.0013 | **$64** |
| **Saving** | | **~$736/month (92%)** |

For comparison, running every example in this repo once (`examples/basic.py` plus `examples/agent.py`) costs **a few cents**, mostly the Opus answer to the coding question in the chat demo (about $0.04 at 2,000 output tokens).

## Examples and tests

The examples read keys from a local `.env` only for convenience. The library itself never does.

```bash
echo 'OPENROUTER_API_KEY=sk-or-...' > .env
uv run python examples/basic.py      # routing, providers, cost cap, oversized input
uv run python examples/agent.py      # plan-and-execute and multi-turn chat (makes real, paid model calls)
```

The test suite is fully offline, so no API key is needed:

```bash
uv sync --group dev
uv run pytest            # 65 tests
uv run ruff check .
```

## Limitations

- Token counts are **estimated** at about 4 characters per token, so the cost and context checks are approximate. Leave some headroom, or swap in `tiktoken` in `model_router/router.py`.
- **Option A (Jev key) is covered by unit tests but not yet checked against the live API.** Every test call made with our Jev key got HTTP 429 ("Too many requests"). Option B has been verified end to end.
- Returned ids use OpenRouter's naming (`anthropic/claude-opus-5.5`). If you call a provider directly, drop the prefix and check the provider's own model name, which can differ (Anthropic's API uses `claude-opus-5-5`).
- Only the first 8,000 characters of a task are sent to Jev for routing. This keeps each request under Jev's 32 KiB limit and keeps routing cheap. The token and cost limits still use the full task.
- `route()` returns only the model id. It doesn't return Jev's confidence or probabilities.
- Routing adds one extra network call before each model call (none when only one model passes the limits).

## Contributing

Issues and pull requests are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) to get set up, and please follow the [Code of Conduct](CODE_OF_CONDUCT.md). Found a security problem? Please report it privately; see [SECURITY.md](SECURITY.md).

Good first contributions:
- exact token counting (optional `tiktoken`)
- returning Jev's confidence alongside the model id
- mapping OpenRouter ids to each provider's native model names
- more real-world examples

## License

[MIT](LICENSE)
