# Finding catalog

ARCH001, ARCH002, ARCH004 и ARCH005 реализованы в PROMPT 005 как static rules по explicit target spec
и resolved internal IAM edges. PROMPT 006 добавляет explicit ARCH003 и отдельные heuristic
GraphCandidate ARCH101–105. PROMPT 008 реализует structured semantic candidate contracts ARCH201–205.
Каталог не содержит measured outputs и не означает одинаковую обнаружимость всеми baseline methods.

| ID | Name | Basis / status |
| --- | --- | --- |
| ARCH001 | Forbidden Dependency | implemented: explicit constraint / deterministic |
| ARCH002 | Layer Violation | implemented: explicit layer constraint / deterministic |
| ARCH003 | Circular Dependency | implemented: enabled explicit rule / one finding per cyclic SCC |
| ARCH004 | Reverse Dependency | implemented: explicit direction constraint |
| ARCH005 | Module Boundary Violation | implemented: explicit module constraint |
| ARCH101 | Excessive Coupling | implemented candidate: explicit distinct-neighbour threshold |
| ARCH102 | Dependency Hub | implemented candidate: explicit Ca threshold |
| ARCH103 | Potential God Component | implemented candidate: size AND coupling, component only |
| ARCH104 | Unstable Dependency | implemented candidate: I(target) − I(source) ≥ delta |
| ARCH105 | Architecture Bottleneck | implemented candidate: directed betweenness + optional support |
| ARCH201 | Responsibility Mismatch | implemented semantic candidate; quality unmeasured |
| ARCH202 | Business Logic in Controller | implemented semantic candidate; quality unmeasured |
| ARCH203 | Infrastructure Leakage | implemented semantic candidate; quality unmeasured |
| ARCH204 | Misplaced Component | implemented semantic candidate; quality unmeasured |
| ARCH205 | Suspicious Cross-Layer Responsibility | implemented semantic candidate; quality unmeasured |

ARCH101–105 не создают Finding: default disabled, confidence absent, `not_calibrated: true`.
Пороги и формулы: [Graph Candidates](GRAPH_CANDIDATES.md). Cycle observation без explicit rule
также не violation. Graph signal может быть детерминированным фактом, а interpretation/threshold — эвристическим.
Severity определяется отдельно от calibration/confidence. Confirmed explicit violation LLM
не отменяет. Target scope ARCH001–ARCH205 означает перечисленные 15 правил, не все 205 чисел.

ARCH201–205 — `SemanticArchitectureCandidate`, не Finding: SUPPORTED / NOT_SUPPORTED /
INSUFFICIENT_CONTEXT, validated subject/evidence refs, `not_calibrated=true`, confidence absent.
Provider/schema/context/version contracts: [AI architecture analysis](AI_ARCHITECTURE_ANALYSIS.md).
Offline scripted tests не доказывают semantic detection quality.

## SEC — planned security extension; not implemented in foundation

| ID | Name |
| --- | --- |
| SEC001 | Hardcoded Secret |
| SEC002 | Possible SQL Injection |
| SEC003 | Possible XSS |
| SEC004 | Unsafe Command Execution |
| SEC005 | Path Traversal |
| SEC006 | Weak Input Validation |
| SEC007 | Insecure Configuration |
| SEC008 | Vulnerable Dependency |
| SEC009 | Possible Authorization Bypass |
| SEC010 | Unsafe Deserialization |

SEC pipeline, calibration и experiment отдельные. SEC findings не входят в Hybrid Architecture
Decision и Architecture F1. Security implementation starts only after CORE THESIS COMPLETE.
