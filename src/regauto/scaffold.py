"""Scaffolding helpers for team-owned regression test assets."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ScaffoldResult:
    """Files created or skipped by a scaffold operation."""

    created: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)


def service_module_name(service: str) -> str:
    """Convert a service name into a safe Python module file name."""
    module = re.sub(r"[^A-Za-z0-9_]+", "_", service.strip()).strip("_").lower()
    if not module:
        raise ValueError("Service name must contain at least one letter or number")
    if module[0].isdigit():
        module = f"service_{module}"
    return module


def test_folder_name(test_id: str) -> str:
    """Convert a test id into a stable folder name."""
    folder = re.sub(r"[^A-Za-z0-9_-]+", "_", test_id.strip()).strip("_")
    if not folder:
        raise ValueError("Test id must contain at least one letter or number")
    return folder


def scaffold_python_test(
    repo_root: Path,
    service: str,
    gate: str,
    test_id: str,
    team: str,
    branches: list[str],
    tags: list[str] | None = None,
    force: bool = False,
) -> ScaffoldResult:
    """Create a service-owned Python executor and matching test asset skeleton."""
    repo_root = repo_root.resolve()
    module_name = service_module_name(service)
    folder_name = test_folder_name(test_id)
    branch_values = branches or ["main", "develop", "test", "release"]
    tag_values = sorted(set((tags or []) + [gate, service, "python", *branch_values]))

    executor_path = repo_root / "regression" / "executors" / f"{module_name}.py"
    test_dir = repo_root / "regression" / "services" / service / gate / folder_name
    files = {
        executor_path: _executor_template(),
        test_dir / "metadata.yaml": _metadata_template(test_id, service, gate, team, tag_values, branch_values, module_name),
        test_dir / "input.json": _json_template({"sampleId": "SAMPLE-001"}),
        test_dir / "expected_output.json": _json_template(
            {
                "body": {
                    "service": service,
                    "status": "TODO",
                    "input": {"sampleId": "SAMPLE-001"},
                }
            }
        ),
    }

    created: list[Path] = []
    skipped: list[Path] = []
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not force:
            skipped.append(path)
            continue
        path.write_text(content, encoding="utf-8")
        created.append(path)
    return ScaffoldResult(created=created, skipped=skipped)


def _executor_template() -> str:
    return '''"""Team-owned regression executor.

Replace the TODO body with service-specific logic. The return value must be
JSON-serializable because the central framework compares it with
expected_output.json.
"""

from typing import Any


def execute(input_payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Build the actual output for this service regression test."""
    return {
        "body": {
            "service": context["service"],
            "status": "TODO",
            "input": input_payload,
        }
    }
'''


def _metadata_template(
    test_id: str,
    service: str,
    gate: str,
    team: str,
    tags: list[str],
    branches: list[str],
    module_name: str,
) -> str:
    return "\n".join(
        [
            f"id: {test_id}",
            f"name: {service} Python executor regression",
            f"team: {team}",
            f"microservice: {service}",
            "service_type: python",
            f"tags: [{', '.join(tags)}]",
            f"branches: [{', '.join(branches)}]",
            "severity: medium",
            "python:",
            f"  script: regression/executors/{module_name}.py",
            "  function: execute",
            "",
        ]
    )


def _json_template(payload: dict[str, object]) -> str:
    return json.dumps(payload, indent=2) + "\n"
