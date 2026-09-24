import io
import json
import unittest
from unittest.mock import MagicMock, patch

from model_router import (
    Limits,
    ModelInfo,
    NoModelFitsError,
    Router,
    RouterError,
    UnknownModelError,
    estimate_tokens,
)

CATALOG = {
    "cheap/small": ModelInfo("cheap/small", 8_000, 2_000, 1e-7, 4e-7, "small fast model"),
    "big/smart": ModelInfo("big/smart", 1_000_000, 64_000, 5e-6, 2.5e-5, "frontier model"),
    "acme/old": ModelInfo("acme/old", 128_000, None, 1e-6, 1e-6, "", created=100),
    "acme/new": ModelInfo("acme/new", 128_000, None, 1e-6, 1e-6, "", created=300),
    "acme/new:batch": ModelInfo("acme/new:batch", 128_000, None, 5e-7, 5e-7, "", created=400),
    "acme/retiring": ModelInfo(
        "acme/retiring", 128_000, None, 1e-6, 1e-6, "", created=500, expires="2026-10-01"
    ),
}


def many_models(n):
    return {
        f"bulk/m{i}": ModelInfo(f"bulk/m{i}", 128_000, None, 1e-6, 1e-6, "d" * 300, created=i)
        for i in range(n)
    }


def make_router(models=("cheap/small", "big/smart"), limits=None, **kw):
    kw.setdefault("openrouter_api_key", "or-key")
    with patch("model_router.router.fetch_catalog", return_value=CATALOG):
        return Router(models=list(models) if models else None, limits=limits or Limits(), **kw)


class ConfigTest(unittest.TestCase):
    def test_timeout_reaches_both_routing_backends(self):
        for backend, payload in [
            ("jev_api_key", {"code": 0, "data": {"decision": "cheap/small"}}),
            ("openrouter_api_key", {"answers": {"model": {"choice": "m0"}}}),
        ]:
            for options, expected in [({}, 60), ({"timeout": 2.5}, 2.5)]:
                with self.subTest(backend=backend, timeout=expected):
                    response = MagicMock()
                    response.__enter__.return_value = io.BytesIO(json.dumps(payload).encode())
                    with patch("urllib.request.urlopen", return_value=response) as urlopen:
                        router = make_router(**{backend: "test-key"}, **options)
                        self.assertEqual(router.route("hello"), "cheap/small")
                    self.assertEqual(urlopen.call_args.kwargs["timeout"], expected)

    def test_timeout_reaches_catalog_download(self):
        from model_router.catalog import refresh_catalog

        refresh_catalog()
        self.addCleanup(refresh_catalog)
        response = MagicMock()
        response.__enter__.return_value = io.BytesIO(
            json.dumps(
                {
                    "data": [
                        {
                            "id": "cheap/small",
                            "context_length": 8000,
                            "pricing": {"prompt": "0.0000001", "completion": "0.0000004"},
                        }
                    ]
                }
            ).encode()
        )
        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            router = Router(openrouter_api_key="test-key", models=["cheap/small"], timeout=5)
            self.assertEqual(router.route("hello"), "cheap/small")
        self.assertEqual(urlopen.call_count, 1)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 5)

    def test_needs_a_routing_key(self):
        with self.assertRaises(RouterError):
            make_router(openrouter_api_key=None)

    def test_needs_providers_or_models(self):
        with self.assertRaises(RouterError):
            make_router(models=None)

    def test_unknown_model(self):
        with self.assertRaises(UnknownModelError):
            make_router(["nope/model"])

    def test_unknown_provider(self):
        with self.assertRaises(UnknownModelError):
            make_router(models=None, providers=["nope"])

    def test_provider_names_pick_newest_and_skip_variants(self):
        r = make_router(models=None, providers=["acme"], models_per_provider=1)
        self.assertEqual([m.id for m in r.models], ["acme/new"])

    def test_provider_names_use_all_current_models(self):
        r = make_router(models=None, providers=["acme"])
        self.assertEqual([m.id for m in r.models], ["acme/new", "acme/old"])  # no :batch, no retiring

    def test_catalog_is_fetched_once_and_cached(self):
        from model_router import catalog

        catalog.refresh_catalog()
        with patch("model_router.catalog.request_json", return_value={"data": []}) as req:
            catalog.fetch_catalog()
            catalog.fetch_catalog()
            self.assertEqual(req.call_count, 1)
            catalog.refresh_catalog()
            catalog.fetch_catalog()
            self.assertEqual(req.call_count, 2)
        catalog.refresh_catalog()

    def test_provider_keys_are_returned_per_model(self):
        r = make_router(models=None, providers={"acme": "sk-acme"})
        self.assertEqual(r.api_key_for("acme/new"), "sk-acme")
        self.assertIsNone(r.api_key_for("other/model"))


class LimitsTest(unittest.TestCase):
    def test_oversized_task_fits_nothing(self):
        with self.assertRaises(NoModelFitsError):
            make_router().route("x" * 5_000_000)

    def test_context_limit_filters(self):
        ids = [m.id for m in make_router().fitting("x" * 40_000)]  # ~10k tokens > 8k context
        self.assertEqual(ids, ["big/smart"])

    def test_output_limit_filters(self):
        ids = [m.id for m in make_router().fitting("hi", Limits(output_tokens=4_000))]
        self.assertEqual(ids, ["big/smart"])

    def test_cost_limit_filters(self):
        ids = [m.id for m in make_router().fitting("hi", Limits(max_cost_usd=0.001))]
        self.assertEqual(ids, ["cheap/small"])


