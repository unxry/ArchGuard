"""Curated definitions create labels BEFORE parsing; IAM only verifies mutations."""

from pathlib import Path
from uuid import UUID

from archguard.architecture.hybrid.serialization import canonical
from archguard.benchmark.identity import case_id
from archguard.benchmark.models import (
    AnnotatedSubject,
    AnnotationScope,
    AnnotationStatus,
    BenchmarkDataset,
    BenchmarkRepository,
    GroundTruthCase,
    Label,
    Locator,
    Origin,
    Subjects,
    rule_family,
)
from archguard.benchmark.mutations import (
    FileChange,
    MutationConfig,
    MutationRegistry,
    MutationResult,
    expected_truth,
    file_hash,
    mutation_identity,
    source_fingerprint,
)
from archguard.benchmark.splits import plan_splits
from archguard.core.model.enums import Language, NodeKind
from archguard.infrastructure.benchmark import build_source

ROOT = Path(__file__).parent / "v1"
NAMESPACE = UUID("c6710f1c-0834-50eb-a7f6-d06ba74d8698")
SEED = "archguard-seed-v1"
repositories: list[BenchmarkRepository] = []


def write(path: str, value: object) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(canonical(value) + "\n", encoding="utf-8")


def locator(lang: Language, folder: str, name: str, kind: NodeKind = NodeKind.CLASS) -> Locator:
    path = f"src/{folder}/{name}.java" if lang == Language.JAVA else f"src/{folder}/{name}.ts"
    qualified = f"{folder.replace('/', '.')}.{name}" if lang == Language.JAVA else f"{path}::{name}"
    return Locator(
        path=path,
        language=lang,
        qualified_name=path if kind == NodeKind.FILE else qualified,
        kind=kind,
    )


def subjects(*locs: Locator, directed: bool = False) -> Subjects:
    values = locs if directed else tuple(sorted(locs, key=lambda loc: loc.model_dump_json()))
    return Subjects(locators=values, directed=directed)


def source(
    lang: Language, folder: str, name: str, body: str = "", imports: str = ""
) -> tuple[str, str]:
    loc = locator(lang, folder, name)
    header = (
        f"package {folder.replace('/', '.')};\npublic class {name}"
        if lang == Language.JAVA
        else imports + f"export class {name}"
    )
    return loc.path, header + " {\n    // BENCHMARK_DEPENDENCIES\n" + body + "\n}\n"


def gt(repo: str, rule: str, label: Label, subject: Subjects, rationale: str) -> GroundTruthCase:
    return GroundTruthCase(
        case_id=case_id(NAMESPACE, repo, rule, label, subject),
        repository_id=repo,
        rule_id=rule,
        rule_family=rule_family(rule),
        label=label,
        subjects=subject,
        rationale=rationale,
        origin=Origin.CURATED,
        annotation_status=AnnotationStatus.CURATED,
    )


def add_repo(
    repo: str,
    family: str,
    lang: Language,
    files: dict[str, str],
    truths: tuple[GroundTruthCase, ...],
    *,
    spec: str | None = None,
    graph_config: str | None = None,
    base: str | None = None,
    mutation: MutationResult | None = None,
    origin: Origin = Origin.SYNTHETIC,
) -> None:
    for path, text in files.items():
        target = ROOT / "repositories" / repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode())
    write(f"ground_truth/{repo}.json", [t.model_dump(mode="json") for t in truths])
    if mutation:
        write(f"mutations/{repo}.json", mutation)
    repositories.append(
        BenchmarkRepository(
            repository_id=repo,
            repository_family_id=family,
            name=repo,
            origin=Origin.MUTATION if mutation else origin,
            languages=(lang,),
            source_path=f"repositories/{repo}",
            source_fingerprint=source_fingerprint(files),
            ground_truth=f"ground_truth/{repo}.json",
            dataset_split=splits[family],
            architecture_spec=spec,
            graph_config=graph_config,
            base_repository_id=base,
            mutation_manifest=f"mutations/{repo}.json" if mutation else None,
            annotation_scope=AnnotationScope(
                rules=tuple(sorted({t.rule_id for t in truths})),
                fully_annotated_subjects=tuple(
                    AnnotatedSubject(rule_id=t.rule_id, subjects=t.subjects) for t in truths
                ),
            ),
        )
    )


