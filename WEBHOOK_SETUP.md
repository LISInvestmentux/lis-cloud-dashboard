# LIS LINE Bot Webhook 部署指南（Phase 38）

## 🎯 目標
讓 LINE 主卡上的按鈕點下去 → 自動推一張「詳細卡」到 LINE chat
（取代不順的 LIFF redirect）

## 📦 已準備的檔案
- `webhook_server.py` — FastAPI webhook handler
- `modules/daily_5cards_detail.py` — 3 張細節卡 builder
- `requirements_webhook.txt` — Webhook 需要的 Python 套件
- `render.yaml` — Render 部署設定
- `modules/daily_5cards.py` — 已改為 postback button（按 `LIS_USE_POSTBACK=true`）

## 🚀 部署步驟（10 分鐘）

### 1. 註冊 Render（免費）
打開 https://render.com → 用 GitHub 帳號登入

### 2. 連接 GitHub repo
- 點 New → Web Service
- Connect repository: 選 `lis-cloud-dashboard`
- Render 會自動讀 `render.yaml`

### 3. 設定環境變數（Render Dashboard）
在 Render service 設定頁加 3 個 secret env vars：
```
LINE_CHANNEL_SECRET = (從 LINE Developers Console 的 "LIS Investment" Provider 拿)
LINE_CHANNEL_ACCESS_TOKEN = (同 .env 裡的值)
LINE_USER_ID = (Ryan 的 LINE user id)
```

> 提示：所有值都在你電腦的 `D:\LIS股票投資系統\API\.env` 裡，複製過去即可。

### 4. 部署
按 Deploy → 等 2-3 分鐘 build
完成後拿到 URL，例如：`https://lis-webhook.onrender.com`

### 5. 驗證部署
打開 `https://lis-webhook.onrender.com/health`
應看到：`{"status":"healthy", "secret_set":true, "token_set":true}`

### 6. 設定 LINE webhook URL
1. 打開 LINE Developers Console: https://developers.line.biz/console/
2. 進 "LIS Investment" Provider → 你的 Messaging Channel
3. Messaging API 分頁 → Webhook settings
4. **Webhook URL**: `https://lis-webhook.onrender.com/webhook`
5. ✓ **Use webhook** 開啟
6. 按 Verify 確認連通

### 7. 測試
- 本機跑 `python -m modules.daily_5cards` 推一張新版主卡到 LINE
- 點任何一個黃色按鈕（如「📈 看每檔詳細」）
- **30 秒內**應該收到對應的「詳細卡」（Render free tier 第一次 cold start 較慢）

## ⚠️ 免費 Tier 限制
- Render free 15 分鐘沒流量會 sleep
- 第一次喚醒 cold start 約 30-60 秒
- LINE 會 retry 3 次（5s/15s/30s），第 2-3 次應該會成功
- 想免 cold start → 設 UptimeRobot 每 10 分鐘 ping `/health`

## 🔧 環境變數開關
本機 daily_5cards 預設用 postback。如要切回 LIFF：
```bash
LIS_USE_POSTBACK=false python -m modules.daily_5cards
```
