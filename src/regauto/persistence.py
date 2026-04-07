"""Persistence adapter for publishing execution results to the dashboard database."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from regauto.execution import TestExecutionResult
from regauto.models import ExecutionRun, Repository, TestResult
from regauto.reporting import should_fail_gate, summarize


def upsert_repository(session: Session, name: str, url: str | None, owner: str | None) -> Repository:
    """Create or update repository metadata."""
    repo = session.query(Repository).filter(Repository.name == name).one_or_none()
    if repo is None:
        repo = Repository(name=name, url=url, owner=owner)
        session.add(repo)
    else:
        repo.url = url
        repo.owner = owner
    session.commit()
    return repo


def persist_run(
    session: Session,
    repository: str,
    gate: str,
    trigger: str,
    results: list[TestExecutionResult],
    commit_sha: str | None = None,
    branch: str | None = None,
) -> ExecutionRun:
    """Persist a run and its test-level results."""
    summary = summarize(results)
    run = ExecutionRun(
        repository=repository,
        gate=gate,
        trigger=trigger,
        commit_sha=commit_sha,
        branch=branch,
        status="failed" if should_fail_gate(results) else "passed",
        pass_rate=float(summary["pass_rate"]),
        total=int(summary["total"]),
        finished_at=datetime.now(UTC),
    )
    for item in results:
        differences = None
        if item.comparison:
            differences = json.dumps([asdict(diff) for diff in item.comparison.differences], default=str)
        run.results.append(
            TestResult(
                test_id=item.test_id,
                service=item.service,
                team=item.team,
                gate=item.gate,
                status=item.status,
                service_type=item.service_type,
                failure_type=item.failure_type,
                duration_ms=item.duration_ms,
                error=item.error,
                differences_json=differences,
            )
        )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run