class BackendTest(unittest.TestCase):
    @patch("model_router.jev.request_json")
    def test_single_candidate_skips_jev(self, req):
        self.assertEqual(make_router(["big/smart"]).route("hi"), "big/smart")
        req.assert_not_called()

    @patch("model_router.jev.request_json", return_value={"answers": {"model": {"choice": "m1"}}})
    def test_openrouter_alias_maps_back_to_id(self, req):
        self.assertEqual(make_router().route("hi"), "big/smart")
        self.assertIn("openrouter.ai", req.call_args.args[0])
        criteria = req.call_args.args[2]["questions"]["model"]["criteria"]
        self.assertEqual(set(criteria), {"m0", "m1"})

    @patch("model_router.jev.request_json", return_value={"code": 0, "data": {"decision": "cheap/small"}})
    def test_jev_direct_uses_model_route(self, req):
        r = make_router(openrouter_api_key=None, jev_api_key="jev-key")
        self.assertEqual(r.route("hi"), "cheap/small")
        url, key, body = req.call_args.args
        self.assertTrue(url.endswith("/decisions/model-route"))
        self.assertEqual(key, "jev-key")
        self.assertEqual([c["id"] for c in body["candidates"]], ["cheap/small", "big/smart"])

    @patch(
        "model_router.jev.request_json",
        return_value={"code": -1, "message": "Too many requests", "data": None},
    )
    def test_jev_error_code_raises(self, req):
        with self.assertRaises(RouterError):
            make_router(openrouter_api_key=None, jev_api_key="jev-key").route("hi")

    @patch("model_router.jev.request_json", return_value={"code": 0, "data": {"decision": "big/smart"}})
    def test_long_task_is_truncated_for_routing(self, req):
        make_router(openrouter_api_key=None, jev_api_key="jev-key").route(
            "y" * 20_000
        )  # fits both models, so Jev is called
        self.assertLess(len(req.call_args.args[2]["task"]), 9_000)

    @patch("model_router.jev.request_json", return_value={"code": 0, "data": {"decision": "bulk/m0"}})
    def test_every_candidate_is_sent_with_live_pricing(self, req):
        with patch("model_router.router.fetch_catalog", return_value=many_models(100)):
            r = Router(jev_api_key="jev-key", providers=["bulk"])
        r.route("hi")
        body = req.call_args.args[2]
        self.assertEqual(len(body["candidates"]), 100)
        self.assertIn("$1.00/M in", body["candidates"][0]["description"])
        self.assertLessEqual(len(json.dumps(body).encode()), 30_000)  # descriptions shrank to fit

    @patch("model_router.jev.request_json")
    def test_too_many_candidates_raises_instead_of_oversized_request(self, req):
        with patch("model_router.router.fetch_catalog", return_value=many_models(1000)):
            r = Router(jev_api_key="jev-key", providers=["bulk"])
        with self.assertRaises(RouterError):
            r.route("hi")
        req.assert_not_called()


class RouterBehaviorTest(unittest.TestCase):
    def test_estimate_tokens(self):
        self.assertEqual(estimate_tokens(""), 1)
        self.assertEqual(estimate_tokens("a" * 400), 101)

    def test_empty_key_counts_as_missing(self):
        with self.assertRaises(RouterError):
            make_router(openrouter_api_key="")

    @patch("model_router.jev.request_json", return_value={"code": 0, "data": {"decision": "big/smart"}})
    def test_jev_key_wins_when_both_given(self, req):
        make_router(jev_api_key="jev-key").route("hi")
        self.assertTrue(req.call_args.args[0].startswith("https://www.jevai.org"))

    def test_models_override_providers(self):
        r = make_router(["big/smart"], providers=["acme"])
        self.assertEqual([m.id for m in r.models], ["big/smart"])

    def test_several_providers_are_combined(self):
        r = make_router(models=None, providers=["acme", "big"])
        self.assertEqual([m.id for m in r.models], ["acme/new", "acme/old", "big/smart"])

    def test_router_default_limits_apply(self):
        r = make_router(limits=Limits(output_tokens=4_000))
        self.assertEqual([m.id for m in r.fitting("hi")], ["big/smart"])

    def test_per_call_limits_override_router_limits(self):
        r = make_router(limits=Limits(output_tokens=4_000))
        self.assertEqual(len(r.fitting("hi", Limits(output_tokens=10))), 2)

    def test_no_fit_message_names_every_model_and_reason(self):
        with self.assertRaises(NoModelFitsError) as ctx:
            make_router().route("hi", Limits(max_cost_usd=0.0))
        msg = str(ctx.exception)
        self.assertIn("cheap/small: cost", msg)
        self.assertIn("big/smart: cost", msg)

    @patch("model_router.jev.request_json", return_value={"answers": {"model": {"choice": "m0"}}})
    def test_only_fitting_models_are_sent_to_jev(self, req):
        with patch("model_router.router.fetch_catalog", return_value=CATALOG):
            r = Router(openrouter_api_key="k", models=["cheap/small", "big/smart", "acme/new"])
        r.route("x" * 40_000)  # too big for cheap/small's 8k context
        criteria = req.call_args.args[2]["questions"]["model"]["criteria"]
        self.assertEqual(len(criteria), 2)
        self.assertNotIn("cheap/small", " ".join(criteria.values()))

    def test_errors_share_a_base_class(self):
        self.assertTrue(issubclass(NoModelFitsError, RouterError))
        self.assertTrue(issubclass(UnknownModelError, RouterError))


if __name__ == "__main__":
    unittest.main()
