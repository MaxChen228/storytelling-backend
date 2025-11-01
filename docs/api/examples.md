# API 使用範例

實際的 API 調用範例（curl、Python、JavaScript）。

## curl 範例

### 基本操作

```bash
# 1. 健康檢查
curl http://localhost:8000/health

# 2. 獲取所有書籍
curl http://localhost:8000/books

# 3. 獲取特定書籍的章節列表
curl http://localhost:8000/books/foundation/chapters

# 4. 獲取章節詳情
curl http://localhost:8000/books/foundation/chapters/chapter0

# 5. 下載音頻
curl -o chapter0.wav \
  http://localhost:8000/books/foundation/chapters/chapter0/audio

# 6. 下載字幕
curl -o chapter0.srt \
  http://localhost:8000/books/foundation/chapters/chapter0/subtitles
```

### 翻譯請求

```bash
curl -X POST http://localhost:8000/translations \
  -H "Content-Type: application/json" \
  -d '{
    "text": "In the previous episode, we explored psychohistory.",
    "target_language": "zh-TW"
  }'
```

### 管理員操作

```bash
# 設置 Token
TOKEN="your_api_token"

# 獲取任務列表
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/admin/tasks

# 提交腳本生成任務
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "generate_script",
    "book_id": "foundation",
    "chapters": ["chapter0", "chapter1"]
  }' \
  http://localhost:8000/admin/tasks

# 獲取任務詳情
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/admin/tasks/task_20250101_120000_abc123

# 獲取任務日誌
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/admin/tasks/task_20250101_120000_abc123/log
```

## Python 範例

### 安裝依賴

```bash
pip install requests
```

### 基本客戶端

```python
import requests

class PodcastAPIClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()

    def get_books(self):
        """獲取所有書籍"""
        response = self.session.get(f"{self.base_url}/books")
        response.raise_for_status()
        return response.json()

    def get_chapters(self, book_id):
        """獲取章節列表"""
        response = self.session.get(
            f"{self.base_url}/books/{book_id}/chapters"
        )
        response.raise_for_status()
        return response.json()

    def get_chapter_detail(self, book_id, chapter_id):
        """獲取章節詳情"""
        response = self.session.get(
            f"{self.base_url}/books/{book_id}/chapters/{chapter_id}"
        )
        response.raise_for_status()
        return response.json()

    def download_audio(self, book_id, chapter_id, output_path):
        """下載音頻文件"""
        url = f"{self.base_url}/books/{book_id}/chapters/{chapter_id}/audio"
        response = self.session.get(url, stream=True)
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    def download_subtitles(self, book_id, chapter_id, output_path):
        """下載字幕文件"""
        url = f"{self.base_url}/books/{book_id}/chapters/{chapter_id}/subtitles"
        response = self.session.get(url)
        response.raise_for_status()

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(response.text)

    def translate(self, text, target_language="zh-TW", **kwargs):
        """翻譯文本"""
        payload = {
            "text": text,
            "target_language": target_language,
            **kwargs
        }
        response = self.session.post(
            f"{self.base_url}/translations",
            json=payload
        )
        response.raise_for_status()
        return response.json()

# 使用示例
client = PodcastAPIClient()

# 獲取書籍列表
books = client.get_books()
print("可用書籍:", books)

# 獲取章節
chapters = client.get_chapters("foundation")
print(f"Foundation 有 {len(chapters)} 個章節")

# 下載音頻和字幕
client.download_audio("foundation", "chapter0", "chapter0.wav")
client.download_subtitles("foundation", "chapter0", "chapter0.srt")

# 翻譯文本
result = client.translate(
    "In the previous episode",
    target_language="zh-TW"
)
print("翻譯結果:", result["translated_text"])
```

### 管理員客戶端

```python
class PodcastAdminClient(PodcastAPIClient):
    def __init__(self, base_url="http://localhost:8000", api_token=None):
        super().__init__(base_url)
        self.api_token = api_token
        if api_token:
            self.session.headers.update({
                "Authorization": f"Bearer {api_token}"
            })

    def list_tasks(self):
        """獲取任務列表"""
        response = self.session.get(f"{self.base_url}/admin/tasks")
        response.raise_for_status()
        return response.json()

    def submit_task(self, task_type, book_id=None, chapters=None, **kwargs):
        """提交任務"""
        payload = {
            "task_type": task_type,
            "book_id": book_id,
            "chapters": chapters or [],
            **kwargs
        }
        response = self.session.post(
            f"{self.base_url}/admin/tasks",
            json=payload
        )
        response.raise_for_status()
        return response.json()

    def get_task(self, task_id):
        """獲取任務詳情"""
        response = self.session.get(
            f"{self.base_url}/admin/tasks/{task_id}"
        )
        response.raise_for_status()
        return response.json()

    def get_task_log(self, task_id):
        """獲取任務日誌"""
        response = self.session.get(
            f"{self.base_url}/admin/tasks/{task_id}/log"
        )
        response.raise_for_status()
        return response.text

# 使用示例
admin_client = PodcastAdminClient(api_token="your_token")

# 提交腳本生成任務
task = admin_client.submit_task(
    task_type="generate_script",
    book_id="foundation",
    chapters=["chapter0", "chapter1"]
)
print("任務已提交:", task["id"])

# 檢查任務狀態
import time
while True:
    task_detail = admin_client.get_task(task["id"])
    print(f"狀態: {task_detail['status']}")

    if task_detail["status"] in ["succeeded", "failed"]:
        break

    time.sleep(5)

# 獲取日誌
log = admin_client.get_task_log(task["id"])
print("任務日誌:")
print(log)
```

## JavaScript/TypeScript 範例

### Fetch API

