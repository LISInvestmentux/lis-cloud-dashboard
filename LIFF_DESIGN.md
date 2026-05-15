# Phase 33.3 LIFF 整合設計

> 目標：在 LINE 內直接打開「LIS 互動操作」，不用切到瀏覽器

## 為什麼要 LIFF
- 收到 LINE 推播 → 點按鈕直接互動
- 「賣 37 股」按鈕 → 直接套把握度折扣
- 「反詐檢查」上傳截圖 → 直接出結果
- 不用切 app、不用記指令

## LIFF 三個 MVP 功能

### 1. 把握度互動套用（最高頻使用）
- LINE 卡上「賣 37 股」按鈕 → 開 LIFF
- LIFF 頁面：拉桿選把握度 (1-10)
- 按「確認」→ 自動套折扣 → 顯示「實際買/賣 X 股」
- 再按「複製到剪貼簿」→ 貼到券商下單

URL: `liff.line.me/<liffId>/conviction?symbol=SATL&shares=37`

### 2. 反詐騙快查
- LIFF 頁面 → 大文字框
- 貼上要檢查的內容（PDF 截圖、訊息、KOL 摘要）
- 按「分析」→ 7 紅旗報告 + 風險等級
- 可選「推 LINE」存檔

URL: `liff.line.me/<liffId>/scam`

### 3. Sylvie CSV 上傳
- LIFF 頁面 → 拖曳 CSV 檔
- 直接傳到後端 → 跑 sylvie_csv_importer
- 顯示「成功匯入 X 檔，總值 NT$ Y」
- 自動 trigger sylvie_tracker 比對動態

URL: `liff.line.me/<liffId>/sylvie-upload`

## 技術選擇

### 選項 A：純前端 LIFF + 連到雲端 API
- 優點：純 JS，部署在 Streamlit Cloud 旁
- 缺點：要寫 FastAPI/Flask 後端 + CORS
- 工時：1.5 天

### 選項 B：LIFF + Streamlit
- 直接讓 LIFF iframe 包 Streamlit page
- 雲端部署完就能用
- 缺點：Streamlit 內無法直接拿 LINE userId
- 工時：4 小時

### 選項 C：Rich Menu + Postback（最簡單）
- 不用 LIFF，純用 LINE Rich Menu
- 按鈕觸發 Postback → 後端 webhook → 推結果
- 缺點：互動受限（不能輸入長文字）
- 工時：1 天

## Phase 33.3 建議順序

### Step 1 — 先做選項 C（Rich Menu）
**最低成本驗證 user 是否真會用互動功能**
- Rich Menu 6 格：
  - 把握度查 / 反詐 / Sylvie / 今日行動 / 持股 / 設定
- 不寫前端，純後端處理 Postback
- 1 天搞定

### Step 2 — 若 user 真常用，再做 LIFF（選項 A）
**互動更豐富**
- 把握度拉桿 / 文字框 / 檔案上傳
- 需要 webhook server（不能 Streamlit Cloud）
- 用 Railway / Render 部署 FastAPI

## 前置作業（給 Ryan）

### 申請 LIFF（10 分鐘）
1. 去 LINE Developers Console
2. 你的 LIS Provider → Messaging API channel
3. LIFF tab → Add → 填：
   - LIFF app name: LIS 互動
   - Size: Full
   - Endpoint URL: 雲端 URL（先填 placeholder）
4. 抓 LIFF ID（liff.line.me/XXXXXXX-XXXXXXX）

### Rich Menu 設計（30 分鐘）
1. 用 LINE Official Account Manager
2. Rich Menu → 設計圖 → 上傳
3. 設 6 個 tap area：
   - Tap 1-3：推 Postback `action=conviction` 等
   - Tap 4-6：開 LIFF URL（之後做）

## 待 Claude 做（雲端 ready 後）

1. `liff/index.html` — LIFF 入口（路由分頁）
2. `liff/conviction.html` — 把握度拉桿
3. `liff/scam.html` — 反詐文字框
4. `liff/sylvie-upload.html` — CSV 拖曳
5. `api/main.py` — FastAPI server
6. `api/routes/` — 對應 3 個功能 endpoint

## 未來擴充（Phase 33.4+）

- 看 8AM 推播後直接在 LIFF 「打勾完成」/「跳過」
- 持股紀錄即時調整（不用改 portfolio.json）
- Sylvie 動態雙頁版面（你 vs 她）
- 即時 chat：問 Claude 「我該賣 X 嗎」直接秒回

## 開發順序
1. 雲端先部署（Phase 33.2）→ DEPLOY.md
2. Rich Menu MVP（不用 LIFF）
3. LIFF 把握度頁（高 ROI）
4. LIFF 反詐頁
5. LIFF Sylvie 上傳頁
