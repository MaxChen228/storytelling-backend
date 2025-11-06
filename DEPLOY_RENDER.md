# Render 部署指南

本指南說明如何將 Storytelling Backend 部署到 Render.com。

---

## 📋 前置準備

### 1. 準備 Google Service Account JSON

確認你有以下檔案：
```bash
secrets/google-translate-service-account.json
```

此檔案需要具備以下權限：
- ✅ `storage.objects.get` - 讀取 GCS 物件
- ✅ `storage.objects.list` - 列出 GCS 物件
- ✅ `cloudtranslate.translations.translate` - Google Translate API

### 2. 確認 GEMINI_API_KEY

從你的 `.env` 檔案取得：
```bash
GEMINI_API_KEY=your_actual_api_key_here
```

⚠️ **重要**：請勿將真實 API Key 提交到 Git！

---

## 🚀 部署步驟

### 步驟 1：推送到 GitHub

```bash
# 確認所有修改已完成
git status

# 加入新檔案
git add render.yaml .renderignore .github/workflows/keep-render-warm.yml

# 提交修改
git commit -m "Add Render deployment configuration"

# 推送到 GitHub
git push origin main
```

### 步驟 2：在 Render 建立服務

1. 前往 https://render.com （如果沒有帳號請先註冊）

2. 點選 **"New +"** → **"Web Service"**

3. 連結 GitHub repository：
   - 授權 Render 訪問你的 GitHub
   - 選擇 `storytelling-backend` repository

4. Render 會自動偵測 `render.yaml`：
   - Service Name: `storytelling-backend`
   - Environment: `Docker`
   - Plan: `Free`
   - 點選 **"Create Web Service"**

### 步驟 3：設定環境變數（敏感資訊）

部署會先失敗，因為缺少敏感環境變數。前往 Render Dashboard：

1. 點選你的服務 **"storytelling-backend"**

2. 前往 **"Environment"** 頁籤

3. 加入以下環境變數：

   | Key | Value |
   |-----|-------|
   | `GEMINI_API_KEY` | `your_actual_gemini_api_key` |

4. 點選 **"Save Changes"**

### 步驟 4：上傳 Secret File

1. 在同一個頁面，向下捲動到 **"Secret Files"** 區塊

2. 點選 **"Add Secret File"**

3. 設定：
   - **Filename**: `gcs-service-account.json`
   - **Contents**: 貼上你的 `secrets/google-translate-service-account.json` 內容
   - **Mount Path**: `/etc/secrets/gcs-service-account.json`

4. 點選 **"Save Changes"**

5. 再加入一個環境變數：
   | Key | Value |
   |-----|-------|
   | `GOOGLE_APPLICATION_CREDENTIALS` | `/etc/secrets/gcs-service-account.json` |

6. 點選 **"Save Changes"**，Render 會自動重新部署

### 步驟 5：等待部署完成

部署約需 3-5 分鐘：
- 查看 **"Logs"** 頁籤觀察進度
- 等待狀態變為 **"Live"**（綠色）

### 步驟 6：驗證部署

部署成功後，Render 會提供一個 URL（例如 `https://storytelling-backend.onrender.com`）

測試各個端點：

```bash
# 1. Health check
curl https://storytelling-backend.onrender.com/health
# 預期輸出：{"status":"ok"}

# 2. Books API
curl https://storytelling-backend.onrender.com/books
# 預期輸出：書籍列表 JSON

# 3. 測試特定書籍
curl https://storytelling-backend.onrender.com/books/Foundation/chapters
# 預期輸出：Foundation 章節列表

# 4. 測試翻譯 API
curl -X POST https://storytelling-backend.onrender.com/translations \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello","target_language":"zh-TW"}'
# 預期輸出：{"translated_text":"你好",...}
```

---

## 🔥 設定保持溫暖（避免冷啟動）

Render Free Tier 會在 15 分鐘無流量後進入 sleep 狀態。我們已經設定 GitHub Actions 自動 ping。

### 啟用 GitHub Actions Workflow

1. 前往你的 GitHub repository

2. 點選 **"Actions"** 頁籤

3. 如果看到 workflow 被禁用，點選 **"I understand my workflows, go ahead and enable them"**

4. 找到 **"Keep Render Service Warm"** workflow

5. 點選 **"Run workflow"** 測試（可選）

6. 確認每 10 分鐘自動執行：
   - 查看 **"Actions"** 頁籤
   - 應該看到定期執行的記錄

