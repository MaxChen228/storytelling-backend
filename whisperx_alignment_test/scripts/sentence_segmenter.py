#!/usr/bin/env python3
"""
Adaptive sentence segmentation utilities for WhisperX word-level alignments.

This module rebuilds sentence-level segments from word timestamps by searching
for a time interval that yields the desired average character count per
sentence, while respecting upper/lower bounds on duration and length.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, pstdev
from typing import Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class WordSpan:
    """Represents a single word with timing information."""

    text: str
    start: float
    end: float


@dataclass
class SentenceSegment:
    """Sentence-level segment reconstructed from word spans."""

    id: int
    start: float
    end: float
    text: str
    char_count: int
    word_count: int
    words: List[WordSpan] = field(repr=False)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass(frozen=True)
class IntervalSearchConfig:
    """Configuration controlling interval search and constraints."""

    model: str = "adaptive_interval"
    target_avg_chars_min: float = 18.0
    target_avg_chars_max: float = 22.0
    max_std_chars: float = 8.0
    min_chars: int = 12
    max_chars: int = 48
    min_duration: float = 1.3
    max_duration: float = 8.0
    min_interval: float = 0.25
    max_interval: float = 1.2
    max_iterations: int = 14
    tolerance: float = 0.02
    fallback_interval: float = 0.45
    anticipation: float = 0.0
    max_silence_gap: float = 1.0


@dataclass(frozen=True)
class SegmentationStats:
    """Aggregate statistics for a segmentation run."""

    interval: float
    avg_chars: float
    std_chars: float
    min_chars: int
    max_chars: int
    segment_count: int


class _IntervalSearchState:
    """Helper to keep track of the best interval so far."""

    def __init__(self):
        self.best_segments: List[SentenceSegment] = []
        self.best_stats: Optional[SegmentationStats] = None

    def consider(
        self,
        segments: Sequence[SentenceSegment],
        stats: SegmentationStats,
        cfg: IntervalSearchConfig,
    ) -> None:
        target_hit = (
            cfg.target_avg_chars_min
            <= stats.avg_chars
            <= cfg.target_avg_chars_max
        ) and stats.std_chars <= cfg.max_std_chars

        if not self.best_stats or target_hit:
            self.best_segments = list(segments)
            self.best_stats = stats
            return

        assert self.best_stats
        current_err = _avg_error(stats, cfg)
        best_err = _avg_error(self.best_stats, cfg)

        if current_err < best_err:
            self.best_segments = list(segments)
            self.best_stats = stats
        elif current_err == best_err and stats.std_chars < self.best_stats.std_chars:
            self.best_segments = list(segments)
            self.best_stats = stats


def segment_words_adaptive(
    words: Sequence[WordSpan],
    cfg: IntervalSearchConfig,
) -> Tuple[List[SentenceSegment], SegmentationStats]:
    """
    Entry point: search for a suitable interval and return refined segments.
    """
    if not words:
        empty_stats = SegmentationStats(
            interval=cfg.fallback_interval,
            avg_chars=0.0,
            std_chars=0.0,
            min_chars=0,
            max_chars=0,
            segment_count=0,
        )
        return [], empty_stats

    state = _IntervalSearchState()
    low, high = cfg.min_interval, cfg.max_interval
    last_interval = cfg.fallback_interval

    for _ in range(cfg.max_iterations):
        interval = (low + high) / 2.0
        segments = _simulate_segments(words, interval, cfg)
        stats = _evaluate_segments(segments, interval)
        state.consider(segments, stats, cfg)

        if cfg.target_avg_chars_min <= stats.avg_chars <= cfg.target_avg_chars_max:
            if stats.std_chars <= cfg.max_std_chars or abs(high - low) <= cfg.tolerance:
                last_interval = interval
                break

        if stats.avg_chars < cfg.target_avg_chars_min:
            low = interval
        elif stats.avg_chars > cfg.target_avg_chars_max:
            high = interval
        else:
            last_interval = interval
            break

        last_interval = interval
        if abs(high - low) <= cfg.tolerance:
            break

    segments = state.best_segments or _simulate_segments(words, last_interval, cfg)
    stats = state.best_stats or _evaluate_segments(segments, last_interval)

    refined = _refine_outliers(segments, cfg)
    stats = _evaluate_segments(refined, stats.interval)
    _assign_ids(refined)
    return refined, stats


def _avg_error(stats: SegmentationStats, cfg: IntervalSearchConfig) -> float:
    if cfg.target_avg_chars_min <= stats.avg_chars <= cfg.target_avg_chars_max:
        return 0.0
    if stats.avg_chars < cfg.target_avg_chars_min:
        return cfg.target_avg_chars_min - stats.avg_chars
    return stats.avg_chars - cfg.target_avg_chars_max


def _simulate_segments(
    words: Sequence[WordSpan],
    interval: float,
    cfg: IntervalSearchConfig,
) -> List[SentenceSegment]:
    segments: List[SentenceSegment] = []
    bucket: List[WordSpan] = []

    for word in words:
        if not word.text:
            continue

        if bucket:
            gap = max(0.0, word.start - bucket[-1].end)
            if gap >= cfg.max_silence_gap:
                segments.append(_build_segment(bucket))
                bucket = []

        bucket.append(word)
        duration = bucket[-1].end - bucket[0].start
        char_count = _char_count(bucket)
        should_close = False

        if duration >= cfg.max_duration or char_count >= cfg.max_chars:
            should_close = True
        elif duration >= interval and char_count >= cfg.min_chars:
            should_close = True

        if should_close:
            segments.append(_build_segment(bucket))
            bucket = []

    if bucket:
        segments.append(_build_segment(bucket))

    return segments


def _refine_outliers(
    segments: Sequence[SentenceSegment],
    cfg: IntervalSearchConfig,
) -> List[SentenceSegment]:
    refined = list(segments)
    changed = True
    iterations = 0

    while changed and iterations < cfg.max_iterations:
        iterations += 1
        changed = False

        # Split overly long segments
        new_segments: List[SentenceSegment] = []
        for seg in refined:
            if seg.char_count > cfg.max_chars and seg.word_count > 1:
                first, second = _split_segment(seg)
                new_segments.extend([first, second])
                changed = True
            else:
                new_segments.append(seg)
        refined = new_segments

        # Merge very short segments with neighbours
        i = 0
        while i < len(refined):
            seg = refined[i]
            if seg.char_count >= cfg.min_chars or len(refined) == 1:
                i += 1
                continue

            if i + 1 < len(refined):
                merged = _merge_segments(seg, refined[i + 1])
                refined[i] = merged
                refined.pop(i + 1)
                changed = True
                continue
            elif i > 0:
                merged = _merge_segments(refined[i - 1], seg)
                refined[i - 1] = merged
                refined.pop(i)
                changed = True
                continue
            i += 1

    return refined


def _split_segment(segment: SentenceSegment) -> Tuple[SentenceSegment, SentenceSegment]:
    half_chars = segment.char_count / 2.0
    accumulator = 0
    split_index = 0

    for idx, word in enumerate(segment.words, start=1):
        accumulator += _char_len(word.text)
        if accumulator >= half_chars:
            split_index = idx
            break

    split_index = max(1, min(split_index, len(segment.words) - 1))
    left_words = segment.words[:split_index]
    right_words = segment.words[split_index:]
    return _build_segment(left_words), _build_segment(right_words)


def _merge_segments(a: SentenceSegment, b: SentenceSegment) -> SentenceSegment:
    words = a.words + b.words
    return _build_segment(words)


def _assign_ids(segments: Sequence[SentenceSegment]) -> None:
    for idx, segment in enumerate(segments, start=1):
        segment.id = idx


def _evaluate_segments(
    segments: Sequence[SentenceSegment],
    interval: float,
) -> SegmentationStats:
    if not segments:
        return SegmentationStats(
            interval=interval,
            avg_chars=0.0,
            std_chars=0.0,
            min_chars=0,
            max_chars=0,
            segment_count=0,
        )

    char_counts = [segment.char_count for segment in segments]
    avg_chars = mean(char_counts)
    std_chars = pstdev(char_counts) if len(char_counts) > 1 else 0.0

    return SegmentationStats(
        interval=interval,
        avg_chars=avg_chars,
        std_chars=std_chars,
        min_chars=min(char_counts),
        max_chars=max(char_counts),
        segment_count=len(segments),
    )


def _build_segment(words: Sequence[WordSpan]) -> SentenceSegment:
    if not words:
        raise ValueError("Cannot build a segment without words")
    texts = [w.text for w in words]
    text = " ".join(texts).strip()
    char_count = sum(_char_len(w.text) for w in words)
    return SentenceSegment(
        id=0,
        start=words[0].start,
        end=words[-1].end,
        text=text,
        char_count=char_count,
        word_count=len(words),
        words=list(words),
    )


def _char_len(text: str) -> int:
    return len(text.replace(" ", ""))


def _char_count(words: Iterable[WordSpan]) -> int:
    return sum(_char_len(w.text) for w in words)


def flatten_alignment_words(result: dict) -> List[WordSpan]:
    """Extracts word spans from a WhisperX alignment result."""
    words: List[WordSpan] = []
    for segment in result.get("segments", []):
        for word in segment.get("words", []):
            text = (word.get("word") or "").strip()
            if not text:
                continue
            start = float(word.get("start", 0.0) or 0.0)
            end = float(word.get("end", start) or start)
            if end < start:
                end = start
            words.append(WordSpan(text=text, start=start, end=end))
    words.sort(key=lambda w: (w.start, w.end))
    return words

