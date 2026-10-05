"""Independent curated scenarios; partition selection uses composition, never predictions."""

import json
from pathlib import Path

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
BASE = BenchmarkDataset.model_validate(json.loads((ROOT / "dataset.json").read_text()))
NS = BASE.namespace
repositories = list(BASE.repositories)


def write(path, value):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(canonical(value) + "\n", encoding="utf-8")


def loc(language, folder, name, kind=NodeKind.CLASS):
    path = f"src/{folder}/{name}" + (".java" if language == Language.JAVA else ".ts")
    q = f"{folder.replace('/', '.')}.{name}" if language == Language.JAVA else f"{path}::{name}"
    return Locator(
        path=path, language=language, qualified_name=path if kind == NodeKind.FILE else q, kind=kind
    )


def subjects(*values, directed=False):
    return Subjects(
        locators=values if directed else tuple(sorted(values, key=lambda x: x.model_dump_json())),
        directed=directed,
    )


def source(language, folder, name, body="", targets=()):
    fields = ""
    imports = ""
    for index, (directory, target) in enumerate(targets):
        if language == Language.JAVA:
            fields += f"    {directory.replace('/', '.')}.{target} reference{index};\n"
        else:
            # All new scenarios use one-level source directories.
            imports += f"import {{ {target} }} from '../{directory}/{target}';\n"
            fields += f"    reference{index}!: {target};\n"
    header = (
        f"package {folder.replace('/', '.')};\npublic class {name}"
        if language == Language.JAVA
        else imports + f"export class {name}"
    )
    return loc(
        language, folder, name
    ).path, header + " {\n" + fields + "    // BENCHMARK_DEPENDENCIES\n" + body + "\n}\n"


def gt(repo, rule, positive, subject, rationale):
    label = Label.POSITIVE if positive else Label.NEGATIVE
    return GroundTruthCase(
        case_id=case_id(NS, repo, rule, label, subject),
        repository_id=repo,
        rule_id=rule,
        rule_family=rule_family(rule),
        label=label,
        subjects=subject,
        rationale=rationale,
        origin=Origin.CURATED,
        annotation_status=AnnotationStatus.CURATED,
    )


def add(repo, family, language, files, truths, spec=None, profile=None, base=None, mutation=None):
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
            origin=Origin.MUTATION if mutation else Origin.CURATED,
            languages=(language,),
            source_path=f"repositories/{repo}",
            source_fingerprint=source_fingerprint(files),
            ground_truth=f"ground_truth/{repo}.json",
            dataset_split=BASE.repositories[0].dataset_split,
            architecture_spec=spec,
            graph_config=profile,
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


def method(language, name="read", number=1):
    return (
        f"    public int {name}() {{ return {number}; }}\n"
        if language == Language.JAVA
        else f"    {name}(): number {{ return {number}; }}\n"
    )


