"""Shared CLI output utilities for storytelling commands."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence, Tuple

BOX_WIDTH = 64


def _box_line(left: str, fill: str, right: str) -> str:
    return f"{left}{fill * BOX_WIDTH}{right}"


def print_header(title: str) -> None:
    print(_box_line("╔", "═", "╗"))
    content = f" {title.strip()} "
    padded = content.ljust(BOX_WIDTH)
    print(f"║{padded}║")
    print(_box_line("╚", "═", "╝"))


def _table_border(left: str, sep: str, right: str, col_widths: Sequence[int]) -> str:
    segments = []
    for width in col_widths:
        segments.append("═" * (width + 2))
    inner = sep.join(segments)
    return f"{left}{inner}{right}"


def _normalize_rows(rows: Iterable[Tuple[str, str]]) -> Tuple[Tuple[str, str], ...]:
    normalized = []
    for key, value in rows:
        k = key.strip()
        v = value if value is not None else "—"
        normalized.append((k, str(v).strip() or "—"))
    return tuple(normalized)


def print_config_table(rows: Iterable[Tuple[str, str]]) -> None:
    data = _normalize_rows(rows)
    if not data:
        return

    headers = ("設定項目", "值")
    label_width = max(len(headers[0]), max(len(k) for k, _ in data))
    value_width = max(len(headers[1]), max(len(v) for _, v in data))
    col_widths = (label_width, value_width)

    top = _table_border("┌", "┬", "┐", col_widths)
    mid = _table_border("├", "┼", "┤", col_widths)
    bottom = _table_border("└", "┴", "┘", col_widths)

    print(top)
    print(_format_row(headers, col_widths))
    print(mid)
    for row in data:
        print(_format_row(row, col_widths))
    print(bottom)


def _format_row(row: Tuple[str, str], col_widths: Sequence[int]) -> str:
    cells = []
    for (value, width) in zip(row, col_widths):
        cells.append(f" {value.ljust(width)} ")
    return f"│{'│'.join(cells)}│"


def print_section(title: str) -> None:
    print(f"\n{title}")
    print("─" * len(title))


def print_footer(message: str, details: Iterable[str] | None = None) -> None:
    print("\n" + _box_line("╔", "═", "╗"))
    content = f" {message.strip()} ".ljust(BOX_WIDTH)
    print(f"║{content}║")
    print(_box_line("╚", "═", "╝"))
    if details:
        for line in details:
            print(f"  • {line}")


def basic_config_rows(basic: Mapping[str, Any]) -> Tuple[Tuple[str, str], ...]:
    keys = (
        "english_level",
        "episode_length",
        "narrator_voice",
        "speaking_pace",
    )
    return tuple((key, str(basic.get(key, "—"))) for key in keys)
