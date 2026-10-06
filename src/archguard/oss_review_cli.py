"""Explicit human annotation commands; no implicit labels, acquisition or evaluation."""

import argparse
from pathlib import Path

from archguard.benchmark.oss.models import canonical
from archguard.benchmark.oss.review import (
    PinnedEvidence,
    ReviewedFreeze,
    ReviewStore,
    RevisionCatalog,
    append_reviews,
    freeze_reviews,
    review_report,
)
from archguard.infrastructure.hybrid_configuration import _read
from archguard.infrastructure.oss_benchmark import cache_root, load_corpus
from archguard.infrastructure.oss_review import (
    export_adjudication,
    import_review_batch,
    initial_catalog,
    prepare_bundles,
    publish_freeze,
    publish_store,
    supplement_context,
    validate_context,
)
from archguard.oss_cli import load_sample


def review_arguments(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="review_command", required=True)
    for name in (
        "prepare",
        "validate",
        "import",
        "status",
        "adjudication-export",
        "freeze",
        "request-extra-context",
    ):
        child = commands.add_parser(name)
        child.add_argument(
            "--corpus", type=Path, default=Path("experiments/oss/oss-corpus-v1.json")
        )
        child.add_argument(
            "--protocol", type=Path, default=Path("experiments/oss/selection-protocol-v1.json")
        )
        child.add_argument(
            "--freeze", type=Path, default=Path("experiments/oss/corpus-freeze.json")
        )
        child.add_argument(
            "--sample", type=Path, default=Path("experiments/oss/annotation/sample-v1.json")
        )
        child.add_argument(
            "--sample-freeze",
            type=Path,
            default=Path("experiments/oss/annotation/sample-freeze-v1.json"),
        )
        child.add_argument("--cache", type=Path)
        child.add_argument("--catalog", type=Path)
        child.add_argument("--store", type=Path)
        child.add_argument("--output", type=Path)
        if name in {"validate", "import"}:
            child.add_argument("--annotations", type=Path, required=True)
        if name == "import":
            child.add_argument("--dry-run", action="store_true")
        if name == "status":
            child.add_argument("--freeze-receipt", type=Path)
        if name == "request-extra-context":
            child.add_argument("--case", required=True)
            child.add_argument(
                "--context",
                type=Path,
                required=True,
                help="JSON array of pinned evidence references",
            )


def execute_review(args: argparse.Namespace) -> int:
    bound = load_corpus(args.corpus, args.protocol, args.freeze)
    sample = load_sample(args.sample, args.sample_freeze)
    cache = cache_root(args.cache)
    catalog = (
        RevisionCatalog.model_validate(_read(args.catalog, 2097152))
        if args.catalog
        else initial_catalog(bound, sample)
    )
    validate_context(bound, sample, cache, catalog)
    previous = ReviewStore.model_validate(_read(args.store, 8388608)) if args.store else None
    store = append_reviews(sample, catalog, previous=previous)
    name = args.review_command
    if name == "status":
        frozen = False
        if args.freeze_receipt:
            receipt = ReviewedFreeze.model_validate(_read(args.freeze_receipt, 8388608))
            if receipt != freeze_reviews(sample, catalog, store):
                raise ValueError("freeze does not match current human review history")
            frozen = True
        print(canonical(review_report(sample, store, frozen=frozen)))
        return 0
    if name in {"validate", "import"}:
        raw = _read(args.annotations, 8388608)
        if not isinstance(raw, dict):
            raise ValueError("review form must be an object")
        imported = import_review_batch(bound, sample, cache, catalog, raw, previous)
        if name == "import" and not args.dry_run:
            if args.output is None:
                raise ValueError("review import requires a new --output directory")
            publish_store(sample, catalog, imported, args.output)
        print(canonical(review_report(sample, imported)))
        return 0
    if args.output is None:
        raise ValueError("review command requires a new --output directory")
    if name == "prepare":
        print(canonical(prepare_bundles(bound, sample, cache, catalog, args.output)))
    elif name == "request-extra-context":
        raw_context = _read(args.context, 2097152)
        if not isinstance(raw_context, list):
            raise ValueError("supplemental context must be an array of pinned evidence references")
        result = supplement_context(
            bound,
            sample,
            cache,
            catalog,
            args.case,
            tuple(PinnedEvidence.model_validate(r) for r in raw_context),
            args.output,
        )
        print(
            canonical(
                {
                    "catalog_fingerprint": result.fingerprint,
                    "case": args.case,
                    "status": "SUPPLEMENTAL_CONTEXT_EXPORTED",
                }
            )
        )
    elif name == "adjudication-export":
        print(
            canonical(
                {
                    "conflicts": export_adjudication(
                        bound, sample, cache, catalog, store, args.output
                    )
                }
            )
        )
    else:
        print(canonical(publish_freeze(sample, catalog, store, args.output)))
    return 0
