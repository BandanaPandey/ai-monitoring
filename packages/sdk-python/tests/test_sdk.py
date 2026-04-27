from unittest.mock import patch

from ai_monitoring_sdk.client import MonitorClient


class DummyResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"accepted": True}


def test_sdk_buffers_and_flushes():
    client = MonitorClient(base_url="http://localhost:8001", api_key="demo")
    client.log({"request_id": "req-sdk", "provider": "openai", "model": "gpt-4o-mini", "latency_ms": 10})

    with patch("httpx.Client.post", return_value=DummyResponse()) as mock_post:
        responses = client.flush()

    assert responses == [{"accepted": True}]
    assert mock_post.call_count == 1

