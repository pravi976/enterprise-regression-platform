from pathlib import Path
import pytest

from regauto.discovery import TestDiscovery
from regauto.config import resolve_gate_decision


def test_discovers_gate1_sample_tests() -> None:
    repo_root = Path(__file__).parents[1] / "samples" / "sample-application-repo"

    tests = TestDiscovery().discover(repo_root, gate="gate1")

    assert {test.service for test in tests} == {
        "customer-service",
        "payment-service",
        "notification-service",
    }
    assert all(test.gate == "gate1" for test in tests)


def test_discovers_branch_applicable_tests() -> None:
    repo_root = Path(__file__).parents[1] / "samples" / "sample-application-repo"

    tests = TestDiscovery().discover(repo_root, gate="gate1", branch="release")

    assert tests
    assert all("release" in test.metadata.branches for test in tests)


def test_resolves_disabled_gate_for_branch() -> None:
    repo_root = Path(__file__).parents[1] / "samples" / "sample-application-repo"

    decision = resolve_gate_decision(repo_root, "gate2", "develop")

    assert not decision.enabled


def test_discovery_flags_missing_expected_output(tmp_path: Path) -> None:
    test_dir = tmp_path / "regression" / "services" / "svc" / "gate1" / "TC001"
    test_dir.mkdir(parents=True)
    (tmp_path / "regression" / "config").mkdir(parents=True)
    (tmp_path / "regression" / "config" / "regression.yaml").write_text("repository: sample\n")
    (test_dir / "input.json").write_text("{}")

    with pytest.raises(ValueError, match="expected_output.json"):
        TestDiscovery().discover(tmp_path, gate="gate1")
