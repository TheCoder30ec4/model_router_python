from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    id: str
    context_length: int
    max_output_tokens: int | None  # None = provider sets no separate cap
    prompt_price: float  # USD per input token
    completion_price: float  # USD per output token
    description: str = ""
    created: int = 0  # unix time the model was listed; used to order a provider's models newest first
    expires: str | None = None  # retirement date if OpenRouter has scheduled one

    def cost(self, in_tokens, out_tokens):
        return in_tokens * self.prompt_price + out_tokens * self.completion_price

    @classmethod
    def from_openrouter(cls, raw):
        pricing = raw.get("pricing") or {}
        top = raw.get("top_provider") or {}
        return cls(
            id=raw["id"],
            context_length=int(raw.get("context_length") or 0),
            max_output_tokens=top.get("max_completion_tokens"),
            # OpenRouter uses negative prices for "variable"; treat as unknown (0) rather than a discount.
            prompt_price=max(float(pricing.get("prompt") or 0), 0.0),
            completion_price=max(float(pricing.get("completion") or 0), 0.0),
            description=(raw.get("description") or "").replace("\n", " "),
            created=int(raw.get("created") or 0),
            expires=raw.get("expiration_date"),
        )


@dataclass(frozen=True)
class Limits:
    output_tokens: int = 1024
    max_cost_usd: float | None = None

    def __post_init__(self):
        if (
            isinstance(self.output_tokens, bool)
            or not isinstance(self.output_tokens, int)
            or self.output_tokens < 1
        ):
            raise ValueError("output_tokens must be an integer >= 1")
        if self.max_cost_usd is not None and (
            isinstance(self.max_cost_usd, bool)
            or not isinstance(self.max_cost_usd, (int, float))
            or not self.max_cost_usd >= 0
        ):
            raise ValueError("max_cost_usd must be None or a number >= 0")
