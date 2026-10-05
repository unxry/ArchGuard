# Hybrid method: evidence composition before calibration

The hypothesis is that Static + Graph + LLM evidence can improve architecture violation detection
over individual methods. PROMPT 009 establishes an interpretable, source-free composition boundary
and deterministic precedence; it does not test that hypothesis or demonstrate improved F1.

Static ARCH001/002/004/005 and explicit target ARCH003 are normative conformance proofs.
Graph ARCH101–105 are structural candidates under explicit configured thresholds. Semantic
ARCH201–205 are provider assessments referencing selected context. Discovery is actual-architecture
hypothesis evidence. Their meanings differ: identity alignment alone does not combine votes or
estimate a probability. Default Hybrid decisions retain proofs and expose uncalibrated review or
insufficient-evidence states. Severity remains a target-rule property, separate from confidence.

Planned baselines: Static, Graph, LLM and Hybrid. The seven channel ablations are Static; Graph;
LLM; Static + Graph; Static + LLM; Graph + LLM; Static + Graph + LLM. Hold IAM/specification and
the evaluated concern/subject definitions constant. Declare candidate-to-ground-truth mapping and
handling of review/insufficient states before computing detection metrics; do not count every
review candidate as a confirmed true positive. Also report candidate volume, coverage and partial
input rates so abstention does not conceal errors. Context-strategy comparisons from PROMPT 008
can be controlled separately without changing the channel ablation definitions.

Ground truth will define labeled architecture cases, source repositories, target specifications,
mutation operators and expert annotation/adjudication. Every example needs repository/project,
commit/mutation identity, concern/rule, stable subject(s), evidence, label provenance and split.
The current feature export intentionally has no labels. Split by repository/project, keeping
all versions, related mutations and cases from one project in the same partition. Splitting
individual findings or files would leak shared source structure across train/validation/test.
Create/verify the dataset only in PROMPT 010, after review of this boundary.

Future weighted scoring and logistic regression must use the same frozen features/encoding and
repository-level splits. Fit only on training data. Select weights, regularization, missing-value
encoding, calibration and decision thresholds using validation data; freeze the selected artifact
before evaluating held-out test repositories. No optimization, artifact choice or threshold
selection uses test labels. Deterministic proof retention is a hard invariant outside the fitted
candidate decision. An artifact must record method, dataset/calibration run/split/schema versions
and fingerprints, coefficients/intercept, threshold and policy version. Neither supplied weights
nor execution/training exists in PROMPT 009.

Measure Precision=TP/(TP+FP), Recall=TP/(TP+FN), F1, FPR=FP/(FP+TN), FNR=FN/(FN+TP), elapsed
time, peak memory, LLM calls, input/output tokens and provider-reported cost when available. Define
undefined denominators as missing, and report aggregation by repository and concern plus sample
sizes. Unknown usage/cost stays unknown; characters are not token counts, and deterministic
fixture execution time is not an LLM evaluation. Record runtime/platform/engine/provider/actual
model/prompt/schema/context/configuration/artifact/split identities and stochastic evaluation
protocol. Repeated fixed artifacts test implementation reproducibility, not model reproducibility.

Limitations: conservative source resolution, parse/unresolved gaps, target-spec quality, ordinal
discovery hypotheses, bounded source contexts, uncalibrated structural thresholds, a deliberately
small concern mapping, model failures/stochasticity and missing cost/token reporting. Offline
scripted assessments verify mechanics and invariants; they do not measure semantic quality,
calibration, injection resistance, superiority or production performance.
