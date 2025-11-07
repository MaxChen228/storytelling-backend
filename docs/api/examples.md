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
