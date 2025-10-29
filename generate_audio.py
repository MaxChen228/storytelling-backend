#!/usr/bin/env python3
"""
Storytelling 模式 - Step 2：將單聲線腳本轉成單聲線音頻
"""

import json
import os
import sys
import wave
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from dotenv import load_dotenv
from google.cloud import texttospeech

from cli_output import basic_config_rows, print_config_table, print_footer, print_header, print_section

CONFIG_PATH_DEFAULT = "./podcast_config.yaml"
load_dotenv()


def load_config(config_path: str = CONFIG_PATH_DEFAULT) -> Dict[str, Any]:
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_wave_file(filename: Path, pcm_data: bytes, channels: int = 1,
                   rate: int = 24000, sample_width: int = 2) -> None:
    with wave.open(str(filename), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_data)


def resolve_script_targets(target: Path) -> Tuple[List[Path], Optional[Dict[str, Any]]]:
    """解析輸入路徑：支援 session manifest、章節腳本資料夾或舊版批次資料夾"""
    target = target.resolve()

    if target.is_file():
        if target.suffix == ".json":
            session_data = json.loads(target.read_text(encoding='utf-8'))
            script_dirs = [Path(p).resolve() for p in session_data.get('script_dirs', [])]
            return script_dirs, session_data
        raise FileNotFoundError(f"不支援的檔案格式: {target}")

    if target.is_dir():
        batch_manifest = target / "batch_manifest.json"
        if batch_manifest.exists():
            manifest = json.loads(batch_manifest.read_text(encoding='utf-8'))
            script_dirs = []
            for entry in manifest.get('entries', []):
                rel = entry.get('script_rel_path')
                if rel:
                    script_dirs.append((target / rel).resolve())
            return script_dirs, manifest

        script_file = target / "podcast_script.txt"
        if script_file.exists():
            return [target], None

    raise FileNotFoundError(f"找不到腳本：{target}")


def build_tts_prompt(script_text: str, metadata: Dict[str, Any], config: Dict[str, Any]) -> str:
    level_label = metadata.get('level_label', metadata.get('english_level', 'intermediate listeners'))
    base_pace = metadata.get('narration_pace', 'steady and clear')
    basic_cfg = config.get('basic', {})
    advanced_cfg = config.get('advanced', {})
    speaking_pace_key = str(metadata.get('speaking_pace') or basic_cfg.get('speaking_pace', 'neutral')).lower()
    pace_profiles = advanced_cfg.get('tts_pace_profiles') or {}
    pace_profile = pace_profiles.get(speaking_pace_key) or pace_profiles.get('neutral') or {}
    pace_hint = (metadata.get('speaking_pace_tts_hint') or pace_profile.get('tts_hint') or "").strip()
    tts_focus = metadata.get('tts_hint', 'single narrator storytelling with gentle teaching moments')
    if pace_hint:
        pacing_prompt = pace_hint
    else:
        pacing_prompt = f"Keep the pacing {base_pace} and ensure consistency."
    return (
        f"Read the following script as a single narrator for {level_label}. "
        f"{pacing_prompt} Emphasize imagery, maintain clarity, and follow inline teaching cues suited to {tts_focus}.\n\n{script_text}"
    )


def _is_book_chapter_script(script_dir: Path) -> bool:
    """
    檢查是否為新架構的章節腳本
    新架構: output/foundation/chapter0/
    舊架構: output/foundation/chapters/chapter0/script/
    """
    try:
        # 檢查父目錄名稱是否為書名（如 foundation）
        parent_name = script_dir.parent.name
        # 檢查目錄名稱是否符合章節模式
        is_chapter = script_dir.name.startswith('chapter')
        # 檢查是否在 output/ 目錄下
        is_in_output = 'output' in [p.name for p in script_dir.parents]
        return is_chapter and is_in_output
    except (IndexError, AttributeError):
        return False


def _infer_book_root(script_dir: Path) -> Optional[Path]:
    """
    推斷書本根目錄
    新架構: output/foundation/chapter0/ → output/foundation/
    """
    if not _is_book_chapter_script(script_dir):
        return None
    # 新架構下，book_root 就是 script_dir 的父目錄
    return script_dir.parent


