# Independent ground truth

Truth is created by curated source scenarios or a priori controlled mutations. A Finding,
GraphCandidate, SemanticArchitectureCandidate or HybridDecision never supplies a label. The
`archguard.benchmark` boundary may consume analyzer results; core/IAM/architecture/application
cannot import benchmark. The AST dependency test enforces this direction. Pipelines receive only
source, namespace, specification and graph configuration; label joins happen afterward.

`GroundTruthCase` records stable UUIDv5(dataset namespace, repository ID, rule, label, logical
locators), rule family, POSITIVE/NEGATIVE/UNKNOWN, subject scope, nonempty rationale, origin,
annotation status, optional expected evidence/mutation identity and review metadata. Coordinates
and runtime IAM NodeIds are not identity. Review fields default to UNREVIEWED with no annotators;
no human agreement/review is invented. Mutation labels are MUTATION_DERIVED, not human VERIFIED.

Locator = relative POSIX path + language + qualified symbol + kind + optional signature. FILE
locators use the relative path as qualified name. Resolver returns RESOLVED/AMBIGUOUS/MISSING
against IAM declarations with exact equality. Signature may be omitted only if the result is unique.
Ambiguous/missing truth yields PARTIAL and UNRESOLVED_TRUTH, never automatic FN. Evaluation compares
resolved IAM IDs, preserving pair direction; unordered SCC members are a canonical set.

Static logical cases use a directed file pair, matching detector callsite aggregation. ARCH003 has
one case per expected cyclic SCC. Component graph and semantic cases use CLASS locators; method
output normalizes through actual IAM containment, and a FILE can normalize to CLASS only when it
contains exactly one class. Multi-class or projected aggregate ambiguity fails explicitly. There is
no name resemblance, fuzzy match or line-level duplicate violation count.

Each repository declares annotated rules and optional full rules, per-rule subjects, full files and
module directories. Full file/module scope requires all subjects to fall inside the declared region.
Explicit cases are scored exactly; outside these annotations predictions become OUT_OF_SCOPE.
An unmatched positive inside a full region is a scoped extra FP, but does not create a negative
universe or TN. An UNKNOWN case overrides any full scope and remains unknown.

ARCH101–105 positives mean **configured structural signal present**, not architectural defect.
The seed fixes known topology and arithmetic independently: Hub has Ca=3, Ce=1; Bridge Ca=1, Ce=3;
instability delta=0.5. Nine-node directed betweenness of Hub and Bridge is 12/(8*7); source In1 is
zero. Thresholds are task configuration, not universal architectural truth.

ARCH201–205 labels come from small source responsibilities: HTTP/pricing in a Repository versus
persistence abstraction; pricing policy in Controller versus delegation; domain SQL versus abstract
port; HTTP presenter in domain versus presentation; presentation/pricing/SQL combined versus
single-purpose service. All five have Java and TypeScript positive/negative controls with explicit
rationales. Semantic labels require independent review before a research-quality benchmark.
