# MFA Lab

實驗場用來跑 Montreal Forced Aligner (MFA) 對齊流程，保留腳本原文字與標點並輸出逐字字幕。

## 目錄

- `prepare_mfa_text.py`：清理 `podcast_script.txt`，移除舞台指示符號，輸出適合 MFA 的逐句文本。
- `textgrid_to_srt.py`：讀取 MFA 產生的 `TextGrid`，比對腳本與時間戳，輸出逐字 SRT。
- `.gitignore`：忽略音檔、對齊結果、micromamba 環境等大型檔案。

## 使用流程

1. **準備文本**
   ```bash
   python3 prepare_mfa_text.py /path/to/podcast_script.txt --output /tmp/chapter_transcript.txt
   ```

2. **建立語料夾**
   ```bash
   mkdir -p /tmp/chapter_corpus
   cp /path/to/podcast.wav /tmp/chapter_corpus/chapter.wav
   cp /tmp/chapter_transcript.txt /tmp/chapter_corpus/chapter.txt
   ```

3. **使用 MFA 對齊**
   ```bash
   micromamba run -n aligner mfa align /tmp/chapter_corpus english_mfa english_mfa /tmp/chapter_aligned
   ```
   > 需先以 micromamba 建立 `aligner` 環境並下載 `english_mfa` acoustic/dictionary。

4. **產生逐字字幕**
   ```bash
   micromamba run -n aligner python textgrid_to_srt.py \
     /tmp/chapter_aligned/chapter.TextGrid \
     /tmp/chapter_transcript.txt \
     /tmp/chapter_words.srt
   ```

5. **播放檢查**
   ```bash
   python3 ../play_with_subtitles.py /path/to/podcast.wav /tmp/chapter_words.srt --player "ffplay -nodisp -autoexit"
   ```

## 備註

- 音檔與對齊成果需自備，避免大量二進位檔納入版本控制。
- 如果腳本含有 SSML 或舞台指示（如 `(soft laugh)`），可先在文本清理階段移除，以提升對齊率。
- 若有新增專案需求，請在本目錄內新增相應腳本即可。