def synthesize_episode(
    script_dir: Path,
    audio_dir: Path,
    config: Dict[str, Any],
    client: texttospeech.TextToSpeechClient,
    timestamp: str,
    save_script_copy: bool = True,
) -> Tuple[Path, Path]:
    script_file = script_dir / "podcast_script.txt"
    if not script_file.exists():
        raise FileNotFoundError(f"找不到腳本: {script_file}")

    script_text = script_file.read_text(encoding='utf-8')
    metadata_file = script_dir / "metadata.json"
    metadata = json.loads(metadata_file.read_text(encoding='utf-8')) if metadata_file.exists() else {}

    advanced_cfg = config.get('advanced', {})
    narrator_voice = metadata.get('narrator_voice') or config.get('basic', {}).get('narrator_voice') or "en-US-LedaNeural"
    tts_model = advanced_cfg.get('tts_model', 'gemini-2.5-pro-tts')
    language_code = (
        metadata.get('tts_language')
        or advanced_cfg.get('language_code')
        or advanced_cfg.get('language')
        or "en-US"
    )
    audio_encoding_name = (advanced_cfg.get('audio_encoding') or "LINEAR16").upper()
    sample_rate_hz = int(advanced_cfg.get('sample_rate_hz', 24000))

    tts_prompt = build_tts_prompt(script_text, metadata, config)

    voice_kwargs: Dict[str, Any] = {
        "language_code": language_code,
        "model_name": tts_model,
    }
    if narrator_voice:
        voice_kwargs["name"] = narrator_voice
    voice_params = texttospeech.VoiceSelectionParams(**voice_kwargs)

    audio_encoding = getattr(texttospeech.AudioEncoding, audio_encoding_name, texttospeech.AudioEncoding.LINEAR16)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=audio_encoding,
        sample_rate_hertz=sample_rate_hz,
    )

    synthesis_input = texttospeech.SynthesisInput(text=tts_prompt)
    response = client.synthesize_speech(
        request=texttospeech.SynthesizeSpeechRequest(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config,
        )
    )
    audio_data = response.audio_content

    audio_dir.mkdir(parents=True, exist_ok=True)
    extension_map = {
        texttospeech.AudioEncoding.LINEAR16: "wav",
        texttospeech.AudioEncoding.MP3: "mp3",
        texttospeech.AudioEncoding.OGG_OPUS: "ogg",
        texttospeech.AudioEncoding.MULAW: "mulaw",
        texttospeech.AudioEncoding.ALAW: "alaw",
    }
    file_extension = extension_map.get(audio_encoding, "audio")
    audio_file = audio_dir / f"podcast.{file_extension}"
    if audio_encoding == texttospeech.AudioEncoding.LINEAR16:
        save_wave_file(audio_file, audio_data, rate=sample_rate_hz)
    else:
        audio_file.write_bytes(audio_data)

    # 只在 legacy 模式或不同目錄時才保存腳本副本
    if save_script_copy and audio_dir != script_dir:
        (audio_dir / "script.txt").write_text(script_text, encoding='utf-8')

    audio_metadata = {
        "narrator_voice": narrator_voice,
        "tts_model": tts_model,
        "script_dir": str(script_dir),
        "script_file": str(script_file),
        "audio_file": str(audio_file),
        "generated_at": timestamp,
        "word_count": metadata.get('actual_words'),
        "book_name": metadata.get('book_name'),
        "chapter_slug": metadata.get('chapter_slug'),
        "speaking_pace": metadata.get('speaking_pace') or config.get('basic', {}).get('speaking_pace'),
        "speaking_pace_tts_hint": metadata.get('speaking_pace_tts_hint'),
        "tts_language_code": language_code,
        "audio_encoding": audio_encoding_name,
        "sample_rate_hz": sample_rate_hz,
    }
    (audio_dir / "metadata.json").write_text(json.dumps(audio_metadata, ensure_ascii=False, indent=2), encoding='utf-8')

    return audio_dir, audio_file


