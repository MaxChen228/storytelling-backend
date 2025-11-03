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
   - GCS bucket，例如 `gs://storytelling-output/output`，產生機已透過 `gsutil rsync` 將輸出同步至此。
   - `.env` 或部署環境已設定 `GEMINI_API_KEY`、`GOOGLE_TRANSLATE_PROJECT_ID` 等必要密鑰。
4. 本機可成功執行 `./run.sh` 並將產出上傳至 bucket。

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
  --set-env-vars GOOGLE_TRANSLATE_PROJECT_ID=new-pro-463006 \
  --set-env-vars GOOGLE_TRANSLATE_LOCATION=global
```

- 若暫不啟用翻譯，可移除最後兩行 `--set-env-vars`。
- 初次啟動會同步整個 bucket，實測至少需 1GB 記憶體；如日誌出現 `Memory limit ... exceeded`，請提高 `--memory` 或精簡資料量。

部署成功後會得到 Service URL，例如 `https://storytelling-backend-service-1034996974388.asia-east1.run.app`。

## 驗證並提供給前端

```bash
SERVICE_URL=https://storytelling-backend-service-1034996974388.asia-east1.run.app
curl -s ${SERVICE_URL}/health          # 應回傳 {"status":"ok"}
curl -s ${SERVICE_URL}/books | head    # 應列出 GCS 中的書籍
```

確認以上結果後，即可通知前端將 `SERVICE_URL` 作為 API base URL。

## 服務帳號與權限

- Cloud Run 預設使用 `<PROJECT_NUMBER>-compute@developer.gserviceaccount.com`。
- 必要角色：
  - `roles/storage.objectViewer`（讀取 GCS bucket）。
  - `roles/cloudtranslate.user`（若啟用翻譯）。
- 可在 bucket 層級授權：

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
  - **記憶體不足**：日誌出現 `Memory limit ... exceeded` → 提高 `--memory` 或縮減同步檔案。
  - **403 權限不足**：`GCSMirror` 報錯 → 確認服務帳號已授予 `storage.objectViewer` 且 IAM 變更已生效。

- 建議在 Cloud Console → Cloud Run 啟用 Metrics 與 Alert，監控錯誤率、延遲、記憶體。

## 維運流程

### 更新映像與回滾

```bash
docker buildx build --platform linux/amd64 -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/storytelling-backend/storytelling-backend:latest --push .
gcloud run deploy ${SERVICE_NAME} --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/storytelling-backend/storytelling-backend:latest --region=${REGION} --allow-unauthenticated --memory=4Gi --cpu=2 --timeout=900 --set-env-vars DATA_ROOT=gs://storytelling-output/output,STORYTELLING_GCS_CACHE_DIR=/tmp/storytelling-output,GOOGLE_TRANSLATE_PROJECT_ID=new-pro-463006,GOOGLE_TRANSLATE_LOCATION=global
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
