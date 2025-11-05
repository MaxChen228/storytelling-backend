# Assets（資源檔案）功能指南

本指南說明如何在 `storytelling-backend` 中使用 assets 功能，為書籍和章節添加圖片、文檔等靜態資源。

## 概述

Assets 功能允許你為每本書和每個章節添加額外的資源檔案（圖片、文檔、視頻等），並透過 REST API 提供給前端使用。

### 支援的資源類型

- **圖片**: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.svg`
- **文檔**: `.pdf`, `.md`, `.txt`, `.json`
- **多媒體**: `.mp4`, `.webm`, `.mp3`, `.wav`
- **其他**: 任何檔案類型（作為 `application/octet-stream`）

## 目錄結構

### 書籍級別資源

```
output/
  <book_name>/
    assets/              # 書籍資源目錄
      cover.jpg         # 封面圖（會自動包含在 API response）
      cover.png         # 封面圖（替代格式）
      author.jpg        # 作者照片
      description.md    # 書籍簡介
      banner.png        # 橫幅圖
      [其他資源...]
    book_metadata.json
    chapter0/
    chapter1/
```

### 章節級別資源

```
output/
  <book_name>/
    chapter0/
      assets/           # 章節資源目錄
        diagram.png     # 圖表
        illustration.jpg # 插圖
        notes.pdf       # 筆記
        [其他資源...]
      metadata.json
      podcast.mp3
      subtitles.srt
```

## API 端點

### 1. 列出書籍資源

```http
GET /books/{book_id}/assets
```

**Response:**
```json
{
  "assets": ["cover.jpg", "author.jpg", "description.md"]
}
```

### 2. 獲取書籍資源

```http
GET /books/{book_id}/assets/{asset_name}
```

**範例:**
```bash
curl https://api.example.com/books/Foundation/assets/cover.jpg
```

- **本地模式 (local)**: 直接返回檔案內容
- **GCS 公開模式 (gcs-public)**: 返回 307 redirect 到 GCS 公開 URL

### 3. 列出章節資源

```http
GET /books/{book_id}/chapters/{chapter_id}/assets
```

**Response:**
```json
{
  "assets": ["diagram.png", "illustration.jpg"]
}
```

### 4. 獲取章節資源

```http
GET /books/{book_id}/chapters/{chapter_id}/assets/{asset_name}
```

**範例:**
```bash
curl https://api.example.com/books/Foundation/chapters/chapter0/assets/diagram.png
```

## 書籍封面特殊處理

書籍封面會自動包含在書籍列表 API 的回應中，前端無需額外請求：

```http
GET /books
```

**Response:**
```json
[
  {
    "id": "Foundation",
    "title": "Foundation",
    "cover_url": "https://storage.googleapis.com/storytelling-output/output/Foundation/assets/cover.jpg"
  }
]
```

**封面偵測邏輯:**
1. 優先使用 `cover.jpg`
2. 若不存在，使用 `cover.png`
3. 必須放在 `<book_name>/assets/` 目錄下

## 使用範例

### 添加書籍封面

```bash
# 1. 創建 assets 目錄
mkdir -p output/Foundation/assets

# 2. 複製封面圖片
cp path/to/cover.jpg output/Foundation/assets/cover.jpg

# 3. （可選）添加其他資源
cp path/to/description.md output/Foundation/assets/description.md
```

### 添加章節圖表

```bash
# 1. 創建章節 assets 目錄
mkdir -p output/Foundation/chapter0/assets

# 2. 複製圖表
cp path/to/diagram.png output/Foundation/chapter0/assets/diagram.png
```

### 資源同步

部署或共享之前，建議將 `output/` 內容同步到 GCS。同步時會排除 `.DS_Store`、`sessions/`、`.wav`、`.textgrid` 等非必要檔案（可透過環境變數調整）。專案提供了腳本協助：

```bash
./scripts/sync_output.sh            # 預設同步到 storytelling-output bucket
./scripts/sync_output.sh my-bucket  # 指定其他 bucket
```

執行 `deploy.sh` 時，若偵測到 `gsutil` 並存在本地 `output/` 目錄，也會自動呼叫 `gsutil -m rsync -r -x "$SYNC_OUTPUT_EXCLUDE" output gs://${BUCKET}/output`，預設排除 `.DS_Store`、`sessions/`、`.wav`、`.textgrid` 等檔案。若想略過同步，可在執行前設定 `SKIP_OUTPUT_SYNC=1`。

