#!/usr/bin/env python3
"""
Storytelling 模式 - Step 1：將英文書章節轉成單聲線講書腳本
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv
from podcastfy.client import generate_podcast

from cli_output import basic_config_rows, print_config_table, print_footer, print_header, print_section

load_dotenv()

CONFIG_PATH_DEFAULT = "./podcast_config.yaml"
TRANSCRIPT_DIR = Path("./data/transcripts")


def load_config(config_path: str = CONFIG_PATH_DEFAULT) -> Dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_book_config(config: Dict[str, Any], book_id: Optional[str]) -> Dict[str, Any]:
    if not book_id:
        book_id = os.environ.get("STORY_BOOK_ID")
    if not book_id:
        raise ValueError("必須指定 --book-id 或設定 STORY_BOOK_ID")

    paths_cfg = config.get("paths", {})
    books_root = Path(paths_cfg.get("books_root", "./data")).expanduser().resolve()
    outputs_root = Path(paths_cfg.get("outputs_root", "./output")).expanduser().resolve()

    book_dir = books_root / book_id
    if not book_dir.exists():
        raise FileNotFoundError(f"找不到書籍資料夾: {book_dir}")

    books_cfg = config.get("books", {})
    defaults = books_cfg.get("defaults", {})
    overrides = (books_cfg.get("overrides", {}) or {}).get(book_id, {})

    merged = dict(defaults)
    merged.update(overrides)
    summary_subdir = merged.get("summary_subdir", "summaries")
    summary_suffix = merged.get("summary_suffix", "_summary.txt")

    merged["book_id"] = book_id
    merged["books_root"] = str(books_root)
    merged["outputs_root"] = str(outputs_root)
    merged["chapters_dir"] = str(book_dir)
    merged["summary_subdir"] = summary_subdir
    merged["summary_suffix"] = summary_suffix
    merged["summaries_dir"] = str((book_dir / summary_subdir).resolve())

    if "book_name_override" not in merged and overrides.get("display_name"):
        merged["book_name_override"] = overrides["display_name"]

    return merged


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


def _natural_key(text: str) -> List[Any]:
    parts = re.split(r"(\d+)", text)
    key: List[Any] = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part.lower())
    return key


def load_chapters_from_files(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    book_cfg = config['book']
    chapters_dir = Path(book_cfg['chapters_dir'])
    if not chapters_dir.exists():
        raise FileNotFoundError(f"找不到書籍資料夾: {chapters_dir}")

    pattern = book_cfg.get('file_pattern', 'chapter*.txt')
    files = sorted(chapters_dir.glob(pattern), key=lambda p: _natural_key(p.stem))

    if not files:
        raise ValueError(f"在 {chapters_dir} 使用樣式 '{pattern}' 未找到任何章節檔案")

    encoding = book_cfg.get('encoding', 'utf-8')
    min_words = book_cfg.get('min_words', 0)
    use_filename = book_cfg.get('title_from_filename', True)
    clean_ws = book_cfg.get('clean_whitespace', True)

    chapters: List[Dict[str, Any]] = []
    skipped_files: List[str] = []

    for file_path in files:
        text = file_path.read_text(encoding=encoding)
        if clean_ws:
            text = clean_text(text)
        words = text.split()
        if len(words) < min_words:
            skipped_files.append(file_path.name)
            continue

        chapter_number = len(chapters) + 1
        title = file_path.stem if use_filename else f"Chapter {chapter_number}"
        chapters.append(
            {
                "number": chapter_number,
                "title": title,
                "content": text,
                "word_count": len(words),
                "preview": " ".join(words[:120]),
                "source_path": str(file_path)
            }
        )

    if skipped_files:
        print(f"⚠️ 以下檔案因字數少於 min_words={min_words} 被略過: {', '.join(skipped_files)}")

    if not chapters:
        raise ValueError("所有章節都被略過，請確認 min_words 或章節檔案內容是否正確")

    return chapters


def load_summary_map(book_cfg: Dict[str, Any], chapters: List[Dict[str, Any]]) -> Dict[int, Dict[str, str]]:
    summaries_dir = book_cfg.get('summaries_dir')
    if not summaries_dir:
        print("⚠️ summaries_dir 未設定，將不包含章節摘要提示")
        return {}
    summaries_path = Path(summaries_dir)
    if not summaries_path.exists():
        print(f"⚠️ 找不到 summaries_dir: {summaries_path}，將不包含章節摘要提示")
        return {}

    suffix = book_cfg.get('summary_suffix', '_summary.txt')
    summary_map: Dict[int, Dict[str, str]] = {}
    for chapter in chapters:
        base_name = Path(chapter['source_path']).stem
        summary_file = summaries_path / f"{base_name}{suffix}"
        summary_text = ""
        if summary_file.exists():
            summary_text = summary_file.read_text(encoding="utf-8").strip()
        summary_map[chapter['number']] = {
            "text": summary_text,
            "file": str(summary_file),
            "exists": summary_file.exists()
        }
    return summary_map


def compose_generation_payload(chapter_text: str, prev_summary: str, next_summary: str) -> str:
    lines = []
    prev_payload = prev_summary if prev_summary else "No previous chapter summary available."
    next_payload = next_summary if next_summary else "No upcoming chapter summary available."
    lines.append("<<PREVIOUS_CHAPTER_SUMMARY>>")
    lines.append(prev_payload)
    lines.append("")
    lines.append("<<CURRENT_CHAPTER_TEXT>>")
    lines.append(chapter_text)
    lines.append("")
    lines.append("<<NEXT_CHAPTER_SUMMARY>>")
    lines.append(next_payload)
    return "\n".join(lines).strip()


def snapshot_transcripts() -> Dict[str, float]:
    return {f.name: f.stat().st_mtime for f in TRANSCRIPT_DIR.glob("transcript*.txt")}


def wait_for_new_transcript(previous_snapshot: Dict[str, float], timeout: int = 30) -> Path:
    deadline = time.time() + timeout
    while time.time() < deadline:
        current_files = list(TRANSCRIPT_DIR.glob("transcript*.txt"))
        candidates = [
            f for f in current_files
            if f.name not in previous_snapshot or f.stat().st_mtime > previous_snapshot.get(f.name, 0)
        ]
        if candidates:
            return max(candidates, key=lambda x: x.stat().st_mtime)
        time.sleep(0.6)
    raise FileNotFoundError("找不到新生成的腳本檔案，請檢查 Podcastfy 寫入權限")


def build_story_instructions(
    level_profile: Dict[str, Any],
    story_cfg: Dict[str, Any],
    chapter: Dict[str, Any],
    length_cfg: Dict[str, Any],
    prev_summary: str,
    next_summary: str,
    pace_hint: str,
) -> str:
    structure = "\n".join(
        f"{idx + 1}. {section}" for idx, section in enumerate(story_cfg['narrative_structure'])
    )
    tone = ", ".join(story_cfg.get('tone', []))
    sensory = ", ".join(story_cfg.get('sensory_focus', []))
    engagement = ", ".join(story_cfg.get('engagement_prompts', []))

    preview = chapter['preview'] if len(chapter['preview']) < 800 else chapter['preview'][:800] + "..."

    instructions = dedent(f"""
