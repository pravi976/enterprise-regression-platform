"""Command-line interface for discovery, execution, onboarding, and publishing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from regauto.config import load_repository_config
from regauto.build import BuildOrchestrator
from regauto.config import resolve_branch_policy, resolve_gate_decision
from regauto.db import SessionLocal, create_schema
from regauto.discovery import TestDiscovery
from regauto.execution import ExecutionEngine
from regauto.impact import impacted_services
from regauto.logging_config import configure_logging
from regauto.persistence import persist_run, upsert_repository
from regauto.reporting import (
    ReportWriter,
    print_console_report,
    publish_github_actions_output,
    should_fail_gate,
    summarize,
)
from regauto.source_control import CheckoutRequest, GitRepositoryManager

app = typer.Typer(help="Enterprise regression automation CLI")
console = Console()


def _run(
    repo_root: Path,
    gate: str | None,
    results_dir: Path,
    tags: list[str] | None,
    services: list[str] | None,
    publish: bool,
    trigger: str,
    commit_sha: str | None,
    branch: str | None,
    exclude_tags: list[str] | None = None,
) -> None:
    configure_logging()
    gate_decision = resolve_gate_decision(repo_root, gate, branch)
    if not gate_decision.enabled:
        reason = gate_decision.reason or "Gate disabled by policy"
        results_dir.mkdir(parents=True, exist_ok=True)
        skipped_summary = {
            "gate": gate,
            "branch": branch,
            "status": "skipped",
            "reason": reason,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errored": 0,
            "pass_rate": 100.0,
        }
        (results_dir / "summary.json").write_text(json.dumps(skipped_summary, indent=2), encoding="utf-8")
        console.print(skipped_summary)
        raise typer.Exit(code=0)
    policy = resolve_branch_policy(repo_root, branch)
    effective_tags = set(tags or [])
    effective_tags.update(policy.include_tags)
    effective_services = set(services or [])
    effective_services.update(policy.services)
    try:
        tests = TestDiscovery().discover(
            repo_root=repo_root,
            gate=gate,
            services=effective_services or None,
            tags=effective_tags or None,
            branch=branch,
        )
    except ValueError as exc:
        results_dir.mkdir(parents=True, exist_ok=True)
        error_summary = {
            "gate": gate,
            "branch": branch,
            "status": "error",
            "reason": str(exc),
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errored": 1,
            "pass_rate": 0.0,
        }
        (results_dir / "summary.json").write_text(json.dumps(error_summary, indent=2), encoding="utf-8")
        (results_dir / "results.json").write_text("[]", encoding="utf-8")
        (results_dir / "junit.xml").write_text(
            "<?xml version='1.0' encoding='utf-8'?>\n"
            "<testsuite name=\"enterprise-regression\" tests=\"0\" failures=\"0\" errors=\"1\" />",
            encoding="utf-8",
        )
        console.print(error_summary)
        raise typer.Exit(code=2) from exc
    excluded = set(exclude_tags or []) | set(policy.exclude_tags)
    if excluded:
        tests = [test for test in tests if not excluded.intersection(test.tags)]
    if not tests:
        results_dir.mkdir(parents=True, exist_ok=True)
        empty_summary = {
            "gate": gate,
            "branch": branch,
            "status": "error",
            "reason": "No regression tests were discovered for the enabled gate and branch",
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errored": 1,
            "pass_rate": 0.0,
        }
        (results_dir / "summary.json").write_text(json.dumps(empty_summary, indent=2), encoding="utf-8")
        (results_dir / "results.json").write_text("[]", encoding="utf-8")
        (results_dir / "junit.xml").write_text(
            "<?xml version='1.0' encoding='utf-8'?>\n"
            "<testsuite name=\"enterprise-regression\" tests=\"0\" failures=\"0\" errors=\"1\" />",
            encoding="utf-8",
        )
        console.print(empty_summary)
        raise typer.Exit(code=2)
    results = ExecutionEngine().run(tests)
    written = ReportWriter().write(results, results_dir)
    print_console_report(results)
    publish_github_actions_output(results, results_dir)
    summary = summarize(results)
    console.print(summary)
    console.print({name: str(path) for name, path in written.items()})
    if publish:
        create_schema()
        with SessionLocal() as session:
            repo_name = load_repository_config(repo_root).repository
            persist_run(session, repo_name, gate or "full", trigger, results, commit_sha, branch)
    if should_fail_gate(results):
        raise typer.Exit(code=1)


def _checkout_build_and_run(
    remote_url: str,
    workspace_root: Path,
    directory_name: str,
    branch: str,
    gate: str,
    results_dir: Path,
    publish: bool,
    trigger: str,
    clean: bool,
) -> None:
    configure_logging()
    checkout = GitRepositoryManager().checkout(
        CheckoutRequest(
            remote_url=remote_url,
            branch=branch,
            workspace_root=workspace_root,
            directory_name=directory_name,
            clean=clean,
        )
    )
    gate_decision = resolve_gate_decision(checkout.repo_root, gate, branch)
    if not gate_decision.enabled:
        reason = gate_decision.reason or "Gate disabled by policy"
        results_dir.mkdir(parents=True, exist_ok=True)
        skipped_summary = {
            "gate": gate,
            "branch": branch,
            "status": "skipped",
            "reason": reason,
            "total": 0,
            "pass_rate": 100.0,
        }
        (results_dir / "summary.json").write_text(json.dumps(skipped_summary, indent=2), encoding="utf-8")
        console.print(f"Skipping {gate} for {branch}: {reason}")
        raise typer.Exit(code=0)
    repo_config = load_repository_config(checkout.repo_root)
    policy = resolve_branch_policy(checkout.repo_root, branch)
    BuildOrchestrator().run(checkout.repo_root, repo_config, policy)
    BuildOrchestrator().run_pre_test(checkout.repo_root, repo_config, policy)
    try:
        _run(
            checkout.repo_root,
            gate,
            results_dir,
            None,
            None,
            publish,
            trigger,
            checkout.commit_sha,
            branch,
        )
    finally:
        BuildOrchestrator().run_post_test(checkout.repo_root, repo_config, policy)


def _build_and_run_existing_repo(
    repo_root: Path,
    branch: str,
    gate: str,
    results_dir: Path,
    publish: bool,
    trigger: str,
    commit_sha: str | None = None,
) -> None:
    configure_logging()
    repo_root = repo_root.resolve()
    gate_decision = resolve_gate_decision(repo_root, gate, branch)
    if not gate_decision.enabled:
        reason = gate_decision.reason or "Gate disabled by policy"
        results_dir.mkdir(parents=True, exist_ok=True)
        skipped_summary = {
            "gate": gate,
            "branch": branch,
            "status": "skipped",
            "reason": reason,
            "total": 0,
            "pass_rate": 100.0,
        }
        (results_dir / "summary.json").write_text(json.dumps(skipped_summary, indent=2), encoding="utf-8")
        console.print(skipped_summary)
        raise typer.Exit(code=0)
    repo_config = load_repository_config(repo_root)
    policy = resolve_branch_policy(repo_root, branch)
    orchestrator = BuildOrchestrator()
    orchestrator.run(repo_root, repo_config, policy)
    orchestrator.run_pre_test(repo_root, repo_config, policy)
    try:
        _run(repo_root, gate, results_dir, None, None, publish, trigger, commit_sha, branch)
    finally:
        orchestrator.run_post_test(repo_root, repo_config, policy)


@app.command("add-repo")
def add_repo(
    name: Annotated[str, typer.Option(help="Logical repository name")],
    url: Annotated[str | None, typer.Option(help="Repository URL")] = None,
    owner: Annotated[str | None, typer.Option(help="Owning team or org")] = None,
) -> None:
    """Onboard a repository in metadata storage."""
    configure_logging()
    create_schema()
    with SessionLocal() as session:
        repo = upsert_repository(session, name, url, owner)
    console.print(f"Repository onboarded: {repo.name}")


@app.command("discover-tests")
def discover_tests(
    repo_root: Annotated[Path, typer.Option(help="Application repository root")],
    gate: Annotated[str | None, typer.Option(help="Optional gate filter")] = None,
    tag: Annotated[list[str] | None, typer.Option("--tag", help="Tag filter")] = None,
    service: Annotated[list[str] | None, typer.Option("--service", help="Service filter")] = None,
) -> None:
    """Discover folder-based regression tests."""
    configure_logging()
    tests = TestDiscovery().discover(repo_root, gate=gate, tags=set(tag or []), services=set(service or []))
    for test in tests:
        console.print(f"{test.id} | {test.service} | {test.gate} | {','.join(test.tags)}")


@app.command("impacted-tests")
def impacted_tests(
    repo_root: Annotated[Path, typer.Option(help="Application repository root")],
    changed_file: Annotated[list[str], typer.Option("--changed-file", help="Changed file path from PR")],
) -> None:
    """Print services impacted by changed files."""
    services = impacted_services(repo_root, changed_file)
    for service in sorted(services):
        console.print(service)


@app.command("run-gate1")
def run_gate1(
    repo_root: Annotated[Path, typer.Option(help="Application repository root")],
    results_dir: Annotated[Path, typer.Option(help="Output directory")] = Path("results/gate1"),
    tag: Annotated[list[str] | None, typer.Option("--tag")] = None,
    service: Annotated[list[str] | None, typer.Option("--service")] = None,
    publish: Annotated[bool, typer.Option(help="Publish to metadata DB")] = False,
    trigger: Annotated[str, typer.Option(help="schedule, pr, commit, manual")] = "manual",
    commit_sha: Annotated[str | None, typer.Option()] = None,
    branch: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Run Gate 1 fast critical regression tests."""
    _run(repo_root, "gate1", results_dir, tag, service, publish, trigger, commit_sha, branch)