# Two architectures differ in topology and responsibilities, not just names/thresholds.
for family in ("static-webshop", "static-batch-workflow"):
    for language in (Language.JAVA, Language.TYPESCRIPT):
        repo = family + "-" + language.value.lower() + "-clean"
        if family == "static-webshop":
            definitions = [
                ("controller", "CartEndpoint", [("service", "CheckoutService")]),
                ("service", "CheckoutService", [("repository", "CartStore"), ("domain", "Cart")]),
                ("repository", "CartStore", []),
                ("domain", "Cart", []),
                ("infrastructure", "AuditTransport", []),
                ("orders", "OrderWorkflow", [("service", "CheckoutService")]),
                ("payments", "SettlementInternal", []),
            ]
            changes = [
                ("ARCH001", ("domain", "Cart"), ("infrastructure", "AuditTransport")),
                ("ARCH002", ("controller", "CartEndpoint"), ("repository", "CartStore")),
                ("ARCH005", ("orders", "OrderWorkflow"), ("payments", "SettlementInternal")),
            ]
        else:
            definitions = [
                ("controller", "BatchEndpoint", [("service", "BatchService")]),
                ("service", "BatchService", [("domain", "Batch"), ("repository", "BatchStore")]),
                ("domain", "Batch", []),
                ("repository", "BatchStore", []),
                ("cycle", "ReadStage", [("cycle", "PlanStage")]),
                ("cycle", "PlanStage", [("cycle", "CommitStage")]),
                ("cycle", "CommitStage", []),
            ]
            changes = [
                ("ARCH002", ("controller", "BatchEndpoint"), ("repository", "BatchStore")),
                ("ARCH003", ("cycle", "CommitStage"), ("cycle", "ReadStage")),
                ("ARCH004", ("domain", "Batch"), ("service", "BatchService")),
            ]
        files = dict(
            source(language, directory, name, method(language, "step", index + 1), targets)
            for index, (directory, name, targets) in enumerate(definitions)
        )
        rules = []
        for rule, _, _ in changes:
            rules.extend(json.loads((ROOT / f"specs/{rule}.json").read_text())["rules"])
        spec_data = json.loads((ROOT / "specs/ARCH001.json").read_text())
        spec_data["rules"] = rules
        spec = f"specs/{family}.json"
        write(spec, spec_data)
        configs = {}
        clean = []
        for rule, (sf, sn), (tf, tn) in changes:
            cycle = (
                tuple(
                    loc(language, "cycle", n).path
                    for n in ("ReadStage", "PlanStage", "CommitStage")
                )
                if rule == "ARCH003"
                else ()
            )
            logical = (
                subjects(
                    *(loc(language, "cycle", n) for n in ("ReadStage", "PlanStage", "CommitStage"))
                )
                if cycle
                else subjects(
                    loc(language, sf, sn, NodeKind.FILE),
                    loc(language, tf, tn, NodeKind.FILE),
                    directed=True,
                )
            )
            configs[rule] = MutationConfig(
                source=loc(language, sf, sn),
                target=loc(language, tf, tn),
                expected_subjects=logical,
                cycle_paths=cycle,
            )
            clean.append(
                gt(
                    repo,
                    rule,
                    False,
                    logical,
                    (
                        "Independent clean architecture delegates through its declared ser"
                        "vice/module boundaries and has no prohibited dependency or closed"
                        " workflow SCC."
                    ),
                )
            )
        add(repo, family, language, files, tuple(clean), spec=spec)
        for rule, config in configs.items():
            op = MutationRegistry().get(rule)
            mid = mutation_identity(NS, repo, op, config, source_fingerprint(files))
            derived = repo + "-" + rule.lower()
            # A priori expected label precedes mutation parsing/verification.
            truth = expected_truth(NS, derived, rule, config, mid)
            after = op.apply(files, config)
            for path, text in after.items():
                target = ROOT / "repositories" / derived / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(text.encode())
            assert op.verify(
                build_source(ROOT / "repositories" / derived, "benchmark:" + derived), config
            )
            mutation = MutationResult(
                mutation_id=mid,
                operator_id=rule,
                base_repository_id=repo,
                derived_repository_id=derived,
                config=config,
                base_fingerprint=source_fingerprint(files),
                result_fingerprint=source_fingerprint(after),
                changed_files=tuple(
                    FileChange(
                        path=p, before_hash=file_hash(files[p]), after_hash=file_hash(after[p])
                    )
                    for p in sorted(files)
                    if files[p] != after[p]
                ),
                expected_cases=(truth,),
                verification_status="VERIFIED",
            )
            add(derived, family, language, after, (truth,), spec=spec, base=repo, mutation=mutation)

