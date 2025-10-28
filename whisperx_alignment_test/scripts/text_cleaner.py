#!/usr/bin/env python3
"""
文本清理工具 - 為 WhisperX 強制對齊準備腳本
移除暫停標記、中文註釋等非語音內容
"""

import re
from typing import List, Dict


def clean_script_for_alignment(script_text: str) -> str:
    """
    清理腳本，移除非語音內容

    Args:
        script_text: 原始腳本文本

    Returns:
        清理後的純英文文本
    """
    # 移除暫停標記 (pause)
    text = re.sub(r'\(pause\)', ' ', script_text)

    # 移除中英文對照註解或導演筆記 (括號內容含中文或全部大寫)
    text = re.sub(r'\([^)]*[\u4e00-\u9fff][^)]*\)', ' ', text)
    text = re.sub(r'\([^)]*[A-Z]{3,}[^)]*\)', ' ', text)

    # 移除方括號／花括號說明
    text = re.sub(r'\[[^\]]*\]', ' ', text)
    text = re.sub(r'\{[^}]*\}', ' ', text)

    # 將破折號或省略號轉換為句號，便於分句
    text = text.replace('—', '.').replace('...', '. ')

    # 移除多餘的空白
    text = re.sub(r'\s+', ' ', text)

    # 移除開頭和結尾的空白
    text = text.strip()

    return text


def split_into_sentences(text: str) -> List[str]:
    """
    將文本分割成句子

    Args:
        text: 清理後的文本

    Returns:
        句子列表
    """
    # 按句號、問號、驚嘆號分割
    sentences = re.split(r'(?<=[.!?])\s+', text)

    # 過濾空句子
    sentences = [s.strip() for s in sentences if s.strip()]

    return sentences


def prepare_segments(script_text: str, max_words_per_segment: int = 50) -> List[Dict[str, str]]:
    """
    準備 WhisperX 對齊所需的 segments 格式

    Args:
        script_text: 原始腳本文本
        max_words_per_segment: 每個 segment 的最大詞數

    Returns:
        segment 列表，格式: [{"text": "..."}, ...]
    """
    # 清理文本
    clean_text = clean_script_for_alignment(script_text)

    # 分割成句子
    sentences = split_into_sentences(clean_text)

    # 組合句子成 segments（避免過長）
    segments = []
    current_segment = []
    current_word_count = 0

    for sentence in sentences:
        words = sentence.split()
        sentence_word_count = len(words)

        # 如果加入這句會超過限制，先儲存當前 segment
        if current_word_count + sentence_word_count > max_words_per_segment and current_segment:
            segments.append({"text": " ".join(current_segment)})
            current_segment = []
            current_word_count = 0

        # 加入句子
        current_segment.append(sentence)
        current_word_count += sentence_word_count

    # 加入最後一個 segment
    if current_segment:
        segments.append({"text": " ".join(current_segment)})

    return segments


def analyze_script(script_path: str) -> Dict[str, any]:
    """
    分析腳本，提供清理前後的統計資訊

    Args:
        script_path: 腳本文件路徑

    Returns:
        統計資訊字典
    """
    with open(script_path, 'r', encoding='utf-8') as f:
        original_text = f.read()

    clean_text = clean_script_for_alignment(original_text)
    segments = prepare_segments(original_text)

    return {
        "original_length": len(original_text),
        "original_word_count": len(original_text.split()),
        "clean_length": len(clean_text),
        "clean_word_count": len(clean_text.split()),
        "pause_marks_removed": original_text.count("(pause)"),
        "chinese_annotations_removed": len(re.findall(r'\([^)]*[\u4e00-\u9fff][^)]*\)', original_text)),
        "segment_count": len(segments),
        "segments": segments
    }


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("使用方式: python text_cleaner.py <script_file>")
        sys.exit(1)

    script_file = sys.argv[1]

    print("=" * 60)
    print("📝 腳本清理工具")
    print("=" * 60)

    # 分析腳本
    stats = analyze_script(script_file)

    print(f"\n原始統計：")
    print(f"  字符數: {stats['original_length']}")
    print(f"  詞數: {stats['original_word_count']}")

    print(f"\n清理統計：")
    print(f"  移除暫停標記: {stats['pause_marks_removed']} 個")
    print(f"  移除中文註釋: {stats['chinese_annotations_removed']} 個")
    print(f"  清理後字符數: {stats['clean_length']}")
    print(f"  清理後詞數: {stats['clean_word_count']}")

    print(f"\n分段資訊：")
    print(f"  總段落數: {stats['segment_count']}")
    print(f"  平均每段詞數: {stats['clean_word_count'] / stats['segment_count']:.1f}")

    # 顯示前 3 個段落預覽
    print(f"\n段落預覽（前 3 個）：")
    for i, seg in enumerate(stats['segments'][:3], 1):
        preview = seg['text'][:80] + "..." if len(seg['text']) > 80 else seg['text']
        print(f"  {i}. {preview}")

    # 輸出 JSON 格式的 segments
    output_file = script_file.replace('.txt', '_segments.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(stats['segments'], f, ensure_ascii=False, indent=2)

    print(f"\n✅ Segments 已保存至: {output_file}")
    print("=" * 60)