**注意**：GitHub Actions 免費帳號有 2,000 分鐘/月的額度，我們的 workflow 每月使用不到 50 分鐘，完全免費。

---

## 📊 監控與日誌

### 查看即時日誌

1. Render Dashboard → 你的服務 → **"Logs"** 頁籤
2. 選擇 **"Live Logs"** 查看即時輸出

### 查看部署歷史

1. Render Dashboard → 你的服務 → **"Events"** 頁籤
2. 可以看到所有部署記錄和狀態

### 查看效能指標

1. Render Dashboard → 你的服務 → **"Metrics"** 頁籤
2. 可以看到：
   - CPU 使用率
   - 記憶體使用率
   - 回應時間
   - 請求數量

---

## 🔄 後續更新

當你修改程式碼後：

```bash
git add .
git commit -m "Your commit message"
git push origin main
```

Render 會**自動偵測並重新部署**（約 3-5 分鐘）

---

## 🐛 常見問題

### 1. 部署失敗：GCS 連線錯誤

**錯誤訊息**：
```
google.api_core.exceptions.Forbidden: 403 Access Denied
```

**解決方案**：
- 確認 Secret File 已正確上傳
- 確認 `GOOGLE_APPLICATION_CREDENTIALS` 環境變數指向正確路徑
- 確認 Service Account 有 Storage Object Viewer 權限

### 2. 冷啟動時間過長

**現象**：首次訪問等待 25 秒

**解決方案**：
- 確認 GitHub Actions workflow 已啟用
- 檢查 Actions 頁籤，確認每 10 分鐘執行
- 如果仍有問題，可額外使用 UptimeRobot（免費）

### 3. 記憶體不足

**錯誤訊息**：
```
Error: Container killed due to memory usage
```

**解決方案**：
- 檢查 `GCS_MIRROR_INCLUDE_SUFFIXES=.json` 是否設定正確
- 確認只下載 JSON 檔案，不下載音訊
- 如果問題持續，考慮升級到 Starter Plan ($7/月，512MB → 2GB）

### 4. 環境變數未生效

**解決方案**：
- 修改環境變數後需要**手動重新部署**
- 點選 **"Manual Deploy"** → **"Clear build cache & deploy"**

---

## 💰 成本估算

### Free Tier 額度

- ✅ 750 小時/月（足夠 24/7 運行）
- ✅ 無限頻寬
- ✅ 自動 SSL 證書
- ⚠️ 15 分鐘無流量後 sleep（已用 GitHub Actions 解決）

### 升級選項（如果需要）

| Plan | 月費 | 記憶體 | 優點 |
|------|------|--------|------|
| **Free** | $0 | 512MB | 適合個人使用 |
| **Starter** | $7 | 2GB | 無 sleep，更多記憶體 |
| **Standard** | $25 | 4GB | 生產環境建議 |

**目前建議**：保持 Free Plan，使用 GitHub Actions 保持溫暖。

---

## 📱 更新 iOS App 的 API URL

部署完成後，需要更新 iOS app 的 API base URL：

```swift
// 原本（Cloud Run）
let baseURL = "https://storytelling-backend-service-xxxxx-uc.a.run.app"

// 更新為（Render）
let baseURL = "https://storytelling-backend.onrender.com"
```

---

## 🔙 回滾到 Cloud Run

如果需要回滾到 Cloud Run：

```bash
# 恢復原本的 Dockerfile
git checkout HEAD~1 -- Dockerfile

# 使用原本的部署腳本
./deploy-cloudrun.sh
```

---

## ✅ 部署檢查清單

- [ ] GitHub repository 已推送最新程式碼
- [ ] Render 服務已建立並連結 GitHub
- [ ] `GEMINI_API_KEY` 環境變數已設定
- [ ] GCS Service Account JSON 已上傳為 Secret File
- [ ] `GOOGLE_APPLICATION_CREDENTIALS` 環境變數已設定
- [ ] 部署狀態為 "Live"（綠色）
- [ ] Health check 端點回應 200
- [ ] Books API 端點回應正常
- [ ] GitHub Actions workflow 已啟用並執行
- [ ] iOS app 的 API URL 已更新

---

## 📞 需要協助？

- Render 官方文檔：https://render.com/docs
- Render 社群論壇：https://community.render.com
- GitHub Issues：https://github.com/your-repo/issues
