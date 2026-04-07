"""Reporting engine for JSON, JUnit XML, and exit-code based CI gates."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement

from regauto.execution import TestExecutionResult


def print_console_report(results: list[TestExecutionResult]) -> None:
    """Print a readable report to stdout for CI logs and local runs."""
    summary = summarize(results)
    print("REGRESSION SUMMARY")
    print(
        " | ".join(
            [
                f"total={summary['total']}",
                f"passed={summary['passed']}",
                f"failed={summary['failed']}",
                f"errored={summary['errored']}",
                f"pass_rate={summary['pass_rate']}%",
            ]
        )
    )
    print("REGRESSION TEST RESULTS")
    for result in results:
        print(
            " | ".join(
                [
                    f"status={result.status.upper()}",
                    f"gate={result.gate}",
                    f"service={result.service}",
                    f"type={result.service_type}",
                    f"test={result.test_id}",
                    f"duration_ms={result.duration_ms}",
                    f"metadata={result.metadata_path or ''}",
                ]
            )
        )


def publish_github_actions_output(results: list[TestExecutionResult], output_dir: Path) -> None:
    """Publish job summary and clickable annotations when running in GitHub Actions."""
    if os.getenv("GITHUB_ACTIONS") != "true":
        return
    _write_github_step_summary(results, output_dir)
    _emit_github_annotations(results)


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


def _write_github_step_summary(results: list[TestExecutionResult], output_dir: Path) -> None:
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    summary = summarize(results)
    lines = [
        "## Enterprise Regression Results",
        "",
        f"- Total: `{summary['total']}`",
        f"- Passed: `{summary['passed']}`",
        f"- Failed: `{summary['failed']}`",
        f"- Errored: `{summary['errored']}`",
        f"- Pass rate: `{summary['pass_rate']}%`",
        "",
        "### Report Files",
        "",
        f"- `{output_dir / 'summary.json'}`",
        f"- `{output_dir / 'results.json'}`",
        f"- `{output_dir / 'junit.xml'}`",
        "",
        "### Test Results",
        "",
        "| Status | Gate | Service | Type | Test | Metadata |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        metadata = _github_annotation_path(result.metadata_path)
        metadata_link = f"[metadata.yaml]({metadata})" if metadata else ""
        lines.append(
            f"| {result.status.upper()} | {result.gate} | {result.service} | "
            f"{result.service_type} | `{result.test_id}` | {metadata_link} |"
        )
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _emit_github_annotations(results: list[TestExecutionResult]) -> None:
    for result in results:
        path = _github_annotation_path(result.metadata_path)
        title = f"{result.gate} {result.status}: {result.test_id}"
        message = (
            f"{result.service} {result.service_type} regression {result.status}; "
            f"duration_ms={result.duration_ms}"
        )
        level = "notice" if result.status == "passed" else "error"
        print(f"::{level} file={path},title={_escape_annotation(title)}::{_escape_annotation(message)}")


def _github_annotation_path(path: str | None) -> str:
    if not path:
        return "regression/config/regression.yaml"
    workspace = os.getenv("GITHUB_WORKSPACE")
    if workspace:
        try:
            return str(Path(path).resolve().relative_to(Path(workspace).resolve())).replace("\\", "/")
        except ValueError:
            pass
    return path.replace("\\", "/")


def _escape_annotation(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A").replace(",", "%2C")


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
