from pathlib import Path

from archguard.architecture.specification.errors import ArchitectureSpecificationError
from archguard.architecture.specification.loader import ArchitectureSpecLoader
from archguard.architecture.specification.models import ArchitectureSpecification


def load_architecture_file(
    path: Path, loader: ArchitectureSpecLoader | None = None
) -> ArchitectureSpecification:
    parser = loader if loader is not None else ArchitectureSpecLoader()
    try:
        with path.open("rb") as stream:
            data = stream.read(parser.config.max_bytes + 1)
    except OSError:
        raise ArchitectureSpecificationError(
            "architecture specification file could not be read"
        ) from None
    return parser.load(data)
