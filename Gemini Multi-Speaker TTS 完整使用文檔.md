# Gemini Multi-Speaker TTS 完整使用文檔

## 概述

Gemini API 可以使用原生文字轉語音（TTS）生成功能將文字輸入轉換為單一說話者或多說話者音訊。文字轉語音（TTS）生成是可控制的，這意味著您可以使用自然語言來構建互動並指導音訊的風格、口音、節奏和語調。

**主要特色：**

- 支援單一和多說話者音訊生成（最多2個說話者）
- 支援24種語言
- 可透過自然語言控制語音風格、情感和節奏
- 30種不同的預建語音選項
- 高品質WAV音訊輸出（24kHz取樣率）

## 支援的模型

### Gemini 2.5 Flash Preview TTS

- **適用場景：** 高性價比的日常應用
- **特點：** 價格效益導向的TTS模型
- **費用：** 免費層：免費使用；付費層：輸入$0.50/百萬token，輸出$10.00/百萬token

### Gemini 2.5 Pro Preview TTS

- **適用場景：** 複雜提示的最佳品質
- **特點：** 最強大的TTS模型
- **費用：** 輸入$1.00/百萬token，輸出$20.00/百萬token

## 單一說話者TTS實作

### Python 實作

```python
from google import genai
from google.genai import types
import wave

# 設定音訊檔案保存
def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)

client = genai.Client()
response = client.models.generate_content(
    model="gemini-2.5-flash-preview-tts",
    contents="Say cheerfully: Have a wonderful day!",
    config=types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name='Kore',
                )
            )
        ),
    )
)

data = response.candidates[0].content.parts[0].inline_data.data
wave_file('output.wav', data)
```

### JavaScript 實作

```javascript
import {GoogleGenAI} from '@google/genai';
import wav from 'wav';

async function saveWaveFile(filename, pcmData, channels = 1, rate = 24000, sampleWidth = 2) {
    return new Promise((resolve, reject) => {
        const writer = new wav.FileWriter(filename, {
            channels,
            sampleRate: rate,
            bitDepth: sampleWidth * 8,
        });
        writer.on('finish', resolve);
        writer.on('error', reject);
        writer.write(pcmData);
        writer.end();
    });
}

async function main() {
    const ai = new GoogleGenAI({});
    const response = await ai.models.generateContent({
        model: "gemini-2.5-flash-preview-tts",
        contents: [{ parts: [{ text: 'Say cheerfully: Have a wonderful day!' }] }],
        config: {
            responseModalities: ['AUDIO'],
            speechConfig: {
                voiceConfig: {
                    prebuiltVoiceConfig: { voiceName: 'Kore' },
                },
            },
        },
    });
    
    const data = response.candidates?.[0]?.content?.parts?.[0]?.inlineData?.data;
    const audioBuffer = Buffer.from(data, 'base64');
    await saveWaveFile('output.wav', audioBuffer);
}
```

## 多說話者TTS實作

### Python 實作

```python
from google import genai
from google.genai import types
import wave

client = genai.Client()

prompt = """TTS the following conversation between Joe and Jane:
Joe: How's it going today Jane?
Jane: Not too bad, how about you?"""

response = client.models.generate_content(
    model="gemini-2.5-flash-preview-tts",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                speaker_voice_configs=[
                    types.SpeakerVoiceConfig(
                        speaker='Joe',
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name='Kore',
                            )
                        )
                    ),
                    types.SpeakerVoiceConfig(
                        speaker='Jane',
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name='Puck',
                            )
                        )
                    ),
                ]
            )
        )
    )
)

data = response.candidates[0].content.parts[0].inline_data.data
wave_file('conversation.wav', data)
```

### JavaScript 實作

```javascript
const prompt = `TTS the following conversation between Joe and Jane:
Joe: How's it going today Jane?
Jane: Not too bad, how about you?`;

const response = await ai.models.generateContent({
    model: "gemini-2.5-flash-preview-tts",
    contents: [{ parts: [{ text: prompt }] }],
    config: {
        responseModalities: ['AUDIO'],
        speechConfig: {
            multiSpeakerVoiceConfig: {
                speakerVoiceConfigs: [
                    {
                        speaker: 'Joe',
                        voiceConfig: {
                            prebuiltVoiceConfig: { voiceName: 'Kore' }
                        }
                    },
                    {
                        speaker: 'Jane',
                        voiceConfig: {
                            prebuiltVoiceConfig: { voiceName: 'Puck' }
                        }
                    }
                ]
            }
        }
    }
});
```

## 語音風格控制

### 單一說話者風格控制

您可以使用自然語言提示來控制單一和多說話者TTS的風格、語調、口音和節奏。

```python
# 例子：恐怖低語
contents="Say in a spooky whisper: By the pricking of my thumbs... Something wicked this way comes"

# 例子：開心語調
contents="Say cheerfully: Have a wonderful day!"

# 例子：疲憊無聊
contents="Say tiredly and bored: What's on the agenda today?"
```

### 多說話者風格控制

```python
prompt = """Make Speaker1 sound tired and bored, and Speaker2 sound excited and happy:
Speaker1: So... what's on the agenda today?
Speaker2: You're never going to guess!"""
```

### 進階情感標籤

Gemini TTS支援廣泛的SSML標籤，您可以將它們與[]情感標記結合使用：

- **停頓控制：** `<break time="2s"/>` 或 `[PAUSE=2s]`
- **語音控制：** 使用 `<prosody>` 標籤控制語速、音調和音量
- **內容類型：** 正確解釋字符、數字、日期和時間

## 可用語音選項

TTS模型支援30種語音選項：