# Topologies and arithmetic are curated directly; no GraphCandidate is consulted.
graphs = [
    (
        "graph-fan-in",
        {
            "Client1": ["Registry"],
            "Client2": ["Registry"],
            "Client3": ["Registry"],
            "Client4": ["Registry"],
            "Registry": ["Sink"],
            "Sink": [],
            "Idle": [],
        },
        {"excessive_coupling": 4, "hub_fan_in": 4},
        [
            ("ARCH101", ["Registry"], True, "Registry has five unique neighbours, threshold four."),
            ("ARCH101", ["Client1"], False, "Client has one neighbour."),
            ("ARCH102", ["Registry"], True, "Registry has four distinct incoming dependents."),
            ("ARCH102", ["Client1"], False, "Client has zero incoming dependents."),
        ],
        (),
    ),
    (
        "graph-fan-out",
        {
            "Dispatcher": ["Worker1", "Worker2", "Worker3", "Worker4", "Worker5"],
            "Worker1": [],
            "Worker2": [],
            "Worker3": [],
            "Worker4": [],
            "Worker5": [],
            "Idle": [],
        },
        {
            "excessive_coupling": 4,
            "god_min_members": 3,
            "god_min_methods": 2,
            "god_min_coupling": 4,
        },
        [
            ("ARCH101", ["Dispatcher"], True, "Dispatcher has five distinct outgoing neighbours."),
            ("ARCH101", ["Worker1"], False, "Worker has one neighbour."),
            (
                "ARCH103",
                ["Dispatcher"],
                True,
                "Dispatcher has three methods plus five fields and five neighbours.",
            ),
            ("ARCH103", ["Idle"], False, "Idle is large (three methods) but has zero coupling."),
        ],
        ("Dispatcher", "Idle"),
    ),
    (
        "graph-diamond",
        {
            "Start": ["Left", "Right"],
            "Left": ["Join"],
            "Right": ["Join"],
            "Join": ["Finish"],
            "Finish": [],
        },
        {"bottleneck_betweenness": 0.2},
        [
            (
                "ARCH105",
                ["Join"],
                True,
                "Five-node diamond: Join lies on three ordered shortest paths, 3/(4*3)=0.25.",
            ),
            (
                "ARCH105",
                ["Left"],
                False,
                "Two alternative shortest paths split credit; Left centrality=1/(4*3), below 0.2.",
            ),
        ],
        (),
    ),
    (
        "graph-cluster-bridge",
        {
            "L1": ["L2", "L3", "L4"],
            "L2": ["L3", "L4"],
            "L3": ["L4"],
            "L4": ["Gate"],
            "Gate": ["R1"],
            "R1": ["R2", "R3"],
            "R2": ["R3"],
            "R3": [],
        },
        {"bottleneck_betweenness": 0.25},
        [
            (
                "ARCH105",
                ["Gate"],
                True,
                "Eight nodes: Gate separates four left and three right nodes, 12/(7*6)>0.25.",
            ),
            (
                "ARCH105",
                ["L1"],
                False,
                "L1 has three neighbours (more than Gate), but source betweenness is zero.",
            ),
        ],
        (),
    ),
    (
        "graph-stable-core",
        {
            "CoreA": ["CoreB", "CoreC", "Adapter"],
            "CoreB": ["CoreA", "CoreC"],
            "CoreC": ["CoreA", "CoreB"],
            "Reader1": ["CoreA"],
            "Reader2": ["CoreA"],
            "Reader3": ["CoreA"],
            "Reader4": ["CoreA"],
            "Adapter": ["Port1", "Port2", "Port3"],
            "Port1": [],
            "Port2": [],
            "Port3": [],
        },
        {"unstable_delta": 0.4},
        [
            (
                "ARCH104",
                ["CoreA", "Adapter"],
                True,
                "CoreA Ca=6/Ce=3: I=1/3; Adapter Ca=1/Ce=3: I=3/4; delta=5/12>0.4.",
            ),
            ("ARCH104", ["CoreA", "CoreB"], False, "CoreB Ca=2/Ce=2: I=1/2; delta=1/6<0.4."),
        ],
        (),
    ),
]
for family, topology, thresholds, controls, large in graphs:
    profile = f"profiles/{family}.json"
    write(profile, {"candidates": thresholds})
    for language in (Language.JAVA, Language.TYPESCRIPT):
        repo = family + "-" + language.value.lower()
        files = dict(
            source(
                language,
                "graph",
                name,
                "".join(method(language, "operation" + str(j), j) for j in range(3))
                if name in large
                else "",
                tuple(("graph", t) for t in targets),
            )
            for name, targets in topology.items()
        )
        truths = tuple(
            gt(
                repo,
                rule,
                positive,
                subjects(
                    *(loc(language, "graph", name) for name in names), directed=rule == "ARCH104"
                ),
                rationale,
            )
            for rule, names, positive, rationale in controls
        )
        add(repo, family, language, files, truths, profile=profile)

