#!/usr/bin/env python3
"""Rewrite TextGrid word labels using the reference transcript and export word-level SRT."""

from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Sequence, Tuple

from praatio import textgrid

TOKEN_RE = re.compile(r"[A-Za-z']+")


def tokenize(text: str) -> List[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]


@dataclass
class IntervalToken:
    token: str
    start: float
    end: float


@dataclass
class ScriptToken:
    original: str
    normalized: str
    is_word: bool
    interval_idx: int | None = None


def extract_interval_tokens(tg_path: Path) -> Tuple[List[IntervalToken], List[Tuple[float, float]]]:
    grid = textgrid.openTextgrid(str(tg_path), includeEmptyIntervals=True)
    words_tier = grid.getTier("words")

    tokens: List[IntervalToken] = []
    spans: List[Tuple[float, float]] = []

    for interval in words_tier.entries:
        label = interval.label.strip()
        if not label or (label.startswith("[") and label.endswith("]")):
            continue
        pieces = tokenize(label)
        if not pieces:
            continue
        span = (interval.start, interval.end)
        spans.append(span)
        for piece in pieces:
            tokens.append(IntervalToken(token=piece, start=interval.start, end=interval.end))

    return tokens, spans


def transcript_tokens(transcript_path: Path) -> List[ScriptToken]:
    tokens: List[ScriptToken] = []
    for line in transcript_path.read_text(encoding="utf-8").splitlines():
        for raw in line.split():
            normalized = "".join(ch.lower() for ch in raw if ch.isalpha() or ch == "'")
            is_word = bool(normalized)
            tokens.append(ScriptToken(original=raw, normalized=normalized, is_word=is_word))
    return tokens


def align_sequences(ref: Sequence[str], hyp: Sequence[str]) -> List[Tuple[int | None, int | None]]:
    n, m = len(ref), len(hyp)
    gap_cost = 1

    dp = [[0] * (m + 1) for _ in range(n + 1)]
    back: List[List[Tuple[int, int]]] = [[(0, 0)] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp[i][0] = i * gap_cost
        back[i][0] = (i - 1, 0)
    for j in range(1, m + 1):
        dp[0][j] = j * gap_cost
        back[0][j] = (0, j - 1)

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sub_cost = dp[i - 1][j - 1] + (0 if ref[i - 1] == hyp[j - 1] else 1)
            del_cost = dp[i - 1][j] + gap_cost
            ins_cost = dp[i][j - 1] + gap_cost

            best = sub_cost
            move = (i - 1, j - 1)

            if del_cost < best:
                best = del_cost
                move = (i - 1, j)
            if ins_cost < best:
                best = ins_cost
                move = (i, j - 1)

            dp[i][j] = best
            back[i][j] = move

    alignment: List[Tuple[int | None, int | None]] = []
    i, j = n, m
    while i > 0 or j > 0:
        prev_i, prev_j = back[i][j]
        if prev_i == i - 1 and prev_j == j - 1:
            alignment.append((i - 1, j - 1))
        elif prev_i == i - 1 and prev_j == j:
            alignment.append((i - 1, None))
        else:
            alignment.append((None, j - 1))
        i, j = prev_i, prev_j

    alignment.reverse()
    return alignment


def format_timestamp(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - math.floor(seconds)) * 1000))
    if millis == 1000:
        millis = 0
        secs += 1
    if secs == 60:
        secs = 0
        minutes += 1
    if minutes == 60:
        minutes = 0
        hours += 1
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def generate_srt(script_tokens: Sequence[ScriptToken], interval_tokens: Sequence[IntervalToken]) -> List[str]:
    lines: List[str] = []
    for token in script_tokens:
        if token.interval_idx is None:
            continue
        interval = interval_tokens[token.interval_idx]
        lines.append(
            "\n".join(
                [
                    str(len(lines) + 1),
                    f"{format_timestamp(interval.start)} --> {format_timestamp(interval.end)}",
                    token.original,
                    "",
                ]
            )
        )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Align transcript tokens to TextGrid timings and export word-level SRT.")
    parser.add_argument("textgrid", type=Path, help="Path to MFA TextGrid (word tier required).")
    parser.add_argument("transcript", type=Path, help="Clean transcript text file.")
    parser.add_argument("output", type=Path, help="Destination SRT path.")
    args = parser.parse_args()

    interval_tokens, _ = extract_interval_tokens(args.textgrid)
    if not interval_tokens:
        raise SystemExit("❌ TextGrid 中沒有可用的單詞間隔。")

    script_tokens = transcript_tokens(args.transcript)
    if not script_tokens:
        raise SystemExit("❌ 腳本沒有任何單詞。")

    word_indices = [idx for idx, token in enumerate(script_tokens) if token.is_word]
    if not word_indices:
        raise SystemExit("❌ 腳本沒有任何可比對的單詞。")

    ref_sequence = [script_tokens[idx].normalized for idx in word_indices]
    hyp_sequence = [it.token for it in interval_tokens]

    alignment = align_sequences(ref_sequence, hyp_sequence)

    matched = 0
    missing = 0
    for ref_idx, hyp_idx in alignment:
        if ref_idx is None:
            continue
        script_idx = word_indices[ref_idx]
        if hyp_idx is None:
            missing += 1
        else:
            script_tokens[script_idx].interval_idx = hyp_idx
            matched += 1

    last_interval: int | None = None
    for token in script_tokens:
        if token.interval_idx is not None:
            last_interval = token.interval_idx
        elif not token.is_word and last_interval is not None:
            token.interval_idx = last_interval

    srt_lines = generate_srt(script_tokens, interval_tokens)

    args.output.write_text("\n".join(srt_lines).strip() + "\n", encoding="utf-8")
    print(f"✅ 已輸出 SRT: {args.output}")
    print(f"   對齊成功 {matched} 詞，腳本遺失 {missing} 詞。")


if __name__ == "__main__":
    main()
