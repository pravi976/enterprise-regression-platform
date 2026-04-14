from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import urlopen


BASE_URL = "http://localhost:8091"


def _get(path: str, query: dict[str, object] | None = None) -> dict[str, object]:
    suffix = f"?{urlencode(query, doseq=True)}" if query else ""
    with urlopen(f"{BASE_URL}{path}{suffix}") as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def execute(input_payload: dict[str, object], context: dict[str, object]) -> dict[str, object]:
    scenario = input_payload["scenario"]
    if scenario == "customer-lookup":
        response = _get(f"/api/upstream/customers/{input_payload['customerId']}")
        return {
            "customerId": response["customerId"],
            "customerName": response["customerName"],
            "tier": response["tier"],
            "status": response["status"],
            "city": response["city"],
        }
    if scenario == "city-search":
        response = _get("/api/upstream/customers", {"city": input_payload["city"]})
        return {
            "city": response["city"],
            "count": response["count"],
            "customerIds": [customer["customerId"] for customer in response["customers"]],
        }
    raise ValueError(f"Unsupported upstream scenario: {scenario}")
