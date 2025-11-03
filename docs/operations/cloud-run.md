# Cloud Run 部署指南

本文說明如何把 `storytelling-backend` 的 FastAPI 服務部署到 Google Cloud Run，搭配本地 CLI 產生機透過 GCS 同步輸出資料。

## 先決條件

1. 已安裝並登入 Google Cloud CLI：`brew install --cask google-cloud-sdk` → `gcloud auth login`
2. Cloud Project 已啟用 Cloud Run、Cloud Build、Artifact Registry、Cloud Storage
3. 擁有一個用來同步輸出的 GCS bucket，例如 `gs://storytelling-output/output`
4. 本機已能執行 `./run.sh` 並透過 `gsutil rsync -m -d -r -x '.*\.wav$' output gs://storytelling-output/output` 上傳輸出結果

## 容器化 FastAPI 服務

專案根目錄提供 `Dockerfile` 與 `.dockerignore`，會建立一個最小化的 Python 3.12 slim 映像，只包含 `server/` 模組與 `requirements/server.txt` 中的依賴。若需要不同 Python 版本或加上版本資訊，可調整 Dockerfile 中的 `FROM` 與 `CMD`。

先在本機測試映像（需安裝 Docker）：

```bash
docker build -t storytelling-backend:local .
docker run --rm -p 8080:8080 \
  -v "$(pwd)/output:/app/output:ro" \
  -e DATA_ROOT=/app/output \
  storytelling-backend:local

curl http://localhost:8080/health
```

如需測試 GCS 同步，可先將 bucket 內容拉到本機暫存，再以 `DATA_ROOT` 指向該資料夾。

## 建置與推送映像

在專案根目錄執行（首次使用 Artifact Registry 時，需先建立 repository，例如
`gcloud artifacts repositories create storytelling-backend --repository-format=docker --location=${REGION}`）：

```bash
PROJECT_ID=$(gcloud config get-value project)
REGION=asia-east1   # 視需求調整

gcloud auth configure-docker
gcloud builds submit \
  --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/storytelling-backend/storytelling-backend:latest
```

命令會自動建立 Artifact Registry 映像，可透過不同 tag 管理版本。

## 部署到 Cloud Run

```bash
gcloud run deploy storytelling-backend-service \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/storytelling-backend/storytelling-backend:latest \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --set-env-vars DATA_ROOT=gs://storytelling-output/output \
  --set-env-vars STORYTELLING_GCS_CACHE_DIR=/tmp/storytelling-output \
  --set-env-vars GOOGLE_TRANSLATE_PROJECT_ID=${PROJECT_ID} \
  --set-env-vars GOOGLE_TRANSLATE_LOCATION=global
```

> 若暫不啟用翻譯，可從指令中移除最後兩行 `--set-env-vars`。

環境變數說明：

- `DATA_ROOT`：若以 `gs://` 開頭，服務會自動啟用 GCS mirror，把 bucket 內容同步到 `STORYTELLING_GCS_CACHE_DIR`
- `STORYTELLING_GCS_CACHE_DIR`：Cloud Run 容器內的暫存路徑，預設 `/tmp/storytelling-output`
- `GOOGLE_TRANSLATE_PROJECT_ID`／`GOOGLE_TRANSLATE_LOCATION`：設定後才會建立 TranslationService；未設定時翻譯功能保持關閉

部署完成後，終端會顯示公開 URL，可用 `curl https://<service-url>/health` 驗證。

## 設定服務帳號權限

1. 進入 Google Cloud Console → IAM
2. 找到 Cloud Run 服務使用的 Service Account（預設為 `<PROJECT-NUMBER>-compute@developer.gserviceaccount.com`）
3. 加上以下角色：
   - `Storage Object Viewer`（讀取 GCS bucket）
   - `Cloud Translation API User`（若設定 `GOOGLE_TRANSLATE_PROJECT_ID`）
4. 如需限制 bucket 權限，可將角色直接指派在桶子層級（Storage → Browser → Permissions）。

## 驗證流程

1. 本地 CLI 產生新章節 → 自動 `gsutil rsync` 同步到 `gs://storytelling-output/output`
2. Cloud Run 服務在下次請求時會先 mirror GCS → `/books` 應出現最新章節
3. `GET /books/<book_id>/chapters/<chapter_id>/audio` 能串流 MP3（未產生 mp3 時回退使用 wav）
4. 若翻譯開啟，`POST /translations` 應返回翻譯結果

## 維運建議

- 在 Cloud Run 服務設定頁調整 `Minimum number of instances`（0 或 1）與 `Maximum number of instances`（避免暴增費用）
- 啟用 Cloud Logging / Monitoring alert 追蹤錯誤率與延遲
- 定期清理 `/tmp/storytelling-output`（Cloud Run 會在容器重新啟動時自動清空）
- 若 bucket 內容大於數 GB，可考慮在產生機端產出壓縮後再同步，減少同步時間
