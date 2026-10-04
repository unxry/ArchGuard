import re
from typing import Annotated

from pydantic import AfterValidator, JsonValue, StringConstraints


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("text must contain a non-whitespace character")
    return value


def _repository_path(value: str) -> str:
    if (
        not value
        or value.startswith("/")
        or "\\" in value
        or "\x00" in value
        or re.match(r"^[A-Za-z]:", value)
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError("file paths must be canonical, repository-relative POSIX paths")
    return _nonblank(value)


NonEmptyString = Annotated[str, StringConstraints(min_length=1), AfterValidator(_nonblank)]
RepositoryPath = Annotated[str, AfterValidator(_repository_path)]
JsonObject = dict[str, JsonValue]
