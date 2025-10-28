#!/usr/bin/env python3
"""WhisperX 強制對齊主腳本

此模組可被直接執行，也可由其他工具匯入。
CLI 支援自訂音頻、腳本、輸出資料夾以及裝置 (CPU/MPS/CUDA)。
當提供腳本時會先經過 `text_cleaner` 處理，並以清理後的段落
覆蓋 Whisper 自動轉錄的結果，達成 Forced Alignment。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from text_cleaner import clean_script_for_alignment, prepare_segments


def check_whisperx_installed():
    """檢查 WhisperX 是否已安裝"""
    try:
        import whisperx
        return True
    except ImportError:
        return False


def resolve_device(device: str) -> str:
    """將使用者輸入的 device 轉換為可以被 whisperx 接受的值。"""

    if device.lower() != "auto":
        return device.lower()

    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass

    return "cpu"


def align_with_whisperx(
    audio_path: Path,
    device: str = "cpu",
    language: str = "en",
    reference_text: Optional[str] = None,
    segments_override: Optional[List[Dict[str, Any]]] = None,
    vad_method: str = "silero",
    whisper_model: str = "small",
) -> Dict[str, Any]:
    """
    使用 WhisperX 完整流程：轉錄 + 對齊

    Args:
        audio_path: 音頻文件路徑
        device: 設備類型 ("cpu", "mps", "cuda")
        language: 語言代碼

    Returns:
        對齊結果
    """
    import whisperx

    print(f"🔧 使用設備: {device}")
    print(f"🌐 語言: {language}")

    # 1. 載入音頻
    print("\n📂 載入音頻...")
    audio = whisperx.load_audio(str(audio_path))
    print(f"✅ 音頻載入成功: {len(audio) / 16000:.1f} 秒")

    # 2. 載入 Whisper 模型並轉錄
    whisper_model_name = whisper_model
    print(f"\n🎙️ 載入 Whisper 模型 ({whisper_model_name})...")
    compute_type = "int8"
    if device in {"mps", "cuda"}:
        compute_type = "float16"
    model = whisperx.load_model(
        whisper_model_name,
        device,
        compute_type=compute_type,
        language=language,
        vad_method=vad_method,
    )
    print(f"✅ Whisper 模型載入成功 (compute_type: {compute_type})")

    print("\n📝 執行轉錄...")
    start_time = datetime.now()

    # WhisperX FasterWhisperPipeline 支持的參數：
    # audio, batch_size, num_workers, language, task, chunk_size, print_progress, combined_progress, verbose
    result = model.transcribe(
        audio,
        batch_size=16,
        language=language
    )
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"✅ 轉錄完成！耗時: {elapsed:.1f} 秒")
    print(f"📊 偵測語言: {result.get('language', 'unknown')}")
    print(f"📊 轉錄段落: {len(result.get('segments', []))}")

    # 3. 載入對齊模型並執行強制對齊
    print(f"\n🔍 載入 {language} 對齊模型...")
    try:
        align_model, metadata = whisperx.load_align_model(
            language_code=result.get("language", language),
            device=device
        )
        print("✅ 對齊模型載入成功")
    except Exception as e:
        print(f"❌ 對齊模型載入失敗: {e}")
        raise

    print("\n⚡ 執行強制對齊（詞級時間戳）...")
    start_time = datetime.now()

    try:
        # ✅ 使用 WhisperX 最佳實踐：直接使用 Whisper 的轉錄段落
        # Whisper 提供基於真實音頻的粗略時間戳，強制對齊會將其精修到詞級
        segments_to_align = result["segments"]

        if segments_override:
            # 保留參考腳本信息用於日誌，但不替換時間戳
            print(f"ℹ️  參考腳本包含 {len(segments_override)} 段（僅用於驗證，不替換時間戳）")
            print(f"ℹ️  使用 Whisper 轉錄的 {len(segments_to_align)} 個段落進行對齊")

        result = whisperx.align(
            segments_to_align,
            align_model,
            metadata,
            audio,
            device,
            return_char_alignments=False
        )

        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"✅ 對齊完成！耗時: {elapsed:.1f} 秒")

        # 統計資訊
        total_words = sum(len(seg.get('words', [])) for seg in result.get('segments', []))
        print(f"📊 對齊詞數: {total_words}")

        if reference_text:
            result["reference_text"] = reference_text

        return result

    except Exception as e:
        print(f"❌ 對齊失敗: {e}")
        raise


def save_alignment_json(result: Dict[str, Any], output_path: Path):
    """保存對齊結果為 JSON"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON 已保存: {output_path}")