| 語音名稱         | 特性            | 語音名稱          | 特性          |
| ------------ | ------------- | ------------- | ----------- |
| Zephyr       | Bright        | Puck          | Upbeat      |
| Charon       | Informative   | Kore          | Firm        |
| Fenrir       | Excitable     | Leda          | Youthful    |
| Orus         | Firm          | Aoede         | Breezy      |
| Callirrhoe   | Easy-going    | Autonoe       | Bright      |
| Enceladus    | Breathy       | Iapetus       | Clear       |
| Umbriel      | Easy-going    | Algieba       | Smooth      |
| Despina      | Smooth        | Erinome       | Clear       |
| Algenib      | Gravelly      | Rasalgethi    | Informative |
| Laomedeia    | Upbeat        | Achernar      | Soft        |
| Alnilam      | Firm          | Schedar       | Even        |
| Gacrux       | Mature        | Pulcherrima   | Forward     |
| Achird       | Friendly      | Zubenelgenubi | Casual      |
| Vindemiatrix | Gentle        | Sadachbia     | Lively      |
| Sadaltager   | Knowledgeable | Sulafat       | Warm        |

**試聽語音：** 您可以在 [Google AI Studio](https://aistudio.google.com/generate-speech) 中試聽所有語音選項。

## 支援語言

TTS模型自動檢測輸入語言，支援24種語言：

|語言|BCP-47代碼|語言|BCP-47代碼|
|---|---|---|---|
|阿拉伯語（埃及）|ar-EG|德語（德國）|de-DE|
|英語（美國）|en-US|西班牙語（美國）|es-US|
|法語（法國）|fr-FR|印地語（印度）|hi-IN|
|印尼語|id-ID|義大利語|it-IT|
|日語|ja-JP|韓語|ko-KR|
|葡萄牙語（巴西）|pt-BR|俄語|ru-RU|
|荷蘭語|nl-NL|波蘭語|pl-PL|
|泰語|th-TH|土耳其語|tr-TR|
|越南語|vi-VN|羅馬尼亞語|ro-RO|
|烏克蘭語|uk-UA|孟加拉語|bn-BD|
|英語（印度）|en-IN & hi-IN|馬拉地語|mr-IN|
|泰米爾語|ta-IN|泰盧固語|te-IN|

## Google AI Studio 網頁介面使用

### 存取方式

1. **直接存取：** [https://aistudio.google.com/generate-speech](https://aistudio.google.com/generate-speech)
2. **通過AI Studio首頁：** 登入後找到語音生成功能

### 使用步驟

1. **選擇模式：**
    
    - 預設為多說話者音訊介面
    - 可切換至單一說話者模式
2. **輸入文字內容：**
    
    - 在左側文字框輸入或貼上要轉換的文字
    - **重要：** 每行開頭使用 `說話者名稱:` 格式指定說話者
3. **配置說話者：**
    
    - 在右側語音設定區域配置每個說話者
    - **說話者名稱：** 必須與文字中的標識符完全匹配
    - **選擇語音：** 從下拉選單選擇語音角色
4. **風格指示：**
    
    - 在「Style instructions」文字框中輸入風格提示
    - 這些提示會應用到整個專案的所有說話者
5. **生成和下載：**
    
    - 點擊藍色「Run」按鈕
    - 等待處理完成後播放預覽
    - 點擊下載按鈕保存到電腦

## 使用限制和注意事項

### 技術限制

- TTS模型只能接收文字輸入並生成音訊輸出
- TTS會話的上下文視窗限制為32k token
- 實際輸入可能在約5418字符（1233 token）後被截斷
- 多說話者模式最多支援2個說話者

### 費率限制

- Preview模型的費率限制較為嚴格，因為它們是實驗性模型
- 免費層有較低的費率限制，用於測試目的
- 付費層提供更高的費率限制

### 最佳實踐

1. **行長度：** 建議每行內容不要過長，保持句子的自然停頓
2. **說話者標識：** 確保文字中的說話者名稱與配置中的完全一致
3. **語音選擇：** 選擇符合角色特性的語音（如Enceladus的呼吸感適合「疲憊」，Puck的振奮感適合「興奮」）
4. **風格提示：** 使用具體的情感描述詞來獲得更好的效果

## API密鑰設定

### 獲取API密鑰

1. 前往 [Google AI Studio](https://aistudio.google.com/)
2. 登入Google帳戶
3. 在設定中生成API密鑰

### 環境變數設定

```bash
# Windows
set GEMINI_API_KEY=your_api_key_here

# macOS/Linux
export GEMINI_API_KEY=your_api_key_here
```

## 應用場景

### 適用領域

- **播客生成：** 創建多人對話的播客內容
- **有聲書製作：** 為書籍內容添加表達豐富的旁白
- **客服系統：** 創建自然的客服對話
- **教育培訓：** 製作互動式教學材料
- **遊戲音效：** 為遊戲角色生成語音

### 技術整合

- 可與其他Gemini模型配合使用先生成文本再轉換為語音
- 支援批次處理模式（50%折扣）
- 可整合到現有的應用程式和工作流程中

## 故障排除

### 常見問題

1. **音訊無法生成：** 檢查API密鑰是否正確設定
2. **說話者不匹配：** 確保文字中的說話者名稱與配置完全相同
3. **風格效果不明顯：** 嘗試更具體的情感描述或選擇更適合的語音
4. **文字被截斷：** 將長文本分割成較短的段落分別處理

### 效能最佳化

- 使用批次模式處理大量請求
- 選擇適合用途的模型（Flash vs Pro）
- 合理利用上下文快取功能

