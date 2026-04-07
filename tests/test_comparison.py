from regauto.comparison import JsonComparator


def test_json_comparator_detects_value_difference() -> None:
    result = JsonComparator().compare({"id": 1}, {"id": 2})

    assert not result.passed
    assert result.differences[0].path == "$.id"


def test_json_comparator_ignores_unexpected_path() -> None:
    result = JsonComparator().compare(
        {"status_code": 200},
        {"status_code": 200, "headers": {"date": "dynamic"}},
        ignore_paths={"$.headers"},
    )

    assert result.passed