```javascript
class PodcastAPIClient {
    constructor(baseURL = 'http://localhost:8000') {
        this.baseURL = baseURL;
    }

    async getBooks() {
        const response = await fetch(`${this.baseURL}/books`);
        if (!response.ok) throw new Error('Failed to fetch books');
        return response.json();
    }

    async getChapters(bookId) {
        const response = await fetch(
            `${this.baseURL}/books/${bookId}/chapters`
        );
        if (!response.ok) throw new Error('Failed to fetch chapters');
        return response.json();
    }

    async getChapterDetail(bookId, chapterId) {
        const response = await fetch(
            `${this.baseURL}/books/${bookId}/chapters/${chapterId}`
        );
        if (!response.ok) throw new Error('Failed to fetch chapter');
        return response.json();
    }

    async translate(text, targetLanguage = 'zh-TW') {
        const response = await fetch(`${this.baseURL}/translations`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                text,
                target_language: targetLanguage
            })
        });
        if (!response.ok) throw new Error('Translation failed');
        return response.json();
    }

    getAudioURL(bookId, chapterId) {
        return `${this.baseURL}/books/${bookId}/chapters/${chapterId}/audio`;
    }

    getSubtitlesURL(bookId, chapterId) {
        return `${this.baseURL}/books/${bookId}/chapters/${chapterId}/subtitles`;
    }
}

// 使用示例
const client = new PodcastAPIClient();

// 獲取書籍和章節
async function loadChapter() {
    const books = await client.getBooks();
    console.log('可用書籍:', books);

    const chapters = await client.getChapters('foundation');
    console.log('章節列表:', chapters);

    const chapter = await client.getChapterDetail('foundation', 'chapter0');
    console.log('章節詳情:', chapter);

    // 播放音頻
    const audioURL = client.getAudioURL('foundation', 'chapter0');
    const audio = new Audio(audioURL);
    audio.play();
}

// 翻譯
async function translateText() {
    const result = await client.translate(
        'In the previous episode',
        'zh-TW'
    );
    console.log('翻譯結果:', result.translated_text);
}

loadChapter();
```

### React Hook 示例

```typescript
import { useState, useEffect } from 'react';

interface Chapter {
    id: string;
    title: string;
    audio_url: string | null;
    subtitles_url: string | null;
}

function useChapter(bookId: string, chapterId: string) {
    const [chapter, setChapter] = useState<Chapter | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<Error | null>(null);

    useEffect(() => {
        async function fetchChapter() {
            try {
                const response = await fetch(
                    `http://localhost:8000/books/${bookId}/chapters/${chapterId}`
                );
                if (!response.ok) throw new Error('Failed to fetch');
                const data = await response.json();
                setChapter(data);
            } catch (err) {
                setError(err as Error);
            } finally {
                setLoading(false);
            }
        }

        fetchChapter();
    }, [bookId, chapterId]);

    return { chapter, loading, error };
}

// 使用 Hook
function ChapterPlayer({ bookId, chapterId }) {
    const { chapter, loading, error } = useChapter(bookId, chapterId);

    if (loading) return <div>載入中...</div>;
    if (error) return <div>錯誤: {error.message}</div>;
    if (!chapter) return <div>章節不存在</div>;

    const audioURL = `http://localhost:8000${chapter.audio_url}`;

    return (
        <div>
            <h2>{chapter.title}</h2>
            <audio controls src={audioURL}>
                您的瀏覽器不支持音頻播放
            </audio>
        </div>
    );
}
```

## 完整工作流程範例

### Python: 下載完整書籍

```python
import os
from podcast_client import PodcastAPIClient

def download_book(book_id, output_dir):
    """下載書籍的所有音頻和字幕"""
    client = PodcastAPIClient()

    # 創建輸出目錄
    os.makedirs(output_dir, exist_ok=True)

    # 獲取章節列表
    chapters = client.get_chapters(book_id)
    print(f"找到 {len(chapters)} 個章節")

    for chapter in chapters:
        if not chapter['audio_available']:
            print(f"跳過 {chapter['id']}: 音頻未生成")
            continue

        print(f"下載 {chapter['id']}...")

        # 下載音頻
        audio_path = os.path.join(output_dir, f"{chapter['id']}.wav")
        client.download_audio(book_id, chapter['id'], audio_path)

        # 下載字幕
        if chapter['subtitles_available']:
            srt_path = os.path.join(output_dir, f"{chapter['id']}.srt")
            client.download_subtitles(book_id, chapter['id'], srt_path)

        print(f"✓ {chapter['id']} 完成")

    print("下載完成！")

# 使用
download_book("foundation", "./downloads/foundation")
```

## 錯誤處理範例

### Python

```python
from requests import HTTPError

try:
    client = PodcastAPIClient()
    chapter = client.get_chapter_detail("foundation", "chapter999")
except HTTPError as e:
    if e.response.status_code == 404:
        print("章節不存在")
    elif e.response.status_code == 500:
        print("服務器錯誤")
    else:
        print(f"請求失敗: {e}")
```

### JavaScript

```javascript
try {
    const chapter = await client.getChapterDetail('foundation', 'chapter999');
} catch (error) {
    if (error.message.includes('404')) {
        console.error('章節不存在');
    } else {
        console.error('請求失敗:', error);
    }
}
```

## 下一步

- 查看 [API 參考](reference.md) 了解完整端點列表
- 查看 [前端集成](../../audio-earning-ios/README.md) 了解 iOS 應用如何使用 API
- 查看 [故障排除](../operations/troubleshooting.md) 解決常見問題

## 需要幫助？

- 📖 [API 文檔](reference.md)
- 🐛 [報告問題](https://github.com/your-org/storytelling-backend/issues)
- 💬 [討論區](https://github.com/your-org/storytelling-backend/discussions)
