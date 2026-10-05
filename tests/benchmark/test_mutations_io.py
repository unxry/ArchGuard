import json
import shutil

import pytest

from archguard.architecture.hybrid.serialization import canonical
from archguard.benchmark.mutations import MutationRegistry, file_hash, source_fingerprint
from archguard.cli import main
from archguard.infrastructure.benchmark import (
    BenchmarkError,
    generate_mutation,
    load_dataset,
    read_manifest,
    safe_path,
    source_files,
)


@pytest.mark.parametrize("language", ["JAVA", "TYPESCRIPT"])
@pytest.mark.parametrize("rule", [f"ARCH00{i}" for i in range(1, 6)])
def test_mutation_structure_and_replay(loaded, validated, language, rule):
    m = next(
        m
        for m in loaded.mutations
        if m.operator_id == rule and m.config.source.language.value == language
    )
    base = next(r for r in loaded.dataset.repositories if r.repository_id == m.base_repository_id)
    files = source_files(safe_path(loaded.root, base.source_path))
    original = dict(files)
    op = MutationRegistry().get(rule)
    first = op.apply(files, m.config)
    assert first == op.apply(files, m.config)
    assert files == original
    assert source_fingerprint(first) == m.result_fingerprint
    assert op.verify(validated[1][m.derived_repository_id], m.config)
    assert not op.verify(validated[1][m.base_repository_id], m.config)
    for changed in m.changed_files:
        assert file_hash(files[changed.path]) == changed.before_hash
        assert file_hash(first[changed.path]) == changed.after_hash


@pytest.mark.parametrize(
    "error",
    ["language", "marker", "files", "bytes", "endpoint", "symbol", "path", "crlf", "operator"],
)
def test_mutation_rejects_unsafe_input(loaded, error):
    m = loaded.mutations[0]
    repo = next(r for r in loaded.dataset.repositories if r.repository_id == m.base_repository_id)
    files = source_files(safe_path(loaded.root, repo.source_path))
    config = m.config
    if error == "language":
        from archguard.core.model.enums import Language

        config = config.model_copy(
            update={"source": config.source.model_copy(update={"language": Language.JAVASCRIPT})}
        )
    elif error in {"marker", "crlf"}:
        files[config.source.path] = files[config.source.path].replace(
            "// BENCHMARK_DEPENDENCIES", "" if error == "marker" else "\r"
        )
    elif error == "files":
        files = {f"f{i}.java": "" for i in range(101)}
    elif error == "bytes":
        files[config.source.path] = "x" * (1024 * 1024 + 1)
    elif error == "endpoint":
        files.pop(config.target.path)
    elif error == "symbol":
        config = config.model_copy(
            update={"target": config.target.model_copy(update={"qualified_name": "evil;code"})}
        )
    elif error == "path":
        files["../outside"] = ""
    with pytest.raises(ValueError):
        MutationRegistry().get("missing" if error == "operator" else m.operator_id).apply(
            files, config
        )


