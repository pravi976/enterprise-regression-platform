"""Folder-based regression test discovery."""

from __future__ import annotations

from pathlib import Path

import structlog

from regauto.config import TestCase, TestMetadata, load_repository_config, load_yaml

LOGGER = structlog.get_logger()


class TestDiscovery:
    """Discovers tests from repo-root/regression/services/<service>/<gate>/<test>."""

    def discover(
        self,
        repo_root: Path,
        gate: str | None = None,
        services: set[str] | None = None,
        tags: set[str] | None = None,
        branch: str | None = None,
    ) -> list[TestCase]:
        repo_root = repo_root.resolve()
        repo_config = load_repository_config(repo_root)
        services_root = repo_root / repo_config.services_root
        if not services_root.exists():
            LOGGER.warning("services_root_missing", path=str(services_root))
            return []

        tests: list[TestCase] = []
        for service_dir in sorted(path for path in services_root.iterdir() if path.is_dir()):
            service = service_dir.name
            if services and service not in services:
                continue
            for gate_dir in sorted(path for path in service_dir.iterdir() if path.is_dir()):
                current_gate = gate_dir.name
                if gate and current_gate != gate:
                    continue
                for test_dir in sorted(path for path in gate_dir.iterdir() if path.is_dir()):
                    test_case = self._build_test_case(repo_config.repository, service, current_gate, test_dir)
                    if not test_case:
                        continue
                    if branch and test_case.metadata.branches and branch not in test_case.metadata.branches:
                        continue
                    if tags and not tags.intersection(test_case.tags):
                        continue
                    tests.append(test_case)
        LOGGER.info("tests_discovered", count=len(tests), repo=str(repo_root), gate=gate)
        return tests

    def _build_test_case(
        self, repo_name: str, service: str, gate: str, test_dir: Path
    ) -> TestCase | None:
        input_path = test_dir / "input.json"
        expected_path = test_dir / "expected_output.json"
        if not input_path.exists() or not expected_path.exists():
            missing = [
                str(path.name)
                for path in (input_path, expected_path)
                if not path.exists()
            ]
            raise ValueError(
                f"Invalid regression test folder {test_dir}: missing required asset(s): "
                f"{', '.join(missing)}"
            )
        metadata_path = test_dir / "metadata.yaml"
        metadata = TestMetadata.model_validate(load_yaml(metadata_path))
        service_type = metadata.service_type if metadata.service_type != "echo" else metadata.executor
        tags = sorted(set(metadata.tags + [gate, service, metadata.team, service_type]))
        test_id = metadata.id or f"{service}.{gate}.{test_dir.name}"
        return TestCase(
            id=test_id,
            repo_name=repo_name,
            service=service,
            gate=gate,
            name=metadata.name or test_dir.name,
            path=test_dir,
            input_path=input_path,
            expected_output_path=expected_path,
            metadata_path=metadata_path if metadata_path.exists() else None,
            metadata=metadata,
            tags=tags,
            service_type=service_type,
        )
