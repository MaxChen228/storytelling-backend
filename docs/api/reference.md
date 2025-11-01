# API 參考文檔

Storytelling Backend REST API 完整參考。

## 基本信息

**Base URL:** `http://localhost:8000`

**版本:** 0.1.0

**認證:** 部分端點需要 Bearer Token

**內容類型:** `application/json`

## 快速開始

### 啟動 API 服務器

```bash
# 開發模式
uvicorn server.app.main:app --reload --host 0.0.0.0 --port 8000

# 生產模式
uvicorn server.app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 訪問 API 文檔

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## 端點概覽

### 公開端點

| 方法 | 端點 | 描述 |
|------|------|------|
| `GET` | `/health` | 健康檢查 |
| `GET` | `/books` | 獲取所有書籍 |
| `GET` | `/books/{book_id}` | 獲取單本書籍 |
| `GET` | `/books/{book_id}/chapters` | 獲取章節列表 |
| `GET` | `/books/{book_id}/chapters/{chapter_id}` | 獲取章節詳情 |
| `GET` | `/books/{book_id}/chapters/{chapter_id}/audio` | 下載音頻 |
| `GET` | `/books/{book_id}/chapters/{chapter_id}/subtitles` | 下載字幕 |
| `POST` | `/translations` | 翻譯文本 |

### 管理端點（需要認證）

| 方法 | 端點 | 描述 |
|------|------|------|
| `GET` | `/admin/tasks` | 獲取任務列表 |
| `POST` | `/admin/tasks` | 提交新任務 |
| `GET` | `/admin/tasks/{task_id}` | 獲取任務詳情 |
| `GET` | `/admin/tasks/{task_id}/log` | 獲取任務日誌 |

---

## 公開端點

### 健康檢查

檢查 API 服務是否運行。

```http
GET /health
```

**響應:**

```json
{
  "status": "ok"
}
```

---

### 獲取所有書籍

獲取系統中所有可用書籍的列表。

```http
GET /books
```

**響應:**

```json
[
  {
    "id": "foundation",
    "title": "Foundation"
  },
  {
    "id": "dune",
    "title": "Dune"
  }
]
```

**響應字段:**

| 字段 | 類型 | 描述 |
|------|------|------|
| `id` | string | 書籍唯一標識符 |
| `title` | string | 書籍標題 |

---

### 獲取單本書籍

獲取特定書籍的詳細信息。

```http
GET /books/{book_id}
```

**路徑參數:**

| 參數 | 類型 | 必需 | 描述 |
|------|------|------|------|
| `book_id` | string | ✅ | 書籍 ID |

**響應:**

```json
{
  "id": "foundation",
  "title": "Foundation"
}
```

**響應頭:**

- `ETag`: 實體標籤，用於緩存驗證

**錯誤碼:**

- `404 Not Found` - 書籍不存在

---

### 獲取章節列表

獲取指定書籍的所有章節。

```http
GET /books/{book_id}/chapters
```

**路徑參數:**

| 參數 | 類型 | 必需 | 描述 |
|------|------|------|------|
| `book_id` | string | ✅ | 書籍 ID |

**響應:**

```json
[
  {
    "id": "chapter0",
    "title": "Chapter 0",
    "chapter_number": 0,
    "audio_available": true,
    "subtitles_available": true,
    "word_count": 1123,
    "audio_duration_sec": 456.78,
    "words_per_minute": 147.5
  },
  {
    "id": "chapter1",
    "title": "Chapter 1",
    "chapter_number": 1,
    "audio_available": false,
    "subtitles_available": false,
    "word_count": null,
    "audio_duration_sec": null,
    "words_per_minute": null
  }
]
```

**響應字段:**

| 字段 | 類型 | 描述 |
|------|------|------|
| `id` | string | 章節唯一標識符 |
| `title` | string | 章節標題 |
| `chapter_number` | integer \| null | 章節編號 |
| `audio_available` | boolean | 音頻是否可用 |
| `subtitles_available` | boolean | 字幕是否可用 |
| `word_count` | integer \| null | 字數統計 |
| `audio_duration_sec` | float \| null | 音頻時長（秒） |
| `words_per_minute` | float \| null | 語速（詞/分鐘） |

**錯誤碼:**

- `404 Not Found` - 書籍不存在

---

### 獲取章節詳情

獲取特定章節的完整播放信息。

```http
GET /books/{book_id}/chapters/{chapter_id}
```

**路徑參數:**

| 參數 | 類型 | 必需 | 描述 |
|------|------|------|------|
| `book_id` | string | ✅ | 書籍 ID |
| `chapter_id` | string | ✅ | 章節 ID |

**響應:**

```json
{
  "id": "chapter0",
  "title": "Chapter 0",
  "chapter_number": 0,
  "audio_url": "/books/foundation/chapters/chapter0/audio",
  "subtitles_url": "/books/foundation/chapters/chapter0/subtitles",
  "word_count": 1123,
  "audio_duration_sec": 456.78,
  "words_per_minute": 147.5
}
```

**響應字段:**

| 字段 | 類型 | 描述 |
|------|------|------|
| `id` | string | 章節唯一標識符 |
| `title` | string | 章節標題 |
| `chapter_number` | integer \| null | 章節編號 |
| `audio_url` | string \| null | 音頻下載 URL（相對路徑） |
| `subtitles_url` | string \| null | 字幕下載 URL（相對路徑） |
| `word_count` | integer \| null | 字數統計 |
| `audio_duration_sec` | float \| null | 音頻時長（秒） |
| `words_per_minute` | float \| null | 語速（詞/分鐘） |

**響應頭:**

- `ETag`: 實體標籤，用於緩存驗證

**錯誤碼:**

- `404 Not Found` - 書籍或章節不存在

---

### 下載音頻

下載章節音頻文件（支持斷點續傳）。

```http
GET /books/{book_id}/chapters/{chapter_id}/audio
```

**路徑參數:**

| 參數 | 類型 | 必需 | 描述 |
|------|------|------|------|
| `book_id` | string | ✅ | 書籍 ID |
| `chapter_id` | string | ✅ | 章節 ID |

**請求頭:**

| 頭部 | 描述 |
|------|------|
| `Range` | 支持範圍請求（斷點續傳）<br>格式：`bytes=0-1023` |

**響應:**

**狀態碼 200 (完整下載):**

- `Content-Type`: `audio/wav` 或 `audio/mpeg`
- `Content-Length`: 文件大小（字節）
- `Accept-Ranges`: `bytes`
- `ETag`: 文件 ETag

**狀態碼 206 (部分內容):**

- `Content-Range`: `bytes 0-1023/5000`（已發送範圍/總大小）
- `Content-Length`: 部分內容大小
- `Accept-Ranges`: `bytes`
- `ETag`: 文件 ETag

**示例:**

```bash
# 完整下載
curl -o chapter0.wav http://localhost:8000/books/foundation/chapters/chapter0/audio