def test_generate_mutation_output(loaded, tmp_path):
    m = loaded.mutations[0]
    first = generate_mutation(
        loaded, m.base_repository_id, m.operator_id, m.config, tmp_path / "one"
    )
    second = generate_mutation(
        loaded, m.base_repository_id, m.operator_id, m.config, tmp_path / "two"
    )
    assert canonical(first) == canonical(second) == canonical(m)
    with pytest.raises(ValueError):
        generate_mutation(loaded, m.base_repository_id, m.operator_id, m.config, tmp_path / "one")
    bad = m.config.model_copy(
        update={
            "expected_subjects": m.config.expected_subjects.model_copy(
                update={
                    "locators": (m.config.source.model_copy(update={"qualified_name": "missing"}),)
                }
            )
        }
    )
    with pytest.raises(ValueError):
        generate_mutation(loaded, m.base_repository_id, m.operator_id, bad, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


@pytest.mark.parametrize(
    "content",
    [
        "a: 1\na: 2",
        "a: &node [1]\nb: *node",
        '!!python/object/apply:os.system ["touch /tmp/archguard-should-not-exist"]',
        "[" * 33 + "0" + "]" * 33,
        "1: bad",
        "a: !!binary eA==",
    ],
)
def test_safe_manifest(content, tmp_path):
    p = tmp_path / "unsafe.yaml"
    p.write_text(content)
    with pytest.raises(ValueError):
        value = read_manifest(p)
        if content.startswith("a: !!binary"):
            # Schema rejects unsupported binary values even under SafeLoader.
            from archguard.benchmark.models import BenchmarkDataset

            BenchmarkDataset.model_validate(value)


def test_manifest_budget_paths_and_encoding(tmp_path):
    p = tmp_path / "large.json"
    p.write_bytes(b" " * (2 * 1024 * 1024 + 1))
    with pytest.raises(BenchmarkError):
        read_manifest(p)
    p.write_bytes(b"\xff")
    with pytest.raises(BenchmarkError):
        read_manifest(p)
    (tmp_path / "link").symlink_to("/tmp")
    with pytest.raises(BenchmarkError):
        safe_path(tmp_path, "link/file")
    with pytest.raises(ValueError):
        safe_path(tmp_path, "../escape")
    with pytest.raises(BenchmarkError):
        source_files(tmp_path)


@pytest.mark.parametrize(
    "tamper",
    [
        "hash",
        "truth_id",
        "truth_repo",
        "truth_scope",
        "truth_language",
        "truth_extra",
        "truth_type",
        "mutation_hash",
        "mutation_id",
        "mutation_cases",
        "lineage_hash",
    ],
)
def test_dataset_rejects_tampering(loaded, tmp_path, tamper):
    root = tmp_path / "dataset"
    shutil.copytree(loaded.root, root)
    path = root / "dataset.json"
    data = json.loads(path.read_text())
    r = data["repositories"][0]
    truth_path = root / r["ground_truth"]
    truth = json.loads(truth_path.read_text())
    if tamper == "hash":
        r["source_fingerprint"] = "0" * 64
    elif tamper.startswith("truth"):
        if tamper == "truth_id":
            truth[0]["case_id"] = str(loaded.dataset.namespace)
        if tamper == "truth_repo":
            truth[0]["repository_id"] = "alien"
        if tamper == "truth_scope":
            r["annotation_scope"]["rules"] = []
        if tamper == "truth_language":
            r["languages"] = ["TYPESCRIPT"]
        if tamper == "truth_extra":
            truth[0]["detector_label"] = True
        if tamper == "truth_type":
            truth = {}
        truth_path.write_text(json.dumps(truth))
    else:
        mutant = next(x for x in data["repositories"] if x["mutation_manifest"])
        mp = root / mutant["mutation_manifest"]
        m = json.loads(mp.read_text())
        if tamper == "mutation_hash":
            m["result_fingerprint"] = "0" * 64
        if tamper == "lineage_hash":
            m["base_fingerprint"] = "0" * 64
        if tamper == "mutation_id":
            m["mutation_id"] = str(loaded.dataset.namespace)
        if tamper == "mutation_cases":
            m["expected_cases"] = []
        mp.write_text(json.dumps(m))
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_dataset(path)


def test_logical_manifest_fingerprint_and_dataset_valid(loaded, validated, tmp_path):
    assert validated[0]["status"] == "VALID" and not validated[0]["diagnostics"]
    assert (validated[0]["repositories"], validated[0]["families"]) == (24, 7)
    assert validated[0]["labels"] == {"POSITIVE": 30, "NEGATIVE": 32}
    shutil.copytree(loaded.root, tmp_path / "seed")
    path = tmp_path / "seed/dataset.json"
    path.write_text(
        "# harmless format comment\n" + json.dumps(json.loads(path.read_text()), indent=2)
    )
    assert load_dataset(path).fingerprint == loaded.fingerprint
    assert len({c.rule_id for c in loaded.truths}) == 15


def test_cli_validate_split_mutate_and_errors(loaded, tmp_path, capsys):
    path = str(loaded.root / "dataset.json")
    assert main(["benchmark", "validate", path]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "VALID"
    assert main(["benchmark", "split", path]) == 0
    assert json.loads(capsys.readouterr().out) == json.loads(
        (loaded.root / "splits.json").read_text()
    )
    m = loaded.mutations[0]
    config = tmp_path / "config.json"
    config.write_text(canonical(m.config))
    args = [
        "benchmark",
        "mutate",
        path,
        "--base",
        m.base_repository_id,
        "--operator",
        m.operator_id,
        "--config",
        str(config),
    ]
    assert main(args) == 2
    assert main([*args, "--output", str(tmp_path / "mutant")]) == 0
    capsys.readouterr()
    assert main(["benchmark", "export-features", path]) == 2
    assert (
        main(
            [
                "benchmark",
                "smoke",
                path,
                "--mode",
                "LLM_ONLY",
                "--task",
                "SEMANTIC_CANDIDATE_DETECTION",
            ]
        )
        == 2
    )


@pytest.mark.parametrize(
    "limit",
    [
        "max_manifest_bytes",
        "max_dataset_manifest_bytes",
        "max_repositories",
        "max_cases",
        "max_source_files",
        "max_source_bytes",
        "max_dataset_source_bytes",
        "max_depth",
        "max_nodes",
    ],
)
def test_configurable_loader_budgets(loaded, limit):
    from archguard.infrastructure.benchmark import BenchmarkLimits

    with pytest.raises(ValueError):
        load_dataset(loaded.root / "dataset.json", BenchmarkLimits.model_validate({limit: 1}))


def test_mutation_output_budget(loaded):
    from archguard.benchmark.mutations import MutationLimits

    m = loaded.mutations[0]
    base = next(r for r in loaded.dataset.repositories if r.repository_id == m.base_repository_id)
    files = source_files(safe_path(loaded.root, base.source_path))
    config = m.config.model_copy(update={"limits": MutationLimits(max_output_bytes=1)})
    with pytest.raises(ValueError):
        MutationRegistry().get(m.operator_id).apply(files, config)


def test_split_manifest_and_changed_hashes_cannot_be_forged(loaded, tmp_path):
    root = tmp_path / "seed"
    shutil.copytree(loaded.root, root)
    split = root / "splits.json"
    split.write_text("{}")
    with pytest.raises(ValueError):
        load_dataset(root / "dataset.json")
    split.write_bytes((loaded.root / "splits.json").read_bytes())
    path = next((root / "mutations").glob("*.json"))
    m = json.loads(path.read_text())
    m["changed_files"][0]["before_hash"] = "0" * 64
    path.write_text(json.dumps(m))
    with pytest.raises(ValueError):
        load_dataset(root / "dataset.json")


def test_source_fingerprint_ignores_non_source_metadata():
    assert source_fingerprint(
        {"src/A.java": "class A {}", "README.md": "one"}
    ) == source_fingerprint({"src/A.java": "class A {}", "README.md": "two"})


def test_unknown_mutation_base_rejected(loaded, tmp_path):
    with pytest.raises(BenchmarkError):
        generate_mutation(
            loaded, "missing", "ARCH001", loaded.mutations[0].config, tmp_path / "no-output"
        )
