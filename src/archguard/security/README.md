# Security extension boundary

**planned security extension; not implemented in foundation.**

**Security implementation starts only after CORE THESIS COMPLETE.**

Future structure:

```text
security/
├── secrets/
├── rules/
├── dependency/
├── configuration/
├── dataflow/
├── taint/
├── graph/
├── intelligence/
└── pipeline/
```

Reuse IAM identifiers, SourceLocation and Finding / Evidence / Trace infrastructure. A dedicated
pipeline emits SEC findings, never inputs to Hybrid Architecture Decision. Its rules, detectors,
calibration, benchmark, run status and metrics are independent. Common UI reporting may combine
the queues but must preserve namespace and provenance. Reserved edge/evidence types are schema
support, not scanners. There is no secret scan, advisory query, data-flow, taint or AI security call.
