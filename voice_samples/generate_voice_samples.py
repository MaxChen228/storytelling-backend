#!/usr/bin/env python3
"""
Batch-generate Gemini TTS voice reference clips for quick listening comparisons.

Usage examples:
    python scripts/generate_voice_samples.py --voices en-US-LedaNeural en-US-RheaNeural
    python scripts/generate_voice_samples.py --config voice_samples.yaml --overwrite
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import wave
from pathlib import Path
from typing import Iterable, List, Optional

import yaml
from dotenv import load_dotenv
from google.cloud import texttospeech


DEFAULT_SAMPLE_TEXT = "Hello! This is a sample line for comparing Gemini voices."
DEFAULT_OUTPUT_DIR = Path("output/voice_samples")
DEFAULT_SAMPLE_RATE = 24000


@dataclasses.dataclass
class VoiceEntry:
    name: str
    language_code: Optional[str] = None
    text: Optional[str] = None
    model: Optional[str] = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate sample audio files for multiple Gemini TTS voices.")
    parser.add_argument(
        "--voices",
        nargs="+",
        help="List of voice names (e.g. en-US-LedaNeural). Overrides voices from config file.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Optional YAML file with keys: voices (list), sample_text, output_dir, language_code, sample_rate_hz.",
    )
    parser.add_argument(
        "--text",
        help="Override sample text spoken by every voice.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Target directory for generated audio files.",
    )
    parser.add_argument(
        "--language-code",
        help="Fallback language code to use when a voice name does not include one.",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=None,
        help="Sample rate in Hz for LINEAR16 output (default 24000).",
    )
    parser.add_argument(
        "--model",
        help="Default Gemini TTS model to use (e.g. gemini-2.5-pro-tts).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-generate files even if the target WAV already exists.",
    )
    return parser.parse_args()


def load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"找不到配置檔: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def coerce_voice_entries(raw: Iterable) -> List[VoiceEntry]:
    entries: List[VoiceEntry] = []
    for item in raw:
        if isinstance(item, str):
            entries.append(VoiceEntry(name=item))
        elif isinstance(item, dict):
            name = item.get("name")
            if not name:
                raise ValueError(f"voice config 缺少名稱: {json.dumps(item, ensure_ascii=False)}")
            entries.append(
                VoiceEntry(
                    name=name,
                    language_code=item.get("language_code"),
                    text=item.get("text"),
                    model=item.get("model"),
                )
            )
        else:
            raise TypeError(f"不支援的 voice 項目格式: {item!r}")
    return entries


def infer_language_code(voice_name: str) -> Optional[str]:
    parts = voice_name.split("-")
    if len(parts) >= 2:
        return "-".join(parts[:2])
    return None


def save_wave_file(path: Path, pcm_data: bytes, sample_rate_hz: int, channels: int = 1, sample_width: int = 2) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(sample_width)
        handle.setframerate(sample_rate_hz)
        handle.writeframes(pcm_data)


def main() -> int:
    load_dotenv()
    args = parse_args()

    config: dict = {}
    if args.config:
        config = load_config(args.config)

    voices_cfg = args.voices or config.get("voices")
    if not voices_cfg:
        print("❌ 請透過 --voices 或 --config 指定至少一個 voice 名稱。")
        return 1

    try:
        voices = coerce_voice_entries(voices_cfg)
    except (TypeError, ValueError) as exc:
        print(f"❌ 解析 voice 清單時發生錯誤: {exc}")
        return 1

    sample_text = args.text or config.get("sample_text") or DEFAULT_SAMPLE_TEXT
    output_dir = Path(args.output_dir or config.get("output_dir") or DEFAULT_OUTPUT_DIR).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    fallback_language = args.language_code or config.get("language_code")
    sample_rate = args.sample_rate or config.get("sample_rate_hz") or DEFAULT_SAMPLE_RATE
    default_model = args.model or config.get("model") or "gemini-2.5-pro-tts"

    try:
        client = texttospeech.TextToSpeechClient()
    except Exception as exc:
        print(f"❌ 初始化 TextToSpeechClient 失敗: {exc}")
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            print("💡 設定 GOOGLE_APPLICATION_CREDENTIALS 指向服務帳戶 JSON 憑證，或確認已配置 Application Default Credentials。")
        return 1

    for voice in voices:
        voice_name = voice.name.strip()
        if not voice_name:
            print("⚠️ 跳過空白 voice 名稱")
            continue

        language_code = voice.language_code or infer_language_code(voice_name) or fallback_language
        if not language_code:
            print(f"⚠️ 無法為 {voice_name} 推斷 language_code，請在 config 或參數中指定。")
            continue

        utterance = voice.text or sample_text
        target_path = output_dir / f"{voice_name}.wav"
        if target_path.exists() and not args.overwrite:
            print(f"⏭️  已存在，略過：{target_path}")
            continue

        print(f"🎙️  生成 {voice_name} → {target_path.name}")
        model_name = voice.model or default_model
        try:
            response = client.synthesize_speech(
                request=texttospeech.SynthesizeSpeechRequest(
                    input=texttospeech.SynthesisInput(text=utterance),
                    voice=texttospeech.VoiceSelectionParams(
                        language_code=language_code,
                        model=model_name,
                        name=voice_name,
                    ),
                    audio_config=texttospeech.AudioConfig(
                        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                        sample_rate_hertz=int(sample_rate),
                    ),
                )
            )
        except Exception as exc:
            print(f"❌ 生成 {voice_name} 失敗: {exc}")
            continue

        try:
            save_wave_file(target_path, response.audio_content, sample_rate_hz=int(sample_rate))
        except Exception as exc:
            print(f"❌ 保存 {target_path} 失敗: {exc}")
            continue

        metadata = {
            "voice_name": voice_name,
            "language_code": language_code,
            "model": model_name,
            "sample_rate_hz": int(sample_rate),
            "text": utterance,
        }
        metadata_path = target_path.with_suffix(".json")
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ 完成，音檔輸出在: {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
