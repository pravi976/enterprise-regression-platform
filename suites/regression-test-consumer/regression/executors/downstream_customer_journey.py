from __future__ import annotations

import json
from urllib.request import urlopen


BASE_URL = "http://localhost:8092"


def _get(path: str) -> dict[str, object]:
    with urlopen(f"{BASE_URL}{path}") as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def execute(input_payload: dict[str, object], context: dict[str, object]) -> dict[str, object]:
    scenario = input_payload["scenario"]
    customer_id = input_payload.get("customerId")
    if scenario == "summary":
        response = _get(f"/api/downstream/customers/{customer_id}/summary")
        return {
            "customerId": response["customerId"],
            "customerName": response["customerName"],
            "tier": response["tier"],
            "activeOrders": response["activeOrders"],
            "lastOrderId": response["lastOrderId"],
            "upstreamStatus": response["upstreamStatus"],
        }
    if scenario == "journey":
        response = _get(f"/api/downstream/customers/{customer_id}/journey")
        return {
            "customerId": response["customerId"],
            "customerName": response["customerName"],
            "city": response["city"],
            "tier": response["tier"],
            "activeOrders": response["activeOrders"],
            "recommendedAction": response["recommendedAction"],
            "journeyStatus": response["journeyStatus"],
        }
    if scenario == "ops":
        response = _get("/api/downstream/ops/status")
        return {
            "service": response["service"],
            "status": response["status"],
            "upstreamAvailable": response["upstreamAvailable"],
            "customerJourneysLoaded": response["customerJourneysLoaded"],
            "resilienceMode": response["resilienceMode"],
        }
    raise ValueError(f"Unsupported downstream scenario: {scenario}")
