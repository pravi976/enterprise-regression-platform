from pathlib import Path
import pytest

from regauto.discovery import TestDiscovery
from regauto.config import resolve_gate_decision


def test_discovers_gate1_sample_tests() -> None:
    repo_root = Path(__file__).parents[1] / "samples" / "sample-application-repo"

    tests = TestDiscovery().discover(repo_root, gate="level1")

    assert {test.service for test in tests} == {
        "customer-service",
        "payment-service",
        "notification-service",
        "recommendation-service",
    }
    assert all(test.gate == "level1" for test in tests)


def test_legacy_gate_alias_maps_to_level1() -> None:
    repo_root = Path(__file__).parents[1] / "samples" / "sample-application-repo"

    tests = TestDiscovery().discover(repo_root, gate="gate1")

    assert tests
    assert all(test.gate == "level1" for test in tests)


def test_discovers_operational_level_tests() -> None:
    repo_root = Path(__file__).parents[1] / "samples" / "sample-application-repo"

    tests = TestDiscovery().discover(repo_root, gate="level5", branch="release")

    assert len(tests) == 1
    assert tests[0].service == "notification-service"
    assert tests[0].gate == "level5"


def test_discovers_branch_applicable_tests() -> None:
    repo_root = Path(__file__).parents[1] / "samples" / "sample-application-repo"

    tests = TestDiscovery().discover(repo_root, gate="level1", branch="release")

    assert tests
    assert all("release" in test.metadata.branches for test in tests)


def test_resolves_disabled_gate_for_branch() -> None:
    repo_root = Path(__file__).parents[1] / "samples" / "sample-application-repo"

    decision = resolve_gate_decision(repo_root, "level3", "develop")

    assert not decision.enabled


def test_discovery_flags_missing_expected_output(tmp_path: Path) -> None:
    test_dir = tmp_path / "regression" / "services" / "svc" / "level1" / "TC001"
    test_dir.mkdir(parents=True)
    (tmp_path / "regression" / "config").mkdir(parents=True)
    (tmp_path / "regression" / "config" / "regression.yaml").write_text("repository: sample\n")
    (test_dir / "input.json").write_text("{}")

    with pytest.raises(ValueError, match="expected_output.json"):
        TestDiscovery().discover(tmp_path, gate="level1")


def test_discovers_tests_from_external_assets_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "app-repo"
    repo_root.mkdir()

    assets_root = tmp_path / "assets"
    test_dir = assets_root / "regression" / "services" / "svc" / "level1" / "TC001"
    test_dir.mkdir(parents=True)
    (assets_root / "regression" / "config").mkdir(parents=True)
    (assets_root / "regression" / "config" / "regression.yaml").write_text("repository: app-repo\n", encoding="utf-8")
    (assets_root / "regression" / "config" / "branches.yaml").write_text(
        "default_branch: main\npolicies: {}\n", encoding="utf-8"
    )
    (test_dir / "input.json").write_text("{}", encoding="utf-8")
    (test_dir / "expected_output.json").write_text("{}", encoding="utf-8")
    (test_dir / "metadata.yaml").write_text(
        "id: TC001\nteam: team\nservice_type: echo\nbranches: [main]\n", encoding="utf-8"
    )

    tests = TestDiscovery().discover(repo_root, assets_root=assets_root, gate="level1", branch="main")

    assert len(tests) == 1
    assert tests[0].service == "svc"
    assert tests[0].gate == "level1"