families = tuple(f"static-{i}" for i in range(1, 6)) + (
    "graph-topology-v1",
    "semantic-responsibilities-v1",
)
splits = plan_splits(families, SEED)
write(
    "splits.json",
    {
        "algorithm": "sha256-ranked-families-v1",
        "seed": SEED,
        "families": {k: v.value for k, v in sorted(splits.items())},
    },
)
for lang in (Language.JAVA, Language.TYPESCRIPT):
    for i in range(1, 6):
        rule = f"ARCH00{i}"
        family = f"static-{i}"
        base = f"static-{lang.value.lower()}-{i}-clean"
        derived = base + "-" + rule.lower()
        folder_a, name_a, folder_b, name_b = {
            1: ("domain", "Order", "infrastructure", "Database"),
            2: ("controller", "Controller", "repository", "Repository"),
            3: ("cycle", "C", "cycle", "A"),
            4: ("domain", "Order", "service", "Service"),
            5: ("orders", "OrderService", "payments", "PaymentInternal"),
        }[i]
        files = dict((source(lang, folder_a, name_a), source(lang, folder_b, name_b)))
        if i == 2:
            files.update((source(lang, "service", "Service"),))
            # Clean presentation -> application -> persistence chain.
            for sf, sn, tf, tn in [
                ("controller", "Controller", "service", "Service"),
                ("service", "Service", "repository", "Repository"),
            ]:
                conf = MutationConfig(
                    source=locator(lang, sf, sn),
                    target=locator(lang, tf, tn),
                    expected_subjects=subjects(
                        locator(lang, sf, sn), locator(lang, tf, tn), directed=True
                    ),
                )
                files = MutationRegistry().get("ARCH002").apply(files, conf)
            # Reinsert a dedicated marker for the controlled forbidden extra dependency.
            p = locator(lang, folder_a, name_a).path
            files[p] = files[p].replace("benchmarkDependency", "serviceDependency")
            files[p] = files[p].replace("\n}", "\n    // BENCHMARK_DEPENDENCIES\n}")
        if i == 3:
            files.update((source(lang, "cycle", "B"),))
            for a, b in [("A", "B"), ("B", "C")]:
                conf = MutationConfig(
                    source=locator(lang, "cycle", a),
                    target=locator(lang, "cycle", b),
                    expected_subjects=subjects(
                        locator(lang, "cycle", a), locator(lang, "cycle", b), directed=True
                    ),
                )
                files = MutationRegistry().get(rule).apply(files, conf)
            logical = subjects(*(locator(lang, "cycle", n) for n in ("A", "B", "C")))
        else:
            logical = subjects(
                locator(lang, folder_a, name_a, NodeKind.FILE),
                locator(lang, folder_b, name_b, NodeKind.FILE),
                directed=True,
            )
        config = MutationConfig(
            source=locator(lang, folder_a, name_a),
            target=locator(lang, folder_b, name_b),
            expected_subjects=logical,
            cycle_paths=tuple(locator(lang, "cycle", n).path for n in ("A", "B", "C"))
            if i == 3
            else (),
        )
        rule_config = {
            1: {
                "type": "forbidden_dependency",
                "from": {"layer": "domain"},
                "to": {"layer": "infrastructure"},
            },
            2: {
                "type": "layer_dependency",
                "from": "presentation",
                "allow": ["application"],
                "allow_same_layer": False,
            },
            3: {"type": "circular_dependency", "projection": "component"},
            4: {"type": "reverse_dependency", "expected": {"from": "application", "to": "domain"}},
            5: {"type": "module_boundary", "from": "orders", "deny": ["payments"]},
        }[i]
        spec = f"specs/{rule}.json"
        write(
            spec,
            {
                "version": "1.0",
                "architecture": {
                    "layers": [
                        {"name": layer, "include": [f"**/{folder}/**"]}
                        for layer, folder in (
                            ("domain", "domain"),
                            ("infrastructure", "infrastructure"),
                            ("presentation", "controller"),
                            ("application", "service"),
                            ("persistence", "repository"),
                        )
                    ],
                    "modules": [
                        {"name": m, "include": [f"**/{m}/**"]} for m in ("orders", "payments")
                    ],
                },
                "rules": [{"id": rule, **rule_config}],
            },
        )
        clean_truth = gt(
            base,
            rule,
            Label.NEGATIVE,
            logical,
            (
                "Controlled base has no forbidden directed dependency or cyclic SC"
                "C under the declared rule."
            ),
        )
        add_repo(base, family, lang, files, (clean_truth,), spec=spec)
        op = MutationRegistry().get(rule)
        mid = mutation_identity(NAMESPACE, base, op, config, source_fingerprint(files))
        # Annotation is created from the intended change before observing any IAM/detector result.
        truth = expected_truth(NAMESPACE, derived, rule, config, mid)
        after = op.apply(files, config)
        for p, text in after.items():
            target = ROOT / "repositories" / derived / p
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode())
        iam = build_source(ROOT / "repositories" / derived, "benchmark:" + derived)
        assert op.verify(iam, config), derived
        mutation = MutationResult(
            mutation_id=mid,
            operator_id=rule,
            base_repository_id=base,
            derived_repository_id=derived,
            config=config,
            base_fingerprint=source_fingerprint(files),
            result_fingerprint=source_fingerprint(after),
            changed_files=tuple(
                FileChange(path=p, before_hash=file_hash(files[p]), after_hash=file_hash(after[p]))
                for p in sorted(files)
                if files[p] != after[p]
            ),
            expected_cases=(truth,),
            verification_status="VERIFIED",
        )
        add_repo(derived, family, lang, after, (truth,), spec=spec, base=base, mutation=mutation)