# 範圍請求（斷點續傳）
curl -H "Range: bytes=1000000-" -o chapter0.wav http://localhost:8000/books/foundation/chapters/chapter0/audio
```

**錯誤碼:**

- `404 Not Found` - 章節或音頻不存在
- `416 Range Not Satisfiable` - 範圍請求無效

---

### 下載字幕

下載章節字幕文件（SRT 格式）。

```http
GET /books/{book_id}/chapters/{chapter_id}/subtitles
```

**路徑參數:**

| 參數 | 類型 | 必需 | 描述 |
|------|------|------|------|
| `book_id` | string | ✅ | 書籍 ID |
| `chapter_id` | string | ✅ | 章節 ID |

**響應:**

**狀態碼 200:**

- `Content-Type`: `text/plain; charset=utf-8`
- `Content-Disposition`: `inline; filename="foundation_chapter0.srt"`
- `ETag`: 文件 ETag

**示例響應:**

```srt
1
00:00:00,000 --> 00:00:02,500
In the previous episode

2
00:00:02,500 --> 00:00:05,100
we explored the concept of psychohistory
```

**錯誤碼:**

- `404 Not Found` - 章節或字幕不存在

---

### 翻譯文本

翻譯指定文本（使用 Google Translation API）。

```http
POST /translations
```

**請求體:**

```json
{
  "text": "In the previous episode, we explored the concept of psychohistory.",
  "target_language": "zh-TW",
  "source_language": "en",
  "book_id": "foundation",
  "chapter_id": "chapter0",
  "subtitle_id": 1
}
```

**請求字段:**

| 字段 | 類型 | 必需 | 描述 |
|------|------|------|------|
| `text` | string | ✅ | 要翻譯的文本（1-5000 字符） |
| `target_language` | string | - | 目標語言代碼（默認：zh-TW） |
| `source_language` | string | - | 源語言代碼（自動檢測） |
| `book_id` | string | - | 書籍 ID（用於緩存鍵） |
| `chapter_id` | string | - | 章節 ID（用於緩存鍵） |
| `subtitle_id` | integer | - | 字幕 ID（用於緩存鍵） |

**支持的語言代碼:**

- `en` - 英語
- `zh-TW` - 繁體中文
- `zh-CN` - 簡體中文
- `ja` - 日語
- `ko` - 韓語
- `es` - 西班牙語
- `fr` - 法語
- `de` - 德語
- 更多語言見 [Google Cloud Translation 文檔](https://cloud.google.com/translate/docs/languages)

**響應:**

```json
{
  "translated_text": "在上一集中，我們探討了心理史學的概念。",
  "detected_source_language": "en",
  "cached": false
}
```

**響應字段:**

| 字段 | 類型 | 描述 |
|------|------|------|
| `translated_text` | string | 翻譯後的文本 |
| `detected_source_language` | string \| null | 檢測到的源語言 |
| `cached` | boolean | 是否從緩存返回 |

**錯誤碼:**

- `400 Bad Request` - 請求參數無效
- `502 Bad Gateway` - 翻譯服務錯誤
- `503 Service Unavailable` - 翻譯服務未配置

---

## 管理端點

所有管理端點都需要認證。

### 認證

使用 Bearer Token 認證：

```http
Authorization: Bearer your_api_token_here
```

**配置 API Token:**

```bash
# 在環境變量中設置
export API_TOKEN=your_secret_token

