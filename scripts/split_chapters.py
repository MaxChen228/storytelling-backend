#!/usr/bin/env python3
"""
Utility to normalize chapter lengths by splitting long files into
segments that resemble the Foundation book chapter sizes.

Default thresholds are derived from the Foundation dataset, but you can
override them via CLI flags.

Optionally, you can emit a flat sequence of files named `chapter0.txt`,
`chapter1.txt`, ... regardless of original chapter boundaries.
"""

from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


def count_words(text: str) -> int:
    return len(text.split())


def read_chapters(directory: Path) -> List[Path]:
    return sorted(directory.glob("chapter*.txt"))


@dataclass(frozen=True)
class DatasetStats:
    count: int
    total_words: int
    min_words: int
    max_words: int
    mean_words: float
    median_words: float
    p10_words: float
    p90_words: float


def dataset_stats(chapters: Sequence[Path]) -> DatasetStats:
    import statistics

    try:
        import numpy as np  # type: ignore
    except ImportError:  # pragma: no cover - fallback when numpy missing
        np = None

    lengths = [count_words(path.read_text(encoding="utf-8")) for path in chapters]
    if not lengths:
        raise ValueError("No chapter files found")
    lengths.sort()
    total = sum(lengths)

    def percentile(sorted_lengths: Sequence[int], fraction: float) -> float:
        if np is not None:
            return float(np.quantile(sorted_lengths, fraction))
        if not sorted_lengths:
            raise ValueError("Cannot compute percentile of empty data")
        if len(sorted_lengths) == 1:
            return float(sorted_lengths[0])
        idx = (len(sorted_lengths) - 1) * fraction
        lower = math.floor(idx)
        upper = math.ceil(idx)
        if lower == upper:
            return float(sorted_lengths[int(idx)])
        lower_val = sorted_lengths[lower]
        upper_val = sorted_lengths[upper]
        return float(lower_val + (upper_val - lower_val) * (idx - lower))

    return DatasetStats(
        count=len(lengths),
        total_words=total,
        min_words=lengths[0],
        max_words=lengths[-1],
        mean_words=statistics.mean(lengths),
        median_words=statistics.median(lengths),
        p10_words=percentile(lengths, 0.10),
        p90_words=percentile(lengths, 0.90),
    )


SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


def split_long_paragraph(
    paragraph: str,
    target_words: int,
    min_words: int,
    max_words: int,
) -> List[str]:
    """Split an oversized paragraph into smaller chunks."""
    cleaned = re.sub(r"\s+", " ", paragraph.strip())
    if not cleaned:
        return [paragraph]

    sentences = [s.strip() for s in SENTENCE_END_RE.split(cleaned) if s.strip()]
    if not sentences:
        return [paragraph]

    chunks: List[str] = []
    current: List[str] = []
    current_words = 0

    for sentence in sentences:
        words = count_words(sentence)
        if current and current_words + words > max_words:
            if current_words < min_words:
                current.append(sentence)
                current_words += words
            else:
                chunks.append(" ".join(current).strip())
                current = [sentence]
                current_words = words
        else:
            current.append(sentence)
            current_words += words

        if current_words >= target_words:
            chunks.append(" ".join(current).strip())
            current = []
            current_words = 0

    if current:
        chunks.append(" ".join(current).strip())

    return [chunk for chunk in chunks if chunk]


def expand_paragraphs(
    paragraphs: Iterable[str], target_words: int, min_words: int, max_words: int
) -> List[str]:
    expanded: List[str] = []
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        words = count_words(paragraph)
        if words > max_words:
            expanded.extend(
                split_long_paragraph(paragraph, target_words, min_words, max_words)
            )
        else:
            expanded.append(paragraph)
    return expanded


