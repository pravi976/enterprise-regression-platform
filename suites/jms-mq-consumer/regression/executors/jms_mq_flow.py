from __future__ import annotations

import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PRODUCER_BASE_URL = "http://localhost:8093"
CONSUMER_BASE_URL = "http://localhost:8094"


def _post(url: str, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _get_json(url: str) -> dict[str, object]:
    with urlopen(url) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _wait_for_processed(transaction_id: str, timeout_seconds: int = 30) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    url = f"{CONSUMER_BASE_URL}/api/jms/processed/{transaction_id}"
    while time.time() < deadline:
        try:
            return _get_json(url)
        except HTTPError as exc:
            if exc.code != 404:
                raise
        time.sleep(1)
    raise TimeoutError(f"Timed out waiting for consumer to process transaction: {transaction_id}")


def execute(input_payload: dict[str, object], context: dict[str, object]) -> dict[str, object]:
    publish_count = int(input_payload.get("publishCount", 1))
    publish_payload = dict(input_payload)
    publish_payload.pop("publishCount", None)
    for _ in range(max(1, publish_count)):
        _post(f"{PRODUCER_BASE_URL}/api/jms/tx/publish", publish_payload)
    processed = _wait_for_processed(str(input_payload["transactionId"]))
    return {
        "transactionId": processed["transactionId"],
        "accountId": processed["accountId"],
        "amount": processed["amount"],
        "currency": processed["currency"],
        "decision": processed["decision"],
        "attempts": processed["attempts"],
    }
