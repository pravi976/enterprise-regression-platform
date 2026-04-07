import json
from pathlib import Path

from regauto.discovery import TestDiscovery
from regauto.execution import ExecutionEngine


def test_python_executor_uses_service_named_file(tmp_path: Path) -> None:
    test_dir = tmp_path / "regression" / "services" / "customer-service" / "gate1" / "TC001"
    executor_dir = tmp_path / "regression" / "executors"
    test_dir.mkdir(parents=True)
    executor_dir.mkdir(parents=True)
    (tmp_path / "regression" / "config").mkdir(parents=True)
    (tmp_path / "regression" / "config" / "regression.yaml").write_text("repository: sample\n")
    (test_dir / "metadata.yaml").write_text(
        "\n".join(
            [
                "id: CUSTOMER_PY_TC001",
                "team: customer-team",
                "service_type: python",
                "tags: [gate1, customer-service, python]",
            ]
        ),
        encoding="utf-8",
    )
    (test_dir / "input.json").write_text(json.dumps({"customerId": "C123"}), encoding="utf-8")
    (test_dir / "expected_output.json").write_text(
        json.dumps({"body": {"customerId": "C123", "status": "ACTIVE"}}),
        encoding="utf-8",
    )
    (executor_dir / "customer_service.py").write_text(
        "\n".join(
            [
                "def execute(input_payload, context):",
                "    return {'body': {'customerId': input_payload['customerId'], 'status': 'ACTIVE'}}",
            ]
        ),
        encoding="utf-8",
    )

    tests = TestDiscovery().discover(tmp_path, gate="gate1")
    results = ExecutionEngine().run(tests)

    assert len(results) == 1
    assert results[0].status == "passed"
    assert results[0].service_type == "python"
