import pytest
from pydantic import ValidationError

from archguard.core.locations import SourceLocation


@pytest.mark.parametrize("end", [None, (4, 3), (5, 1)])
def test_valid_ranges(end: tuple[int, int] | None) -> None:
    data: dict[str, object] = {"file_path": "src/Orders.java", "start_line": 4, "start_column": 3}
    if end is not None:
        data.update(end_line=end[0], end_column=end[1])
    location = SourceLocation.model_validate(data)
    assert SourceLocation.model_validate_json(location.model_dump_json()) == location


@pytest.mark.parametrize(
    "changes",
    [
        {"start_line": 0},
        {"start_line": -1},
        {"start_column": 0},
        {"start_line": True},
        {"start_line": 1.5},
        {"start_line": "1"},
        {"end_line": 2},
        {"end_column": 1},
        {"end_line": 3, "end_column": 9},
        {"end_line": 4, "end_column": 2},
        {"end_line": 0, "end_column": 1},
        {"end_line": 5, "end_column": 0},
    ],
)
def test_invalid_ranges(changes: dict[str, object]) -> None:
    data = {"file_path": "src/Orders.java", "start_line": 4, "start_column": 3} | changes
    with pytest.raises(ValidationError):
        SourceLocation.model_validate(data)


@pytest.mark.parametrize(
    "path",
    [
        "",
        " ",
        "/src/A.java",
        "../A.java",
        "src/../A.java",
        "./A.java",
        "src//A.java",
        "C:/A.java",
        "src\\A.java",
        "src/A.java\x00",
        "src/",
    ],
)
def test_invalid_paths(path: str) -> None:
    with pytest.raises(ValidationError):
        SourceLocation(file_path=path, start_line=1)
