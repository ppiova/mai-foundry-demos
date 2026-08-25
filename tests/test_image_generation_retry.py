import unittest
from unittest.mock import patch

import requests

from mai.client import MAIClient
from mai.config import Config


class FakeResponse:
    def __init__(self, status_code=200, payload=None, exc=None):
        self.status_code = status_code
        self._payload = payload or {}
        self._exc = exc

    def raise_for_status(self):
        if self._exc is not None:
            raise self._exc

    def json(self):
        return self._payload


class GenerateImageRetryTests(unittest.TestCase):
    def test_retries_with_smaller_dimensions_for_a_request_shape_error(self):
        cfg = Config(
            image_endpoint="https://example.services.ai.azure.com",
            image_api_key="test-key",
            image_gen_deployment="MAI-Image-2.5-Flash",
            image_edit_deployment="MAI-Image-2.5",
        )
        client = MAIClient(cfg)

        first_error = requests.HTTPError("bad request")
        first_error.response = type("Resp", (), {"status_code": 400})()

        with (
            patch(
                "mai.client.requests.post",
                side_effect=[
                    FakeResponse(status_code=429, exc=first_error),
                    FakeResponse(status_code=200, payload={"data": [{"b64_json": "dGVzdA=="}]}),
                ],
            ) as mock_post,
            patch("mai.client.fallback.generate_image", return_value=b"fallback"),
        ):
            result = client.generate_image("A test prompt", width=896, height=896)

        self.assertEqual(result.source, "live")
        self.assertEqual(result.data, b"test")
        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(mock_post.call_args_list[1].kwargs["json"]["width"], 768)
        self.assertEqual(mock_post.call_args_list[1].kwargs["json"]["height"], 768)

    def test_does_not_retry_rate_limits_with_an_unrelated_request_change(self):
        cfg = Config(
            image_endpoint="https://example.services.ai.azure.com",
            image_api_key="test-key",
        )
        error = requests.HTTPError("rate limited")
        error.response = type("Resp", (), {"status_code": 429})()
        with (
            patch("mai.client.requests.post", return_value=FakeResponse(exc=error)) as mock_post,
            patch("mai.client.fallback.generate_image", return_value=b"fallback"),
        ):
            result = MAIClient(cfg).generate_image("A test prompt", width=896, height=896)
        self.assertEqual(result.source, "fallback")
        self.assertEqual(mock_post.call_count, 1)

    def test_uses_configured_edit_deployment_for_deployment_retry(self):
        cfg = Config(
            image_endpoint="https://example.services.ai.azure.com",
            image_api_key="test-key",
            image_gen_deployment="custom-fast",
            image_edit_deployment="custom-quality",
        )
        error = requests.HTTPError("deployment not found")
        error.response = type("Resp", (), {"status_code": 404})()
        with patch(
            "mai.client.requests.post",
            side_effect=[
                FakeResponse(exc=error),
                FakeResponse(payload={"data": [{"b64_json": "dGVzdA=="}]}),
            ],
        ) as mock_post:
            result = MAIClient(cfg).generate_image("A test prompt", width=768, height=768)
        self.assertEqual(result.meta["model"], "custom-quality")
        self.assertEqual(mock_post.call_args_list[1].kwargs["json"]["model"], "custom-quality")


if __name__ == "__main__":
    unittest.main()
