from __future__ import annotations

import json
from urllib.request import Request, urlopen


BASE_URL = "http://localhost:8093"


def _post(path: str, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{BASE_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def execute(input_payload: dict[str, object], context: dict[str, object]) -> dict[str, object]:
    response = _post("/api/jms/tx/publish", input_payload)
    return {"status": response["status"], "transactionId": response["transactionId"]}
