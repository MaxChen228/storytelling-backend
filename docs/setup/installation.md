# 安裝指南

完整的環境設置和依賴安裝指南。

## 系統需求

### 最低需求
- Python 3.12 或更高版本
- 至少 4GB RAM
- 至少 5GB 磁盤空間（用於模型和輸出文件）
- macOS、Linux 或 Windows（建議使用 macOS/Linux）

### 推薦配置
- Python 3.12+
- 8GB+ RAM
- 20GB+ 磁盤空間
- macOS（M1/M2/M3）或 Linux

## 快速安裝

### 1. 克隆倉庫

```bash
git clone <your-repo-url>
cd storytelling-backend
```

### 2. 創建虛擬環境

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows:**
```cmd
python -m venv .venv
.venv\Scripts\activate
```

### 3. 安裝依賴

```bash
# 安裝核心依賴
pip install --upgrade pip
pip install -r requirements/base.txt

# 如果需要運行 API 服務器
pip install -r requirements/server.txt
```

### 4. 配置環境變量

創建 `.env` 文件：
```bash
cp .env.example .env  # 如果有提供範本
# 或直接創建
echo "GEMINI_API_KEY=your_api_key_here" > .env
```

**必需的環境變量：**
```env
# Gemini API（必需）
GEMINI_API_KEY=your_gemini_api_key

# GCS 認證（必需，用於讀取輸出資料）
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

### 5. 驗證安裝

```bash
# 測試 Gemini API 連接
python test_api.py

# 啟動 CLI（應該能看到交互式菜單）
./run.sh
```

## 詳細安裝步驟

### Python 環境

#### 檢查 Python 版本
```bash
python3 --version
# 應該顯示 Python 3.12.x 或更高
```

#### 如果版本過舊

**macOS (使用 Homebrew):**
```bash
brew install python@3.12
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip
```

**使用 pyenv (推薦):**
```bash
# 安裝 pyenv
curl https://pyenv.run | bash

# 安裝 Python 3.12
pyenv install 3.12.0
pyenv local 3.12.0
```

### Montreal Forced Aligner (MFA)

MFA 用於生成詞級精準字幕。使用 micromamba 進行安裝。

#### 安裝 micromamba

**macOS:**
```bash
brew install micromamba
```

**Linux:**
```bash
"${SHELL}" <(curl -L micro.mamba.pm/install.sh)
```

#### 設置 MFA 環境

```bash
# 創建 MFA 環境
micromamba create -n aligner montreal-forced-aligner -c conda-forge

# 下載模型
micromamba run -n aligner mfa model download dictionary english_mfa
micromamba run -n aligner mfa model download acoustic english_mfa
```

#### 驗證 MFA 安裝

```bash
micromamba run -n aligner mfa version
# 應該顯示 MFA 版本信息
```

#### 配置 MFA 路徑

確保 `podcast_config.yaml` 中的路徑正確：
```yaml
alignment:
  mfa:
    micromamba_bin: "/opt/homebrew/opt/micromamba/bin/micromamba"  # macOS
    # 或 "/usr/local/bin/micromamba"  # Linux
    env_name: "aligner"
```

查找 micromamba 路徑：
```bash
which micromamba
```

### API 金鑰設置

#### Gemini API

1. 前往 [Google AI Studio](https://aistudio.google.com/app/apikey)
2. 創建新的 API 金鑰
3. 複製金鑰並添加到 `.env`

```env
GEMINI_API_KEY=AIzaSy...
```

## 依賴說明

### 核心依賴 (requirements/base.txt)

| 套件 | 版本 | 用途 |
|------|------|------|
| google-genai | latest | Gemini API 客戶端 |
| pydantic | ^2.0 | 數據驗證 |
| pyyaml | latest | 配置文件解析 |
| python-dotenv | latest | 環境變量管理 |
| pydub | latest | 音頻處理 |

### 服務器依賴 (requirements/server.txt)

| 套件 | 版本 | 用途 |
|------|------|------|
| fastapi | ^0.104 | Web 框架 |
| uvicorn | latest | ASGI 服務器 |

### 可選依賴

```bash
# 開發工具
pip install pytest pytest-cov black ruff
```

## 故障排除

### 問題 1: `python3: command not found`

**解決方法：**
```bash
# 嘗試使用 python
python --version

# 或安裝 Python 3
# macOS
brew install python@3.12

# Ubuntu/Debian
sudo apt install python3.12
```

### 問題 2: `pip install` 失敗

**解決方法：**
```bash
# 升級 pip
pip install --upgrade pip setuptools wheel

# 使用國內鏡像（如果在中國）
pip install -r requirements/base.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 問題 3: MFA 安裝失敗

**解決方法：**
```bash
# 清除現有環境
micromamba env remove -n aligner

# 重新創建
micromamba create -n aligner montreal-forced-aligner -c conda-forge
```

### 問題 4: `ModuleNotFoundError: No module named 'google.genai'`

**解決方法：**
```bash
# 確認虛擬環境已激活
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# 重新安裝依賴
pip install -r requirements/base.txt
```

### 問題 5: `GEMINI_API_KEY not found`

**解決方法：**
```bash
# 確認 .env 文件存在
ls -la .env

# 確認內容格式正確（無空格）
cat .env
# 應該是：GEMINI_API_KEY=AIza...
# 不是：GEMINI_API_KEY = AIza...
```

### 問題 6: Permission denied: `./run.sh`

**解決方法：**
```bash
# 添加執行權限
chmod +x run.sh

# 然後運行
./run.sh
```

## 平台特定說明

### macOS (Apple Silicon M1/M2/M3)

某些依賴可能需要 Rosetta 2：
```bash
# 安裝 Rosetta 2（如果需要）
softwareupdate --install-rosetta
```

### Windows

**使用 WSL2（推薦）：**
```bash
# 在 PowerShell（管理員）中啟用 WSL
wsl --install

# 安裝 Ubuntu
wsl --install -d Ubuntu-22.04

# 然後在 WSL 中按照 Linux 步驟安裝
```

**原生 Windows：**
- 確保使用 `python` 而非 `python3`
- 路徑使用反斜槓 `\` 或雙斜槓 `\\`
- 某些功能（如 MFA）可能需要額外配置

### Linux

**Ubuntu/Debian:**
```bash
# 安裝系統依賴
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip ffmpeg
```

**CentOS/RHEL:**
```bash
# 安裝系統依賴
sudo yum install python3 python3-pip ffmpeg
```

## Docker 安裝（高級）

如果您熟悉 Docker，可以使用容器化部署：

```bash
# 構建映像
docker build -t storytelling-backend .

# 運行容器
docker run -it --rm \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/output:/app/output \
  -e GEMINI_API_KEY=your_key \
  storytelling-backend
```

查看 [部署指南](../operations/deployment.md#docker-部署) 了解詳情。

## 下一步

安裝完成後，請查看：
- [配置說明](configuration.md) - 了解如何配置系統
- [工作流程指南](../usage/workflow.md) - 開始生成您的第一個播客
- [CLI 使用指南](../usage/cli-guide.md) - 熟悉命令行界面

## 需要幫助？

- 📖 查看 [故障排除指南](../operations/troubleshooting.md)
- 🐛 [報告安裝問題](https://github.com/your-org/storytelling-backend/issues)
- 💬 [社群討論](https://github.com/your-org/storytelling-backend/discussions)
