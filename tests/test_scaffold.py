from pathlib import Path

from regauto.discovery import TestDiscovery
from regauto.execution import ExecutionEngine
from regauto.scaffold import scaffold_python_test, service_module_name


def test_service_module_name_normalizes_service_names() -> None:
    assert service_module_name("customer-service") == "customer_service"
    assert service_module_name("123-payment") == "service_123_payment"


def test_scaffold_python_test_creates_executable_assets(tmp_path: Path) -> None:
    result = scaffold_python_test(
        repo_root=tmp_path,
        service="customer-service",
        gate="gate1",
        test_id="TC001_customer_lookup",
        team="customer-team",
        branches=["main"],
        tags=["critical"],
    )

    assert tmp_path / "regression" / "executors" / "customer_service.py" in result.created
    assert (
        tmp_path
        / "regression"
        / "services"
        / "customer-service"
        / "gate1"
        / "TC001_customer_lookup"
        / "metadata.yaml"
    ) in result.created

    tests = TestDiscovery().discover(tmp_path, gate="gate1", branch="main")
    results = ExecutionEngine().run(tests)

    assert len(results) == 1
    assert results[0].status == "passed"
    assert results[0].service_type == "python"