@app.command("run-gate2")
def run_gate2(
    repo_root: Annotated[Path, typer.Option(help="Application repository root")],
    results_dir: Annotated[Path, typer.Option(help="Output directory")] = Path("results/gate2"),
    tag: Annotated[list[str] | None, typer.Option("--tag")] = None,
    service: Annotated[list[str] | None, typer.Option("--service")] = None,
    publish: Annotated[bool, typer.Option(help="Publish to metadata DB")] = False,
    trigger: Annotated[str, typer.Option(help="schedule, pr, commit, manual")] = "manual",
    commit_sha: Annotated[str | None, typer.Option()] = None,
    branch: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Run Gate 2 broader regression tests."""
    _run(repo_root, "gate2", results_dir, tag, service, publish, trigger, commit_sha, branch)


@app.command("run-full")
def run_full(
    repo_root: Annotated[Path, typer.Option(help="Application repository root")],
    results_dir: Annotated[Path, typer.Option(help="Output directory")] = Path("results/full"),
    publish: Annotated[bool, typer.Option(help="Publish to metadata DB")] = False,
    trigger: Annotated[str, typer.Option(help="schedule, pr, commit, manual")] = "manual",
) -> None:
    """Run all discovered regression tests."""
    _run(repo_root, None, results_dir, None, None, publish, trigger, None, None)


@app.command("checkout-build-run")
def checkout_build_run(
    remote_url: Annotated[str, typer.Option(help="GitHub HTTPS or SSH repository URL")],
    branch: Annotated[str, typer.Option(help="Branch to checkout, for example develop/test/release")],
    gate: Annotated[str, typer.Option(help="Gate to run, for example gate1 or gate2")],
    workspace_root: Annotated[Path, typer.Option(help="Local workspace root for cloned repositories")],
    directory_name: Annotated[str, typer.Option(help="Local directory name for the repository clone")],
    results_dir: Annotated[Path, typer.Option(help="Output directory")] = Path("results"),
    publish: Annotated[bool, typer.Option(help="Publish to metadata DB")] = False,
    trigger: Annotated[str, typer.Option(help="schedule, pr, commit, manual")] = "manual",
    clean: Annotated[bool, typer.Option(help="Clean untracked files before build")] = False,
) -> None:
    """Clone/fetch a branch, build the app, run a regression gate, and return CI exit code."""
    _checkout_build_and_run(
        remote_url=remote_url,
        workspace_root=workspace_root,
        directory_name=directory_name,
        branch=branch,
        gate=gate,
        results_dir=results_dir,
        publish=publish,
        trigger=trigger,
        clean=clean,
    )


@app.command("build-run")
def build_run(
    repo_root: Annotated[Path, typer.Option(help="Existing checked-out application repository root")],
    branch: Annotated[str, typer.Option(help="Logical branch policy to apply")],
    gate: Annotated[str, typer.Option(help="Gate to run, for example gate1 or gate2")],
    results_dir: Annotated[Path, typer.Option(help="Output directory")] = Path("results"),
    publish: Annotated[bool, typer.Option(help="Publish to metadata DB")] = False,
    trigger: Annotated[str, typer.Option(help="schedule, pr, commit, manual")] = "manual",
    commit_sha: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Build an already checked-out repository and run a regression gate."""
    _build_and_run_existing_repo(repo_root, branch, gate, results_dir, publish, trigger, commit_sha)


@app.command("init-db")
def init_db() -> None:
    """Create starter database schema."""
    create_schema()
    console.print("Database schema initialized")


if __name__ == "__main__":
    app()