# 或在配置文件中設置
# server/config.yaml
api_token: "your_secret_token"
```

---

### 獲取任務列表

獲取所有後台任務的列表。

```http
GET /admin/tasks
```

**請求頭:**

```http
Authorization: Bearer your_api_token
```

**響應:**

```json
[
  {
    "id": "task_20250101_120000_abc123",
    "task_type": "generate_script",
    "status": "succeeded",
    "book_id": "foundation",
    "chapters": ["chapter0", "chapter1"],
    "created_at": "2025-01-01T12:00:00Z",
    "updated_at": "2025-01-01T12:05:00Z",
    "log_path": "/path/to/log"
  }
]
```

**響應字段:**

| 字段 | 類型 | 描述 |
|------|------|------|
| `id` | string | 任務唯一標識符 |
| `task_type` | string | 任務類型（見下表） |
| `status` | string | 任務狀態（見下表） |
| `book_id` | string \| null | 書籍 ID |
| `chapters` | string[] | 章節 ID 列表 |
| `created_at` | datetime | 創建時間 |
| `updated_at` | datetime | 更新時間 |
| `log_path` | string \| null | 日誌文件路徑 |

**任務類型:**

- `generate_script` - 生成腳本
- `generate_audio` - 生成音頻
- `generate_subtitles` - 生成字幕

**任務狀態:**

- `pending` - 等待中
- `running` - 運行中
- `succeeded` - 成功
- `failed` - 失敗

**錯誤碼:**

- `401 Unauthorized` - 缺少或無效的 Token
- `403 Forbidden` - Token 不正確

---

### 提交新任務

提交後台任務以生成腳本、音頻或字幕。

```http
POST /admin/tasks
```

**請求頭:**

```http
Authorization: Bearer your_api_token
Content-Type: application/json
```

**請求體:**

```json
{
  "task_type": "generate_script",
  "book_id": "foundation",
  "chapters": ["chapter0", "chapter1"],
  "config_path": "/path/to/podcast_config.yaml",
  "force": false,
  "env_overrides": {
    "PODCAST_SCRIPT_BATCH_SIZE": "10"
  }
}
```

**請求字段:**

| 字段 | 類型 | 必需 | 描述 |
|------|------|------|------|
| `task_type` | string | ✅ | 任務類型 |
| `book_id` | string | - | 書籍 ID |
| `chapters` | string[] | - | 章節 ID 列表 |
| `config_path` | string | - | 配置文件路徑 |
| `force` | boolean | - | 強制重新生成（默認：false） |
| `env_overrides` | object | - | 環境變量覆寫 |

**響應:**

```json
{
  "id": "task_20250101_120000_abc123",
  "task_type": "generate_script",
  "status": "pending",
  "book_id": "foundation",
  "chapters": ["chapter0", "chapter1"],
  "created_at": "2025-01-01T12:00:00Z",
  "updated_at": "2025-01-01T12:00:00Z",
  "log_path": null,
  "result": null,
  "error": null
}
```

**錯誤碼:**

- `400 Bad Request` - 請求參數無效
- `401 Unauthorized` - 缺少或無效的 Token
- `403 Forbidden` - Token 不正確

---

### 獲取任務詳情

獲取特定任務的詳細信息和結果。

```http
GET /admin/tasks/{task_id}
```

**路徑參數:**

| 參數 | 類型 | 必需 | 描述 |
|------|------|------|------|
| `task_id` | string | ✅ | 任務 ID |

**請求頭:**

```http
Authorization: Bearer your_api_token
```

**響應:**

```json
{
  "id": "task_20250101_120000_abc123",
  "task_type": "generate_script",
  "status": "succeeded",
  "book_id": "foundation",
  "chapters": ["chapter0", "chapter1"],
  "created_at": "2025-01-01T12:00:00Z",
  "updated_at": "2025-01-01T12:05:00Z",
  "log_path": "/path/to/log",
  "result": {
    "chapters_processed": 2,
    "success_count": 2,
    "failed_count": 0
  },
  "error": null
}
```

**錯誤碼:**

- `401 Unauthorized` - 缺少或無效的 Token
- `403 Forbidden` - Token 不正確
- `404 Not Found` - 任務不存在

---

### 獲取任務日誌

獲取任務執行的日誌輸出。

```http
GET /admin/tasks/{task_id}/log
```

**路徑參數:**

| 參數 | 類型 | 必需 | 描述 |
|------|------|------|------|
| `task_id` | string | ✅ | 任務 ID |

**請求頭:**

```http
Authorization: Bearer your_api_token
```

**響應:**

**狀態碼 200:**

- `Content-Type`: `text/plain; charset=utf-8`

**示例響應:**

```
[2025-01-01 12:00:00] Task started: generate_script
[2025-01-01 12:00:05] Processing chapter0...
[2025-01-01 12:02:30] Chapter0 completed successfully
[2025-01-01 12:02:31] Processing chapter1...
[2025-01-01 12:05:00] Chapter1 completed successfully
[2025-01-01 12:05:00] Task completed: 2/2 succeeded
```

**錯誤碼:**

- `401 Unauthorized` - 缺少或無效的 Token
- `403 Forbidden` - Token 不正確
- `404 Not Found` - 任務不存在或日誌不可用

---

## 錯誤響應格式

所有錯誤響應都遵循標準格式：

```json
{
  "detail": "Error message here"
}
```

**HTTP 狀態碼:**

| 狀態碼 | 描述 |
|--------|------|
| `200 OK` | 請求成功 |
| `201 Created` | 資源已創建 |
| `206 Partial Content` | 部分內容（範圍請求） |
| `304 Not Modified` | 資源未修改（ETag 匹配） |
| `400 Bad Request` | 請求參數無效 |
| `401 Unauthorized` | 缺少認證 |
| `403 Forbidden` | 權限不足 |
| `404 Not Found` | 資源不存在 |
| `416 Range Not Satisfiable` | 範圍請求無效 |
| `500 Internal Server Error` | 服務器錯誤 |
| `502 Bad Gateway` | 上游服務錯誤 |
| `503 Service Unavailable` | 服務不可用 |

---

## 緩存策略

### ETag 支持

以下端點支持 ETag 緩存驗證：

- `GET /books/{book_id}`
- `GET /books/{book_id}/chapters/{chapter_id}`
- `GET /books/{book_id}/chapters/{chapter_id}/audio`
- `GET /books/{book_id}/chapters/{chapter_id}/subtitles`

**使用示例:**

```bash
# 第一次請求
curl -i http://localhost:8000/books/foundation
# HTTP/1.1 200 OK
# ETag: "abc123..."

