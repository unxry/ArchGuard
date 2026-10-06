# ADR 0019: Blind human annotation from detector/model outputs

Status: accepted for PROMPT 012 foundation, 2026-10-05.

Decision: sample raw IAM subjects/degree strata with frozen hash ranking, freeze subject/question
scope before AI, and export only pinned source/documentation references. Separate private analysis
from annotation. Preserve individual actual human reviews and require explicit adjudication for
conflict. Freeze corpus/sample/annotation fingerprints separately for future model-linked evaluation.

Consequences: unannotated is not negative; out-of-scope predictions cannot affect scoped accuracy.
Single review remains provisional. All 40 initial packets are UNREVIEWED; no fake reviewers, labels
or agreement values are created. Model-independent sampling does not eliminate selection/context bias.
