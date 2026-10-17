# Graphite Studio · visual tokens

Источник: `tokens.css`; композиция и responsive-варианты: `studio.css`. Системные шрифты, без удалённых font requests.

| Роль | Cinematic | Precision |
|---|---|---|
| Canvas | `#202124` | `#ece9e2` |
| Navigation | `#191a1c` | `#191a1c` |
| Surface | `#292a2d` | `#f7f4ed` |
| Text | `#f5f1e9` | `#292a2d` |
| Secondary | `#b2b0ac` | `#666460` |
| Accent | `#e4b77c` | `#975b26` |
| Coral / signal | `#ec947e` | `#a64532` |
| Cool / uncertainty | `#a9c6dc` | `#38617b` |
| Evidence paper | `#f0ece3` | `#faf7f0` |
| Evidence ink | `#292a2d` | `#292a2d` |
| Radius | 8–12 px | 4 px |

Иерархия: hero 38–66 px; workspace title 30–38; dossier 23–29; body 14–15; evidence 13; controls 12–14; metadata 10–12. Micro labels используются только для индексов/edition, не для основного технического содержания. SVG label 16/17 units; на мобильном масштаб обеспечивает основным видимым подписям ≥12 screen px.

Сетка: навигация 232 px на 1440; main padding 40; секционные интервалы 24/32/40; панели 24–30. Breakpoints: 1700, 1200, 1000, 760. При 760 — нижняя навигация, stacked panels, читаемый module list. Системные safe-area insets учитываются в нижней навигации.

Amber указывает выбор и направление. Coral обозначает требующее внимания evidence. Холодный оттенок помогает отличать неопределённость. Цвет не заменяет текстовый статус, scope или provenance. Не использовать свечение как оценку риска, анимацию как runtime или нулевое число находок как гарантию безопасности.

Motion tokens: 180 ms controls, 420 ms camera, 450–480 ms dossier, cubic-bezier(.22,1,.36,1), finite four-second trace. Нет вечных decorative loops. Reduced motion отключает CSS/WAAPI/RAF movement.