def generate_audio_from_script(script_reference: str, config_path: str = CONFIG_PATH_DEFAULT) -> Optional[str]:
    print_header("🎵 Storytelling 單聲線音頻生成")

    config = load_config(config_path)
    basic = config.get("basic", {})
    print_config_table(basic_config_rows(basic))

    script_target = Path(script_reference).resolve()
    try:
        script_dirs, manifest = resolve_script_targets(script_target)
    except FileNotFoundError as exc:
        print(f"❌ {exc}")
        return None

    if not script_dirs:
        print("❌ 未找到任何腳本")
        return None

    print_section("輸入資訊")
    print(f"📁 腳本來源: {script_target}")
    print(f"📝 章節數量: {len(script_dirs)}")
    if manifest and manifest.get('chapters'):
        chapter_labels = [entry.get('chapter_slug') or entry.get('chapter_number') for entry in manifest.get('chapters', [])]
        print(f"🗂️ 本次章節: {chapter_labels}")

    try:
        client = texttospeech.TextToSpeechClient()
    except Exception as exc:
        print(f"❌ 無法初始化 Cloud Text-to-Speech 用戶端: {exc}")
        credentials_hint = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not credentials_hint:
            print("💡 提示：請設定 GOOGLE_APPLICATION_CREDENTIALS 或使用其它 Application Default Credentials。")
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    use_book_structure = all(_is_book_chapter_script(Path(script_path)) for script_path in script_dirs)
    legacy_output_dir: Optional[Path] = None
    book_root: Optional[Path] = None
    book_name: Optional[str] = None

    if use_book_structure:
        book_root = _infer_book_root(Path(script_dirs[0]))
        if book_root is None:
            use_book_structure = False
        else:
            book_root.mkdir(parents=True, exist_ok=True)
            book_name = book_root.name
            sessions_root = book_root / "sessions"
            sessions_root.mkdir(parents=True, exist_ok=True)
    if not use_book_structure:
        legacy_output_dir = Path(f"./output/audio/storytelling/audio_{timestamp}")
        legacy_output_dir.mkdir(parents=True, exist_ok=True)

    generated_entries: List[Dict[str, Any]] = []
    for script_path in script_dirs:
        script_path = Path(script_path)
        print(f"🚀 生成音頻 - 來源 {script_path}")
        try:
            if use_book_structure and book_root is not None:
                # 新架構：直接使用章節目錄，不創建 audio/ 子目錄
                # output/foundation/chapter0/ → podcast.wav 直接放這裡
                chapter_root = script_path
                audio_dir = chapter_root
                # 新架構下不需要保存腳本副本（腳本和音頻在同一目錄）
                chapter_audio_dir, audio_file = synthesize_episode(script_path, audio_dir, config, client, timestamp, save_script_copy=False)
            else:
                # 舊架構（legacy）
                chapter_root = script_path.parent
                audio_dir = (legacy_output_dir / chapter_root.name) if legacy_output_dir else chapter_root / "audio"
                # 舊架構下保存腳本副本（腳本和音頻在不同目錄）
                chapter_audio_dir, audio_file = synthesize_episode(script_path, audio_dir, config, client, timestamp, save_script_copy=True)
            metadata_file = script_path / "metadata.json"
            metadata = json.loads(metadata_file.read_text(encoding='utf-8')) if metadata_file.exists() else {}
            generated_entries.append({
                "chapter_slug": metadata.get('chapter_slug', chapter_root.name),
                "chapter_number": metadata.get('chapter_number'),
                "book_name": metadata.get('book_name', book_name),
                "script_dir": str(script_path),
                "audio_dir": str(chapter_audio_dir),
                "audio_file": str(audio_file),
                "generated_at": timestamp
            })
            print(f"✅ 完成：{chapter_audio_dir}")
        except Exception as exc:
            print(f"❌ 章節失敗 ({script_path}): {exc}")

    if not generated_entries:
        print("❌ 沒有任何音頻成功生成")
        return None

    details = [
        f"{entry['chapter_slug']} → {entry['audio_dir']}"
        for entry in generated_entries
    ]

    if use_book_structure and book_root is not None:
        sessions_root = book_root / "sessions"
        audio_session = {
            "session_type": "audio_generation",
            "book_name": book_name or book_root.name,
            "timestamp": timestamp,
            "chapters": generated_entries
        }
        audio_manifest = sessions_root / f"audio_session_{timestamp}.json"
        audio_manifest.write_text(json.dumps(audio_session, ensure_ascii=False, indent=2), encoding='utf-8')
        print_footer("🎉 音頻生成完成", details)
        return str(audio_manifest)

    summary = {
        "timestamp": timestamp,
        "chapters": generated_entries
    }
    assert legacy_output_dir is not None
    (legacy_output_dir / "batch_manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    print_footer("🎉 音頻生成完成", details)
    return str(legacy_output_dir)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方式: python generate_audio.py <script_reference>")
        sys.exit(1)
    generate_audio_from_script(sys.argv[1])
