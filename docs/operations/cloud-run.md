# Cloud Run 部署與維運指南

本文整合 2025 年 11 月 03 日實際部署經驗，說明如何將 `storytelling-backend` FastAPI 服務部署到 Google Cloud Run，並提供後續維運、監控與回滾流程。

## 先決條件

1. 安裝並登入 Google Cloud CLI：`brew install --cask google-cloud-sdk` → `gcloud auth login`
2. 啟用必要 API（專案只需設定一次）：

   ```bash
   gcloud services enable \
     artifactregistry.googleapis.com \
     cloudbuild.googleapis.com \
     run.googleapis.com \
     storage.googleapis.com
   ```

3. 準備輸入資料來源：
   - GCS bucket，例如 `gs://storytelling-output/output`，建議僅保留必要章節與 metadata。
   - **設定 bucket 為公開讀取**（gcs-public 模式必要）：`gsutil iam ch allUsers:objectViewer gs://storytelling-output`
   - 以 Secret Manager 或環境變數提供 `GEMINI_API_KEY`、`GOOGLE_TRANSLATE_PROJECT_ID`（若啟用翻譯）。
   - 確認 Cloud Run 服務帳號具備 `roles/storage.objectViewer` 權限以讀取物件。
4. 本機可成功執行 `./run.sh`，並透過 `./scripts/sync_output.sh` 將 `output/` 內容同步到 GCS bucket。

### 同步輸出資料

部署前建議先同步本地 `output/` 至雲端。同步指令預設會排除 `.DS_Store`、`sessions/`、`.wav`、`.textgrid` 等非必要檔案（可用 `SYNC_OUTPUT_EXCLUDE` 自訂）：

```bash
./scripts/sync_output.sh            # 預設同步到 storytelling-output
./scripts/sync_output.sh my-bucket  # 指定其他 bucket
```

`deploy.sh` 會在偵測到 `gsutil` 與 `output/` 目錄時自動執行相同的 `gsutil rsync`（含預設排除規則）；若要略過，可於執行前設定 `SKIP_OUTPUT_SYNC=1`。

## 本機建置與驗證容器

專案根目錄已提供 `Dockerfile` 與 `.dockerignore`。建議先在本機確認服務可以啟動：

```bash
docker build -t storytelling-backend:local .
docker run --rm -p 8080:8080 \
  -v "$(pwd)/output:/app/output:ro" \
  -e DATA_ROOT=/app/output \
  storytelling-backend:local

curl http://localhost:8080/health
```

若要測試 GCS 鏡射，可另建本機暫存資料夾並將 `DATA_ROOT` 指向該資料。

> 💡 建議：雲端部署時可將 `MEDIA_DELIVERY_MODE` 設為 `gcs-public`，僅同步 `.json` metadata，音檔與字幕會透過公開 GCS URL 提供，可縮短冷啟動並降低記憶體消耗。

## 推送映像到 Artifact Registry

### 建立（或驗證）Artifact Registry repository

```bash
PROJECT_ID=$(gcloud config get-value project)
REGION=asia-east1

gcloud artifacts repositories describe storytelling-backend --location=${REGION} >/dev/null 2>&1 || \
  gcloud artifacts repositories create storytelling-backend \
    --repository-format=docker \
    --location=${REGION} \
    --description="Storytelling backend container images"

gcloud auth configure-docker ${REGION}-docker.pkg.dev
```

### 建置 `linux/amd64` 映像並推送

> Cloud Run 需要 `linux/amd64`，若在 Apple Silicon 建置須加入 `--platform linux/amd64`。

```bash
docker buildx build \
  --platform linux/amd64 \
  -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/storytelling-backend/storytelling-backend:latest \
  --push .
```

完成後，可確認映像存在與 digest：

```bash
gcloud artifacts docker images list ${REGION}-docker.pkg.dev/${PROJECT_ID}/storytelling-backend
```

