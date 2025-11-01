#!/usr/bin/env python3
"""Generate word-level subtitles for a chapter using Montreal Forced Aligner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

import yaml

from alignment.mfa import MfaAlignmentError, align_chapter_with_mfa, build_config_from_dict


SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_FOUNDATION_DIR = SCRIPT_ROOT / "output" / "foundation"
CONFIG_PATH_DEFAULT = "./podcast_config.yaml"


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def update_metadata(chapter_dir: Path, alignment_stats: dict) -> None:
    metadata_file = chapter_dir / "metadata.json"
    if not metadata_file.exists():
        return
    metadata = json.loads(metadata_file.read_text(encoding="utf-8")) or {}
    metadata.update(alignment_stats)
    metadata["alignment_srt"] = alignment_stats.get("alignment_srt")
    metadata_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_chapter_dir(raw: str) -> Path:
    candidate = Path(raw).expanduser()
    if candidate.is_dir():
        return candidate
    return (DEFAULT_FOUNDATION_DIR / candidate.name).resolve()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="使用 MFA 生成逐字字幕")
    parser.add_argument("chapter", help="章節資料夾路徑或名稱")
    parser.add_argument("--config", default=CONFIG_PATH_DEFAULT, help="配置檔路徑")
    parser.add_argument("--audio", default=None, help="指定音訊檔案，預設使用章節資料夾內的 podcast.wav")
    parser.add_argument("--keep-intermediate", action="store_true", help="保留 TextGrid 與清理後的 transcript")
    parser.add_argument("--keep-workdir", action="store_true", help="保留 MFA 臨時工作目錄")
    args = parser.parse_args(argv)

    chapter_dir = resolve_chapter_dir(args.chapter)
    if not chapter_dir.exists():
        print(f"❌ 找不到章節資料夾：{chapter_dir}")
        return 1

    config = load_config(Path(args.config))
    mfa_config = build_config_from_dict(config)
    if args.keep_intermediate:
        mfa_config.keep_intermediate = True
    if args.keep_workdir:
        mfa_config.keep_workdir = True

    audio_override: Optional[Path] = None
    if args.audio:
        audio_override = Path(args.audio).expanduser()
        if not audio_override.exists():
            print(f"❌ 找不到音訊檔案：{audio_override}")
            return 1

    try:
        result = align_chapter_with_mfa(chapter_dir, config=mfa_config, audio_path=audio_override)
    except MfaAlignmentError as exc:
        print(f"❌ MFA 對齊失敗：{exc}")
        return 1

    alignment_meta = result.as_metadata()
    alignment_meta["alignment_srt"] = str(result.srt_path)
    update_metadata(chapter_dir, alignment_meta)

    print("🎉 字幕生成完成")
    print(f"📄 SRT : {result.srt_path}")
    if alignment_meta.get("alignment_textgrid"):
        print(f"📊 TextGrid: {alignment_meta['alignment_textgrid']}")
    print(
        f"   對齊成功 {result.matched_tokens}/{result.total_tokens}，缺詞 {result.missing_tokens}"
    )

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
