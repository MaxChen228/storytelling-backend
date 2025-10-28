#!/usr/bin/env python3
"""Generate condensed chapter summaries with Gemini 2.5 Flash."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List, Tuple

import yaml
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ 請先在 .env 設定 GEMINI_API_KEY")
    sys.exit(1)


def load_config(config_path: str) -> Dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def clean_text(content: str) -> str:
    lines = [line.rstrip() for line in content.splitlines()]
    cleaned: List[str] = []
    for line in lines:
        if not line.strip():
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue
        cleaned.append(line.strip())
    return "\n".join(cleaned).strip()


def natural_key(text: str) -> List[Any]:
    import re

    parts = re.split(r"(\d+)", text)
    key: List[Any] = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part.lower())
    return key


@dataclass
class ChapterFile:
    number: int
    path: Path
    word_count: int
    content: str


def collect_chapter_files(book_cfg: Dict[str, Any]) -> List[ChapterFile]:
    chapters_dir = Path(book_cfg['chapters_dir']).expanduser()
    if not chapters_dir.exists():
        raise FileNotFoundError(f"找不到書籍資料夾: {chapters_dir}")

    pattern = book_cfg.get('file_pattern', 'chapter*.txt')
    files = sorted(chapters_dir.glob(pattern), key=lambda p: natural_key(p.stem))
    if not files:
        raise ValueError(f"在 {chapters_dir} 使用樣式 '{pattern}' 未找到任何章節檔案")

    encoding = book_cfg.get('encoding', 'utf-8')
    clean_ws = book_cfg.get('clean_whitespace', True)
    min_words = book_cfg.get('min_words', 0)

    chapters: List[ChapterFile] = []
    skipped: List[str] = []
    for file_path in files:
        text = file_path.read_text(encoding=encoding)
        if clean_ws:
            text = clean_text(text)
        words = text.split()
        if len(words) < min_words:
            skipped.append(file_path.name)
            continue
        chapters.append(
            ChapterFile(
                number=len(chapters) + 1,
                path=file_path,
                word_count=len(words),
                content=text,
            )
        )

    if skipped:
        print(f"⚠️ 以下檔案因字數少於 min_words={min_words} 被略過: {', '.join(skipped)}")
    if not chapters:
        raise ValueError("所有章節都被略過，請確認章節檔案內容")
    return chapters


def extract_text(response) -> str:
    if hasattr(response, "text") and response.text:
        return response.text
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", []) or []:
            if hasattr(part, "text") and part.text:
                return part.text
    raise ValueError("回應中沒有文字內容")


def summarize_chapter(client: genai.Client, model: str, chapter: ChapterFile,
                      target_words: int, temperature: float = 0.2) -> str:
    prompt = dedent(f"""
    You are preparing a condensed recap for an audio storytelling workflow.
    - Compress the chapter to roughly {target_words} words (~1/8 of the source length).
    - Preserve key plot beats, character motivations, and any foreshadowing hooks.
    - Use 2-3 short paragraphs written in present tense narrative voice.
    - End with one sentence that hints at what listeners should anticipate next if such hint exists.
    - Do not include bullet lists or chapter numbers.

    Source chapter:
    {chapter.content}
    """).strip()

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=temperature)
    )
    summary = extract_text(response).strip()
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="使用 Gemini-2.5-Flash 為每個章節生成濃縮版摘要"
    )
    parser.add_argument("--config", default="./podcast_config.yaml",
                        help="配置檔路徑 (預設: ./podcast_config.yaml)")
    parser.add_argument("--ratio", type=float, default=8.0,
                        help="摘要壓縮比（原文/摘要字數），預設 8")
    parser.add_argument("--min-summary-words", type=int, default=80,
                        help="每篇摘要最少字數")
    parser.add_argument("--max-summary-words", type=int, default=400,
                        help="每篇摘要最多字數")
    parser.add_argument("--force", action="store_true",
                        help="忽略現有摘要並重新生成")
    parser.add_argument("--model", default="gemini-2.5-flash",
                        help="要使用的 Gemini 模型名稱")
    parser.add_argument("--workers", type=int, default=0,
                        help="同時送出的請求數 (0 表示依章節數全開)")
    parser.add_argument("--temperature", type=float, default=0.2,
                        help="Gemini 生成摘要時的 temperature")
    return parser


def _generate_summary_task(chapter: ChapterFile, summary_path: Path, target_words: int,
                           model: str, temperature: float) -> str:
    client = genai.Client(api_key=GEMINI_API_KEY)
    summary = summarize_chapter(client, model, chapter, target_words, temperature)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary, encoding="utf-8")
    return summary


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    config = load_config(args.config)
    book_cfg = config['book']
    summaries_dir = Path(book_cfg.get('summaries_dir') or (Path(book_cfg['chapters_dir']) / "summaries"))
    summaries_dir.mkdir(parents=True, exist_ok=True)

    chapters = collect_chapter_files(book_cfg)
    metadata: List[Dict[str, Any]] = []
    generated = 0
    skipped = 0
    start_time = time.time()
    pending_jobs: List[Tuple[ChapterFile, Path, int]] = []
    suffix = book_cfg.get('summary_suffix', '_summary.txt')

    for chapter in chapters:
        summary_path = summaries_dir / f"{chapter.path.stem}{suffix}"

        if summary_path.exists() and not args.force:
            skipped += 1
            metadata.append({
                "chapter": chapter.number,
                "file": str(chapter.path),
                "summary_file": str(summary_path),
                "word_count": chapter.word_count,
                "status": "existing"
            })
            continue

        target_words = int(max(
            args.min_summary_words,
            min(args.max_summary_words, round(chapter.word_count / args.ratio))
        ))
        pending_jobs.append((chapter, summary_path, target_words))

    workers = args.workers if args.workers > 0 else max(1, len(pending_jobs))

    if pending_jobs:
        print(f"🚀 同步送出 {len(pending_jobs)} 章節摘要請求 (workers={workers})")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {}
            for chapter, summary_path, target_words in pending_jobs:
                print(f"   ↳ 排程 章節 {chapter.number}: {chapter.path.name} → 目標 {target_words} words")
                future = executor.submit(
                    _generate_summary_task,
                    chapter,
                    summary_path,
                    target_words,
                    args.model,
                    args.temperature,
                )
                future_map[future] = (chapter, summary_path, target_words)

            for future in as_completed(future_map):
                chapter, summary_path, target_words = future_map[future]
                try:
                    future.result()
                except Exception as exc:
                    print(f"❌ 章節 {chapter.number} 生成失敗: {exc}")
                    metadata.append({
                        "chapter": chapter.number,
                        "file": str(chapter.path),
                        "summary_file": str(summary_path),
                        "word_count": chapter.word_count,
                        "target_summary_words": target_words,
                        "status": f"error: {exc}"
                    })
                    continue

                generated += 1
                metadata.append({
                    "chapter": chapter.number,
                    "file": str(chapter.path),
                    "summary_file": str(summary_path),
                    "word_count": chapter.word_count,
                    "target_summary_words": target_words,
                    "status": "generated"
                })
                print(f"✅ 已保存: {summary_path}")

    meta_path = summaries_dir / "summaries_index.json"
    meta_payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "chapters_dir": book_cfg['chapters_dir'],
        "model": args.model,
        "ratio": args.ratio,
        "min_summary_words": args.min_summary_words,
        "max_summary_words": args.max_summary_words,
        "workers": workers,
        "items": metadata
    }
    meta_path.write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    duration = time.time() - start_time
    print("=" * 60)
    print("📝 濃縮摘要完成")
    print(f"   • 新生成: {generated}")
    print(f"   • 已存在跳過: {skipped}")
    print(f"   • 輸出資料夾: {summaries_dir}")
    print(f"   • 花費時間: {duration:.1f} 秒")
    print("=" * 60)


if __name__ == "__main__":
    main()
