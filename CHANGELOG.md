# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-09-25

### Added
- `await router.aroute(task, limits=None)`: async version of `route()` for asyncio apps (#18).
- `Router(timeout=60)`: configurable HTTP timeout in seconds for catalog downloads and routing calls (#13).

### Fixed
- `request_json` now raises `RouterError` (with the original exception chained) for non-JSON responses, read timeouts and connection errors, so `except RouterError:` fallbacks work as documented (#5).
- A JSON response that isn't an object (e.g. `null` or a list), or a model list without `data`, now raises `RouterError` instead of `AttributeError`/`KeyError`.
- `Limits` rejects invalid values (`output_tokens < 1`, negative or NaN `max_cost_usd`, booleans) with `ValueError` (#9).
- `Router` rejects a non-positive or non-numeric `timeout` with `ValueError`.
- Duplicate model ids or providers are removed, keeping first-seen order, so Jev never sees the same model twice (#8).

### Internal
- The examples run offline in CI with mocked network calls (#20).

## [0.1.0] - 2026-09-23

### Added
- `Router` picks the best model for a task by filtering on context window, max output tokens and cost budget (`Limits`), then letting Jev choose.
- Two routing backends: `jev_api_key` (Jev's model-route API) or `openrouter_api_key` (Jev via OpenRouter decisions).
- Candidates from `providers` (names or `{name: api_key}`, every current model) or an exact `models` list.
- Live prices, context and output limits from OpenRouter's public model list, cached for 24h (`refresh_catalog()`).
- Requests automatically fit Jev's 32 KiB body limit.
- `router.api_key_for(model_id)` returns your key for the chosen model's provider.
- Examples for basic routing and agents (plan-and-execute, multi-turn chat, fallback).

[Unreleased]: https://github.com/TheCoder30ec4/model_router_python/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/TheCoder30ec4/model_router_python/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/TheCoder30ec4/model_router_python/releases/tag/v0.1.0
