# syntax=docker/dockerfile:1

# 基底映像採用官方 Python slim，降低體積
FROM python:3.12-slim AS base

# 設定非互動模式避免 tzdata 等套件安裝時等待輸入
ENV DEBIAN_FRONTEND=noninteractive

# 建置階段安裝必要系統套件（pip 需要 git/編譯工具時使用）
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       curl \
       git \
    && rm -rf /var/lib/apt/lists/*

# 建立工作目錄
WORKDIR /app

# 提前複製依賴檔，讓 Docker layer cache 能在程式碼變動時重用已安裝的套件
COPY requirements/ ./requirements/
COPY requirements.txt ./

# 安裝伺服器所需依賴
RUN pip install --no-cache-dir -r requirements/server.txt

# 複製伺服器程式碼以及需要的資源
COPY server/ ./server/
COPY docs/ ./docs/
COPY podcast_config.yaml ./podcast_config.yaml

# 若 FastAPI 服務會讀取版本資訊，可在此加入 git metadata (可選)
# ARG GIT_SHA=unknown
# ENV GIT_SHA=${GIT_SHA}

# Cloud Run 預設使用 8080 port
ENV PORT=8080

# 啟動指令使用 uvicorn 服務 FastAPI 應用
CMD ["uvicorn", "server.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
