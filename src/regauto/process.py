"""Safe process execution primitives for VM and CI runner orchestration."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    """Captured command result."""

    command: str
    cwd: Path
    return_code: int
    stdout: str
    stderr: str


class CommandExecutionError(RuntimeError):
    """Raised when a command exits non-zero."""

    def __init__(self, result: CommandResult, failure_type: str) -> None:
        self.result = result
        self.failure_type = failure_type
        output = "\n".join(part for part in [result.stdout[-2000:], result.stderr[-2000:]] if part)
        super().__init__(
            f"{failure_type} command failed with exit code {result.return_code}: "
            f"{result.command}\n{output}"
        )


def run_command(command: str, cwd: Path, failure_type: str, timeout_seconds: int = 1800) -> CommandResult:
    """Run a command using the host OS shell and capture stdout/stderr."""
    completed = subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    result = CommandResult(
        command=command,
        cwd=cwd,
        return_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if result.return_code != 0:
        raise CommandExecutionError(result, failure_type)
    return result
