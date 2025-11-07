#!/bin/bash
set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置變數
PROJECT_ID="gen-lang-client-0768448049"
REGION="asia-east1"
SERVICE_NAME="storytelling-backend-service"
REPOSITORY="storytelling-backend"
IMAGE_NAME="storytelling-backend"
BUCKET="storytelling-output"

# 構建完整的映像名稱
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Storytelling Backend 部署腳本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 步驟 1: 檢查環境
echo -e "${YELLOW}[1/6] 檢查環境配置...${NC}"
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
if [ "$CURRENT_PROJECT" != "$PROJECT_ID" ]; then
    echo -e "${RED}錯誤: 當前 GCP 專案 ($CURRENT_PROJECT) 與預期不符 ($PROJECT_ID)${NC}"
    exit 1
fi
echo -e "${GREEN}✓ GCP 專案: $PROJECT_ID${NC}"
echo -e "${GREEN}✓ 區域: $REGION${NC}"
echo ""

# 步驟 2: 同步本地輸出到 GCS（可選）
if [ -n "${SKIP_OUTPUT_SYNC:-}" ]; then
    echo -e "${YELLOW}[2/6] 跳過輸出資料同步 (SKIP_OUTPUT_SYNC 已設置)${NC}"
else
    if command -v gsutil >/dev/null 2>&1; then
        if [ -d "output" ]; then
            EXCLUDE_REGEX="${SYNC_OUTPUT_EXCLUDE:-'.*\\.DS_Store$|^.*/sessions/.*|.*\\.wav$|.*\\.textgrid$'}"
            echo -e "${YELLOW}[2/6] 同步 output/ → gs://${BUCKET}/output...${NC}"
            echo -e "${YELLOW}    排除規則: ${EXCLUDE_REGEX}${NC}"
            gsutil -m rsync -r -x "${EXCLUDE_REGEX}" output "gs://${BUCKET}/output"
            echo -e "${GREEN}✓ 輸出資料同步完成${NC}"
        else
            echo -e "${YELLOW}⚠ output/ 目錄不存在，略過同步${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ 找不到 gsutil，略過輸出資料同步${NC}"
    fi
fi
echo ""

# 步驟 3: 建置 Docker 映像
echo -e "${YELLOW}[3/6] 建置 Docker 映像 (linux/amd64)...${NC}"
docker buildx build \
    --platform linux/amd64 \
    -t "${IMAGE_URI}" \
    --push \
    .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 映像建置並推送成功${NC}"
else
    echo -e "${RED}✗ 映像建置失敗${NC}"
    exit 1
fi
echo ""

# 步驟 4: 驗證映像
echo -e "${YELLOW}[4/6] 驗證映像已推送...${NC}"
gcloud artifacts docker images describe "${IMAGE_URI}" --quiet > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 映像存在於 Artifact Registry${NC}"
else
    echo -e "${RED}✗ 映像驗證失敗${NC}"
    exit 1
fi
echo ""

# 步驟 5: 部署到 Cloud Run
echo -e "${YELLOW}[5/6] 部署到 Cloud Run...${NC}"
gcloud run deploy ${SERVICE_NAME} \
    --image "${IMAGE_URI}" \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --memory=4Gi \
    --cpu=2 \
    --timeout=900 \
    --set-env-vars DATA_ROOT=gs://${BUCKET}/output \
    --set-env-vars STORYTELLING_GCS_CACHE_DIR=/tmp/storytelling-output \
    --set-env-vars MEDIA_DELIVERY_MODE=gcs-public \
    --set-env-vars GCS_MIRROR_INCLUDE_SUFFIXES=.json \
    --set-secrets GEMINI_API_KEY=gemini-api-key:latest \
    --quiet

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 部署成功${NC}"
else
    echo -e "${RED}✗ 部署失敗${NC}"
    exit 1
fi
echo ""

# 步驟 6: 驗證部署
echo -e "${YELLOW}[6/6] 驗證服務健康狀態...${NC}"

# 獲取 Service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --region ${REGION} \
    --format 'value(status.url)' 2>/dev/null)

if [ -z "$SERVICE_URL" ]; then
    echo -e "${RED}✗ 無法獲取 Service URL${NC}"
    exit 1
fi

# 等待服務就緒
echo "等待服務啟動..."
sleep 5

# 測試 health 端點
HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" "${SERVICE_URL}/health")
if [ "$HEALTH_CHECK" = "200" ]; then
    echo -e "${GREEN}✓ Health check 通過 (200)${NC}"
else
    echo -e "${RED}✗ Health check 失敗 (HTTP $HEALTH_CHECK)${NC}"
    exit 1
fi

# 測試 books 端點
BOOKS_CHECK=$(curl -s -o /dev/null -w "%{http_code}" "${SERVICE_URL}/books")
if [ "$BOOKS_CHECK" = "200" ]; then
    echo -e "${GREEN}✓ Books API 正常 (200)${NC}"
else
    echo -e "${YELLOW}⚠ Books API 回應異常 (HTTP $BOOKS_CHECK)${NC}"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}         部署完成！${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${BLUE}Service URL:${NC} ${SERVICE_URL}"
echo -e "${BLUE}Revision:${NC} $(gcloud run revisions list --service=${SERVICE_NAME} --region=${REGION} --limit=1 --format='value(metadata.name)' 2>/dev/null)"
echo ""
echo -e "${YELLOW}快速測試命令:${NC}"
echo "  curl ${SERVICE_URL}/health"
echo "  curl ${SERVICE_URL}/books"
echo ""