def merge_small_chunks(
    chunks: List[List[str]],
    chunk_sizes: List[int],
    min_words: int,
    max_words: int,
) -> None:
    idx = 0
    while idx < len(chunks):
        if chunk_sizes[idx] >= min_words or len(chunks) == 1:
            idx += 1
            continue

        if idx == 0:
            merged_size = chunk_sizes[0] + chunk_sizes[1]
            if merged_size <= max_words:
                chunk_sizes[1] = merged_size
                chunks[1] = chunks[0] + chunks[1]
                del chunks[0]
                del chunk_sizes[0]
            else:
                idx += 1
        else:
            merged_prev = chunk_sizes[idx - 1] + chunk_sizes[idx]
            merged_next = (
                chunk_sizes[idx] + chunk_sizes[idx + 1]
                if idx + 1 < len(chunks)
                else None
            )

            if merged_prev <= max_words:
                chunk_sizes[idx - 1] = merged_prev
                chunks[idx - 1].extend(chunks[idx])
                del chunks[idx]
                del chunk_sizes[idx]
                idx -= 1
            elif merged_next is not None and merged_next <= max_words:
                chunk_sizes[idx + 1] = merged_next
                chunks[idx + 1] = chunks[idx] + chunks[idx + 1]
                del chunks[idx]
                del chunk_sizes[idx]
            else:
                idx += 1

    micro_threshold = max(150, min_words // 3)
    idx = 0
    while idx < len(chunks):
        if chunk_sizes[idx] >= micro_threshold or len(chunks) == 1:
            idx += 1
            continue

        if idx == 0:
            chunk_sizes[1] += chunk_sizes[0]
            chunks[1] = chunks[0] + chunks[1]
            del chunks[0]
            del chunk_sizes[0]
        else:
            chunk_sizes[idx - 1] += chunk_sizes[idx]
            chunks[idx - 1].extend(chunks[idx])
            del chunks[idx]
            del chunk_sizes[idx]
            idx -= 1


def build_chunks(
    paragraphs: Sequence[str],
    target_words: int,
    min_words: int,
    max_words: int,
) -> List[str]:
    chunks: List[List[str]] = []
    chunk_sizes: List[int] = []

    current: List[str] = []
    current_words = 0

    for paragraph in paragraphs:
        words = count_words(paragraph)
        if current and current_words + words > max_words:
            chunks.append(current)
            chunk_sizes.append(current_words)
            current = [paragraph]
            current_words = words
        else:
            current.append(paragraph)
            current_words += words

        if current_words >= target_words:
            chunks.append(current)
            chunk_sizes.append(current_words)
            current = []
            current_words = 0

    if current:
        chunks.append(current)
        chunk_sizes.append(current_words)

    merge_small_chunks(chunks, chunk_sizes, min_words, max_words)

    normalized: List[str] = []
    for chunk in chunks:
        text = "\n\n".join(p for p in chunk if p.strip())
        normalized.append(text.strip() + "\n")
    return normalized


def split_chapter(
    path: Path,
    target_words: int,
    min_words: int,
    max_words: int,
) -> Tuple[List[str], List[int]]:
    raw_text = path.read_text(encoding="utf-8")
    paragraphs = raw_text.split("\n\n")
    expanded = expand_paragraphs(paragraphs, target_words, min_words, max_words)
    chunks = build_chunks(expanded, target_words, min_words, max_words)
    counts = [count_words(chunk) for chunk in chunks]
    return chunks, counts


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def plan_chunk_names(
    chapter_path: Path,
    chunk_count: int,
    flat_index: bool,
    start_index: int,
) -> List[str]:
    if flat_index:
        return [f"chapter{start_index + i}.txt" for i in range(chunk_count)]
    if chunk_count == 1:
        return [chapter_path.name]
    stem = chapter_path.stem
    return [f"{stem}_part{i}.txt" for i in range(1, chunk_count + 1)]


def write_chunks(
    chapter_path: Path,
    chunks: Sequence[str],
    output_dir: Path,
    flat_index: bool,
    start_index: int,
) -> Tuple[List[Path], int]:
    written_paths: List[Path] = []
    current_index = start_index

    for idx, chunk in enumerate(chunks):
        if flat_index:
            filename = f"chapter{current_index}.txt"
            current_index += 1
        else:
            if len(chunks) == 1:
                filename = chapter_path.name
            else:
                filename = f"{chapter_path.stem}_part{idx + 1}.txt"
        out_path = output_dir / filename
        out_path.write_text(chunk, encoding="utf-8")
        written_paths.append(out_path)

    return written_paths, current_index


def human_stats(counts: Sequence[int]) -> str:
    if not counts:
        return "0 chunks"
    parts = ", ".join(str(c) for c in counts)
    return f"{len(counts)} chunks [{parts}]"


def main() -> None:
    parser = argparse.ArgumentParser(description="Split long chapters to match reference lengths.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        required=True,
        help="Directory containing the chapters to split (e.g. data/hero_of_ages)",
    )
    parser.add_argument(
        "--reference-dir",
        type=Path,
        required=True,
        help="Directory used as reference for length statistics (e.g. data/foundation)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where the split chapters will be written",
    )
    parser.add_argument(
        "--target-words",
        type=int,
        help="Desired target word count per chunk (defaults to reference median)",
    )
    parser.add_argument(
        "--min-words",
        type=int,
        help="Minimum acceptable words per chunk before forcing a split",
    )
    parser.add_argument(
        "--max-words",
        type=int,
        help="Maximum words per chunk before forcing a split",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report how chapters would be split without writing files",
    )
    parser.add_argument(
        "--flat-index",
        action="store_true",
        help="Name outputs sequentially as chapter0.txt, chapter1.txt, ...",
    )

    args = parser.parse_args()

    reference_files = read_chapters(args.reference_dir)
    ref_stats = dataset_stats(reference_files)

    target_words = args.target_words or int(round(ref_stats.median_words))
    min_words = args.min_words or int(max(600, ref_stats.min_words * 0.8))
    max_words = args.max_words or int(math.ceil(ref_stats.p90_words * 1.15))

    if min_words >= max_words:
        raise ValueError("min_words must be smaller than max_words")

    source_files = read_chapters(args.source_dir)
    if not source_files:
        raise ValueError("No chapter files found in source directory")

    print("Reference stats:")
    print(f"  chapters: {ref_stats.count}")
    print(f"  median: {ref_stats.median_words:.0f} words")
    print(f"  p10-p90: {ref_stats.p10_words:.0f} - {ref_stats.p90_words:.0f} words")
    print("")
    print("Split thresholds:")
    print(f"  target_words = {target_words}")
    print(f"  min_words    = {min_words}")
    print(f"  max_words    = {max_words}")
    print("")

    if not args.dry_run:
        ensure_dir(args.output_dir)

    total_written = 0
    total_chunks = 0

    sequence_index = 0

    for chapter in source_files:
        chunks, counts = split_chapter(chapter, target_words, min_words, max_words)
        total_chunks += len(chunks)
        planned_names = plan_chunk_names(
            chapter, len(chunks), args.flat_index, sequence_index
        )

        if args.dry_run:
            name_preview = ", ".join(planned_names)
            print(f"{chapter.name}: {human_stats(counts)} -> {name_preview}")
            if args.flat_index:
                sequence_index += len(chunks)
        else:
            written_paths, sequence_index = write_chunks(
                chapter,
                chunks,
                args.output_dir,
                flat_index=args.flat_index,
                start_index=sequence_index,
            )
            total_written += len(written_paths)
            names = ", ".join(path.name for path in written_paths)
            print(f"Wrote {chapter.name}: {human_stats(counts)} -> {names}")

    if args.dry_run:
        print("")
        print(f"[dry-run] Chapters processed: {len(source_files)}")
        print(f"[dry-run] Total chunks: {total_chunks}")
    else:
        print("")
        print(f"Chapters processed: {len(source_files)}")
        print(f"Chunks written: {total_written}")
        print(f"Output directory: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