# Responsibility pairs include neutral names, delegation and abstraction controls.
semantics = [
    (
        "semantic-shipping",
        (Language.JAVA, Language.TYPESCRIPT),
        [
            (
                "ARCH202",
                "controller",
                "Coordinator",
                True,
                (
                    "Controller endpoint makes shipping/routing policy branches and pr"
                    "ice decisions despite neutral naming."
                ),
                (
                    "public int route(int weight) { if (weight > 20) { return weight *"
                    " 7 + 40; } return weight * 3; }"
                ),
                (
                    "route(weight: number): number { if (weight > 20) { return weight "
                    "* 7 + 40; } return weight * 3; }"
                ),
                (),
            ),
            (
                "ARCH202",
                "controller",
                "RequestEndpoint",
                False,
                (
                    "Multiple helpers only validate/map request fields and delegate; t"
                    "hey implement no shipping price/routing policy."
                ),
                (
                    "public int handle(int weight) { int value = map(weight); if (!val"
                    "id(value)) { return -1; } return reference0.route(value); } priva"
                    "te int map(int value) { return value; } private boolean valid(int"
                    " value) { return value >= 0; }"
                ),
                (
                    "handle(weight: number): number { const value = this.map(weight); "
                    "if (!this.valid(value)) { return -1; } return this.reference0.rou"
                    "te(value); } private map(value: number): number { return value; }"
                    " private valid(value: number): boolean { return value >= 0; }"
                ),
                (("service", "ShippingService"),),
            ),
            (
                "ARCH205",
                "controller",
                "Processor",
                True,
                (
                    "One endpoint parses the request, applies freight pricing and crea"
                    "tes a persistence SQL statement."
                ),
                (
                    "public String submit(String text) { int weight = Integer.parseInt"
                    "(text); int price = weight > 20 ? weight * 7 : weight * 3; return"
                    ' "INSERT INTO freight(price) VALUES (" + price + ")"; }'
                ),
                (
                    "submit(text: string): string { const weight = Number(text); const"
                    ' price = weight > 20 ? weight * 7 : weight * 3; return "INSERT IN'
                    'TO freight(price) VALUES (" + price + ")"; }'
                ),
                (),
            ),
            (
                "ARCH205",
                "service",
                "ShippingService",
                False,
                (
                    "Service only chooses a shipping price; presentation and persisten"
                    "ce are outside its responsibility."
                ),
                "public int route(int weight) { return weight * 3; }",
                "route(weight: number): number { return weight * 3; }",
                (),
            ),
        ],
    ),
    (
        "semantic-reporting",
        (Language.JAVA,),
        [
            (
                "ARCH201",
                "repository",
                "ReportRepository",
                True,
                (
                    "Repository computes revenue categories and formats a reporting CS"
                    "V response instead of providing persistence abstraction."
                ),
                (
                    "public String report(int gross, int refunds) { int net = gross - "
                    'refunds; String band = net > 1000 ? "large" : "small"; return "ne'
                    't,band\\n" + net + "," + band; }'
                ),
                "",
                (),
            ),
            (
                "ARCH201",
                "repository",
                "ReportStore",
                False,
                (
                    "Caching store only saves/loads a supplied report identifier; the "
                    "similar repository placement matches persistence responsibility."
                ),
                (
                    "private int cached; public void save(int id) { cached = id; } pub"
                    "lic int load() { return cached; }"
                ),
                "",
                (),
            ),
            (
                "ARCH204",
                "infrastructure",
                "RevenuePolicy",
                True,
                (
                    "Curated target expects revenue policy in the domain; this infrast"
                    "ructure component performs only business revenue classification."
                ),
                (
                    "public int bracket(int revenue) { return revenue > 1000 ? 3 : rev"
                    "enue > 500 ? 2 : 1; }"
                ),
                "",
                (),
            ),
            (
                "ARCH204",
                "infrastructure",
                "CsvTransport",
                False,
                (
                    "Infrastructure placement matches conversion to an external CSV se"
                    "rialization protocol."
                ),
                'public String encode(int id) { return "report_id\\n" + id; }',
                "",
                (),
            ),
        ],
    ),
    (
        "semantic-ledger",
        (Language.JAVA, Language.TYPESCRIPT),
        [
            (
                "ARCH203",
                "domain",
                "LedgerCoordinator",
                True,
                (
                    "Domain component constructs vendor-specific SQLite transaction/up"
                    "sert protocol, not a storage abstraction."
                ),
                (
                    'public String commit(int id) { return "BEGIN IMMEDIATE; INSERT IN'
                    'TO ledger(id) VALUES (" + id + ") ON CONFLICT DO NOTHING; COMMIT;'
                    '"; }'
                ),
                (
                    'commit(id: number): string { return "BEGIN IMMEDIATE; INSERT INTO'
                    ' ledger(id) VALUES (" + id + ") ON CONFLICT DO NOTHING; COMMIT;";'
                    " }"
                ),
                (),
            ),
            (
                "ARCH203",
                "domain",
                "Ledger",
                False,
                (
                    "Domain depends only on an abstract CommitPort and forwards an ide"
                    "ntifier; no vendor/SQL detail is present."
                ),
                "public void commit(int id) { reference0.commit(id); }",
                "commit(id: number): void { this.reference0.commit(id); }",
                (("domain", "CommitPort"),),
            ),
            (
                "ARCH205",
                "controller",
                "TransactionManager",
                True,
                (
                    "Neutral named HTTP-facing component parses input, applies account"
                    " policy and forms vendor SQL persistence."
                ),
                (
                    "public String submit(String input) { int amount = Integer.parseIn"
                    't(input); int fee = amount > 100 ? amount / 10 : 5; return "INSER'
                    'T INTO ledger(fee) VALUES (" + fee + ")"; }'
                ),
                (
                    "submit(input: string): string { const amount = Number(input); con"
                    'st fee = amount > 100 ? amount / 10 : 5; return "INSERT INTO ledg'
                    'er(fee) VALUES (" + fee + ")"; }'
                ),
                (),
            ),
            (
                "ARCH205",
                "service",
                "PostingCoordinator",
                False,
                (
                    "Higher coupling to three ports serves one orchestration purpose: "
                    "forward posting, notify and audit; no HTTP parsing/pricing/SQL im"
                    "plementation."
                ),
                (
                    "public void post(int id) { reference0.commit(id); reference1.reco"
                    "rd(id); reference2.publish(id); }"
                ),
                (
                    "post(id: number): void { this.reference0.commit(id); this.referen"
                    "ce1.record(id); this.reference2.publish(id); }"
                ),
                (("domain", "CommitPort"), ("domain", "AuditPort"), ("domain", "EventPort")),
            ),
        ],
    ),
    (
        "semantic-ui-orders",
        (Language.TYPESCRIPT,),
        [
            (
                "ARCH202",
                "controller",
                "Handler",
                True,
                (
                    "Browser event endpoint chooses order approval state and inventory"
                    " allocation based on business rules, not request mapping."
                ),
                "",
                (
                    "approve(quantity: number, stock: number): string { if (quantity >"
                    ' stock) { return "backorder"; } return quantity > 10 ? "bulk-appr'
                    'oved" : "retail-approved"; }'
                ),
                (),
            ),
            (
                "ARCH202",
                "controller",
                "OrderEndpoint",
                False,
                (
                    "Endpoint checks request shape, maps a value and delegates approva"
                    "l; helper methods contain no inventory/approval decisions."
                ),
                "",
                (
                    "handle(quantity: number): string { if (!this.valid(quantity)) { r"
                    'eturn "invalid"; } return this.reference0.approve(this.map(quanti'
                    "ty)); } private valid(value: number): boolean { return value >= 0"
                    "; } private map(value: number): number { return value; }"
                ),
                (("service", "ApprovalService"),),
            ),
            (
                "ARCH204",
                "domain",
                "NotificationRenderer",
                True,
                (
                    "Curated domain target excludes presentation; component builds HTM"
                    "L/CSS UI markup instead of order domain responsibility."
                ),
                "",
                (
                    'render(value: string): string { return "<span class=order-status>'
                    '" + value + "</span>"; }'
                ),
                (),
            ),
            (
                "ARCH204",
                "controller",
                "ViewRenderer",
                False,
                (
                    "Presentation folder is the curated expected placement for renderi"
                    "ng order status HTML."
                ),
                "",
                (
                    'render(value: string): string { return "<span class=order-status>'
                    '" + value + "</span>"; }'
                ),
                (),
            ),
        ],
    ),
]
for family, languages, scenarios in semantics:
    for language in languages:
        repo = family + "-" + language.value.lower()
        files = {}
        truths = []
        for rule, folder, name, positive, rationale, java, ts, targets in scenarios:
            files.update(
                (
                    source(
                        language,
                        folder,
                        name,
                        "    " + (java if language == Language.JAVA else ts) + "\n",
                        targets,
                    ),
                )
            )
            truths.append(
                gt(repo, rule, positive, subjects(loc(language, folder, name)), rationale)
            )
        if family == "semantic-ledger":
            for name, action in [
                ("CommitPort", "commit"),
                ("AuditPort", "record"),
                ("EventPort", "publish"),
            ]:
                path = loc(language, "domain", name).path
                files[path] = (
                    f"package domain; public interface {name} {{ void {action}(int id); }}\n"
                    if language == Language.JAVA
                    else f"export interface {name} {{ {action}(id: number): void; }}\n"
                )
        if family == "semantic-ui-orders":
            files.update(
                (
                    source(
                        language,
                        "service",
                        "ApprovalService",
                        (
                            '    approve(quantity: number): string { return "accepted:" + quan'
                            "tity; }\n"
                        ),
                    ),
                )
            )
        add(repo, family, language, files, tuple(truths))

