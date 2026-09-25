import unittest
from unittest.mock import patch

from model_router import ModelInfo, RouterError, catalog


def raw(id, output=("text",), **extra):
    return {"id": id, "context_length": 1000, "architecture": {"output_modalities": list(output)}, **extra}


class FetchCatalogTest(unittest.TestCase):
    def setUp(self):
        catalog.refresh_catalog()

    def tearDown(self):
        catalog.refresh_catalog()

    @patch("model_router.catalog.request_json")
    def test_keeps_only_text_models(self, req):
        req.return_value = {
            "data": [raw("a/chat"), raw("a/image", output=("image",)), raw("a/both", ("text", "image"))]
        }
        self.assertEqual(sorted(catalog.fetch_catalog()), ["a/both", "a/chat"])

    @patch("model_router.catalog.request_json")
    def test_missing_architecture_counts_as_text(self, req):
        req.return_value = {"data": [{"id": "a/old", "context_length": 1000}]}
        self.assertIn("a/old", catalog.fetch_catalog())

    @patch("model_router.catalog.request_json", return_value={"data": [raw("a/chat")]})
    def test_values_are_model_info(self, req):
        self.assertIsInstance(catalog.fetch_catalog()["a/chat"], ModelInfo)

    @patch("model_router.catalog.request_json", return_value={"data": []})
    def test_cached_until_max_age(self, req):
        with patch("model_router.catalog.time.time", return_value=1_000.0):
            catalog.fetch_catalog()
        with patch("model_router.catalog.time.time", return_value=1_000.0 + catalog.CATALOG_TTL_SECONDS - 1):
            catalog.fetch_catalog()
        self.assertEqual(req.call_count, 1)
        with patch("model_router.catalog.time.time", return_value=1_000.0 + catalog.CATALOG_TTL_SECONDS + 1):
            catalog.fetch_catalog()
        self.assertEqual(req.call_count, 2)

    @patch("model_router.catalog.request_json", return_value={"data": []})
    def test_custom_max_age_zero_always_refetches(self, req):
        catalog.fetch_catalog()
        with patch("model_router.catalog.time.time", return_value=10**12):
            catalog.fetch_catalog(max_age=0)
        self.assertEqual(req.call_count, 2)

    def test_response_without_data_list_is_router_error(self):
        for res in ({}, {"error": {"message": "down"}}, {"data": None}):
            with self.subTest(res=res), patch("model_router.catalog.request_json", return_value=res):
                with self.assertRaises(RouterError):
                    catalog.fetch_catalog()


def info(id, created=0, expires=None):
    return ModelInfo(id, 1000, None, 0.0, 0.0, "", created=created, expires=expires)


CAT = {
    m.id: m
    for m in [
        info("openai/a", created=1),
        info("openai/b", created=3),
        info("openai/c", created=2),
        info("openai/b:batch", created=9),
        info("openai/free:free", created=9),
        info("openai/old", created=5, expires="2026-10-01"),
        info("openai-compat/x", created=9),
        info("anthropic/z", created=9),
    ]
}


class ProviderModelsTest(unittest.TestCase):
    def test_newest_first_without_variants_or_retiring(self):
        ids = [m.id for m in catalog.provider_models(CAT, "openai")]
        self.assertEqual(ids, ["openai/b", "openai/c", "openai/a"])

    def test_prefix_must_match_whole_provider_name(self):
        ids = [m.id for m in catalog.provider_models(CAT, "openai")]
        self.assertNotIn("openai-compat/x", ids)
        self.assertEqual(catalog.provider_models(CAT, "open"), [])

    def test_limit(self):
        ids = [m.id for m in catalog.provider_models(CAT, "openai", limit=2)]
        self.assertEqual(ids, ["openai/b", "openai/c"])

    def test_unknown_provider_is_empty(self):
        self.assertEqual(catalog.provider_models(CAT, "nope"), [])


if __name__ == "__main__":
    unittest.main()