> 備案：可改用 `gcloud builds submit`，若遇 `SERVICE_DISABLED` 或權限錯誤，需啟用 Cloud Build API 並確認服務帳號權限。

## 部署至 Cloud Run

```bash
SERVICE_NAME=storytelling-backend-service
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')
REGION=asia-east1

# 確保 Cloud Run 服務帳號能讀取 bucket
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member=serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com \
  --role=roles/storage.objectViewer

gcloud run deploy ${SERVICE_NAME} \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/storytelling-backend/storytelling-backend:latest \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --memory=4Gi \
  --cpu=2 \
  --timeout=900 \
  --set-env-vars DATA_ROOT=gs://storytelling-output/output \
  --set-env-vars STORYTELLING_GCS_CACHE_DIR=/tmp/storytelling-output \
  --set-env-vars MEDIA_DELIVERY_MODE=gcs-public \
  --set-env-vars GCS_MIRROR_INCLUDE_SUFFIXES=.json \
  --set-env-vars GOOGLE_TRANSLATE_PROJECT_ID=new-pro-463006 \
  --set-env-vars GOOGLE_TRANSLATE_LOCATION=global \
  --set-secrets GEMINI_API_KEY=gemini-api-key:latest
```

- 若暫不啟用翻譯，可移除 `GOOGLE_TRANSLATE_*` 兩行。
- 建議保留 `MEDIA_DELIVERY_MODE=gcs-public` 與 `GCS_MIRROR_INCLUDE_SUFFIXES=.json`，僅同步 metadata；若改回 `local` 模式，請確保 Cloud Run 記憶體 ≥4GiB（避免 `Memory limit exceeded`）。

部署成功後會得到 Service URL，例如 `https://storytelling-backend-service-1034996974388.asia-east1.run.app`。

## 驗證並提供給前端

```bash
SERVICE_URL=https://storytelling-backend-service-1034996974388.asia-east1.run.app
curl -s ${SERVICE_URL}/health          # 應回傳 {"status":"ok"}
curl -s ${SERVICE_URL}/books | head    # 應列出 GCS 中的書籍
curl -I ${SERVICE_URL}/books/demo_book/chapters/chapter0/audio  # gcs-public 模式下會回 307
```

確認以上結果後，即可通知前端將 `SERVICE_URL` 作為 API base URL。若 `MEDIA_DELIVERY_MODE=gcs-public`，音檔端點會回傳 307 並提供公開 GCS URL，代表設定成功。

> ✅ 無論本地 (`MEDIA_DELIVERY_MODE=local`) 或雲端 (`gcs-public`/`gcs-signed`)，前端皆透過同樣的 URL 取得封面、圖片、音訊與字幕；差別僅在於本地由後端讀取 `output/`，雲端則轉址到 GCS。

## 服務帳號與權限

- Cloud Run 預設使用 `<PROJECT_NUMBER>-compute@developer.gserviceaccount.com`。
- 必要角色：
  - `roles/storage.objectViewer`（讀取 GCS bucket metadata）。
  - `roles/cloudtranslate.user`（若啟用翻譯）。
- GCS bucket 權限：
  - **bucket 必須設為公開讀取**（gcs-public 模式）：
    ```bash
    gsutil iam ch allUsers:objectViewer gs://storytelling-output
    ```
  - 或在 bucket 層級授權服務帳號：
    ```bash
    gsutil iam ch serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com:objectViewer gs://storytelling-output
    ```

## 日誌、監控與常見問題

- 查看最新日誌：

  ```bash
  gcloud logging read \
    "resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME}" \
    --limit=100 --format="value(timestamp,textPayload)"
  ```

