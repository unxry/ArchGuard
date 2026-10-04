# CORE THESIS COMPLETE

**Статус: milestone не достигнут. Foundation не реализует analysis pipeline.**

Milestone принимается только по рабочим implementations, tests и measured experiment artifacts:

- [ ] Java + TypeScript parsers и versioned IAM реально работают.
- [ ] Dependency extraction и dependency graph работают на обоих языках.
- [ ] Architecture rules и graph algorithms реализованы и проверены на ground truth.
- [ ] LLM architecture analysis и graph-guided context работают с audit/provenance.
- [ ] Hybrid decision работает и сохраняет доказанные deterministic violations.
- [ ] ARCH001–ARCH205 target scope: все 15 правил из FINDING_CATALOG явно покрыты и оценены.
- [ ] Versioned benchmark и repository-level calibration/validation/test split готовы.
- [ ] Static / Graph / LLM / Hybrid experiment проведён на одинаковых evaluation units.
- [ ] Architecture Precision / Recall / F1 и остальные protocol metrics измерены.
- [ ] Ablation study выполнен для семи заданных комбинаций.
- [ ] Reproducibility manifests/raw outputs и limitations зафиксированы; результаты воспроизводимы
      в пределах явно описанной LLM nondeterminism.

Наличие enum/Protocol, demo UI, synthetic contract fixture или каталогов правил не закрывает
пункты. Evidence acceptance: code revision, tests, dataset/ground-truth/split versions, config,
raw measured outputs и protocol report. Если гипотеза не подтверждается, результаты фиксируются
честно; milestone требует корректного исследования, не выдуманного повышения F1.

Только после этого Security Engine становится обязательным следующим расширением.
**Security implementation starts only after CORE THESIS COMPLETE.**
