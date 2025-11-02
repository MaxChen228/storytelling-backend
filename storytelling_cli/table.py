"""Utilities for rendering chapter status tables."""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Tuple

from storytelling_cli.status import ChapterStatus


ColorizeFn = Callable[[str, str, bool], str]
FormatGapFn = Callable[[Optional[float]], str]
FormatDurationFn = Callable[[float], str]


def build_chapter_table(
    statuses: Sequence[ChapterStatus],
    *,
    use_color: bool,
    gap_threshold: float,
    colorize: ColorizeFn,
    format_gap: FormatGapFn,
    format_duration: FormatDurationFn,
) -> str:
    """Return a formatted table summarizing chapter status."""

    header = ("Idx", "Chapter", "Source", "Summary", "Script", "Audio", "Audio(s)", "Subtitle", "ΔAudio-Sub")
    widths = [len(h) for h in header]
    rows: List[Tuple[str, ...]] = []

    for idx, status in enumerate(statuses):
        gap_label = format_gap(status.audio_subtitle_gap)
        audio_label = format_duration(status.audio_duration) if status.audio_duration is not None else "—"
        row = (
            str(idx),
            status.slug,
            "✓" if status.has_source else "✗",
            "✓" if status.has_summary else "✗",
            "✓" if status.has_script else "✗",
            "✓" if status.has_audio else "✗",
            audio_label,
            "✓" if status.has_subtitle else "✗",
            gap_label,
        )
        rows.append(row)
        widths = [max(widths[i], len(row[i])) for i in range(len(header))]

    def draw_border(left: str, mid: str, right: str) -> str:
        parts = ["═" * (w + 2) for w in widths]
        return f"{left}{mid.join(parts)}{right}"

    def style_cell(column: int, value: str, gap_value: Optional[float]) -> str:
        text = value.ljust(widths[column])
        if not use_color or column < 2:
            return text
        if value == "✓":
            return colorize(text, "green", True)
        if value == "✗":
            return colorize(text, "red", True)
        if header[column] == "ΔAudio-Sub" and gap_value is not None and gap_value > gap_threshold:
            return colorize(text, "red", True)
        return text

    def draw_row(values: Sequence[str]) -> str:
        gap_value: Optional[float] = None
        if len(values) >= len(header) and values[0].isdigit():
            idx_value = int(values[0])
            if 0 <= idx_value < len(statuses):
                gap_value = statuses[idx_value].audio_subtitle_gap
        cells = []
        for col, value in enumerate(values):
            cells.append(f" {style_cell(col, value, gap_value)} ")
        return f"│{'│'.join(cells)}│"

    lines = [
        draw_border("┌", "┬", "┐"),
        draw_row(header),
        draw_border("├", "┼", "┤"),
    ]
    for row in rows:
        lines.append(draw_row(row))
    lines.append(draw_border("└", "┴", "┘"))
    return "\n".join(lines)