ROLE & VOICE
─ Be the sole narrator, embodying the "{level_profile['label']}" persona.
    ─ Speak directly to the listener as if guiding a book club: first-person, warm, curious, and vividly sensory ({tone}).
    ─ Output must read like a verbatim transcript: sprinkle natural fillers (e.g., "Mmm...", "uh", soft laughs) and subtle breath cues only where they heighten authenticity.
    ─ Maintain this pacing guidance: {pace_hint}
─ Listener proficiency: {level_profile['vocabulary_hint']}. Obey their needs in every sentence.

STORY TARGET
    ─ Word count: ~{length_cfg['word_count']} (±5%).
    ─ Open with 2–3 sentences that elegantly weave in PREVIOUS_CHAPTER_SUMMARY (if present) so the audience feels anchored.
    ─ Close with 2–3 sentences that plant an irresistible hook using NEXT_CHAPTER_SUMMARY (if present).
    ─ Keep narration single-voiced; never simulate dialogues or multiple speakers.

    STRUCTURE (blend naturally, no headings):
    {structure}

STYLE DIRECTIVES
    ─ Stay immersive, expressive, and slightly improvisational—capture the cadence of a live storyteller thinking aloud.
    ─ Use transcript-friendly cues sparingly: e.g., “Mmm…”, “you know,” “(soft laugh)” to dramatize thoughts, especially before insightful pivots or vocabulary spotlights.
    ─ Sprinkle in {', '.join(story_cfg.get('engagement_prompts', []))}.
    ─ Highlight 1–2 vocabulary items: say the English word, briefly explain meaning per {level_profile['explanation_style']}.
    ─ {level_profile['recap_style']}
    ─ {level_profile['narrator_goal']}
    ─ When challenging an idea, frame it as reflective commentary (e.g., "I can’t help questioning...").

    CONTEXT PACKET (quote faithfully, never invent):
    • <<PREVIOUS_CHAPTER_SUMMARY>>  – recap status: {'available' if prev_summary else 'missing'}
    • <<CURRENT_CHAPTER_TEXT>>      – full chapter text (primary source)
    • <<NEXT_CHAPTER_SUMMARY>>      – teaser material: {'available' if next_summary else 'missing'}

