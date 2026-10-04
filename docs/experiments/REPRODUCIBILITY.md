# Scientific reproducibility

Foundation предоставляет `ReproducibilityManifest` как versioned typed config envelope, без
runner/results. При measured runs хранить manifest и ссылки на immutable raw artifacts.

| Field / artifact | Requirement |
| --- | --- |
| software version | package version + resolved dependency lock checksum |
| git commit | exact code revision, clean/dirty state и patch artifact при dirty run |
| dataset version | source/ground-truth/split manifest versions и checksums |
| repository revision | exact commit каждого source project, intake exclusions |
| random seed | explicit seed или null, не implicit magic value |
| model/provider | exact model identifier/provider, available snapshot version/date |
| model parameters | temperature, sampling/budgets, seed if supported; explicit defaults |
| prompts/context | template version, selection policy, context hashes, redaction policy |
| parser version | per-language parser/tool version и canonical identity policy |
| analysis config | enabled rules, thresholds, graph projections, fusion/context policies |
| runtime | Python patch version, OS/architecture, hardware, Docker image digest where used |
| execution | timestamps, durations, cache policy, failures/retries/timeouts |
| scoring | matching/deduplication rules, label exclusions, metric definitions/version |
| resource usage | measured memory, actual tokens/calls, missing-data semantics |

Current typed envelope stores software/dataset versions, optional random seed/model/parser
versions/git commit and JSON analysis config. Detailed artifact/lifecycle fields will be added
with actual runner requirements through schema review, not fabricated default values.

Calibration artifacts содержат training split provenance и frozen parameters, references
из Confidence указывают на них. Validation/test не изменяют calibration parameters. Model calls
могут быть nondeterministic или менять provider behavior: record observed metadata, повторения,
uncertainty и ограничения. API keys, passwords и raw secrets не сохраняются в manifests/logs.

HTML demo metrics не являются data source. Synthetic contract fixtures не составляют benchmark.
Ни один experiment result в foundation не создан.
