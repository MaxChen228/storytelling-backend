#!/usr/bin/env python3
"""Generate MFA-friendly transcript files from the chapter script."""

from __future__ import annotations

import argparse
from pathlib import Path

from alignment.mfa import clean_script_for_alignment


def clean_text(script_path: Path) -> str:
    raw = script_path.read_text(encoding="utf-8")
    cleaned = clean_script_for_alignment(raw)
    # MFA 對 \n 斷行敏感，保留句子換行以利閱讀
    return cleaned.replace(". ", ".\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare transcript text for MFA alignment.")
    parser.add_argument("input", type=Path, help="原始章節腳本路徑")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="輸出的純文字檔，預設為 <input>_mfa.txt",
    )
    args = parser.parse_args()

    cleaned = clean_text(args.input)
    if not cleaned:
        raise SystemExit("清理後的腳本為空，請檢查原始內容。")

    output_path = args.output or args.input.with_name(f"{args.input.stem}_mfa.txt")
    output_path.write_text(cleaned + "\n", encoding="utf-8")
    print(f"✅ 已生成 MFA 文本: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
