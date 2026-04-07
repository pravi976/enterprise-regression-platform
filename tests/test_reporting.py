from regauto.comparison import ComparisonResult, Difference
from regauto.execution import TestExecutionResult
from regauto.reporting import print_console_report


def test_console_report_prints_field_level_differences(capsys) -> None:
    result = TestExecutionResult(
        test_id="TC001",
        repo_name="repo",
        service="inventory-service",
        gate="gate1",
        team="inventory-team",
        status="failed",
        duration_ms=12,
        comparison=ComparisonResult(
            passed=False,
            differences=[
                Difference("$.body.status", "ACTIVE", "INACTIVE", "value mismatch"),
            ],
        ),
        service_type="rest",
    )

    print_console_report([result])

    captured = capsys.readouterr().out
    assert "DIFF | path=$.body.status" in captured
    assert 'expected="ACTIVE"' in captured
    assert 'actual="INACTIVE"' in captured