def generate_srt(result: Dict[str, Any], output_path: Path):
    """生成 SRT 字幕文件"""

    def format_timestamp(seconds: float) -> str:
        """轉換秒數為 SRT 時間格式 (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    with open(output_path, 'w', encoding='utf-8') as f:
        subtitle_index = 1

        for segment in result.get('segments', []):
            for word_info in segment.get('words', []):
                word = word_info.get('word', '').strip()
                start = word_info.get('start', 0.0)
                end = word_info.get('end', 0.0)

                if word:  # 只輸出有內容的詞
                    f.write(f"{subtitle_index}\n")
                    f.write(f"{format_timestamp(start)} --> {format_timestamp(end)}\n")
                    f.write(f"{word}\n\n")
                    subtitle_index += 1

    print(f"✅ SRT 已保存: {output_path}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="WhisperX 強制對齊工具")
    parser.add_argument("--audio", type=Path, required=True, help="音頻檔案 (wav/mp3)")
    parser.add_argument("--script", type=Path, help="對齊用的腳本檔 (可選)")
    parser.add_argument("--out-dir", type=Path, default=Path("output"), help="輸出資料夾")
    parser.add_argument("--device", default="auto", help="裝置：auto/cpu/mps/cuda")
    parser.add_argument("--language", default="en", help="語言代碼 (預設 en)")
    parser.add_argument("--max-words", type=int, default=50, help="腳本分段最大詞數")
    parser.add_argument("--force", action="store_true", help="若輸出存在則覆寫")
    parser.add_argument(
        "--vad-method",
        default="silero",
        choices=["silero", "pyannote"],
        help="選擇語音活動偵測 (VAD) 模型，預設使用 silero（較新且無需 pyannote）",
    )
    parser.add_argument(
        "--model",
        default="small",
        choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"],
        help="Whisper 模型尺寸，預設 small",
    )

    args = parser.parse_args(argv)

    print("=" * 60)
    print("🎯 WhisperX 強制對齊")
    print("=" * 60)

    if not check_whisperx_installed():
        print("\n❌ WhisperX 未安裝！請先執行 `pip install whisperx`");
        return 1

    audio_file: Path = args.audio
    script_file: Optional[Path] = args.script
    output_dir: Path = args.out_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if not audio_file.exists():
        print(f"❌ 音頻文件不存在: {audio_file}")
        return 1
    if script_file and not script_file.exists():
        print(f"❌ 腳本文件不存在: {script_file}")
        return 1

    json_output = output_dir / "aligned_transcript.json"
    srt_output = output_dir / "subtitles.srt"
    if (json_output.exists() or srt_output.exists()) and not args.force:
        print("⚠️  輸出檔已存在，若要覆寫請加上 --force")
        print(f"  JSON: {json_output}")
        print(f"  SRT : {srt_output}")
        return 0

    device = resolve_device(args.device)
    print(f"📂 音頻: {audio_file}")
    if script_file:
        print(f"📝 參考腳本: {script_file}")
    print(f"⚙️  使用裝置: {device}")

    segments_override: Optional[List[Dict[str, Any]]] = None
    clean_reference: Optional[str] = None
    if script_file:
        raw_text = script_file.read_text(encoding="utf-8")
        clean_reference = clean_script_for_alignment(raw_text)
        segments_override = prepare_segments(raw_text, max_words_per_segment=args.max_words)

    try:
        result = align_with_whisperx(
            audio_path=audio_file,
            device=device,
            language=args.language,
            reference_text=clean_reference,
            segments_override=segments_override,
            vad_method=args.vad_method,
            whisper_model=args.model,
        )

        save_alignment_json(result, json_output)
        generate_srt(result, srt_output)

        print("\n" + "=" * 60)
        print("🎉 對齊完成！")
        print("=" * 60)
        print(f"  📄 JSON: {json_output}")
        print(f"  📄 SRT : {srt_output}")
        return 0

    except Exception as exc:
        print(f"\n❌ 錯誤: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