for lang in (Language.JAVA, Language.TYPESCRIPT):
    family = f"graph-{lang.value.lower()}"
    files = {}
    topology = {
        "In1": ["Hub"],
        "In2": ["Hub"],
        "In3": ["Hub"],
        "Hub": ["Bridge"],
        "Bridge": ["Leaf1", "Leaf2", "Leaf3"],
        "Leaf1": [],
        "Leaf2": [],
        "Leaf3": [],
        "LargeIsolated": [],
    }
    for name, targets in topology.items():
        body = ""
        imports = ""
        for j, t in enumerate(targets):
            body += f"    {t} dep{j};\n" if lang == Language.JAVA else f"    dep{j}!: {t};\n"
            if lang == Language.TYPESCRIPT:
                imports += f"import {{ {t} }} from './{t}';\n"
        if name in {"Hub", "LargeIsolated"}:
            body += "".join(
                f"    public int m{j}() {{ return {j}; }}\n"
                if lang == Language.JAVA
                else f"    m{j}(): number {{ return {j}; }}\n"
                for j in range(3)
            )
        files.update((source(lang, "graph", name, body, imports),))
    graph_config = "graph-config.json"
    write(
        graph_config,
        {
            "candidates": {
                "excessive_coupling": 4,
                "hub_fan_in": 3,
                "god_min_members": 3,
                "god_min_methods": 2,
                "god_min_coupling": 4,
                "unstable_delta": 0.4,
                "bottleneck_betweenness": 0.2,
            }
        },
    )
    controls = [
        ("ARCH101", ["Hub"], True, "Hub has four unique neighbours; threshold is four."),
        ("ARCH101", ["Leaf1"], False, "Leaf1 has one unique neighbour, below four."),
        (
            "ARCH102",
            ["Hub"],
            True,
            "Hub has three distinct incoming dependents; threshold is three.",
        ),
        ("ARCH102", ["Bridge"], False, "Bridge has one incoming dependent, below three."),
        (
            "ARCH103",
            ["Hub"],
            True,
            "Hub has at least three members, three methods and four neighbours.",
        ),
        (
            "ARCH103",
            ["Bridge"],
            False,
            "Bridge has four neighbours but zero methods; fails configured size condition.",
        ),
        ("ARCH103", ["LargeIsolated"], False, "LargeIsolated has three methods but no coupling."),
        ("ARCH104", ["Hub", "Bridge"], True, "Hub I=1/4; Bridge I=3/4; delta=1/2 exceeds 0.4."),
        (
            "ARCH104",
            ["Bridge", "Leaf1"],
            False,
            "Bridge I=3/4; Leaf1 I=0; delta=-3/4 is below 0.4.",
        ),
        (
            "ARCH105",
            ["Hub"],
            True,
            (
                "Nine-node directed graph: Hub lies on 12 ordered shortest paths; "
                "normalized betweenness=12/(8*7)>0.2."
            ),
        ),
        ("ARCH105", ["In1"], False, "In1 is a source and lies on zero internal shortest paths."),
    ]
    truths = tuple(
        gt(
            family,
            rule,
            Label.POSITIVE if positive else Label.NEGATIVE,
            subjects(*(locator(lang, "graph", n) for n in names), directed=rule == "ARCH104"),
            rationale,
        )
        for rule, names, positive, rationale in controls
    )
    add_repo(family, "graph-topology-v1", lang, files, truths, graph_config=graph_config)

