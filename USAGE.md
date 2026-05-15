# LIS 投資系統 — 使用指南

> Ryan 的 Life Is Shit 投資系統 — 每天 8AM 自動推播決策卡，21:25 推美股盤前。
> 整套設計：你只要看 LINE 就知道該做什麼。

---

## 🌅 每天會自動發生什麼

| 時間 | 任務 | 內容 |
|---|---|---|
| 08:00 | LIS_Daily_Report | 全套晨報 6 張卡（**今日行動卡 = 第 1 張**）|
| 09:00 | LIS_Health_Check | 系統自查 + 排程異常推播 |
| 09:00 | LIS_TW_Morning | 台股盤前 |
| 13:30 | LIS_TW_Close | 台股收盤總結 |
| 21:25 | LIS_Order_Reminder_US | **今夜美股行動卡** + 待掛單提醒 |
| 22:30 | LIS_US_Premarket | 美股盤前 |
| 00:00 | LIS_US_Midnight | 美股盤中 |
| 03:00 | LIS_US_3am | 美股盤後 |

## 🎯 「今日行動卡」內容（6 色語意系統）
- 🔴 **必做**：達 +15% 停利 / 破 -5%-3% 停損
- 🔵 **已掛單**：pending_orders 等成交
- 🟡 **預警**：接近停利/停損
- 🟠 **不該追**：過熱別追加
- 🟢 **資金流入**：T+2 即將入帳
- 🟣 **累計已實現**：本月/本季/今年 (US + TW)
- ⚠️ **震盪預警**：F&G 連 5+ 天極端
- ❌ **資金不適合**：戰法不適合你的資金等級

---

## 🛠️ 手動工具（隨時可用）

### `check_scam.py` — 反詐騙快速檢查
```powershell
# 直接傳文字
python check_scam.py "跟我學年化 300%，加 LINE 私訊報名"

# 傳檔案
python check_scam.py 林大投顧.txt

# 從剪貼簿讀（複製文字後直接跑）
python check_scam.py
```
紅旗 ≥ 3 → 自動推 LINE 警告

### `check_conviction.py` — 把握度折扣快算
系統算「該買 200 股」，但你只有 7 成把握 → 套折扣算實際買幾股
```powershell
python check_conviction.py SATL 7 75 8.60
# 結果：把握 7 成 → 實際買 52 股 @ $8.60 = $447.20
```

### `python -m modules.sylvie_csv_importer` — 太太對帳單匯入
```powershell
python -m modules.sylvie_csv_importer 太太對帳單.csv --dry  # 先 dry run 看效果
python -m modules.sylvie_csv_importer 太太對帳單.csv         # 正式匯入（會自動備份舊版）
```
支援券商：國泰 / 元大 / 永豐（自動偵測欄位）

### `python -m modules.health_audit` — 系統健康檢查
```powershell
python -m modules.health_audit          # 只在終端印
python -m modules.health_audit --push   # 有異常推 LINE
```
每天 9:00 自動跑一次。

### `python -m modules.factor_lab` — 多因子回測
```powershell
python -m modules.factor_lab
```
找出對你最有效的因子權重（需累積 10+ 筆已平倉訊號才能跑）

---

## 📁 重要檔案

| 檔案 | 用途 | 改了要注意 |
|---|---|---|
| `API/portfolio.json` | 你的部位 + 現金 + pending | 買賣後手動更新 |
| `API/.env` | API keys | **絕對不上傳 git** |
| `API/watchlist.json` | 觀察清單 69 檔 | 加 watchlist 改這個 |
| `數據/sylvie_portfolio.json` | 太太對帳單 | 用 csv_importer 更新 |
| `數據/sim_ledger.db` | 訊號歷史（給 factor_lab）| 系統自動寫 |
| `數據/cache/fg_history.json` | F&G 歷史（給震盪預警）| 系統自動寫 |

## 🚨 常見狀況 SOP

### 收到「破停損」必做卡
1. 開 LINE 看 → 點開今日行動卡
2. 第 1 個必做項 = 該全停損
3. 確認 → 開券商 app 掛市價單

### 收到「達 +15% 停利」必做卡
1. 按 Strategy D：賣 50%（卡上會算好賣多少股）
2. 國泰整買零賣下單，掛限價
3. 系統自動加進 pending_settlement，T+2 入帳

### 收到「震盪預警」
- 黃燈：留意過熱別追高
- 紅燈（連 10+ 天）：減碼 / 拉高閒錢比 / 停利優先

### 8AM 沒收到推播
1. 開 PowerShell 跑 `python -m modules.health_audit`
2. 看 logs：`D:\LIS股票投資系統\數據\logs\run_2026-MM-DD.log`
3. 8AM carousel 400 = 已修（line_push 自動淨化空 text）

### 想加觀察新股
1. 改 `API/watchlist.json` 加進去
2. 隔天 8AM 會自動納入分析

### Sylvie 寄新對帳單來
1. 存成 CSV：`D:\LIS股票投資系統\數據\sylvie_2026MMDD.csv`
2. `python -m modules.sylvie_csv_importer 數據/sylvie_2026MMDD.csv`
3. 隔天系統會自動比對「太太動態」推 LINE

---

## ⚙️ 排程修改

排程在 Windows 工作排程器 (Task Scheduler)，搜尋 `LIS*`

新增 / 修改 / 暫停：
```powershell
# 列全部
Get-ScheduledTask -TaskName "LIS*"

# 暫停某個
Disable-ScheduledTask -TaskName "LIS_TW_Morning"

# 重啟
Enable-ScheduledTask -TaskName "LIS_TW_Morning"
```

---

## 🎨 設計哲學（永遠優先）

1. **今日行動卡 = 主角**，其他卡是參考
2. **操作直覺優先**：賣多少股、多少錢、預估落袋
3. **美股晚場用同邏輯**：21:25 一張行動卡
4. **反 CC 機制**：系統自查 + Claude 持續找盲點
5. **智能進化**：給新資料 → 系統學 → 給判斷建議

---

## 📞 系統指令快速查

| 指令 | 用途 |
|---|---|
| `python push_今日行動.py` | 手動推一張今日行動卡 |
| `python LIS全套晨報.py` | 跑完整 6 張卡晨報 |
| `python -m modules.health_audit` | 系統健診 |
| `python check_scam.py "<文字>"` | 反詐 |
| `python check_conviction.py <symbol> <把握度>` | 把握度折扣 |
| `python -m modules.sylvie_csv_importer <csv>` | Sylvie CSV |
| `python -m modules.factor_lab` | 多因子回測 |

---

## 雲端版

見 [DEPLOY.md](DEPLOY.md) — 45 分鐘部署到 Streamlit Cloud。
