# LIS 完整雲端遷移指南（Phase 39 — Vultr 台灣）

## 🎯 目標
把整套 LIS 系統從本機（Windows）搬到 Vultr 台灣 VPS（Ubuntu），
24h 不關機、不靠 user 電腦運作。

## 💰 月費：US$ 6 ≈ NT$ 200

---

## 📋 預先準備（5 分鐘）

### 1. Vultr 註冊
- 打開 https://www.vultr.com/
- 註冊帳號（用 GitHub 或 Email）
- 加信用卡

### 2. 開一台 VM
- Products → Deploy Instance
- Server Type: **Cloud Compute - High Performance**
- Location: **Taiwan / Taipei**（如果沒有，選 Tokyo）
- OS: **Ubuntu 22.04 LTS x64**
- Plan: **$6/month** (1 vCPU / 1GB RAM / 25GB SSD)
- Hostname: `lis-server`
- 開機後拿到：
  - **IP address**（例如 `45.32.10.123`）
  - **root password**

### 3. (可選) 買域名
- 不買也可以 — 用 Vultr 給的 IP 也行
- 想要的話 NameCheap / Cloudflare Registrar 都可以
- 例如 `lis.your-domain.com` → 設定 A record 指 VPS IP

---

## 🚀 一鍵安裝（在 VPS 上跑）

### 步驟 1: SSH 連線到 VPS
從本機（Windows PowerShell）：
```bash
ssh root@你的VPS_IP
# 輸入 root password
```

### 步驟 2: 跑一鍵安裝腳本
```bash
curl -sSL https://raw.githubusercontent.com/LISInvestmentux/lis-cloud-dashboard/main/migrate_to_cloud.sh -o migrate_to_cloud.sh
chmod +x migrate_to_cloud.sh
sudo ./migrate_to_cloud.sh
```

腳本會自動：
1. 裝 Python 3.11, git, nginx, certbot, ufw
2. clone lis-cloud-dashboard repo 到 `/opt/lis`
3. 建立 venv + 裝所有 requirements
4. 設定 ufw 防火牆（只開 22/80/443 port）
5. 提示你輸入 secrets（LINE_CHANNEL_SECRET, ACCESS_TOKEN, 等）
6. 設定 systemd service for webhook（24h 不掛）
7. 設定 nginx reverse proxy
8. 申請 Let's Encrypt SSL（如果有域名）
9. 設定 cron jobs（取代 Windows Task Scheduler）
10. 跑一次健康檢查推播驗證

跑完約 5-10 分鐘。

---

## 📦 搬遷資料（從本機到 VPS）

腳本跑完後，用 `scp` 從本機把資料推到 VPS：

```powershell
# 從本機 Windows
$VPS_IP = "你的VPS_IP"

# 推 portfolio.json
scp "D:\LIS股票投資系統\API\portfolio.json" root@${VPS_IP}:/opt/lis/API/

# 推 watchlist.json
scp "D:\LIS股票投資系統\API\watchlist.json" root@${VPS_IP}:/opt/lis/API/

# 推數據資料夾（持股快取/Sylvie 等）
scp -r "D:\LIS股票投資系統\數據" root@${VPS_IP}:/opt/lis/

# 推 KOL sources
scp "D:\LIS股票投資系統\API\kol_sources.json" root@${VPS_IP}:/opt/lis/API/
```

---

## 🔧 設定 LINE Webhook

1. 打開 LINE Developers Console: https://developers.line.biz/console/
2. 進 **LIS Investment** Provider → 你的 Messaging Channel
3. **Messaging API** → **Webhook URL**:
   - 有域名: `https://lis.你的-domain.com/webhook`
   - 沒域名: `https://你的VPS_IP/webhook`（要先給 IP 申請 SSL）
4. ✓ Use webhook 開
5. 按 Verify

---

## ✅ 驗證一切正常

### 1. 看 webhook server 狀態
```bash
sudo systemctl status lis-webhook
# 應該看到 active (running)
```

### 2. 看 cron 排程
```bash
crontab -l
# 應該看到 ~10 條 LIS_* 排程
```

### 3. 看 health endpoint
打開 `https://你的-domain.com/health` 或 `https://VPS_IP/health`

### 4. 試推今日行動卡
```bash
cd /opt/lis
source .venv/bin/activate
python -m modules.daily_5cards
# LINE 應收到 3 張主卡
```

### 5. 點主卡按鈕 → 應該 1 秒內收到細節卡 ✅

---

## 🛑 關閉本機所有排程

一切順利後，回到本機關閉 Windows Task Scheduler：

```powershell
# 列出所有 LIS_* 排程
Get-ScheduledTask -TaskName "LIS_*"

# 全部停用（不刪除，以防需要回頭）
Get-ScheduledTask -TaskName "LIS_*" | Disable-ScheduledTask
```

本機可正常用電腦做別的事，LIS 完全在雲端跑。

---

## 🆘 萬一出問題

### 看 log
```bash
# Webhook server log
sudo journalctl -u lis-webhook -f

# Cron job log
tail -f /var/log/lis/cron.log

# Nginx log
sudo tail -f /var/log/nginx/error.log
```

### 回滾
```bash
# 把本機 Task Scheduler 重啟
Get-ScheduledTask -TaskName "LIS_*" | Enable-ScheduledTask

# VPS 上停掉 systemd
sudo systemctl stop lis-webhook
sudo systemctl disable lis-webhook
```

本機 D:\LIS股票投資系統 完整保留，可隨時切回來。

---

## 📊 預期效益

| 項目 | 本機 | Vultr |
|------|------|-------|
| 24h 在線 | ❌ | ✅ |
| LINE webhook 回應 | N/A | < 1 秒 |
| 出國/停電影響 | 全停 | 零 |
| 月費 | $0 | NT$ 200 |
| 維運 | 你自己 | Claude 可遠端幫忙 |
