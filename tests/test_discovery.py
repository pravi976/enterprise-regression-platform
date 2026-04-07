from pathlib import Path

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
