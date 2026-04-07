"""Map changed files to impacted services and tests."""

from __future__ import annotations

from pathlib import PurePosixPath, Path

from regauto.config import load_repository_config


def impacted_services(repo_root: Path, changed_files: list[str]) -> set[str]:
    """Resolve changed repository paths to impacted microservices."""
    config = load_repository_config(repo_root)
    impacted: set[str] = set()
    for changed_file in changed_files:
        normalized = changed_file.replace("\\", "/")
        path = PurePosixPath(normalized)
        for pattern, services in config.impact_map.items():
            if path.match(pattern):
                impacted.update(services)
        for service in config.service_owners:
            if service in normalized:
                impacted.add(service)
    return impacted
