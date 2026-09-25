import asyncio
from functools import partial

from . import jev
from .catalog import fetch_catalog, provider_models
from .errors import NoModelFitsError, RouterError, UnknownModelError
from .models import Limits


def estimate_tokens(text):
    # ponytail: ~4 chars/token heuristic, swap in tiktoken if you need exact counts
    return len(text) // 4 + 1


class Router:
    def __init__(
        self,
        *,
        jev_api_key=None,
        openrouter_api_key=None,
        providers=None,
        models=None,
        limits=Limits(),
        models_per_provider=None,
        timeout=60,
    ):
        """
        Routing backend (one is required; jev_api_key wins if both are given):
          jev_api_key         call Jev directly at jevai.org
          openrouter_api_key  call Jev through OpenRouter
        Candidate models (at least one is required):
          providers  {"openai": "sk-...", "anthropic": "sk-ant-..."} or just ["openai", "anthropic"];
                     uses every current model from those providers (or the newest `models_per_provider`)
          models     exact OpenRouter-style ids, e.g. ["anthropic/claude-opus-5.5"]; overrides the auto-pick
        """
        if jev_api_key:
            self._choose = partial(jev.choose_via_jev, jev_api_key)
        elif openrouter_api_key:
            self._choose = partial(jev.choose_via_openrouter, openrouter_api_key)
        else:
            raise RouterError("Pass jev_api_key or openrouter_api_key")
        if not providers and not models:
            raise RouterError("Pass providers (names or {name: api_key}) and/or models")

        self.provider_keys = dict(providers) if isinstance(providers, dict) else {}
        self.limits = limits
        self.timeout = timeout
        # Live prices/context/limits, fetched once and cached (see catalog.fetch_catalog).
        catalog = fetch_catalog(timeout=self.timeout)

        if models:
            models = list(dict.fromkeys(models))
            unknown = [m for m in models if m not in catalog]
            if unknown:
                raise UnknownModelError(f"Not in OpenRouter catalog: {unknown}")
            self.models = [catalog[m] for m in models]
        else:
            self.models = []
            for p in providers:
                found = provider_models(catalog, p, models_per_provider)
                if not found:
                    raise UnknownModelError(f"No models found for provider '{p}'")
                self.models += found
            self.models = list(dict.fromkeys(self.models))

    def api_key_for(self, model_id):
        """The API key you passed for this model's provider, or None."""
        return self.provider_keys.get(model_id.split("/", 1)[0])

    def _reject_reason(self, m, in_tokens, limits):
        if m.context_length < in_tokens + limits.output_tokens:
            return f"context {m.context_length} < {in_tokens + limits.output_tokens} tokens"
        if m.max_output_tokens is not None and m.max_output_tokens < limits.output_tokens:
            return f"max output {m.max_output_tokens} < {limits.output_tokens} tokens"
        if limits.max_cost_usd is not None:
            cost = m.cost(in_tokens, limits.output_tokens)
            if cost > limits.max_cost_usd:
                return f"cost ${cost:.6f} > ${limits.max_cost_usd}"
        return None

    def fitting(self, task, limits=None):
        """Models that satisfy the context, output-token and cost limits for `task`."""
        limits = limits or self.limits
        in_tokens = estimate_tokens(task)
        return [m for m in self.models if self._reject_reason(m, in_tokens, limits) is None]

    def route(self, task, limits=None):
        """Return the id of the best model for `task`."""
        limits = limits or self.limits
        in_tokens = estimate_tokens(task)
        reasons = {m.id: self._reject_reason(m, in_tokens, limits) for m in self.models}
        candidates = [m for m in self.models if reasons[m.id] is None]
        if not candidates:
            raise NoModelFitsError("; ".join(f"{i}: {r}" for i, r in reasons.items()))
        if len(candidates) == 1:
            return candidates[0].id
        return self._choose(task, in_tokens, candidates, limits)

    async def aroute(self, task, limits=None):
        """Asynchronously return the id of the best model for `task`."""
        return await asyncio.to_thread(self.route, task, limits=limits)
