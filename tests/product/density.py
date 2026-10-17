"""Generate a real 200-file sandbox result for the browser density check."""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

from archguard.product.runtime import Runtime


async def generate(output: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="archguard-density-") as temporary:
        folder = Path(temporary)
        project = folder / "projects/density-ts"
        project.mkdir(parents=True)
        for index in range(200):
            source = (
                f"import {{ M{index + 1} }} from './m{index + 1}';\n" if index < 199 else ""
            ) + f"export class M{index} {{}}\n"
            (project / f"m{index}.ts").write_text(source)
        runtime = Runtime(folder / "projects", folder / "state")
        try:
            job = runtime.start(runtime.catalog()[0]["id"], False, False)
            await job.task
            if job.status != "READY":
                raise RuntimeError(job.error or job.status)
            result = json.loads((runtime.state / f"{job.id}.json").read_text())
            assert len(result["graph"]["graph"]["nodes"]) == 200
            assert len(result["graph"]["graph"]["edges"]) == 199
            output.write_text(json.dumps(result))
        finally:
            await runtime.close()


if __name__ == "__main__":
    asyncio.run(generate(Path(sys.argv[1])))
