import io
import json
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from model_router import RouterError
from model_router._http import request_json


def fake_response(payload):
    resp = MagicMock()
    resp.__enter__.return_value = io.BytesIO(json.dumps(payload).encode())
    return resp


class RequestJsonTest(unittest.TestCase):
    @patch("urllib.request.urlopen", return_value=fake_response({"ok": 1}))
    def test_get_without_key(self, urlopen):
        self.assertEqual(request_json("https://x.test/a"), {"ok": 1})
        req = urlopen.call_args.args[0]
        self.assertIsNone(req.data)
        self.assertEqual(req.get_method(), "GET")
        self.assertIsNone(req.get_header("Authorization"))

    @patch("urllib.request.urlopen", return_value=fake_response({"ok": 1}))
    def test_post_with_key_and_json_body(self, urlopen):
        request_json("https://x.test/a", "secret", {"q": 1})
        req = urlopen.call_args.args[0]
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.get_header("Authorization"), "Bearer secret")
        self.assertEqual(req.get_header("Content-type"), "application/json")
        self.assertEqual(json.loads(req.data), {"q": 1})

    @patch("urllib.request.urlopen", return_value=fake_response({}))
    def test_passes_timeout(self, urlopen):
        request_json("https://x.test/a", timeout=5)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 5)

    def test_http_error_becomes_router_error_with_status_and_body(self):
        err = urllib.error.HTTPError(
            "https://x.test", 429, "Too Many", {}, io.BytesIO(b'{"message":"slow down"}')
        )
        with patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(RouterError) as ctx:
                request_json("https://x.test/a")
        self.assertIn("429", str(ctx.exception))
        self.assertIn("slow down", str(ctx.exception))

    def test_network_error_becomes_router_error(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("no route")):
            with self.assertRaises(RouterError) as ctx:
                request_json("https://x.test/a")
        self.assertIn("no route", str(ctx.exception))

    def test_non_json_body_becomes_router_error(self):
        resp = MagicMock()
        resp.__enter__.return_value = io.BytesIO(b"<html>oops</html>")
        with patch("urllib.request.urlopen", return_value=resp):
            with self.assertRaises(RouterError) as ctx:
                request_json("https://x.test/a")
        self.assertIsInstance(ctx.exception.__cause__, json.JSONDecodeError)

    def test_read_timeout_becomes_router_error(self):
        resp = MagicMock()
        resp.__enter__.return_value.read.side_effect = TimeoutError("The read operation timed out")
        with patch("urllib.request.urlopen", return_value=resp):
            with self.assertRaises(RouterError) as ctx:
                request_json("https://x.test/a", timeout=5)
        self.assertIn("timed out", str(ctx.exception))
        self.assertIsInstance(ctx.exception.__cause__, TimeoutError)

    def test_connection_reset_becomes_router_error(self):
        with patch("urllib.request.urlopen", side_effect=ConnectionResetError("reset by peer")):
            with self.assertRaises(RouterError) as ctx:
                request_json("https://x.test/a")
        self.assertIsInstance(ctx.exception.__cause__, ConnectionResetError)

    def test_json_that_is_not_an_object_becomes_router_error(self):
        for body in (b"null", b"[1, 2]", b'"ok"'):
            with self.subTest(body=body):
                resp = MagicMock()
                resp.__enter__.return_value = io.BytesIO(body)
                with patch("urllib.request.urlopen", return_value=resp):
                    with self.assertRaises(RouterError):
                        request_json("https://x.test/a")


if __name__ == "__main__":
    unittest.main()
