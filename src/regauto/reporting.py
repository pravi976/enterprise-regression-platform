"""Reporting engine for JSON, JUnit XML, and exit-code based CI gates."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement

from regauto.execution import TestExecutionResult


def summarize(results: list[TestExecutionResult]) -> dict[str, object]:
    """Build an executive and machine-readable summary."""
    total = len(results)
    failed = sum(1 for item in results if item.status == "failed")
    errored = sum(1 for item in results if item.status == "error")
    passed = sum(1 for item in results if item.status == "passed")
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total": total,
        "passed": passed,
        "failed": failed,
        "errored": errored,
        "pass_rate": round((passed / total) * 100, 2) if total else 100.0,
        "by_service": _group_counts(results, "service"),
        "by_team": _group_counts(results, "team"),
        "by_gate": _group_counts(results, "gate"),
        "by_service_type": _group_counts(results, "service_type"),
        "by_failure_type": _group_counts(results, "failure_type"),
    }


def should_fail_gate(results: list[TestExecutionResult]) -> bool:
    """Return True when CI should fail."""
    return any(result.status in {"failed", "error"} for result in results)


class ReportWriter:
    """Writes regression results in formats consumed by CI and dashboards."""

    def write(self, results: list[TestExecutionResult], output_dir: Path) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "results.json"
        summary_path = output_dir / "summary.json"
        junit_path = output_dir / "junit.xml"
        json_path.write_text(
            json.dumps([self._serialize_result(result) for result in results], indent=2),
            encoding="utf-8",
        )
        summary_path.write_text(json.dumps(summarize(results), indent=2), encoding="utf-8")
        self._write_junit(results, junit_path)
        return {"results": json_path, "summary": summary_path, "junit": junit_path}

    def _serialize_result(self, result: TestExecutionResult) -> dict[str, object]:
        payload = asdict(result)
        if result.comparison:
            payload["comparison"] = {
                "passed": result.comparison.passed,
                "differences": [asdict(diff) for diff in result.comparison.differences],
            }
        return payload

    def _write_junit(self, results: list[TestExecutionResult], junit_path: Path) -> None:
        suite = Element(
            "testsuite",
            name="enterprise-regression",
            tests=str(len(results)),
            failures=str(sum(1 for result in results if result.status == "failed")),
            errors=str(sum(1 for result in results if result.status == "error")),
        )
        for result in results:
            case = SubElement(
                suite,
                "testcase",
                classname=f"{result.repo_name}.{result.service}.{result.gate}",
                name=result.test_id,
                time=str(result.duration_ms / 1000),
            )
            if result.status == "failed" and result.comparison:
                message = "; ".join(diff.message for diff in result.comparison.differences)
                failure = SubElement(case, "failure", message=message[:500])
                failure.text = json.dumps([asdict(diff) for diff in result.comparison.differences], default=str)
            if result.status == "error":
                error = SubElement(case, "error", message=(result.error or "execution error")[:500])
                error.text = result.error
        ElementTree(suite).write(junit_path, encoding="utf-8", xml_declaration=True)


def _group_counts(results: list[TestExecutionResult], attribute: str) -> dict[str, dict[str, int]]:
    grouped: dict[str, dict[str, int]] = {}
    for result in results:
        key = str(getattr(result, attribute) or "none")
        grouped.setdefault(key, {"total": 0, "passed": 0, "failed": 0, "error": 0})
        grouped[key]["total"] += 1
        grouped[key][result.status] += 1
    return grouped