### 前端使用範例

**獲取書籍封面 (方法1 - 推薦):**
```javascript
// 從書籍列表直接獲取
const response = await fetch(`${API_BASE}/books`);
const books = await response.json();
const coverUrl = books[0].cover_url;  // 直接可用
```

**獲取書籍封面 (方法2 - 額外請求):**
```javascript
const coverUrl = `${API_BASE}/books/Foundation/assets/cover.jpg`;
```

**列出並獲取章節資源:**
```javascript
// 1. 列出章節的所有資源
const response = await fetch(`${API_BASE}/books/Foundation/chapters/chapter0/assets`);
const { assets } = await response.json();  // ["diagram.png", "illustration.jpg"]

// 2. 獲取特定資源
const diagramUrl = `${API_BASE}/books/Foundation/chapters/chapter0/assets/diagram.png`;
```

## 本地與雲端的 URL 行為

- 不論是本地 (`MEDIA_DELIVERY_MODE=local`) 或雲端 (`gcs-public`/`gcs-signed`)，API 一律回傳 HTTP URL。前端只需存取 URL，無需關心檔案實際位置。
- 本地模式：URL 指向後端自身的路徑（例如 `http://localhost:8000/books/Foundation/assets/cover.jpg`），FastAPI 會直接讀取 `output/` 目錄中的檔案並串流回應。
- 雲端模式：URL 會 307 轉址到 GCS 公開/簽名連結，Cloud Run 無需下載大型媒體檔。

## GCS 公開模式

當部署到 Cloud Run 並使用 `MEDIA_DELIVERY_MODE=gcs-public` 時：

1. **資料同步**:
   - 建議在部署前先執行 `./scripts/sync_output.sh`
   - `deploy.sh` 會在偵測到 `gsutil` 與 `output/` 目錄時自動同步（可透過 `SKIP_OUTPUT_SYNC=1` 跳過）

2. **公開存取**:
   - Bucket 必須設為公開：`gsutil iam ch allUsers:objectViewer gs://storytelling-output`
   - API 會返回 307 redirect 到 GCS 公開 URL

3. **URL 格式**:
   ```
   https://storage.googleapis.com/storytelling-output/output/<book_name>/assets/<filename>
   https://storage.googleapis.com/storytelling-output/output/<book_name>/<chapter_id>/assets/<filename>
   ```

## 檔案大小與效能建議

- **封面圖**: 建議 < 500KB，解析度 800x1200
- **章節圖表**: 建議 < 1MB
- **文檔**: 建議 < 5MB
- **視頻**: 如需提供視頻，建議使用專門的視頻託管服務（YouTube, Vimeo 等）

## 安全考量

### 本地模式
- 檔案直接從伺服器讀取
- 需確保檔案權限正確

### GCS 公開模式
- 所有資源皆為公開可存取
- 任何擁有 URL 的人都可以下載
- 不適合敏感或版權受保護的內容
- 考慮使用難猜的檔名或定期輪換

## 故障排除

### 資源不顯示

1. **檢查目錄結構**:
   ```bash
   ls -R output/Foundation/assets/
   ```

2. **檢查檔案權限**:
   ```bash
   chmod 644 output/Foundation/assets/*
   ```

3. **檢查 API response**:
   ```bash
   curl http://localhost:8000/books/Foundation/assets
   ```

### GCS 模式 403 錯誤

```bash
# 確認 bucket 權限
gsutil iam get gs://storytelling-output

# 應該看到：
# "members": ["allUsers"]
# "role": "roles/storage.objectViewer"
```

## 相關文檔

- [API Reference](./reference.md) - 完整 API 規格
- [Cloud Run 部署指南](../operations/cloud-run.md) - GCS 模式配置
- [架構設計](../development/architecture.md) - 系統架構說明
