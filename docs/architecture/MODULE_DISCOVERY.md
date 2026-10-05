# Structural module candidates

ModuleDiscovery предлагает implementation feature groups, не target modules/Maven/npm modules.
Discovery не требует community detection. Candidate ID versioned UUIDv5: project + normalized
config hash + seed kind/namespace + sorted component IDs. Different language namespace seeds
не сливаются только из-за одинакового feature name.

## Seeds и configuration

Java использует actual IAM package namespaces. Common package prefix определяется segment-wise,
ограничивается java_min_package_depth−1 (default depth 3), затем берётся feature branch на глубине
max(prefix length, minimum depth−1). com.example.orders.controller/repository и com.example.payments.*
дают com.example.orders и com.example.payments, без nested modules на каждый package.
java_common_prefix можно задать явно, например org.acme.app для более глубокого project root.
Missing/unrelated/shallow package namespaces остаются unassigned. Maven ownership не изобретается.

TS/JS использует complete relative directory segments. module_root_hints (default ["src"]) — exact
relative root prefixes. Более одного matching root → AMBIGUOUS_MODULE_ROOT, без arbitrary winner.
Без explicit match распознаётся единственный src wrapper в пределах max_module_depth (default 4),
затем первая feature directory; это поддерживает language-prefixed mixed fixtures. Без clear root
common directory prefix даёт только WEAK seeds. Несколько nested src roots ambiguous. Excessive
root depth/no feature directory → unassigned. Отдельные technical branch names src/main/java/com/
org/example/controller/service/repository/domain/application/infrastructure и equivalents не modules.

Candidate size по default minimum 2 components. Small seed остаётся WEAK candidate, не assigned
module. Clear root + sufficient size → MODERATE; internal edges > all boundary edges → STRONG.
Unclear root остаётся WEAK независимо от size. Default minimum_module_strength MODERATE;
explicit WEAK допускает uncertain roots только при sufficient size. minimum STRONG требует
strong structural evidence. Shared/common/utils/util получают shared_support hint; это descriptive
support convention, не business responsibility или mandatory catch-all module.

## Metrics и assignment

Все counts — unique simple directed projected graph edges, не occurrences/callsites:

- internal_dependency_edges: оба endpoints в candidate membership;
- incoming_cross_module_edges: target внутри, source вне;
- outgoing_cross_module_edges: source внутри, target вне;
- internal_component_count: actual candidate members;
- cohesion_ratio = internal / (internal + incoming + outgoing), denominator 0 → null.

Boundary counts включают unassigned/residual FILE endpoints, даже без identified second module.
incoming/outgoing_module_ids содержат только identifiable neighbour candidates, включая weak seeds.
Это dependency cohesion ratio, НЕ NetworkX modularity/quality score/probability. Groundable seed
evidence содержит actual subject/path/package, member count и configured minimum size.

Selected component module_id ставится только при size/minimum strength policy; UNKNOWN/UNASSIGNED
допустимы. Candidate members и accepted assignment — разные понятия. Matrix использует accepted
assignments, weak/unassigned members попадают в UNASSIGNED bucket. Internal matrix diagonal
отдельна от cross-candidate relationships. Seed metrics используют потенциальную membership.

Feature fixture: orders internal=2, incoming=0, outgoing=1 → cohesion=2/3;
shared internal=1, incoming=1, outgoing=0 → cohesion=1/2. Single ui/Widget остаётся WEAK/unassigned.
Ни path size, ни cohesion не calibrated module certainty; richer monorepo/ownership inference отложено.