for lang in (Language.JAVA, Language.TYPESCRIPT):
    family = f"semantic-{lang.value.lower()}"
    scenarios = [
        (
            "ARCH201",
            "domain",
            "HttpRepository",
            True,
            (
                "Repository-named component builds an HTTP response and computes o"
                "rder pricing, contradicting persistence-only responsibility."
            ),
            (
                "public String handleHttp(int quantity) { int price = quantity > 1"
                '0 ? quantity * 8 : quantity * 10; return "HTTP/1.1 200 OK price="'
                " + price; }"
            ),
        ),
        (
            "ARCH201",
            "repository",
            "OrderRepository",
            False,
            "Repository only abstracts saving and loading an order identifier.",
            (
                "private int saved; public void save(int id) { saved = id; } publi"
                "c int load() { return saved; }"
            ),
        ),
        (
            "ARCH202",
            "controller",
            "PricingController",
            True,
            "Controller computes quantity discount and tax, which are explicit pricing policy.",
            (
                "public int price(int quantity) { int subtotal = quantity > 10 ? q"
                "uantity * 8 : quantity * 10; return subtotal + subtotal / 5; }"
            ),
        ),
        (
            "ARCH202",
            "controller",
            "ThinController",
            False,
            "Thin controller delegates to PricingService without business calculation.",
            (
                "private service.PricingService pricing; public int price(int quan"
                "tity) { return pricing.price(quantity); }"
            ),
        ),
        (
            "ARCH203",
            "domain",
            "SqlOrder",
            True,
            "Domain constructs SQL and chooses an infrastructure-specific database table.",
            (
                'public String persistSql(int id) { return "INSERT INTO postgres_o'
                'rders VALUES (" + id + ")"; }'
            ),
        ),
        (
            "ARCH203",
            "domain",
            "Order",
            False,
            (
                "Domain records an identifier through an abstract port; no SQL/ven"
                "dor implementation responsibility."
            ),
            "private OrderPort port; public void save(int id) { port.save(id); }",
        ),
        (
            "ARCH204",
            "domain",
            "HttpPresenter",
            True,
            (
                "Curated placement expectation: domain holds business objects, whi"
                "le this component formats an HTTP presentation response."
            ),
            'public String respond(String content) { return "HTTP/1.1 200 OK body=" + content; }',
        ),
        (
            "ARCH204",
            "controller",
            "HttpController",
            False,
            (
                "Presentation folder is the curated expected placement for formatt"
                "ing an HTTP response."
            ),
            'public String respond(String content) { return "HTTP/1.1 200 OK body=" + content; }',
        ),
        (
            "ARCH205",
            "controller",
            "CheckoutController",
            True,
            (
                "One component parses presentation quantity, computes discount and"
                " constructs a persistence SQL statement."
            ),
            (
                "public String checkout(String quantity) { int count = Integer.par"
                "seInt(quantity); int total = count > 10 ? count * 8 : count * 10;"
                ' return "INSERT INTO orders(total) VALUES (" + total + ")"; }'
            ),
        ),
        (
            "ARCH205",
            "service",
            "PricingService",
            False,
            "Service only computes price, with no presentation or persistence responsibility.",
            "public int price(int quantity) { return quantity * 10; }",
        ),
    ]
    files = {}
    truths = []
    for rule, folder, name, positive, rationale, body in scenarios:
        imports = ""
        if lang == Language.TYPESCRIPT:
            replacements = {
                "public String ": "",
                "public int ": "",
                "public void ": "",
                "private int saved;": "private saved = 0;",
                "int quantity": "quantity: number",
                "int id": "id: number",
                "String content": "content: string",
                "String quantity": "quantity: string",
                "int price =": "const price =",
                "int subtotal =": "const subtotal =",
                "int count =": "const count =",
                "int total =": "const total =",
                "Integer.parseInt": "Number",
                "saved = id": "this.saved = id",
                "return saved": "return this.saved",
                "private service.PricingService pricing;": "private pricing!: PricingService;",
                "return pricing.price": "return this.pricing.price",
                "private OrderPort port;": "private port!: OrderPort;",
                "port.save": "this.port.save",
            }
            for old, new in replacements.items():
                body = body.replace(old, new)
            if name == "ThinController":
                imports = "import { PricingService } from '../service/PricingService';\n"
            if name == "Order":
                imports = "import { OrderPort } from './OrderPort';\n"
        files.update((source(lang, folder, name, "    " + body, imports),))
        truths.append(
            gt(
                family,
                rule,
                Label.POSITIVE if positive else Label.NEGATIVE,
                subjects(locator(lang, folder, name)),
                rationale,
            )
        )
    if lang == Language.JAVA:
        files["src/domain/OrderPort.java"] = (
            "package domain; public interface OrderPort { void save(int id); }\n"
        )
    else:
        files["src/domain/OrderPort.ts"] = (
            "export interface OrderPort { save(id: number): void; }\n"
        )
    add_repo(
        family, "semantic-responsibilities-v1", lang, files, tuple(truths), origin=Origin.CURATED
    )

dataset = BenchmarkDataset(
    dataset_id="archguard-benchmark-v1",
    dataset_version="1.0.0",
    namespace=NAMESPACE,
    split_seed=SEED,
    repositories=tuple(sorted(repositories, key=lambda r: r.repository_id)),
)
write("dataset.json", dataset)
print(f"{len(repositories)} repositories; {len(families)} families")