OUTPUT SAFEGUARDS
─ Deliver finished narration only. No scratchpads, planning notes, stage directions, or mention of these instructions.
    ─ Do not label sections; let the flow imply structure. Stage cues are limited to subtle transcript markers like soft laughs or quiet breaths when necessary.
    ─ Maintain consistent first-person viewpoint with occasional listener address ("you").

    QUICK REFERENCE EXCERPT (for tone calibration only; paraphrase instead of quoting more than two sentences):
    {preview}
    """).strip()
    return instructions


def clean_speaker_tags(text: str) -> str:
    """移除 Podcastfy 生成的說話者標籤（單人旁白模式不需要）"""
    # 移除所有 <PersonN> 和 </PersonN> 標籤
    cleaned = re.sub(r'</?Person\d+>', '', text)
    # 移除可能的多餘空行
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def save_chapter_script(output_dir: Path, script_text: str, metadata: Dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # ✅ 清除 Podcastfy 對話標籤（Gemini TTS 單人模式不需要這些標籤）
    cleaned_script = clean_speaker_tags(script_text)

    script_file = output_dir / "podcast_script.txt"
    script_file.write_text(cleaned_script, encoding="utf-8")
    metadata_file = output_dir / "metadata.json"
    metadata_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_script_only(config_path: str = CONFIG_PATH_DEFAULT,
                         chapter_name: Optional[str] = None,
                         book_id: Optional[str] = None) -> str:
    print_header("📚 Storytelling 單聲線腳本生成")

    config = load_config(config_path)
    try:
        book_cfg = resolve_book_config(config, book_id)
    except Exception as exc:
        print_footer("❌ 錯誤", [str(exc)])
        sys.exit(1)

    config = dict(config)
    config['book'] = book_cfg

    paths_cfg = config.get('paths', {})
    transcripts_root = Path(paths_cfg.get('transcripts_root', "./data/transcripts")).expanduser().resolve()
    global TRANSCRIPT_DIR
    TRANSCRIPT_DIR = transcripts_root
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)

    basic = config['basic']
    story_cfg = config['storytelling']
    advanced = config.get('advanced', {})

    english_level_key = basic.get('english_level', 'intermediate').lower()
    level_profile = story_cfg['english_levels'].get(english_level_key)
    if not level_profile:
        raise ValueError(f"找不到 english_level '{english_level_key}' 對應的設定")

    length_key = basic.get('episode_length', 'medium')
    length_cfg = story_cfg['lengths'].get(length_key)
    if not length_cfg:
        raise ValueError(f"找不到 episode_length '{length_key}' 對應的設定")

    narrator_voice = basic.get('narrator_voice', 'Aoede')
    pace_key = str(basic.get('speaking_pace', 'neutral')).lower()
    pace_profiles = advanced.get('tts_pace_profiles') or {}
    pace_profile = pace_profiles.get(pace_key) or pace_profiles.get('neutral') or {}
    pace_script_hint = pace_profile.get('script_hint', '').strip() or "Keep a balanced conversational tempo suited to attentive learners."
    pace_tts_hint = pace_profile.get('tts_hint', '').strip()

    chapters = load_chapters_from_files(config)
    summary_map = load_summary_map(book_cfg, chapters)
    total_chapters = len(chapters)

    # 如果指定了章節名稱，找到對應的索引
    if chapter_name:
        # 找到匹配的章節
        chapter_index = None
        for idx, ch in enumerate(chapters):
            # 檢查檔案名稱（不含副檔名）或標題是否匹配
            if 'source_path' in ch:
                file_stem = Path(ch['source_path']).stem
                if file_stem == chapter_name:
                    chapter_index = idx
                    break
            # 也嘗試用標題匹配
            if ch.get('title') == chapter_name:
                chapter_index = idx
                break

        if chapter_index is None:
            raise ValueError(f"找不到章節：{chapter_name}")

        # 設置為只生成這一章
        start_chapter = chapter_index + 1
        chapters_per_run = 1
        print(f"🎯 指定章節模式: {chapter_name} (第 {chapter_index + 1} 章)")
    else:
        # 使用配置文件中的設定
        start_chapter = max(1, int(basic.get('start_chapter', 1)))
        chapters_per_run = max(1, int(basic.get('chapters_per_run', 1)))

    end_index = start_chapter - 1 + chapters_per_run
    selected = chapters[start_chapter - 1:end_index]

    if not selected:
        raise ValueError("沒有選到任何章節，請調整 start_chapter 或 chapters_per_run")

    print_config_table(basic_config_rows(basic))
    print_section("處理資訊")
    print(f"📚 書籍: {book_cfg.get('book_id')} (章節數 {len(chapters)})")
    print(f"📖 章節資料夾: {book_cfg['chapters_dir']}")
    print(f"📌 全部章節數量: {total_chapters}")
    print(f"🎯 本次處理: 第 {start_chapter} - {start_chapter + len(selected) - 1} 章")
    print(f"🗣️ 英語等級: {level_profile['label']}")
    print(f"🎧 旁白聲線: {narrator_voice}")
    print(f"⏱️ 預計時長: {length_cfg['time_range']} ({length_cfg['word_count']} words)")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chapters_dir_path = Path(book_cfg['chapters_dir']).expanduser().resolve()
    book_name = book_cfg.get('book_name_override') or os.environ.get('STORY_BOOK_NAME') or book_cfg.get('book_id') or chapters_dir_path.name

    book_output_root = Path(book_cfg.get('outputs_root', "./output")).expanduser().resolve()
    book_output_dir = book_output_root / book_name
    # 直接使用 book_output_dir 作為 chapters_root，不再創建 chapters/ 子目錄
    chapters_root = book_output_dir
    sessions_root = book_output_dir / "sessions"
    chapters_root.mkdir(parents=True, exist_ok=True)
    sessions_root.mkdir(parents=True, exist_ok=True)

    book_meta_file = book_output_dir / "book_metadata.json"
    book_meta = {
        "book_name": book_name,
        "book_id": book_cfg.get('book_id', book_name),
        "chapters_dir": str(chapters_dir_path),
        "summaries_dir": book_cfg.get('summaries_dir'),
        "updated_at": timestamp
    }
    book_meta_file.write_text(json.dumps(book_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    session_entries: List[Dict[str, Any]] = []
    transcript_snapshot = snapshot_transcripts()
    llm_model = advanced.get('llm_model', 'gemini-1.5-pro')
    longform = length_key == 'long'

    for batch_index, chapter in enumerate(selected, start=1):
        chapter_slug = Path(chapter['source_path']).stem
        chapter_root = chapters_root / chapter_slug
        # 直接使用 chapter_root，不再創建 script/ 子目錄
        script_output_dir = chapter_root
        script_output_dir.mkdir(parents=True, exist_ok=True)
        prev_entry = summary_map.get(chapter['number'] - 1, {}) or {}
        next_entry = summary_map.get(chapter['number'] + 1, {}) or {}
        prev_summary = (prev_entry.get("text") or "").strip()
        next_summary = (next_entry.get("text") or "").strip()
        instructions = build_story_instructions(
            level_profile,
            story_cfg,
            chapter,
            length_cfg,
            prev_summary,
            next_summary,
            pace_script_hint
        )
        generation_payload = compose_generation_payload(chapter['content'], prev_summary, next_summary)

        conversation_config = {
            "word_count": length_cfg['word_count'],
            "max_num_chunks": length_cfg['max_num_chunks'],
            "min_chunk_size": length_cfg['min_chunk_size'],
            "language": advanced.get('language', 'English'),
            "output_folder": "./output",
            "podcast_name": f"Storytelling Series - {level_profile['label']}",
            "podcast_tagline": "Immersive single-narrator book retellings",
            "output_language": "English",
            "conversation_style": story_cfg.get('tone', []),
            "roles": ["Narrator"],
            "roles_person1": "Narrator",
            "dialogue_structure": story_cfg['narrative_structure'],
            "engagement_techniques": story_cfg['engagement_prompts'],
            "creativity": story_cfg.get('creativity', 0.65),
            "user_instructions": instructions
        }

        print(f"🚀 生成章節 {chapter['number']}: {chapter['title']}")
        previous_snapshot = dict(transcript_snapshot)

        generate_podcast(
            text=generation_payload,
            llm_model_name=llm_model,
            api_key_label="GEMINI_API_KEY",
            conversation_config=conversation_config,
            transcript_only=True,
            longform=longform
        )

        new_transcript = wait_for_new_transcript(previous_snapshot)
        transcript_snapshot[new_transcript.name] = new_transcript.stat().st_mtime
        script_text = new_transcript.read_text(encoding="utf-8")

        # ✅ 清除標籤後再計算詞數（因為標籤會被移除）
        cleaned_text = clean_speaker_tags(script_text)
        actual_words = len(cleaned_text.split())

        current_summary_entry = summary_map.get(chapter['number'], {}) or {}
        metadata = {
            "timestamp": timestamp,
            "book_name": book_name,
            "chapter_directory": str(chapter_root.resolve()),
            "chapter_number": chapter['number'],
            "batch_order": batch_index,
            "chapter_title": chapter['title'],
            "source_file": chapter['source_path'],
            "output_folder_name": chapter_slug,
            "source_word_count": chapter['word_count'],
            "english_level": english_level_key,
            "level_label": level_profile['label'],
            "episode_length": length_key,
            "target_words": length_cfg['word_count'],
            "actual_words": actual_words,
            "narrator_voice": narrator_voice,
            "instructions_chars": len(instructions),
            "narration_pace": level_profile['pacing'],
            "speaking_pace": pace_key,
            "speaking_pace_script_hint": pace_script_hint,
            "speaking_pace_tts_hint": pace_tts_hint,
            "longform": longform,
            "current_summary_file": current_summary_entry.get("file"),
            "current_summary_present": bool((current_summary_entry.get("text") or "").strip()),
            "previous_summary_file": prev_entry.get("file"),
            "next_summary_file": next_entry.get("file"),
            "previous_summary_present": bool(prev_summary),
            "next_summary_present": bool(next_summary)
        }

        save_chapter_script(script_output_dir, script_text, metadata)
        session_entries.append(
            {
                "chapter_number": chapter['number'],
                "chapter_slug": chapter_slug,
                "chapter_title": chapter['title'],
                "script_dir": str(script_output_dir.resolve()),
                "chapter_dir": str(chapter_root.resolve()),
                "target_words": length_cfg['word_count'],
                "actual_words": actual_words,
                "source_file": chapter['source_path'],
                "previous_summary_present": bool(prev_summary),
                "next_summary_present": bool(next_summary)
            }
        )

        print(f"✅ 完成章節 {chapter['number']}，實際字數 {actual_words}")

    chapters_index_file = book_output_dir / "chapters_index.json"
    if chapters_index_file.exists():
        chapters_index = json.loads(chapters_index_file.read_text(encoding="utf-8"))
    else:
        chapters_index = {}
    for entry in session_entries:
        chapters_index[entry['chapter_slug']] = {
            "chapter_number": entry['chapter_number'],
            "chapter_title": entry['chapter_title'],
            "script_dir": entry['script_dir'],
            "last_script_generated_at": timestamp,
            "source_file": entry['source_file']
        }
    chapters_index_file.write_text(json.dumps(chapters_index, ensure_ascii=False, indent=2), encoding="utf-8")

    session_manifest = sessions_root / f"script_session_{timestamp}.json"
    session_data = {
        "session_type": "script_generation",
        "book_name": book_name,
        "book_id": book_cfg.get('book_id', book_name),
        "timestamp": timestamp,
        "chapters_dir": str(chapters_dir_path),
        "output_dir": str(book_output_dir.resolve()),
        "script_dirs": [entry["script_dir"] for entry in session_entries],
        "chapters": session_entries
    }
    session_manifest.write_text(json.dumps(session_data, ensure_ascii=False, indent=2), encoding="utf-8")

    details = [
        f"{entry['chapter_slug']} ({entry['chapter_title']}) → {entry['actual_words']} words"
        for entry in session_entries
    ]
    print_footer("🎉 腳本生成完成", details)

    return str(session_manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="生成 Storytelling 單聲線腳本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  # 使用配置文件中的設定生成章節
  python generate_script.py

  # 指定配置文件
  python generate_script.py --config custom_config.yaml

  # 生成特定章節（忽略配置文件中的 start_chapter）
  python generate_script.py chapter3

  # 生成特定章節並指定配置文件
  python generate_script.py chapter5 --config custom_config.yaml
        """
    )
    parser.add_argument(
        'chapter',
        nargs='?',
        default=None,
        help='要生成的章節名稱（例如：chapter3），不指定則使用配置文件中的設定'
    )
    parser.add_argument(
        '--config',
        '-c',
        default=CONFIG_PATH_DEFAULT,
        help=f'配置文件路徑（預設：{CONFIG_PATH_DEFAULT}）'
    )
    parser.add_argument(
        '--book-id',
        '-b',
        default=os.environ.get("STORY_BOOK_ID"),
        help='要生成的書籍資料夾名稱（必填，可用 STORY_BOOK_ID 環境變數）'
    )

    args = parser.parse_args()
    generate_script_only(config_path=args.config, chapter_name=args.chapter, book_id=args.book_id)
