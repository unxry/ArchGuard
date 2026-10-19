"""Produce grayscale SVG research diagrams and high-resolution embedded PNG copies."""

from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/thesis/assets"


def svg_text(
    x: float, y: float, text: str, size: int = 27, anchor: str = "middle", color: str = "#111"
) -> str:
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" '
        f'text-anchor="{anchor}" fill="{color}">{html.escape(text)}</text>'
    )


def shell(height: int, content: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" '
        f'viewBox="0 0 1200 {height}"><rect width="1200" height="{height}" fill="white"/>'
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" '
        'orient="auto"><path d="M0 0 L8 3 L0 6" fill="none" stroke="#222"/></marker></defs>'
        '<g font-family="Times New Roman,serif">' + content + "</g></svg>"
    )


def diagram(stages: list[str], note: str = "", connectors: bool = True) -> str:
    columns = min(3, len(stages))
    rows = (len(stages) + columns - 1) // columns
    width, boxheight, left, top = 350, 145, 35, 25
    content = ""
    for i, label in enumerate(stages):
        row, col = divmod(i, columns)
        if row % 2:
            col = columns - 1 - col
        x, y = left + col * 390, top + row * 205
        content += (
            f'<rect x="{x}" y="{y}" width="{width}" height="{boxheight}" '
            'fill="#f4f4f4" stroke="#222" stroke-width="2"/>'
        )
        lines = textwrap.wrap(label, 24)
        for j, line in enumerate(lines):
            content += svg_text(x + width / 2, y + 75 - 17 * (len(lines) - 1) + j * 34, line)
        if connectors and i + 1 < len(stages):
            if (i + 1) % columns:
                start, end = (x + width, x + 385) if row % 2 == 0 else (x, x - 35)
                content += (
                    f'<path d="M{start} {y + boxheight / 2} H{end}" '
                    'fill="none" stroke="#222" stroke-width="2" marker-end="url(#arrow)"/>'
                )
            else:
                content += (
                    f'<path d="M{x + width / 2} {y + boxheight} V{y + 200}" '
                    'fill="none" stroke="#222" stroke-width="2" marker-end="url(#arrow)"/>'
                )
    height = rows * 205 + (70 if note else 0)
    if note:
        for i, line in enumerate(textwrap.wrap(note, 88)):
            content += svg_text(600, height - 45 + i * 31, line, 25)
    return shell(height, content)


def uml_source(key: str, stages: list[str], note: str) -> str:
    lines = [
        "@startuml",
        "skinparam defaultFontName Times New Roman",
        "skinparam defaultFontSize 20",
        "skinparam shadowing false",
        "skinparam backgroundColor white",
        "skinparam monochrome true",
        "skinparam roundcorner 0",
        "skinparam linetype ortho",
        "skinparam nodesep 35",
        "skinparam ranksep 35",
        "hide stereotype",
    ]
    if key == "hybrid_engine":
        lines += [
            'rectangle "Статические\\nсвидетельства" as S',
            'rectangle "Графовые\\nсвидетельства" as G',
            'rectangle "Семантические\\nоценки LLM" as L',
            'rectangle "Нормализация и применимость\\n'
            'Приоритет детерминированных ограничений" as F',
            'rectangle "Решение Hybrid и свидетельства\\n'
            'confidence и severity имеют разный смысл" as R',
            "S -[hidden]right-> G",
            "G -[hidden]right-> L",
            "S --> F",
            "G --> F",
            "L --> F",
            "F --> R",
            "legend bottom\nLLM не отменяет доказанное запрещённое ребро\nendlegend",
        ]
    elif key == "architecture":
        lines += [
            'component "Локальный CLI" as CLI',
            'component "HTTP API\\nhealth и system info" as API',
            'component "Приём и разбор\\nисходников" as P',
            'component "IAM и графы" as IAM',
            'component "Static / Graph / LLM\\nHybrid и свидетельства" as H',
            'component "Провайдер LLM" as LLM',
            'component "SQLAlchemy / Alembic\\nоснова хранения" as DB',
            "CLI --> P",
            "P -right-> IAM",
            "IAM -right-> H",
            "H --> LLM",
            "API -[hidden]-> P",
            "DB -[hidden]right-> LLM",
            "legend bottom\nПрикладное постоянное хранение анализов "
            "и сервисная очередь не завершены\nendlegend",
        ]
    else:
        for i, label in enumerate(stages):
            wrapped = "\\n".join(textwrap.wrap(label, 25))
            lines.append(f'rectangle "{wrapped}" as N{i}')
        for i in range(len(stages) - 1):
            direction = "right" if i < 2 else "down" if i == 2 else "left"
            arrow = f"-{direction}->" if key != "ablations" else f"-[hidden]{direction}->"
            lines.append(f"N{i} {arrow} N{i + 1}")
        if note:
            lines += ["legend bottom", "\n".join(textwrap.wrap(note, 80)), "endlegend"]
    return "\n".join(lines + ["@enduml", ""])


