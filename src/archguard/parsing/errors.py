from archguard.parsing.enums import ParserDiagnosticCode


class ParsingError(Exception):
    code = ParserDiagnosticCode.EXECUTION_ERROR


class UnsupportedLanguageError(ParsingError):
    code = ParserDiagnosticCode.UNSUPPORTED_LANGUAGE


class DuplicateParserError(ParsingError):
    pass


class IneligibleSourceError(ParsingError):
    code = ParserDiagnosticCode.SOURCE_INELIGIBLE


class ParserResourceLimitError(ParsingError):
    code = ParserDiagnosticCode.RESOURCE_LIMIT


class ParserExecutionError(ParsingError):
    pass


class SourceDecodingError(ParsingError):
    code = ParserDiagnosticCode.DECODING_ERROR

    def __init__(self, byte_offset: int, line: int, column: int) -> None:
        super().__init__("source is not valid UTF-8")
        self.byte_offset = byte_offset
        self.line = line
        self.column = column
