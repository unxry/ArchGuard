# Planned finding catalog

Это целевой каталог, **правила и детекторы не реализованы в foundation**.
Каталог не содержит measured outputs и не означает одинаковую обнаружимость всеми baseline methods.

| ID | Name | Planned basis |
| --- | --- | --- |
| ARCH001 | Forbidden Dependency | explicit constraint / deterministic |
| ARCH002 | Layer Violation | explicit constraint / deterministic |
| ARCH003 | Circular Dependency | graph path / cycle |
| ARCH004 | Reverse Dependency | explicit direction constraint |
| ARCH005 | Module Boundary Violation | explicit module constraint |
| ARCH101 | Excessive Coupling | structural / heuristic |
| ARCH102 | Dependency Hub | structural / heuristic |
| ARCH103 | Potential God Component | structural / heuristic candidate |
| ARCH104 | Unstable Dependency | structural / heuristic |
| ARCH105 | Architecture Bottleneck | structural / heuristic |
| ARCH201 | Responsibility Mismatch | semantic |
| ARCH202 | Business Logic in Controller | semantic |
| ARCH203 | Infrastructure Leakage | semantic |
| ARCH204 | Misplaced Component | semantic |
| ARCH205 | Suspicious Cross-Layer Responsibility | semantic |

Graph signal может быть детерминированным фактом, а interpretation/threshold — эвристическим.
Severity определяется отдельно от calibration/confidence. Confirmed explicit violation LLM
не отменяет. Target scope ARCH001–ARCH205 означает перечисленные 15 правил, не все 205 чисел.

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