def hybrid_diagram() -> str:
    content = ""
    for x, label in zip(
        (35, 425, 815),
        ("Static: свидетельство", "Graph: свидетельство", "LLM: семантическая оценка"),
        strict=True,
    ):
        content += (
            f'<rect x="{x}" y="25" width="350" height="125" '
            'fill="#f4f4f4" stroke="#222" stroke-width="2"/>'
        )
        for index, line in enumerate(textwrap.wrap(label, 24)):
            content += svg_text(x + 175, 85 + index * 32, line)
        content += f'<path d="M{x + 175} 150 V190" fill="none" stroke="#222"/>'
    content += (
        '<path d="M210 190 H990 M600 190 V230" fill="none" stroke="#222" '
        'stroke-width="2" marker-end="url(#arrow)"/>'
    )
    for y, labels in (
        (230, ["Нормализация, применимость и приоритет", "детерминированных ограничений"]),
        (
            420,
            [
                "Решение Hybrid и прослеживаемое свидетельство",
                "confidence и severity имеют разный смысл",
            ],
        ),
    ):
        content += (
            f'<rect x="200" y="{y}" width="800" height="120" '
            'fill="#f4f4f4" stroke="#222" stroke-width="2"/>'
        )
        for index, line in enumerate(labels):
            content += svg_text(600, y + 50 + index * 34, line)
    content += (
        '<path d="M600 350 V420" fill="none" stroke="#222" stroke-width="2" '
        'marker-end="url(#arrow)"/>'
    )
    content += svg_text(600, 602, "LLM не отменяет доказанное детерминированное нарушение", 25)
    return shell(640, content)


def grouped_bars(labels: list[str], series: list[tuple[str, list[float]]]) -> str:
    x0, y0, plotw, ploth = 100, 425, 1060, 350
    content = ""
    for tick in range(0, 101, 20):
        y = y0 - ploth * tick / 100
        content += f'<path d="M{x0} {y} H1160" stroke="#bbb" stroke-width="1"/>'
        content += svg_text(82, y + 9, str(tick), 26, "end")
    content += svg_text(30, 45, "%", 27)
    groupw = plotw / len(labels)
    barw = min(65, (groupw - 35) / len(series))
    fills = ["#333", "#888", "#ccc", "#fff"]
    for j, (name, values) in enumerate(series):
        for i, value in enumerate(values):
            x = x0 + groupw * i + (groupw - len(series) * barw) / 2 + j * barw
            h = ploth * value
            content += (
                f'<rect x="{x}" y="{y0 - h}" width="{barw - 5}" height="{h}" '
                f'fill="{fills[j]}" stroke="#222"/>'
            )
            if len(series) < 3:
                content += svg_text(
                    x + (barw - 5) / 2, y0 - h - 10, f"{100 * value:.1f}".replace(".", ","), 25
                )
        legend_x = 100 + j * 570 if len(series) == 2 else 150 + j * 300
        content += (
            f'<rect x="{legend_x}" y="530" width="28" height="25" fill="{fills[j]}" stroke="#222"/>'
        )
        content += svg_text(legend_x + 40, 552, name, 26, "start")
    for i, label in enumerate(labels):
        for j, line in enumerate(label.split("\n")):
            content += svg_text(x0 + groupw * (i + 0.5), y0 + 38 + j * 29, line, 26)
    return shell(590, content)


def outcomes() -> str:
    entries = [
        ("Определённо положительные", 41, "#333"),
        ("PARTIAL", 137, "#999"),
        ("POTENTIAL", 12, "#ccc"),
        ("UNSUPPORTED", 10, "#eee"),
    ]
    content, x = "", 45.0
    for i, (name, count, fill) in enumerate(entries):
        width = 1110 * count / 200
        content += (
            f'<rect x="{x}" y="35" width="{width}" height="110" fill="{fill}" stroke="#111"/>'
        )
        content += svg_text(x + width / 2, 105, str(count), 29, color="white" if i == 0 else "#111")
        x += width
        content += (
            f'<rect x="55" y="{195 + i * 48}" width="27" height="27" fill="{fill}" stroke="#111"/>'
        )
        content += svg_text(105, 219 + i * 48, f"{name}: {count}/200", 27, "start")
    content += svg_text(600, 440, "Определённо отрицательные = 0; FAILED = 0", 28)
    return shell(480, content)


