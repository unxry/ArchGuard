class ArchitectureSpecificationError(Exception):
    code = "INVALID_ARCHITECTURE_SPECIFICATION"

    def __init__(self, message: str, *, line: int | None = None, column: int | None = None) -> None:
        super().__init__(message)
        self.line = line
        self.column = column


class UnsupportedArchitectureSpecVersionError(ArchitectureSpecificationError):
    code = "UNSUPPORTED_ARCHITECTURE_SPEC_VERSION"


class UnsupportedArchitectureRuleError(ArchitectureSpecificationError):
    code = "UNSUPPORTED_ARCHITECTURE_RULE"


class ArchitectureSpecResourceLimitError(ArchitectureSpecificationError):
    code = "ARCHITECTURE_SPEC_RESOURCE_LIMIT"


class StaticRuleRegistrationError(Exception):
    pass
