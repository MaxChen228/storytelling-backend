"""Console I/O helpers for the storytelling CLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


ColorizeFn = Callable[[str, str, bool], str]


@dataclass
class ConsoleIO:
    """Encapsulates console input/output behaviour."""

    use_color: bool
    colorize_fn: ColorizeFn

    def _apply_color(self, text: str, color: Optional[str]) -> str:
        if color:
            return self.colorize_fn(text, color, self.use_color)
        return text

    def print(self, text: str = "", *, color: Optional[str] = None) -> None:
        """Print a single line to stdout."""
        print(self._apply_color(text, color))

    def prompt(self, prompt_text: str, *, color: Optional[str] = None) -> str:
        """Prompt for input, preserving EOFError semantics."""
        return input(self._apply_color(prompt_text, color))

    def confirm(self, prompt_text: str, *, color: Optional[str] = None) -> bool:
        """Ask for Y/N style confirmation."""
        response = self.prompt(prompt_text, color=color).strip().lower()
        return response in {"y", "yes"}
