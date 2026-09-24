import time

from ._http import request_json
from .models import ModelInfo

MODELS_URL = "https://openrouter.ai/api/v1/models"
CATALOG_TTL_SECONDS = 24 * 3600

_cache = {"at": 0.0, "data": None}


def fetch_catalog(max_age=CATALOG_TTL_SECONDS, *, timeout=60):
    """Live prices, context and output limits for every text model on OpenRouter, keyed by id.

    Public endpoint, no key needed. Fetched once and shared by every Router in the process,
    then refreshed after `max_age` seconds so price changes are picked up.
    """
    # ponytail: in-process cache only; persist to disk if many short-lived processes each pay the fetch
    if _cache["data"] is None or time.time() - _cache["at"] > max_age:
        _cache["data"] = {
            m["id"]: ModelInfo.from_openrouter(m)
            for m in request_json(MODELS_URL, timeout=timeout)["data"]
            if "text" in ((m.get("architecture") or {}).get("output_modalities") or ["text"])
        }
        _cache["at"] = time.time()
    return _cache["data"]


def refresh_catalog():
    """Force the next fetch_catalog() call to download fresh data."""
    _cache["data"] = None


def provider_models(catalog, provider, limit=None):
    """Every current model from one provider, newest first.

    Skips variants like ':batch' or ':free' and models scheduled for retirement.
    """
    models = [
        m for m in catalog.values() if m.id.startswith(f"{provider}/") and ":" not in m.id and not m.expires
    ]
    return sorted(models, key=lambda m: m.created, reverse=True)[:limit]
