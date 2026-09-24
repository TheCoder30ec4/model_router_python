"""Run the examples against the real Router API without provider calls."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from model_router import ModelInfo

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
FAKE_KEY = "offline-example-key"
MODEL_IDS = ("anthropic/claude-opus-5.5", "openai/gpt-6-luna", "google/gemini-3.5-flash-lite")
CATALOG = {name: ModelInfo(name, 32_000, 4_000, 1e-8, 1e-8, "Offline test model") for name in MODEL_IDS}


def load_example(name, monkeypatch):
    spec = importlib.util.spec_from_file_location(name, EXAMPLES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def offline(monkeypatch, tmp_path):
    # Never load a developer's .env, keys or a cached example module.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    monkeypatch.delenv("jev_api_key", raising=False)
    with (
        patch("socket.socket.connect", side_effect=AssertionError("unexpected network call")),
        patch("model_router.router.fetch_catalog", return_value=CATALOG),
        patch(
            "model_router.jev.request_json",
            return_value={"answers": {"model": {"choice": "m0"}}},
        ) as route,
    ):
        yield route


def test_basic_main_runs_offline(offline, monkeypatch, capsys):
    basic = load_example("basic", monkeypatch)

    basic.main()

    output = capsys.readouterr().out
    assert "candidates from providers:" in output
    assert "<- cost-capped" in output
    assert "no fit:" in output
    assert offline.call_count == 3
    assert all(call.args[1] == FAKE_KEY for call in offline.call_args_list)


def test_agent_main_runs_offline(offline, monkeypatch, capsys):
    load_example("basic", monkeypatch)  # agent.py imports its neighboring example
    agent = load_example("agent", monkeypatch)
    replies = ["Research\nDraft\nReview", "research", "draft", "review", "summary", "Canberra", "algorithm"]
    responses = [{"choices": [{"message": {"content": reply}}]} for reply in replies]
    with patch.object(agent, "request_json", side_effect=responses) as chat:
        agent.main()

    output = capsys.readouterr().out
    assert "estimated spend" in output
    assert "== Chat session" in output
    assert "Canberra" in output and "algorithm" in output
    assert chat.call_count == offline.call_count == 7
    assert all(call.args[0] == agent.CHAT_URL and call.args[1] == FAKE_KEY for call in chat.call_args_list)
    assert all(call.args[2]["model"] in CATALOG for call in chat.call_args_list)
