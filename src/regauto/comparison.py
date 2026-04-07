"""JSON comparator engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Difference:
    """Single expected-vs-actual JSON difference."""

    path: str
    expected: Any
    actual: Any
    message: str


@dataclass
class ComparisonResult:
    """Comparator output."""

    passed: bool
    differences: list[Difference] = field(default_factory=list)


class JsonComparator:
    """Strict recursive JSON comparator with configurable ignored paths."""

    def compare(self, expected: Any, actual: Any, ignore_paths: set[str] | None = None) -> ComparisonResult:
        differences: list[Difference] = []
        self._compare_value("$", expected, actual, ignore_paths or set(), differences)
        return ComparisonResult(passed=not differences, differences=differences)

    def _compare_value(
        self,
        path: str,
        expected: Any,
        actual: Any,
        ignore_paths: set[str],
        differences: list[Difference],
    ) -> None:
        if path in ignore_paths:
            return
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                differences.append(Difference(path, expected, actual, "type mismatch"))
                return
            for key in expected.keys() - actual.keys():
                child_path = f"{path}.{key}"
                if child_path not in ignore_paths:
                    differences.append(Difference(child_path, expected[key], None, "missing key"))
            for key in actual.keys() - expected.keys():
                child_path = f"{path}.{key}"
                if child_path not in ignore_paths:
                    differences.append(Difference(child_path, None, actual[key], "unexpected key"))
            for key in expected.keys() & actual.keys():
                self._compare_value(f"{path}.{key}", expected[key], actual[key], ignore_paths, differences)
            return
        if isinstance(expected, list):
            if not isinstance(actual, list):
                differences.append(Difference(path, expected, actual, "type mismatch"))
                return
            if len(expected) != len(actual):
                differences.append(Difference(path, len(expected), len(actual), "list length mismatch"))
            for index, (expected_item, actual_item) in enumerate(zip(expected, actual, strict=False)):
                self._compare_value(f"{path}[{index}]", expected_item, actual_item, ignore_paths, differences)
            return
        if expected != actual:
            differences.append(Difference(path, expected, actual, "value mismatch"))
