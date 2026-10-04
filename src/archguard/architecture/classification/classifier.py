import fnmatch

from archguard.architecture.classification.models import (
    ArchitectureClassification,
    ConformanceDiagnostic,
    NodeClassification,
)
from archguard.architecture.specification.models import ArchitectureScope, ArchitectureSpecification
from archguard.core.model.enums import NodeKind
from archguard.iam.model import ArchitectureModel


def path_matches(path: str, pattern: str) -> bool:
    parts = path.split("/")
    positions = {0}
    for segment in pattern.split("/"):
        if not positions:
            return False
        if segment == "**":
            positions = set(range(min(positions), len(parts) + 1))
        else:
            positions = {
                i + 1
                for i in positions
                if i < len(parts) and fnmatch.fnmatchcase(parts[i], segment)
            }
    return len(parts) in positions


def _scope_matches(path: str, scope: ArchitectureScope) -> bool:
    return any(path_matches(path, pattern) for pattern in scope.include) and not any(
        path_matches(path, pattern) for pattern in scope.exclude
    )


class ArchitectureClassifier:
    version = "1.0.0"

    def classify(
        self, model: ArchitectureModel, spec: ArchitectureSpecification
    ) -> ArchitectureClassification:
        files = {file.id: file for file in model.source_files}
        symbols = {symbol.id: symbol for symbol in model.symbols}
        matches = {}
        diagnostics = []
        for file in sorted(model.source_files, key=lambda item: item.file_path):
            layers = tuple(
                scope.name
                for scope in spec.architecture.layers
                if _scope_matches(file.file_path, scope)
            )
            modules = tuple(
                scope.name
                for scope in spec.architecture.modules
                if _scope_matches(file.file_path, scope)
            )
            matches[file.id] = layers, modules
            for kind, candidates in (("LAYER", layers), ("MODULE", modules)):
                if len(candidates) > 1:
                    diagnostics.append(
                        ConformanceDiagnostic(
                            code=f"AMBIGUOUS_{kind}_MATCH",
                            message="multiple target scopes match one source file",
                            file_path=file.file_path,
                        )
                    )
        classified = []
        for node in sorted(model.nodes, key=lambda item: str(item.id)):
            if node.kind in {NodeKind.PROJECT, NodeKind.PACKAGE, NodeKind.EXTERNAL_DEPENDENCY}:
                continue
            file_id = node.file_id
            if file_id is None and node.symbol_id is not None:
                file_id = symbols[node.symbol_id].file_id
            if file_id is None:
                continue
            layers, modules = matches[file_id]
            classified.append(
                NodeClassification(
                    node_id=node.id,
                    file_id=file_id,
                    file_path=files[file_id].file_path,
                    layer=layers[0] if len(layers) == 1 else None,
                    module=modules[0] if len(modules) == 1 else None,
                    layer_candidates=layers,
                    module_candidates=modules,
                )
            )
        return ArchitectureClassification(nodes=tuple(classified), diagnostics=tuple(diagnostics))
