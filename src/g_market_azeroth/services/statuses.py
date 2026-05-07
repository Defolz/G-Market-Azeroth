from __future__ import annotations

from g_market_azeroth.catalog import request_status_label


_STATUS_ICONS = {
    "new": "🟡",
    "in_progress": "🟠",
    "completed": "🟢",
    "cancelled": "🔴",
}
_TIMELINE_STEPS = (
    ("new", "Создана"),
    ("in_progress", "В обработке"),
    ("completed", "Выполнена"),
)


def format_request_status(status: str, *, compact: bool = False) -> str:
    label = request_status_label(status)
    icon = _STATUS_ICONS.get(status, "📦")
    if compact:
        return f"{icon} {label}"

    if status == "cancelled":
        return f"📦 Статус заявки: {icon} {label}"

    return "\n".join(
        [
            f"📦 Статус заявки: {icon} {label}",
            "",
            *_timeline_lines(status),
        ]
    )


def _timeline_lines(status: str) -> list[str]:
    current_index = _status_index(status)
    lines: list[str] = []
    for index, (step_status, step_label) in enumerate(_TIMELINE_STEPS):
        if index < current_index:
            marker = "✅"
        elif step_status == status:
            marker = _STATUS_ICONS.get(status, "📦")
        else:
            marker = "⚪"
        lines.append(f"{marker} {step_label}")

    return lines


def _status_index(status: str) -> int:
    for index, (step_status, _) in enumerate(_TIMELINE_STEPS):
        if step_status == status:
            return index

    return 0
