import posixpath
from collections import defaultdict
from dataclasses import dataclass

from archguard.core.model.enums import Language
from archguard.extraction.errors import IAMValidationError
from archguard.extraction.models import ExtractedDeclaration, ExtractedFileFacts, ExtractedImport


@dataclass(frozen=True)
class IndexedSymbol:
    file: ExtractedFileFacts
    declaration: ExtractedDeclaration


class SymbolIndex:
    def __init__(self, files: tuple[ExtractedFileFacts, ...]) -> None:
        self.files: dict[str, ExtractedFileFacts] = {}
        self.symbols: dict[str, IndexedSymbol] = {}
        qualified: dict[tuple[Language, str], list[str]] = defaultdict(list)
        simple: dict[tuple[Language, str], list[str]] = defaultdict(list)
        top: dict[tuple[str, str], list[str]] = defaultdict(list)
        container: dict[tuple[str, str], list[str]] = defaultdict(list)
        package: dict[tuple[str, str], list[str]] = defaultdict(list)
        exports: dict[tuple[str, str], list[str]] = defaultdict(list)
        bindings: dict[tuple[str, str], list[ExtractedImport]] = defaultdict(list)
        self.java_packages: set[str] = set()
        for file in files:
            path = file.source_file.relative_path
            if path in self.files:
                raise IAMValidationError("duplicate extracted file identity")
            self.files[path] = file
            if file.package_name is not None:
                self.java_packages.add(file.package_name)
            for declaration in file.declarations:
                if declaration.key in self.symbols:
                    raise IAMValidationError("duplicate incompatible symbol identity")
                self.symbols[declaration.key] = IndexedSymbol(file, declaration)
                qualified[file.language, declaration.qualified_name].append(declaration.key)
                simple[file.language, declaration.name].append(declaration.key)
                if declaration.container_key is None:
                    top[path, declaration.name].append(declaration.key)
                    if file.package_name is not None:
                        package[file.package_name, declaration.name].append(declaration.key)
                    if declaration.is_exported:
                        export_name = (
                            "default" if declaration.is_default_export else declaration.name
                        )
                        exports[path, export_name].append(declaration.key)
                else:
                    container[declaration.container_key, declaration.name].append(declaration.key)
            for imported in file.imports:
                if imported.local_alias:
                    bindings[path, imported.local_alias].append(imported)
        for file in files:
            path = file.source_file.relative_path
            for exported in file.exports:
                if exported.module_specifier is None and exported.local_name is not None:
                    exports[path, exported.exported_name].extend(
                        top.get((path, exported.local_name), ())
                    )
        self.qualified = {key: tuple(sorted(value)) for key, value in qualified.items()}
        self.simple = {key: tuple(sorted(value)) for key, value in simple.items()}
        self.top = {key: tuple(sorted(value)) for key, value in top.items()}
        self.container = {key: tuple(sorted(value)) for key, value in container.items()}
        self.package = {key: tuple(sorted(value)) for key, value in package.items()}
        self.exports = {key: tuple(sorted(set(value))) for key, value in exports.items()}
        self.bindings = {key: tuple(value) for key, value in bindings.items()}

    def relative_modules(self, source_file: str, specifier: str) -> tuple[str, ...]:
        if not specifier.startswith("."):
            return ()
        base = posixpath.normpath(posixpath.join(posixpath.dirname(source_file), specifier))
        if base == ".." or base.startswith("../") or base.startswith("/"):
            return ()
        candidates = (
            [base]
            if posixpath.splitext(base)[1]
            else [base + extension for extension in (".ts", ".tsx", ".js", ".jsx")]
            + [base + "/index" + extension for extension in (".ts", ".tsx", ".js", ".jsx")]
        )
        return tuple(
            sorted(
                path
                for path in candidates
                if path in self.files and self.files[path].language != Language.JAVA
            )
        )
