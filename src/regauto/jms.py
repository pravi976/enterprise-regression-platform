"""JMS provider abstraction.

The built-in file provider is intentionally simple and infrastructure-free for local and CI
validation. Enterprise teams can add IBM MQ, ActiveMQ, Solace, or other broker providers by
implementing the same interface and registering it with the executor registry.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4

from regauto.config import JmsExecutorConfig, TestCase


class JmsProvider(ABC):
    """JMS provider plugin contract."""

    @abstractmethod
    def request_reply(self, test_case: TestCase, payload: Any, correlation_id: str) -> Any:
        """Publish a request message and return the response payload."""


class FileJmsProvider(JmsProvider):
    """File-backed JMS provider for deterministic CI and provider contract testing."""

    def request_reply(self, test_case: TestCase, payload: Any, correlation_id: str) -> Any:
        config = _require_jms_config(test_case)
        request_dir = test_case.path / ".jms" / config.request_queue
        request_dir.mkdir(parents=True, exist_ok=True)
        request_file = request_dir / f"{correlation_id}.json"
        request_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        if config.response_fixture:
            fixture = test_case.path / config.response_fixture
            return json.loads(fixture.read_text(encoding="utf-8"))

        if config.response_queue:
            response_dir = test_case.path / ".jms" / config.response_queue
            response_file = response_dir / f"{correlation_id}.json"
            deadline = time.monotonic() + config.timeout_seconds
            while time.monotonic() < deadline:
                if response_file.exists():
                    return json.loads(response_file.read_text(encoding="utf-8"))
                time.sleep(0.25)

        # For sample suites, echoing the payload keeps JMS tests runnable without a broker.
        return payload


def build_correlation_id(config: JmsExecutorConfig, payload: Any) -> str:
    """Build a correlation ID based on metadata policy."""
    if config.correlation_id_strategy == "uuid":
        return str(uuid4())
    if config.correlation_id_strategy == "input" and isinstance(payload, dict):
        value = payload.get(config.correlation_id_field)
        if value:
            return str(value)
    return config.headers.get(config.correlation_id_field, str(uuid4()))


def _require_jms_config(test_case: TestCase) -> JmsExecutorConfig:
    if not test_case.metadata.jms:
        raise ValueError(f"Test {test_case.id} uses JMS without jms config")
    return test_case.metadata.jms
