# LIS Streamlit Cloud 雲端部署指南

## 為什麼要雲端
- 電腦壞了 LIS 也能看 ✅
- 手機隨時看 dashboard ✅
- 排程仍在本機跑（推 LINE），雲端只負責「儀表板可看」

## 部署步驟（45 分鐘）

### Step 1: 建立 portfolio.json 私密 Gist（10 分鐘）
1. 去 https://gist.github.com
2. 把 `D:\LIS股票投資系統\API\portfolio.json` 內容貼進去
3. **務必選「Secret Gist」**（不要 Public）
4. 創建後抓 raw URL：點 "Raw" 按鈕 → 複製網址
5. 範例：`https://gist.githubusercontent.com/LISInvestmentux/abc123/raw/portfolio.json`

> ⚠️ Secret Gist 不是真的「秘密」，URL 拿到的人都能看。
> 但因為 URL 隨機 hash，比 public repo 安全。
> 若要更安全，未來改用 AWS S3 + signed URL。

### Step 2: 推 LIS code 到 GitHub（10 分鐘）
1. 在 https://github.com/new 建 repo 名 `lis-cloud-dashboard`，選 Private
2. 在本機跑：
   ```powershell
   cd D:\LIS股票投資系統\程式碼
   git init
   git add .
   git commit -m "LIS 雲端部署版"
   git remote add origin https://github.com/LISInvestmentux/lis-cloud-dashboard.git
   git push -u origin main
   ```
3. `.gitignore` 已經把 `portfolio.json` / `.env` 排除，不會上傳敏感資料 ✅

### Step 3: 連結 Streamlit Cloud（10 分鐘）
1. 去 https://share.streamlit.io
2. 用 GitHub 登入
3. 點「New app」
4. 選 repo `LISInvestmentux/lis-cloud-dashboard`
5. Main file path 填：`streamlit_app.py`
6. App URL 取名：`lis-portfolio`（之後變 `https://lis-portfolio.streamlit.app`）

### Step 4: 設定 Secrets（10 分鐘）
1. 進 Streamlit app 後台 → Settings → Secrets
2. 貼 `.streamlit/secrets.toml.example` 內容
3. 把每行的 `"你的_xxx"` 換成實際值：
   - `LINE_CHANNEL_ACCESS_TOKEN` ← 從 `D:\LIS股票投資系統\API\.env` 找
   - `LINE_USER_ID` ← 同上
   - `GEMINI_API_KEY` ← 同上
   - `FUGLE_API_TOKEN` ← 同上（如有）
   - `PORTFOLIO_GIST_URL` ← Step 1 的 raw URL
4. 按「Save」會自動 redeploy

### Step 5: 驗證（5 分鐘）
1. 開 `https://lis-portfolio.streamlit.app`
2. 應該看到 LIS dashboard（持股/水位/F&G 等）
3. 若顯示「找不到 portfolio.json」→ 檢查 Gist URL 是不是 raw

## 更新流程

### 改程式碼
```powershell
cd D:\LIS股票投資系統\程式碼
git add .
git commit -m "改了 X"
git push
```
Streamlit Cloud 會自動偵測 push 並重新部署（30 秒）

### 改 portfolio（買賣後）
1. 本機改 `D:\LIS股票投資系統\API\portfolio.json`
2. 同步到 Gist：複製 → 貼上 → Save Gist
3. Streamlit app 重新整理即可看到新資料

> 自動化：可以寫個 `sync_to_gist.py` 用 GitHub API 自動推。

## 限制
- Streamlit Cloud 免費版：1 GB RAM / 不能跑背景排程
- 推播 LINE / 抓 yfinance / Gemini 仍在本機排程跑
- 雲端只是「看 dashboard」+「測新功能」
- 若本機壞了 → 至少還能看歷史快照（手動上傳 snapshot）

## 後續可做
- [ ] Phase 33.3 LIFF 整合（手機 LINE 內打開）
- [ ] 雲端排程：用 GitHub Actions cron（每小時拉 yfinance 寫 Gist）
- [ ] 多帳號：Ryan + Sylvie 兩套 dashboard

## 待 Ryan 自己做的事
1. ✅ 建 Secret Gist（私密）
2. ✅ 建 GitHub repo（Private）
3. ✅ 在 Streamlit Cloud 連結 + 設 Secrets
4. ✅ 第一次部署驗證能跑

Claude 已準備好的檔案（不用動）：
- `requirements.txt`
- `.streamlit/config.toml`
- `.streamlit/secrets.toml.example`
- `.gitignore`
- `streamlit_app.py`（雲端入口）
- `web_dashboard.py`（既有的 dashboard）
