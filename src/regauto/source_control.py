"""GitHub branch checkout and pull orchestration for standard runners."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import structlog

from regauto.process import CommandExecutionError, run_command

LOGGER = structlog.get_logger()


@dataclass(frozen=True)
class CheckoutRequest:
    """Repository checkout request."""

    remote_url: str
    branch: str
    workspace_root: Path
    directory_name: str
    clean: bool = False


@dataclass(frozen=True)
class CheckoutResult:
    """Repository checkout result."""

    repo_root: Path
    branch: str
    commit_sha: str


class GitRepositoryManager:
    """Clone, fetch, checkout, and pull GitHub branches on a normal server/runner."""

    def checkout(self, request: CheckoutRequest) -> CheckoutResult:
        request.workspace_root.mkdir(parents=True, exist_ok=True)
        repo_root = request.workspace_root / request.directory_name
        if not (repo_root / ".git").exists():
            run_command(
                f'git clone --branch "{request.branch}" "{request.remote_url}" "{repo_root}"',
                request.workspace_root,
                "source_checkout_failure",
            )
        else:
            run_command("git fetch --all --prune", repo_root, "source_checkout_failure")
            run_command(f'git checkout "{request.branch}"', repo_root, "source_checkout_failure")
            if request.clean:
                run_command("git clean -fdx", repo_root, "source_checkout_failure")
                run_command("git reset --hard HEAD", repo_root, "source_checkout_failure")
            run_command(f'git pull --ff-only origin "{request.branch}"', repo_root, "source_checkout_failure")
        commit = run_command("git rev-parse HEAD", repo_root, "source_checkout_failure").stdout.strip()
        LOGGER.info("repository_checked_out", repo=str(repo_root), branch=request.branch, commit=commit)
        return CheckoutResult(repo_root=repo_root, branch=request.branch, commit_sha=commit)


def is_checkout_failure(error: Exception) -> bool:
    """Return True when an exception represents a source checkout failure."""
    return isinstance(error, CommandExecutionError) and error.failure_type == "source_checkout_failure"
