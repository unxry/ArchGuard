# Graph-guided LLM context: experimental hypothesis

Гипотеза: bounded graph-guided context может уменьшить передаваемый контекст относительно bounded
expanded baseline при сохранении качества semantic architecture analysis. PROMPT 008 её не доказывает.
LOCAL_ONLY обеспечивает отдельную ablation: меньше context может означать недостаток relevant evidence.
Fixture character comparison не является measured token savings, Precision/Recall/F1 или LLM quality.

Будущий controlled experiment использует общие ground-truth labels, одинаковые targets/rules,
provider/model/prompt/schema/generation settings и budgets, independent evaluation и repeated runs.
Discovery hypotheses не становятся ground truth; graph preselection оценивается отдельно от semantic
classifier, включая пропущенные targets. Truncated/INSUFFICIENT_CONTEXT/failed calls учитываются
явно, без их исключения ради улучшения metrics. Выделять cold context construction и provider latency.

Measurements: Precision, Recall, F1; provider-reported/tokenizer-backed input/output tokens;
calls/failed calls; latency; billed cost только если доступна; selected nodes/files/fragments,
serialized context chars/source chars, bytes, truncation и coverage. Unknown tokens/cost остаются null.
Versioned manifests/fingerprints, target/rule choices и invocation metadata сохраняются source-free;
source-bearing debug exports требуют отдельной явной политики.

Детерминизм оценивается для context selection/ranges/hashes/metadata/serialization на macOS/Linux,
отдельно от stochastic assessments внешней модели. Evidence-reference validation измеряется как
contract validity, а не semantic correctness. Prompt injection regression сейчас проверяет разделение
instructions/data в реально сформированном request; resistance самой модели потребует отдельного
adversarial benchmark и не заявляется доказанной.

Текущие synthetic measurements и offline scripted сценарии:
[PROMPT 008 verification](../verification/PROMPT_008.md).
Hybrid fusion, arbitrary weights, confidence calibration, benchmark quality, Security и health score
в этом этапе не реализуются. Следующий этап начинается только после review AI boundary.
