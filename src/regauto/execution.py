"""Test execution engine and pluggable executors."""

from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import structlog

from regauto.comparison import ComparisonResult, JsonComparator
from regauto.config import TestCase
from regauto.jms import FileJmsProvider, JmsProvider, build_correlation_id

LOGGER = structlog.get_logger()


@dataclass
class TestExecutionResult:
    """Final result for a single test case."""

    test_id: str
    repo_name: str
    service: str
    gate: str
    team: str
    status: str
    duration_ms: int
    comparison: ComparisonResult | None = None
    error: str | None = None
    actual_output: Any | None = None
    tags: list[str] = field(default_factory=list)
    service_type: str = "unknown"
    failure_type: str | None = None


class TestExecutor(ABC):
    """Executor plugin contract."""

    @abstractmethod
    def execute(self, test_case: TestCase, input_payload: Any) -> Any:
        """Execute a test case and return actual output."""


class EchoExecutor(TestExecutor):
    """Local executor used for examples and contract-like deterministic tests."""

    def execute(self, test_case: TestCase, input_payload: Any) -> Any:
        return input_payload


class RestExecutor(TestExecutor):
    """REST executor for live microservice regression calls."""

    def execute(self, test_case: TestCase, input_payload: Any) -> Any:
        config = test_case.metadata.rest or test_case.metadata.http
        if not config:
            raise ValueError(f"Test {test_case.id} uses REST executor without rest config")
        if config.response_fixture:
            fixture = test_case.path / config.response_fixture
            return json.loads(fixture.read_text(encoding="utf-8"))
        url = str(config.url or "")
        if not url:
            if not config.base_url or not config.endpoint:
                raise ValueError(f"Test {test_case.id} must define url or base_url plus endpoint")
            endpoint = config.endpoint.format(**config.path_params)
            url = str(config.base_url).rstrip("/") + "/" + endpoint.lstrip("/")
        headers = dict(config.headers)
        if config.auth_token_env:
            token = os.getenv(config.auth_token_env)
            if not token:
                raise ValueError(f"Missing auth token environment variable: {config.auth_token_env}")
            headers["Authorization"] = f"Bearer {token}"
        with httpx.Client(timeout=config.timeout_seconds) as client:
            response = client.request(
                config.method,
                url,
                json=input_payload if config.method != "GET" else None,
                params={**config.query_params, **(input_payload if config.method == "GET" and isinstance(input_payload, dict) else {})},
                headers=headers,
            )
            actual = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.json() if response.content else None,
            }
            if response.status_code != config.expected_status:
                return actual
            return actual


class JmsExecutor(TestExecutor):
    """JMS executor using a provider abstraction."""

    def __init__(self, providers: dict[str, JmsProvider] | None = None) -> None:
        self.providers = providers or {"file": FileJmsProvider()}

    def execute(self, test_case: TestCase, input_payload: Any) -> Any:
        if not test_case.metadata.jms:
            raise ValueError(f"Test {test_case.id} uses JMS executor without jms config")
        config = test_case.metadata.jms
        provider = self.providers.get(config.provider)
        if not provider:
            raise ValueError(f"No JMS provider registered for {config.provider}")
        last_error: Exception | None = None
        for _ in range(max(config.retry_count, 1)):
            try:
                correlation_id = build_correlation_id(config, input_payload)
                return provider.request_reply(test_case, input_payload, correlation_id)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        raise RuntimeError(f"JMS execution failed after {config.retry_count} attempt(s): {last_error}")


class ExecutorRegistry:
    """Registry for built-in and future executor plugins."""

    def __init__(self) -> None:
        self._executors: dict[str, TestExecutor] = {
            "echo": EchoExecutor(),
            "http": RestExecutor(),
            "rest": RestExecutor(),
            "jms": JmsExecutor(),
        }

    def get(self, name: str) -> TestExecutor:
        try:
            return self._executors[name]
        except KeyError as exc:
            raise ValueError(f"Unknown executor plugin: {name}") from exc

    def register(self, name: str, executor: TestExecutor) -> None:
        self._executors[name] = executor


class ExecutionEngine:
    """Loads assets, executes tests, and compares actual output with expected JSON."""

    def __init__(self, comparator: JsonComparator | None = None, registry: ExecutorRegistry | None = None) -> None:
        self.comparator = comparator or JsonComparator()
        self.registry = registry or ExecutorRegistry()

    def run(self, test_cases: list[TestCase]) -> list[TestExecutionResult]:
        return [self.run_one(test_case) for test_case in test_cases]

    def run_one(self, test_case: TestCase) -> TestExecutionResult:
        start = time.perf_counter()
        try:
            input_payload = self._load_json(test_case.input_path)
            expected_payload = self._load_json(test_case.expected_output_path)
            executor_name = test_case.metadata.executor
            if test_case.metadata.service_type in {"rest", "jms"}:
                executor_name = test_case.metadata.service_type
            executor = self.registry.get(executor_name)
            actual_payload = executor.execute(test_case, input_payload)
            comparison = self.comparator.compare(
                expected_payload,
                actual_payload,
                ignore_paths=set(test_case.metadata.ignore_json_paths),
            )
            status = "passed" if comparison.passed else "failed"
            return self._result(test_case, start, status, comparison, None, actual_payload)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("test_execution_error", test_id=test_case.id, error=str(exc))
            return self._result(test_case, start, "error", None, str(exc), None, "execution_failure")

    def _result(
        self,
        test_case: TestCase,
        start: float,
        status: str,
        comparison: ComparisonResult | None,
        error: str | None,
        actual_output: Any | None,
        failure_type: str | None = None,
    ) -> TestExecutionResult:
        return TestExecutionResult(
            test_id=test_case.id,
            repo_name=test_case.repo_name,
            service=test_case.service,
            gate=test_case.gate,
            team=test_case.metadata.team,
            status=status,
            duration_ms=int((time.perf_counter() - start) * 1000),
            comparison=comparison,
            error=error,
            actual_output=actual_output,
            tags=test_case.tags,
            service_type=test_case.service_type,
            failure_type=failure_type,
        )

    def _load_json(self, path: Path) -> Any:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