# Lowest deterministic seed meeting declared family-composition constraints, no detector run.
families = tuple(sorted({r.repository_family_id for r in repositories}))
for index in range(100000):
    seed = f"archguard-expanded-composition-v1:{index}"
    splits = plan_splits(families, seed)
    holdouts = [{f for f, s in splits.items() if s == split} for split in ("VALIDATION", "TEST")]
    if all(
        len(group & {"static-webshop", "static-batch-workflow"}) == 1
        and len(group & {"semantic-shipping", "semantic-ledger"}) == 1
        and len([f for f in group if f.startswith("graph-")]) == 1
        for group in holdouts
    ):
        break
else:
    raise ValueError("composition-only split seed not found")
updated = tuple(
    BenchmarkRepository.model_validate(
        r.model_copy(update={"dataset_split": splits[r.repository_family_id]})
    )
    for r in sorted(repositories, key=lambda r: r.repository_id)
)
dataset = BenchmarkDataset(
    dataset_id=BASE.dataset_id,
    dataset_version="1.1.0",
    namespace=NS,
    split_seed=seed,
    split_manifest="splits-1.1.json",
    repositories=updated,
)
write(
    "splits-1.1.json",
    {
        "algorithm": dataset.split_algorithm,
        "seed": seed,
        "families": {k: v.value for k, v in sorted(splits.items())},
    },
)
write("dataset-1.1.json", dataset)
print(len(updated), "repositories;", len(families), "families;", seed)