def create(node: Path, plantuml: Path | None = None) -> None:
    evidence = json.loads((ROOT / "docs/thesis/internal/architecture-evidence.json").read_text())
    methods = evidence["primary"]["methods"]
    diagrams = {
        "pipeline": (
            [
                "Исходный код и целевые правила",
                "AST и промежуточная модель IAM",
                "Статические и графовые свидетельства",
                "Контекст для языковой модели",
                "Гибридное правило решения",
                "Finding и проверяемое свидетельство",
            ],
            "Архитектурные решения и отдельные Security-результаты не смешиваются",
        ),
        "architecture": (
            [
                "FastAPI: health и metadata",
                "Прикладные сервисы анализа",
                "Доменные модели Pydantic",
                "Парсеры Java / TypeScript",
                "Статический и графовый анализ",
                "Провайдерный контракт LLM",
            ],
            "Экспериментальные workers отделены; прикладная ORM и постоянные jobs не реализованы",
        ),
        "static_pipeline": (
            [
                "Обнаружение допустимых файлов",
                "Tree-sitter и AST",
                "Извлечение символов",
                "IAM и зависимости",
                "Правила и целевая архитектура",
                "Finding со ссылкой на исходник",
            ],
            "Ошибка разбора и неподдерживаемая конструкция не означают соответствие",
        ),
        "iam_graph": (
            [
                "Файл и единица исходного кода",
                "Символ / модуль в IAM",
                "Ссылка на расположение",
                "Направленная зависимость",
                "Архитектурный граф",
                "Путь и свидетельство правила",
            ],
            "Граф связывает представление кода и правило; не заменяет семантику языка",
        ),
        "dsl_flow": (
            [
                "YAML-спецификация",
                "Валидация и нормализация",
                "Распознавание модулей",
                "Проверка разрешённых связей",
                "Запрещённое ребро / иное правило",
                "Детерминированное свидетельство",
            ],
            "Без целевой спецификации можно описать аномалию, "
            "но не произвольное нарушение соответствия",
        ),
        "graph_context": (
            [
                "Кандидат на нарушение",
                "Целевая сущность и правило",
                "Релевантный k-hop контекст",
                "Отобранный код и IAM",
                "Структурированный запрос",
                "Проверка ответа LLM",
            ],
            "Сокращение входа сопровождается умеренным снижением качества",
        ),
        "hybrid_engine": (
            [
                "Static: свидетельство",
                "Graph: свидетельство",
                "LLM: семантическая оценка",
                "Нормализация и калибровка",
                "Приоритет строгих ограничений",
                "Решение, confidence, severity",
            ],
            "LLM не отменяет детерминированное запрещённое ребро; confidence не равен severity",
        ),
        "finding_lifecycle": (
            [
                "Обнаруженная сущность",
                "Привязка к исходному коду",
                "Свидетельства компонентов",
                "Контракт правила",
                "Нормализация Finding",
                "Сериализация исследовательского результата",
            ],
            "Это реализованный исследовательский поток, "
            "а не утверждение о готовом UI или системе jobs",
        ),
        "experiment_design": (
            [
                "Протокол и разбиение проектов",
                "DEV: настройка и выбор",
                "Фиксация H2 при 0,75",
                "Слепое получение LLM-ответов",
                "Фиксация предсказаний",
                "Оценка FINAL: 300 случаев",
            ],
            "Все семь абляций учитываются; технически отсутствующие ответы не превращаются в успех",
        ),
        "ablations": (
            [
                "A1 Static",
                "A2 Graph",
                "A3 LLM",
                "A4 Static + Graph",
                "A5 Static + LLM",
                "A6 Graph + LLM",
                "A7 Static + Graph + LLM",
            ],
            "Сравнение зафиксировано на общей контролируемой выборке; не причинное доказательство",
        ),
        "security_flow": (
            [
                "Источник и известный sink",
                "Локальный поток и алиасы",
                "Ограниченные сводки функций",
                "Правило-специфичный proof",
                "Инвалидация при новой неопределённости",
                "Finding либо неполное решение",
            ],
            "Обычное отсутствие finding не превращается в окончательный отрицательный ответ",
        ),
        "security_blind": (
            [
                "Фиксация V3 и его исходников",
                "FINAL: только разрешённые исходники",
                "Seatbelt и прикладной fence",
                "200 предсказаний без truth",
                "Реестр закрыт и зафиксирован",
                "После этого: truth join и оценка",
            ],
            "Выполнен один авторитетный слепой запуск; настройки после FINAL отсутствуют",
        ),
        "security_review": (
            [
                "Проспективный benchmark 300",
                "Независимые рецензенты A и B",
                "290 совпадений, 10 разногласий",
                "10 решений третьего человека",
                "Фиксация четырёх состояний truth",
                "DEV 100 / FINAL 200",
            ],
            "Intent конструирования не является truth; "
            "κ описывает согласие, а не точность детектора",
        ),
        "custody": (
            [
                "Публичный протокол и commit",
                "Приватные case-данные",
                "Источник и ограниченный worker",
                "Фиксация предсказаний",
                "Разрешённое соединение с truth",
                "Публичные агрегаты и SHA-256",
            ],
            "Отпечаток связывает артефакты, но не доказывает истинность и авторство",
        ),
    }
    assets: dict[str, Any] = {}
    OUT.mkdir(parents=True, exist_ok=True)
    for key, (stages, note) in diagrams.items():
        content = (
            hybrid_diagram()
            if key == "hybrid_engine"
            else diagram(stages, note, connectors=key != "ablations")
        )
        if plantuml:
            source = OUT / "plantuml" / f"{key}.puml"
            source.parent.mkdir(exist_ok=True)
            source.write_text(uml_source(key, stages, note), encoding="utf-8")
            result = subprocess.run(
                [str(plantuml), "-tsvg", "-pipe", "-charset", "UTF-8"],
                input=source.read_bytes(),
                capture_output=True,
                check=True,
            )
            content = result.stdout.decode("utf-8")
        (OUT / f"{key}.svg").write_text(content, encoding="utf-8")
        assets[key] = dict(svg=f"{key}.svg", png=f"{key}.png", width_cm=16.5, type="diagram")
        if plantuml:
            assets[key]["plantuml"] = f"plantuml/{key}.puml"
    plots = {
        "architecture_results": grouped_bars(
            ["Static", "Graph", "LLM", "Hybrid A7"],
            [
                (label, [methods[k][metric] for k in ("A1", "A2", "A3", "A7")])
                for label, metric in (
                    ("Точность", "Precision"),
                    ("Полнота", "Recall"),
                    ("F1", "F1"),
                )
            ],
        ),
        "context_tradeoff": grouped_bars(
            ["Входной контекст", "Оценочная стоимость"],
            [("Сокращение", [0.527000496, 0.369695411])],
        ),
        "security_recovery": grouped_bars(
            ["V2 DEV", "V3 DEV", "V3 FINAL"],
            [
                ("Эффективное обнаружение", [7 / 37, 21 / 37, 38 / 85]),
                ("Покрытие бинарных случаев", [7 / 89, 21 / 89, 41 / 191]),
            ],
        ),
        "security_outcomes": outcomes(),
    }
    for key, content in plots.items():
        (OUT / f"{key}.svg").write_text(content, encoding="utf-8")
        assets[key] = dict(svg=f"{key}.svg", png=f"{key}.png", width_cm=16.5, type="chart")
    program = (
        "const sharp=require('sharp');sharp(process.argv[1],{density:300})"
        ".resize({width:2400}).flatten({background:'#ffffff'}).png().toFile(process.argv[2])"
        ".catch(e=>{console.error(e.message);process.exit(1)});"
    )
    packages = node.parent.parent / "node_modules"
    environment = dict(PATH="/usr/bin:/bin:/usr/sbin:/sbin", NODE_PATH=str(packages))
    for entry in assets.values():
        subprocess.run(
            [str(node), "-e", program, str(OUT / entry["svg"]), str(OUT / entry["png"])],
            env=environment,
            check=True,
            capture_output=True,
        )
    (OUT / "figures.json").write_text(
        json.dumps(assets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Created {len(assets)} SVG and PNG research figures")


def main() -> None:
    parser = argparse.ArgumentParser()
    fallback = Path(sys.executable).parent.parent.parent / "node/bin/node"
    parser.add_argument(
        "--node", type=Path, default=Path(os.environ.get("CODEX_VKR_NODE", str(fallback)))
    )
    parser.add_argument("--plantuml", type=Path, help="Local PlantUML executable for diagrams")
    args = parser.parse_args()
    create(args.node, args.plantuml)


if __name__ == "__main__":
    main()
