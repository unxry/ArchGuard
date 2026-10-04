from archguard.extraction.ecmascript.extractor import (
    JavaScriptExtractor,
    TSXExtractor,
    TypeScriptExtractor,
)
from archguard.extraction.java.extractor import JavaExtractor
from archguard.extraction.registry import ExtractorRegistry


def create_extractor_registry() -> ExtractorRegistry:
    return ExtractorRegistry(
        (JavaExtractor(), TypeScriptExtractor(), JavaScriptExtractor(), TSXExtractor())
    )
