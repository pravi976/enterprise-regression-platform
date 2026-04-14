"""Configuration models for repositories and regression test metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


LAYER_ALIASES: dict[str, str] = {
    "gate1": "level1",
    "gate2": "level2",
}

VALID_LAYERS: tuple[str, ...] = ("level1", "level2", "level3", "level4", "level5")


def canonical_gate_name(gate: str | None) -> str | None:
    """Normalize legacy gate aliases to the enterprise layer model."""
    if gate is None:
        return None
    normalized = gate.strip().lower()
    if not normalized:
        return None
    return LAYER_ALIASES.get(normalized, normalized)


def gate_aliases(gate: str | None) -> set[str]:
    """Return all accepted names for a logical regression layer."""
    canonical = canonical_gate_name(gate)
    if canonical is None:
        return set()
    aliases = {canonical}
    aliases.update(alias for alias, target in LAYER_ALIASES.items() if target == canonical)
    return aliases


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    database_url: str = "sqlite:///./regression.db"
    log_level: str = "INFO"
    api_key: str | None = None
    github_webhook_secret: str | None = None
    github_token: str | None = None
    max_parallel_tests: int = 1
    runner_slots: int = 1
    queue_poll_seconds: float = 2.0
    queue_timeout_seconds: int = 900
    webhook_workspace_root: str = "./regression-workspaces"
    webhook_results_root: str = "./regression-results"
    webhook_clean_workspace: bool = True
    webhook_publish: bool = True

    model_config = SettingsConfigDict(env_prefix="REGAUTO_", env_file=".env", extra="ignore")


class CommandHookConfig(BaseModel):
    """Repository command hooks for traditional VM/runner build orchestration."""

    pre_build: list[str] = Field(default_factory=list)
    build: list[str] = Field(default_factory=list)
    post_build: list[str] = Field(default_factory=list)
    pre_test: list[str] = Field(default_factory=list)
    post_test: list[str] = Field(default_factory=list)


class BranchPolicy(BaseModel):
    """Branch-specific gate, environment, and build behavior."""

    environment: str = "DEV"
    gates: list[str] = Field(default_factory=lambda: ["level1"])
    include_tags: list[str] = Field(default_factory=list)
    exclude_tags: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    clean_workspace: bool = False
    commands: CommandHookConfig = Field(default_factory=CommandHookConfig)
    disabled_gates: list[str] = Field(default_factory=list)
    gate_overrides: dict[str, "GatePolicy"] = Field(default_factory=dict)


class BranchConfig(BaseModel):
    """Branch policy file loaded from regression/config/branches.yaml."""

    default_branch: str = "main"
    policies: dict[str, BranchPolicy] = Field(default_factory=dict)


class GatePolicy(BaseModel):
    """Gate-level on/off policy."""

    enabled: bool = True
    reason: str | None = None


class GateDecision(BaseModel):
    """Resolved gate enablement decision."""

    enabled: bool
    reason: str | None = None


class RepositoryConfig(BaseModel):
    """Repository-level regression configuration."""

    repository: str
    owner: str | None = None
    default_branch: str = "main"
    remote_url: str | None = None
    services_root: str = "regression/services"
    build_tool: Literal["maven", "gradle", "npm", "custom", "none"] = "none"
    commands: CommandHookConfig = Field(default_factory=CommandHookConfig)
    gates: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "level1": ["level1", "gate1"],
            "level2": ["level2", "gate2"],
            "level3": ["level3"],
            "level4": ["level4"],
            "level5": ["level5"],
        }
    )
    gate_policies: dict[str, GatePolicy] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    service_owners: dict[str, str] = Field(default_factory=dict)
    impact_map: dict[str, list[str]] = Field(default_factory=dict)


class RestExecutorConfig(BaseModel):
    """REST executor configuration for service-backed tests."""

    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST"
    url: HttpUrl | None = None
    base_url: HttpUrl | None = None
    endpoint: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    query_params: dict[str, Any] = Field(default_factory=dict)
    path_params: dict[str, Any] = Field(default_factory=dict)
    auth_token_env: str | None = None
    expected_status: int = 200
    timeout_seconds: float = 10.0
    response_fixture: str | None = None


class JmsExecutorConfig(BaseModel):
    """JMS executor configuration with provider abstraction."""

    provider: Literal["file", "plugin"] = "file"
    request_queue: str
    response_queue: str | None = None
    queue_manager: str | None = None
    topic: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    correlation_id_strategy: Literal["uuid", "metadata", "input"] = "uuid"
    correlation_id_field: str = "correlationId"
    message_selector: str | None = None
    timeout_seconds: float = 30.0
    retry_count: int = 1
    response_fixture: str | None = None


class PythonExecutorConfig(BaseModel):
    """Team-owned Python executor configuration.

    The script path is resolved relative to the application repository root.
    If omitted, the framework searches common service-named locations such as
    regression/executors/<service>.py and regression/services/<service>/<service>.py.
    """

    script: str | None = None
    function: str = "execute"


class TestMetadata(BaseModel):
    """Per-test metadata loaded from metadata.yaml."""

    id: str | None = None
    name: str | None = None
    description: str | None = None
    team: str = "unknown"
    microservice: str | None = None
    gate: str | None = None
    service_type: Literal["echo", "rest", "jms", "python"] = "echo"
    tags: list[str] = Field(default_factory=list)
    branches: list[str] = Field(default_factory=list)
    executor: Literal["echo", "rest", "jms", "http", "python"] = "echo"
    rest: RestExecutorConfig | None = None
    http: RestExecutorConfig | None = None
    jms: JmsExecutorConfig | None = None
    python: PythonExecutorConfig | None = None
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    timeout_seconds: float = 30.0
    ignore_json_paths: list[str] = Field(default_factory=list)


class TestCase(BaseModel):
    """Discovered executable regression test case."""

    id: str
    repo_name: str
    service: str
    gate: str
    name: str
    path: Path
    input_path: Path
    expected_output_path: Path
    metadata_path: Path | None = None
    metadata: TestMetadata
    tags: list[str] = Field(default_factory=list)
    service_type: str = "echo"

    model_config = {"arbitrary_types_allowed": True}


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return an empty mapping for missing or empty files."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_repository_config(repo_root: Path) -> RepositoryConfig:
    """Load regression/config/regression.yaml from an application repository."""
    config_path = repo_root / "regression" / "config" / "regression.yaml"
    data = load_yaml(config_path)
    if not data:
        data = {"repository": repo_root.name}
    return RepositoryConfig.model_validate(data)


def load_branch_config(repo_root: Path) -> BranchConfig:
    """Load optional branch policies from regression/config/branches.yaml."""
    config_path = repo_root / "regression" / "config" / "branches.yaml"
    data = load_yaml(config_path)
    if not data:
        repository_config = load_repository_config(repo_root)
        data = {"default_branch": repository_config.default_branch, "policies": {}}
    return BranchConfig.model_validate(data)


def resolve_branch_policy(repo_root: Path, branch: str | None) -> BranchPolicy:
    """Resolve an exact branch policy or return a sensible default policy."""
    branch_config = load_branch_config(repo_root)
    selected_branch = branch or branch_config.default_branch
    if selected_branch in branch_config.policies:
        policy = branch_config.policies[selected_branch]
    else:
        policy = BranchPolicy()
    policy.gates = [canonical_gate_name(gate) or gate for gate in policy.gates]
    policy.disabled_gates = [canonical_gate_name(gate) or gate for gate in policy.disabled_gates]
    policy.gate_overrides = {
        canonical_gate_name(gate) or gate: override for gate, override in policy.gate_overrides.items()
    }
    return policy


def resolve_gate_decision(repo_root: Path, gate: str | None, branch: str | None = None) -> GateDecision:
    """Resolve whether a gate is enabled at repository and branch scope."""
    normalized_gate = canonical_gate_name(gate)
    if not normalized_gate:
        return GateDecision(enabled=True)
    repo_config = load_repository_config(repo_root)
    repo_gate_policies = {
        canonical_gate_name(name) or name: policy for name, policy in repo_config.gate_policies.items()
    }
    repo_gate_policy = repo_gate_policies.get(normalized_gate, GatePolicy())
    if not repo_gate_policy.enabled:
        return GateDecision(
            enabled=False,
            reason=repo_gate_policy.reason or f"{normalized_gate} disabled by repository policy",
        )
    branch_policy = resolve_branch_policy(repo_root, branch)
    if normalized_gate in branch_policy.disabled_gates:
        return GateDecision(enabled=False, reason=f"{normalized_gate} disabled for branch {branch}")
    branch_gate_policy = branch_policy.gate_overrides.get(normalized_gate)
    if branch_gate_policy and not branch_gate_policy.enabled:
        return GateDecision(
            enabled=False,
            reason=branch_gate_policy.reason or f"{normalized_gate} disabled by branch policy",
        )
    return GateDecision(enabled=True)