# 條件請求
curl -H 'If-None-Match: "abc123..."' http://localhost:8000/books/foundation
# HTTP/1.1 304 Not Modified（如果資源未改變）
```

### CORS 支持

API 支持跨域請求（CORS）。

**配置:**

```bash
# 環境變量
export CORS_ORIGINS="http://localhost:3000,https://your-frontend.com"

# 或在配置文件中
cors_origins:
  - "http://localhost:3000"
  - "https://your-frontend.com"
```

---

## 限制與配額

### 翻譯 API

- 單次請求最大長度：5000 字符
- 默認緩存大小：256 條翻譯
- 緩存過期時間：基於 LRU 策略

### 音頻流

- 支持範圍請求（HTTP Range）
- 支持斷點續傳
- 自動 GZip 壓縮（最小 1KB）

---

## 開發工具

### cURL 示例

```bash
# 獲取書籍列表
curl http://localhost:8000/books

# 獲取章節詳情
curl http://localhost:8000/books/foundation/chapters/chapter0

# 下載音頻
curl -o chapter0.wav http://localhost:8000/books/foundation/chapters/chapter0/audio

# 翻譯文本
curl -X POST http://localhost:8000/translations \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","target_language":"zh-TW"}'

# 管理員 - 獲取任務列表
curl -H "Authorization: Bearer your_token" \
  http://localhost:8000/admin/tasks
```

### Python 客戶端

查看 [使用範例](examples.md) 了解完整的 Python 客戶端代碼。

---

## 下一步

- 查看 [API 使用範例](examples.md) 了解實際使用方法
- 查看 [部署指南](../operations/deployment.md) 了解生產環境配置
- 查看 [故障排除](../operations/troubleshooting.md) 解決常見問題

## 需要幫助？

- 📖 查看 [Swagger UI](http://localhost:8000/docs) 交互式文檔
- 🐛 [報告 API 問題](https://github.com/your-org/storytelling-backend/issues)
- 💬 [API 討論](https://github.com/your-org/storytelling-backend/discussions)
