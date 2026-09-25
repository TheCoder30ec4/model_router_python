import dataclasses
import unittest

from model_router import Limits, ModelInfo

RAW = {
    "id": "anthropic/claude-opus-5.5",
    "context_length": 1_000_000,
    "pricing": {"prompt": "0.000004", "completion": "0.00002"},
    "top_provider": {"max_completion_tokens": 128_000},
    "description": "Flagship model.\nGreat at code.",
    "created": 1_790_000_000,
    "expiration_date": None,
}


class ModelInfoTest(unittest.TestCase):
    def test_parses_openrouter_entry(self):
        m = ModelInfo.from_openrouter(RAW)
        self.assertEqual(m.id, "anthropic/claude-opus-5.5")
        self.assertEqual(m.context_length, 1_000_000)
        self.assertEqual(m.max_output_tokens, 128_000)
        self.assertAlmostEqual(m.prompt_price, 4e-6)
        self.assertAlmostEqual(m.completion_price, 2e-5)
        self.assertEqual(m.created, 1_790_000_000)
        self.assertIsNone(m.expires)

    def test_description_newlines_are_flattened(self):
        self.assertEqual(ModelInfo.from_openrouter(RAW).description, "Flagship model. Great at code.")

    def test_negative_variable_price_is_treated_as_zero(self):
        m = ModelInfo.from_openrouter({**RAW, "pricing": {"prompt": "-1", "completion": "-1"}})
        self.assertEqual((m.prompt_price, m.completion_price), (0.0, 0.0))

    def test_missing_fields_get_safe_defaults(self):
        m = ModelInfo.from_openrouter({"id": "x/y"})
        self.assertEqual(m.context_length, 0)
        self.assertIsNone(m.max_output_tokens)
        self.assertEqual((m.prompt_price, m.completion_price), (0.0, 0.0))
        self.assertEqual(m.description, "")

    def test_expiration_date_is_kept(self):
        m = ModelInfo.from_openrouter({**RAW, "expiration_date": "2026-12-01"})
        self.assertEqual(m.expires, "2026-12-01")

    def test_cost_uses_input_and_output_prices(self):
        m = ModelInfo.from_openrouter(RAW)
        self.assertAlmostEqual(m.cost(1_000, 500), 1_000 * 4e-6 + 500 * 2e-5)

    def test_is_immutable(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            ModelInfo.from_openrouter(RAW).context_length = 1


class LimitsTest(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(Limits(), Limits(output_tokens=1024, max_cost_usd=None))

    def test_positive_integer_output_tokens_are_accepted(self):
        for output_tokens in (1, 500, 1024):
            with self.subTest(output_tokens=output_tokens):
                self.assertEqual(Limits(output_tokens=output_tokens).output_tokens, output_tokens)

    def test_invalid_output_tokens_raise_value_error(self):
        for output_tokens in (0, -5, 1.0, 1.5, "1", None, True, False):
            with self.subTest(output_tokens=output_tokens):
                with self.assertRaisesRegex(ValueError, "output_tokens must be an integer >= 1"):
                    Limits(output_tokens=output_tokens)

    def test_optional_nonnegative_cost_is_accepted(self):
        for max_cost_usd in (None, 0, 0.0, 0.001, 1):
            with self.subTest(max_cost_usd=max_cost_usd):
                self.assertEqual(Limits(max_cost_usd=max_cost_usd).max_cost_usd, max_cost_usd)

    def test_invalid_cost_raises_value_error(self):
        for max_cost_usd in (-1, -0.001, float("nan"), "0", True, False):
            with self.subTest(max_cost_usd=max_cost_usd):
                with self.assertRaisesRegex(ValueError, "max_cost_usd must be None or a number >= 0"):
                    Limits(max_cost_usd=max_cost_usd)

    def test_is_immutable(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            Limits().output_tokens = 5

    def test_not_negative_output_tokens(self):
        with self.assertRaises(ValueError):
            Limits(output_tokens=0, max_cost_usd=1)

    def test_not_negative_max_cost_usd(self):
        with self.assertRaises(ValueError):
            Limits(output_tokens=1024, max_cost_usd=-1)


if __name__ == "__main__":
    unittest.main()