- 常見錯誤排查：
  - **映像架構錯誤**：部署訊息提到 `manifest must support amd64/linux` → 使用 `docker buildx --platform linux/amd64`。
  - **記憶體不足**：日誌出現 `Memory limit exceeded` → 啟用 `MEDIA_DELIVERY_MODE=gcs-public` 或提高 `--memory`、裁剪同步資料量。
  - **403 權限不足**：音檔/字幕無法下載 → 確認 bucket 已設為公開讀取：`gsutil iam get gs://storytelling-output`。
  - **GCSMirror 報錯**：確認服務帳號已授予 `storage.objectViewer` 且 IAM 變更已生效。

- 建議在 Cloud Console → Cloud Run 啟用 Metrics 與 Alert，監控錯誤率、延遲、記憶體。

## 維運流程

### 一鍵部署（推薦）

專案已提供 `deploy.sh` 腳本，可自動完成建置、推送、部署與驗證：

```bash
./deploy.sh
```

腳本會自動執行：
1. 檢查 GCP 環境配置
2. 建置 linux/amd64 Docker 映像並推送
3. 部署到 Cloud Run
4. 驗證服務健康狀態（/health 和 /books 端點）

### 手動更新映像與回滾

```bash
docker buildx build --platform linux/amd64 -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/storytelling-backend/storytelling-backend:latest --push .
gcloud run deploy ${SERVICE_NAME} --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/storytelling-backend/storytelling-backend:latest --region=${REGION} --allow-unauthenticated --memory=4Gi --cpu=2 --timeout=900 --set-env-vars DATA_ROOT=gs://storytelling-output/output,STORYTELLING_GCS_CACHE_DIR=/tmp/storytelling-output,MEDIA_DELIVERY_MODE=gcs-public,GCS_MIRROR_INCLUDE_SUFFIXES=.json,GOOGLE_TRANSLATE_PROJECT_ID=new-pro-463006,GOOGLE_TRANSLATE_LOCATION=global --set-secrets GEMINI_API_KEY=gemini-api-key:latest
```

- 查詢 revision：`gcloud run revisions list --service=${SERVICE_NAME} --region=${REGION}`
- 回滾流量：

  ```bash
  gcloud run services update-traffic ${SERVICE_NAME} \
    --region=${REGION} \
    --to-revisions ${SERVICE_NAME}-00004-zsj=100
  ```

### 調整環境變數 / 縮放

- 更新環境變數：

  ```bash
  gcloud run services update ${SERVICE_NAME} \
    --region=${REGION} \
    --update-env-vars=ALLOW_TRANSLATION=False
  ```

- 縮放設定：
  - `--min-instances=0` → 完全按需付費。
  - `--min-instances=1` → 保持熱身降低冷啟動。
  - `--max-instances` → 限制成本。

### IAM 與自訂網域

- 限制存取：移除 `--allow-unauthenticated`，改以 IAM 指定可呼叫者：

  ```bash
  gcloud run services add-iam-policy-binding ${SERVICE_NAME} \
    --region=${REGION} \
    --member=serviceAccount:<frontend-sa>@${PROJECT_ID}.iam.gserviceaccount.com \
    --role=roles/run.invoker
  ```

- 綁定自訂網域：

  ```bash
  gcloud run domain-mappings create \
    --service=${SERVICE_NAME} \
    --region=${REGION} \
    --domain=api.example.com
  ```

### CI/CD 建議

- 以 Cloud Build Trigger 或 GitHub Actions 自動化 `docker buildx` + `gcloud run deploy`。
- 於 `.github/workflows` 或 `cloudbuild.yaml` 中設定部署步驟，確保主分支更新自動推送。

## 常用檢查指令

- `gcloud run services describe ${SERVICE_NAME} --region=${REGION}`：確認目前 revision、環境變數與 URL。
- `gcloud run services list --region=${REGION}`：查看所有服務。
- `gcloud artifacts docker images list ...`：檢查映像版本。
- `curl ${SERVICE_URL}/health`、`curl ${SERVICE_URL}/books`：快速驗證 API。
- 定期檢視 bucket 容量，必要時清除舊產出或壓縮檔案。

以上流程可確保部署可重現、權限正確，並提供清楚的維運與回滾手冊。
