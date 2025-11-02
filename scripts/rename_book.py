#!/usr/bin/env python3
"""
互動式書籍改名工具。

此腳本會：
1. 將 `data/<old_id>` 目錄重新命名為新的 book id。
2. 視情況重新命名 `output/<book_output>` 目錄。
3. 掃描相關 JSON/環境設定，更新其中的路徑與 book id/name。
4. 提示還需要手動處理的事項（例如 GCS 同步、podcast_config overrides）。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "podcast_config.yaml"
ENV_PATH = REPO_ROOT / ".env"


# ---------------------------------------------------------------------------
# 基礎工具
# ---------------------------------------------------------------------------

def _resolve_path(base: Path, raw: str) -> Path:
    candidate = Path(raw).expanduser()
    return candidate if candidate.is_absolute() else (base / candidate).resolve()


def _load_yaml(path: Path) -> Dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"找不到配置檔：{path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _prompt(message: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{message}{suffix}: ").strip()
        if not value and default is not None:
            return default
        if value:
            return value
        print("請輸入有效內容。")


def _ensure_directory_available(path: Path, label: str) -> None:
    if path.exists():
        raise FileExistsError(f"{label} 已存在：{path}")


def _replace_strings(obj: Union[Dict, List, str, int, float, None], replacements: Iterable[Tuple[str, str]]) -> Union[Dict, List, str, int, float, None]:
    if isinstance(obj, dict):
        return {key: _replace_strings(value, replacements) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_replace_strings(item, replacements) for item in obj]
    if isinstance(obj, str):
        updated = obj
        for old, new in replacements:
            if old:
                updated = updated.replace(old, new)
        return updated
    return obj


def _update_json_file(path: Path, transform) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    updated = transform(data)
    path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# 核心流程
# ---------------------------------------------------------------------------

def _gather_book_metadata(config: Dict[str, object], old_id: str) -> Dict[str, object]:
    books_cfg = config.get("books", {}) if isinstance(config, dict) else {}
    defaults = books_cfg.get("defaults", {}) if isinstance(books_cfg, dict) else {}
    overrides_map = books_cfg.get("overrides", {}) if isinstance(books_cfg, dict) else {}
    overrides = overrides_map.get(old_id, {}) or {}

    merged: Dict[str, object] = dict(defaults)
    merged.update(overrides)

    display_name = (
        overrides.get("display_name")
        or merged.get("book_name")
        or old_id
    )
    output_folder = (
        overrides.get("output_folder")
        or merged.get("book_name_override")
        or merged.get("book_name")
        or overrides.get("display_name")
        or display_name
    )
    summary_subdir = merged.get("summary_subdir", "summaries")

    return {
        "defaults": defaults,
        "overrides": overrides,
        "overrides_map": overrides_map,
        "display_name": display_name,
        "output_folder": output_folder,
        "summary_subdir": summary_subdir,
    }


def _update_json_tree(root: Path, replacements: List[Tuple[str, str]], book_id: str, book_name: str, data_dir: Path, output_dir: Optional[Path] = None) -> None:
    if not root.exists():
        return

    json_files = [p for p in root.rglob("*.json") if p.is_file()]
    for json_path in json_files:

        def transform(payload):
            payload = _replace_strings(payload, replacements)
            if isinstance(payload, dict):
                if "book_id" in payload:
                    payload["book_id"] = book_id
                if "book_name" in payload:
                    payload["book_name"] = book_name
                if "chapters_dir" in payload:
                    payload["chapters_dir"] = str(data_dir)
                if "summaries_dir" in payload:
                    payload["summaries_dir"] = str(data_dir / "summaries")
                if "chapter_directory" in payload:
                    payload["chapter_directory"] = str(
                        Path(payload["chapter_directory"])
                    )
                if "output_dir" in payload and output_dir is not None:
                    payload["output_dir"] = str(output_dir)
            return payload

        _update_json_file(json_path, transform)


def _update_env(env_path: Path, old_id: str, new_id: str, old_name: str, new_name: str) -> bool:
    if not env_path.exists():
        return False

    changed = False
    lines: List[str] = []

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line
        if line.startswith("STORY_BOOK_ID="):
            _, _, value = line.partition("=")
            if value == old_id:
                line = f"STORY_BOOK_ID={new_id}"
                changed = True
        elif line.startswith("STORY_BOOK_NAME="):
            _, _, value = line.partition("=")
            if value == old_name:
                line = f"STORY_BOOK_NAME={new_name}"
                changed = True
        lines.append(line)

    if changed:
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changed


def rename_book(old_id: str, new_id: str, display_name: Optional[str] = None, new_output_folder: Optional[str] = None) -> None:
    config = _load_yaml(CONFIG_PATH)
    config_dir = CONFIG_PATH.parent

    metadata = _gather_book_metadata(config, old_id)

    paths_cfg = config.get("paths", {}) if isinstance(config, dict) else {}
    books_root = _resolve_path(config_dir, paths_cfg.get("books_root", "./data"))
    outputs_root = _resolve_path(config_dir, paths_cfg.get("outputs_root", "./output"))

    old_data_dir = books_root / old_id
    new_data_dir = books_root / new_id
    if not old_data_dir.exists():
        raise FileNotFoundError(f"找不到資料夾：{old_data_dir}")
    _ensure_directory_available(new_data_dir, "新的書籍資料夾")

    summary_subdir = metadata["summary_subdir"]

    current_output_folder = metadata["output_folder"]
    resolved_output_folder = new_output_folder or (
        new_id if current_output_folder == old_id else current_output_folder
    )
    old_output_dir = outputs_root / current_output_folder
    new_output_dir = outputs_root / resolved_output_folder
    output_will_move = old_output_dir.exists() and old_output_dir != new_output_dir

    old_display_name = metadata["display_name"]
    target_display_name = display_name or (new_id if old_display_name == old_id else old_display_name)

    print("🛠️  開始處理書籍改名...")
    print(f"   • 原書籍 ID        : {old_id}")
    print(f"   • 新書籍 ID        : {new_id}")
    print(f"   • 原顯示名稱       : {old_display_name}")
    print(f"   • 新顯示名稱       : {target_display_name}")
    print(f"   • 原輸出資料夾     : {current_output_folder}")
    print(f"   • 新輸出資料夾     : {resolved_output_folder}")
    print()

    # Step 1: rename data directory
    shutil.move(str(old_data_dir), str(new_data_dir))
    print(f"✅ 已將 data 目錄搬遷至：{new_data_dir}")

    # Step 2: rename output directory when applicable
    if old_output_dir.exists():
        if output_will_move:
            _ensure_directory_available(new_output_dir, "新的輸出資料夾")
            shutil.move(str(old_output_dir), str(new_output_dir))
            print(f"✅ 已將 output 目錄搬遷至：{new_output_dir}")
        else:
            new_output_dir = old_output_dir
            print("ℹ️  輸出資料夾名稱未變更。")
    else:
        print("⚠️  找不到對應的 output 目錄，略過目錄搬移。")
        new_output_dir = outputs_root / resolved_output_folder

    # Step 3: update JSON metadata
    replacements: List[Tuple[str, str]] = [
        (old_id, new_id),
        (str(books_root / old_id), str(new_data_dir)),
        (f"data/{old_id}", f"data/{new_id}"),
        (str(old_output_dir), str(new_output_dir)),
        (f"/{current_output_folder}/", f"/{resolved_output_folder}/"),
        (f"\\{current_output_folder}\\", f"\\{resolved_output_folder}\\"),
    ]

    summaries_index = new_data_dir / summary_subdir / "summaries_index.json"
    if summaries_index.exists():
        _update_json_file(summaries_index, lambda data: _replace_strings(data, replacements))
        _update_json_file(summaries_index, lambda data: {**data, "book_id": new_id})
        print(f"✅ 已更新摘要索引：{summaries_index}")
    else:
        print("ℹ️  未找到 summaries_index.json，略過此步驟。")

    _update_json_tree(new_data_dir, replacements, new_id, target_display_name, new_data_dir, None)
    _update_json_tree(new_output_dir, replacements, new_id, target_display_name, new_data_dir, new_output_dir)
    print("✅ 已更新輸出與章節 metadata JSON。")

    env_updated = _update_env(ENV_PATH, old_id, new_id, old_display_name, target_display_name)
    if env_updated:
        print(f"✅ 已更新 .env 中的 STORY_BOOK_ID/NAME。")

    # Warn about config overrides
    if metadata["overrides"]:
        print("⚠️  注意：podcast_config.yaml 中存在 overrides 設定，需要手動調整新 key。")
    else:
        print("ℹ️  未偵測到 overrides 設定，無需更新 podcast_config.yaml。")

    print()
    print("🎉 書籍改名完成！下一步建議：")
    print("   1. 若使用 GCS，同步新的 output：")
    print("      gsutil -m rsync -d -r output \"$STORYTELLING_SYNC_BUCKET\"")
    print("   2. 如果有部署 FastAPI，重新整理快取或重啟服務。")
    print("   3. 若 CLI 或文件中引用舊書名，手動更新。")


def main() -> None:
    parser = argparse.ArgumentParser(description="重命名書籍資料夾與輸出")
    parser.add_argument("old_id", nargs="?", help="原書籍 ID（例如 foundation）")
    parser.add_argument("new_id", nargs="?", help="新書籍 ID（例如 foundation_v2）")
    parser.add_argument("--display-name", help="新的顯示名稱（預設自動推導）")
    parser.add_argument("--output-folder", help="指定新的輸出資料夾名稱")
    args = parser.parse_args()

    old_id = args.old_id or _prompt("請輸入原書籍 ID")
    new_id = args.new_id or _prompt("請輸入新的書籍 ID")
    if old_id == new_id:
        print("❌ 新舊書籍 ID 相同，取消操作。")
        sys.exit(1)

    display_name = args.display_name
    if display_name is None:
        display_name = _prompt("新的顯示名稱（可直接 Enter 沿用預設）", default="")
        display_name = display_name or None

    try:
        rename_book(old_id, new_id, display_name=display_name, new_output_folder=args.output_folder)
    except Exception as exc:
        print(f"❌ 操作失敗：{exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
