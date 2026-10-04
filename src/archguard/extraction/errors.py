class ExtractionError(Exception):
    pass


class DuplicateExtractorError(ExtractionError):
    pass


class UnsupportedExtractorError(ExtractionError):
    pass


class ExtractionLimitError(ExtractionError):
    pass


class IAMValidationError(ExtractionError):
    pass
