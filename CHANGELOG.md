# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- Reject invalid `Limits` values with a clear `ValueError`: `output_tokens` must be a positive integer, and `max_cost_usd` must be `None` or a nonnegative number. Booleans and NaN are rejected; a zero budget remains valid.

## [0.1.0] - 2026-09-23

### Added
- `Router` picks the best model for a task by filtering on context window, max output tokens and cost budget (`Limits`), then letting Jev choose.
- Two routing backends: `jev_api_key` (Jev's model-route API) or `openrouter_api_key` (Jev via OpenRouter decisions).
- Candidates from `providers` (names or `{name: api_key}`, every current model) or an exact `models` list.
- Live prices, context and output limits from OpenRouter's public model list, cached for 24h (`refresh_catalog()`).
- Requests automatically fit Jev's 32 KiB body limit.
- `router.api_key_for(model_id)` returns your key for the chosen model's provider.
- Examples for basic routing and agents (plan-and-execute, multi-turn chat, fallback).

[Unreleased]: https://github.com/TheCoder30ec4/model_router_python/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/TheCoder30ec4/model_router_python/releases/tag/v0.1.0
