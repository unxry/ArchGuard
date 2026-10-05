# Structural role/layer hypotheses

Role taxonomy: CONTROLLER, SERVICE, REPOSITORY, DOMAIN_MODEL, DOMAIN_SERVICE, ADAPTER, GATEWAY,
CLIENT, CONFIGURATION, UTILITY, UNKNOWN. Discovered layers: PRESENTATION, APPLICATION, DOMAIN,
PERSISTENCE, INFRASTRUCTURE, UNKNOWN, AMBIGUOUS. Это отдельные enums, не target layer names.

## Signals и precedence

Evidence kinds: NAME_PATTERN, PATH_PATTERN, ANNOTATION, DECORATOR, INHERITANCE, IMPORT_PATTERN,
DEPENDENCY_DIRECTION, GRAPH_POSITION, STRUCTURAL_SHAPE, MODULE_PATH. Каждый kind можно отключить.
Нет weighted sum, confidence или probability. WEAK/MODERATE/STRONG — ordinal evidence labels;
AMBIGUOUS — конфликт, не низкая численная вероятность.

Name matching разделяет CamelCase/acronyms/underscores/hyphens и проверяет whole token suffix.
Controller/Resource/Handler → controller; Service/UseCase → service; Repository/Dao/DAO → repository;
Entity/Aggregate/AggregateRoot → domain model; DomainService → domain service; Adapter/Gateway/Client,
Config/Configuration и Util/Utils/Helper → соответствующие роли. Longer specific suffix DomainService
имеет precedence над generic Service. Serviceability не Service; ControllerFactory не Controller;
ControllerFactoryHelper может быть UTILITY по Helper, не CONTROLLER по substring.

Path matching — complete case-insensitive directory segments repository-relative POSIX path, без
filename/absolute-root inference. controller(s)/handlers, service(s)/usecases, repository/repositories/
dao, adapter(s), clients/config/utils дают role hints. domain/application/presentation/persistence/
infrastructure/infra дают layer hints; domain path сам по себе не объявляет DOMAIN_MODEL role.

Specific annotation/decorator name hint → STRONG. Independent name+path agreement → STRONG.
Single naming/path или resolved inheritance base-name hint → MODERATE. Framework-import hint →
WEAK. Highest precedence unique role выбирается при configured minimum strength; lower conflicting
roles сохраняются. Equal highest conflicting roles → role UNKNOWN + strength AMBIGUOUS, без first-win.
Insufficient specific evidence → UNKNOWN/WEAK, с retained candidate roles/evidence.

## Framework metadata

Java names уже извлекаются declaration-level в Symbol.attributes.annotations. Registry:
RestController/Controller, Service, Repository, Configuration, Entity/AggregateRoot. Component —
generic managed-component evidence, без конкретной роли. Entity не Repository.

Additive ECMAScript extractor 1.1.0 сохраняет только decorator names в существующем annotations
field, включая qualified/called decorators около class/export declaration. Argument text не хранится.
Nest-style Controller даёт controller hint; Injectable generic, без forced SERVICE. Name/path могут
дать SERVICE/REPOSITORY независимо от generic decorator. Arbitrary/custom annotation с совпадающим
именем может давать ложный hint: registry не подтверждает import binding/framework runtime semantics.

Inheritance использует actual resolved graph proof. Import hints используют actual IAM IMPORTS,
validated provenance/source location и external namespace metadata; small registry Spring/Nest,
без десятков framework adapters. Framework signals можно отключить целиком.

## Layer inference и graph support

CONTROLLER→PRESENTATION, SERVICE→APPLICATION, DOMAIN_MODEL/DOMAIN_SERVICE→DOMAIN,
REPOSITORY→PERSISTENCE, ADAPTER/GATEWAY/CLIENT/CONFIGURATION→INFRASTRUCTURE.
UTILITY не имеет автоматического layer. Layer берёт selected role, direct path/framework layer hints
и role ambiguity candidates. Два разных labels дают AMBIGUOUS даже при stronger role annotation:
src/domain/PaymentController + RestController → strong CONTROLLER, ambiguous DOMAIN/PRESENTATION.
Role и layer остаются разными hypotheses; role assignment не устраняет конфликт ownership.

Graph Ca/Ce и declaration shape — только WEAK supporting evidence, без role hint. Центральность
не создаёт SERVICE/CONTROLLER. После независимого initial layer pass выполняется ровно один
secondary direction pass: actual edge directions добавляются evidence к уже selected known layers.
Pass не меняет assignments/strengths и не подгоняет topology под conventional layered architecture.
Unknown/ambiguous layers не переименовываются ради coverage. graph_refinement=false выключает
secondary graph/shape/direction evidence; primary name/path/framework inference продолжает работать.

Strength не calibrated certainty; expressive naming может быть неверным. Нет Express routing analysis:
app.get/router.post не объявляются guaranteed Controller. TSX/JSX не объявляются Controller.
