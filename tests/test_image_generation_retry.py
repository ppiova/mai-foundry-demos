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
    def test_retries_when_live_image_generation_fails_with_a_retryable_error(self):
        cfg = Config(
            image_endpoint="https://example.services.ai.azure.com",
            image_api_key="test-key",
            image_gen_deployment="MAI-Image-2.5-Flash",
            image_edit_deployment="MAI-Image-2.5",
        )
        client = MAIClient(cfg)

        first_error = requests.HTTPError("bad request")
        first_error.response = type("Resp", (), {"status_code": 429})()

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


if __name__ == "__main__":
    unittest.main()
