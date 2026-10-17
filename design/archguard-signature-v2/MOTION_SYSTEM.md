# Motion system

Micro 120ms, contextual 220ms, navigation 300ms, spatial camera 420ms. Easing cubic-bezier(.2,.75,.2,1). Нет задержек обработки ради анимации.

Graph pulse использует SVG path.getTotalLength/getPointAtLength: t растёт от source к target. Не больше четырёх активных paths, один selection/replay запускает конечное окно до 4 секунд. Подпись объясняет static relation direction. Никаких random particles или claims о runtime calls.

Play/pause сохраняет preference; reduced-motion отключает pulses и spatial tween; visibilitychange прекращает requestAnimationFrame; unmount очищает listeners/frames. Pan/zoom делаются одним transform, без пересоздания nodes. Для плотной модели сначала domain aggregates; node labels раскрываются внутри области.

Demo analysis progress — отдельная конечная state machine, явно synthetic; cancel чистит timers. UI transitions не меняют semantics successful/partial/failed. Скриншоты не доказывают качество движения: дополнительно сохраняется browser-recorded WebM showcase и измеренные frame/long-task observations.
