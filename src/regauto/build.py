"""Repository build orchestration for traditional runners and servers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import structlog

from regauto.config import BranchPolicy, CommandHookConfig, RepositoryConfig
from regauto.process import CommandResult, run_command

LOGGER = structlog.get_logger()


@dataclass
class BuildResult:
    """Build orchestration outcome."""

    status: str
    commands: list[CommandResult] = field(default_factory=list)


class BuildOrchestrator:
    """Runs pre-build, build, post-build, and pre-test hooks from configuration."""

    def run(self, repo_root: Path, repo_config: RepositoryConfig, policy: BranchPolicy) -> BuildResult:
        commands = self._merge_commands(repo_root, repo_config.commands, policy.commands, repo_config.build_tool)
        executed: list[CommandResult] = []
        for command in commands:
            LOGGER.info("build_command_start", command=command, cwd=str(repo_root))
            executed.append(run_command(command, repo_root, "build_failure"))
        return BuildResult(status="passed", commands=executed)

    def run_pre_test(self, repo_root: Path, repo_config: RepositoryConfig, policy: BranchPolicy) -> list[CommandResult]:
        commands = [*repo_config.commands.pre_test, *policy.commands.pre_test]
        return [run_command(command, repo_root, "startup_failure") for command in commands]

    def run_post_test(self, repo_root: Path, repo_config: RepositoryConfig, policy: BranchPolicy) -> list[CommandResult]:
        commands = [*policy.commands.post_test, *repo_config.commands.post_test]
        return [run_command(command, repo_root, "environment_failure") for command in commands]

    def _merge_commands(
        self,
        repo_root: Path,
        repo_commands: CommandHookConfig,
        policy_commands: CommandHookConfig,
        build_tool: str,
    ) -> list[str]:
        build_commands = [*repo_commands.build, *policy_commands.build]
        if not build_commands:
            build_commands = self._default_build_commands(repo_root, build_tool)
        return self._dedupe([
            *repo_commands.pre_build,
            *policy_commands.pre_build,
            *build_commands,
            *policy_commands.post_build,
            *repo_commands.post_build,
        ])

    def _default_build_commands(self, repo_root: Path, build_tool: str) -> list[str]:
        gradle_command = "gradlew.bat build" if (repo_root / "gradlew.bat").exists() else "./gradlew build"
        defaults = {
            "maven": ["mvn -B clean verify -DskipTests=false"],
            "gradle": [gradle_command],
            "npm": ["npm ci", "npm test -- --watch=false", "npm run build"],
            "custom": [],
            "none": [],
        }
        return defaults.get(build_tool, [])

    def _dedupe(self, commands: list[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for command in commands:
            if command not in seen:
                seen.add(command)
                unique.append(command)
        return unique
