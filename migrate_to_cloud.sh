#!/bin/bash
# LIS 雲端遷移一鍵腳本（Phase 39）
# 目標：在 Ubuntu 22.04 VPS 上 5-10 分鐘完成 LIS 部署
#
# 用法（在 VPS root 跑）:
#   curl -sSL https://raw.githubusercontent.com/LISInvestmentux/lis-cloud-dashboard/main/migrate_to_cloud.sh -o migrate_to_cloud.sh
#   chmod +x migrate_to_cloud.sh
#   sudo ./migrate_to_cloud.sh

set -e  # 任何錯誤就退出

# ════════════════════════════════════════════
# 設定
# ════════════════════════════════════════════
LIS_DIR="/opt/lis"
LIS_USER="lis"
REPO_URL="https://github.com/LISInvestmentux/lis-cloud-dashboard.git"
PYTHON_VER="3.11"

# 顏色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $*"; }
ok()  { echo -e "${GREEN}[$(date +%H:%M:%S)] ✓${NC} $*"; }
warn(){ echo -e "${YELLOW}[$(date +%H:%M:%S)] ⚠${NC} $*"; }
err() { echo -e "${RED}[$(date +%H:%M:%S)] ✗${NC} $*"; exit 1; }

# ════════════════════════════════════════════
# 預檢
# ════════════════════════════════════════════
log "🔍 預檢..."
[ "$EUID" -ne 0 ] && err "請用 sudo 跑：sudo ./migrate_to_cloud.sh"
[ -f /etc/lsb-release ] && source /etc/lsb-release
[ "${DISTRIB_ID:-}" != "Ubuntu" ] && warn "非 Ubuntu，腳本可能不相容"
ok "OS: ${DISTRIB_DESCRIPTION:-unknown}"

# ════════════════════════════════════════════
# 1. 系統套件
# ════════════════════════════════════════════
log "📦 1/8 安裝系統套件..."
apt update -qq
apt install -y -qq \
    python3.11 python3.11-venv python3-pip \
    git curl nano vim \
    nginx certbot python3-certbot-nginx \
    ufw fail2ban \
    cron tzdata
timedatectl set-timezone Asia/Taipei
ok "系統套件安裝完成"

# ════════════════════════════════════════════
# 2. 防火牆
# ════════════════════════════════════════════
log "🔥 2/8 設定防火牆..."
ufw --force reset > /dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw --force enable
ok "ufw 已啟用（只開 22/80/443）"

# ════════════════════════════════════════════
# 3. 建 lis user + 目錄
# ════════════════════════════════════════════
log "👤 3/8 建立 lis user + 目錄..."
if ! id -u $LIS_USER > /dev/null 2>&1; then
    useradd -m -s /bin/bash $LIS_USER
    ok "user 'lis' 已建立"
else
    ok "user 'lis' 已存在"
fi

mkdir -p $LIS_DIR $LIS_DIR/API $LIS_DIR/數據/{logs,daily,cache}
mkdir -p /var/log/lis

# ════════════════════════════════════════════
# 4. Clone repo
# ════════════════════════════════════════════
log "📥 4/8 Clone lis-cloud-dashboard..."
if [ -d "$LIS_DIR/.git" ]; then
    cd $LIS_DIR
    git pull
    ok "Repo 已存在，git pull 更新"
else
    git clone $REPO_URL $LIS_DIR
    ok "Repo clone 完成"
fi
chown -R $LIS_USER:$LIS_USER $LIS_DIR /var/log/lis

# ════════════════════════════════════════════
# 5. Python venv + 套件
# ════════════════════════════════════════════
log "🐍 5/8 建立 Python venv + 裝套件..."
cd $LIS_DIR
sudo -u $LIS_USER python3.11 -m venv .venv
sudo -u $LIS_USER .venv/bin/pip install --upgrade pip -q
sudo -u $LIS_USER .venv/bin/pip install -r requirements_webhook.txt -q
# 如果有 requirements.txt 也裝（給 daily_5cards 用）
if [ -f requirements.txt ]; then
    sudo -u $LIS_USER .venv/bin/pip install -r requirements.txt -q
fi
ok "Python 環境準備完成"

# ════════════════════════════════════════════
# 6. Secrets 設定
# ════════════════════════════════════════════
log "🔐 6/8 設定 secrets..."
ENV_FILE="$LIS_DIR/API/.env"
if [ ! -f "$ENV_FILE" ]; then
    cat > $ENV_FILE <<EOF
# LIS Cloud .env
# 請填入實際 token（從本機 D:\LIS股票投資系統\API\.env 複製）

LINE_CHANNEL_ID=
LINE_CHANNEL_SECRET=
LINE_CHANNEL_ACCESS_TOKEN=
LINE_USER_ID=

GEMINI_API_KEY=
FUGLE_MARKETDATA_API_KEY=
FUGLE_API_TOKEN=
ALPHA_VANTAGE_API_KEY=
NEWS_API_KEY=

GITHUB_TOKEN=
GIST_ID_PORTFOLIO=
GIST_ID_SYLVIE=

LIFF_URL=https://liff.line.me/2010070081-6wmnysUD

# 雲端配置
LIS_USE_POSTBACK=true
LIS_PORTFOLIO_PATH=$LIS_DIR/API/portfolio.json
EOF
    chown $LIS_USER:$LIS_USER $ENV_FILE
    chmod 600 $ENV_FILE
    warn "secrets 範本已建在 $ENV_FILE"
    warn "請用 nano 編輯填入實際 token：sudo nano $ENV_FILE"
    warn "或從本機 scp 過來覆蓋：scp ../API/.env root@VPS_IP:$ENV_FILE"
else
    ok "secrets 已存在，跳過"
fi

# ════════════════════════════════════════════
# 7. systemd service for webhook
# ════════════════════════════════════════════
log "⚙️ 7/8 設定 systemd service for webhook..."
cat > /etc/systemd/system/lis-webhook.service <<EOF
[Unit]
Description=LIS LINE Bot Webhook Server
After=network.target

[Service]
Type=simple
User=$LIS_USER
WorkingDirectory=$LIS_DIR
Environment="PATH=$LIS_DIR/.venv/bin:/usr/bin:/bin"
Environment="PORT=8000"
EnvironmentFile=$ENV_FILE
ExecStart=$LIS_DIR/.venv/bin/uvicorn webhook_server:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10
StandardOutput=append:/var/log/lis/webhook.log
StandardError=append:/var/log/lis/webhook_err.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable lis-webhook
systemctl start lis-webhook
sleep 2
if systemctl is-active --quiet lis-webhook; then
    ok "lis-webhook systemd service 已啟動"
else
    warn "lis-webhook 啟動失敗，看 log: journalctl -u lis-webhook"
fi

# ════════════════════════════════════════════
# 8. nginx reverse proxy
# ════════════════════════════════════════════
log "🌐 8/8 設定 nginx..."
cat > /etc/nginx/sites-available/lis <<EOF
server {
    listen 80;
    server_name _;

    location /webhook {
        proxy_pass http://127.0.0.1:8000/webhook;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Line-Signature \$http_x_line_signature;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }

    location / {
        proxy_pass http://127.0.0.1:8000/;
    }
}
EOF

ln -sf /etc/nginx/sites-available/lis /etc/nginx/sites-enabled/lis
rm -f /etc/nginx/sites-enabled/default
nginx -t > /dev/null && systemctl reload nginx
ok "nginx reverse proxy 設定完成"

# ════════════════════════════════════════════
# 9. Cron jobs（取代 Windows Task Scheduler）
# ════════════════════════════════════════════
log "⏰ 額外：設定 cron jobs..."
PYTHON_BIN="$LIS_DIR/.venv/bin/python"
CRON_LOG="/var/log/lis/cron.log"

# 寫進 lis user 的 crontab
sudo -u $LIS_USER bash <<EOF
cat > /tmp/lis_cron <<CRONEOF
# LIS 自動排程（Linux cron 取代 Windows Task Scheduler）
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# 8AM 早晨主推（3 張主卡）
0 8 * * * cd $LIS_DIR && $PYTHON_BIN LIS全套晨報.py >> $CRON_LOG 2>&1

# 美股相關（凌晨）
0 3 * * * cd $LIS_DIR && $PYTHON_BIN push_美股晚場.py >> $CRON_LOG 2>&1
5 4 * * * cd $LIS_DIR && $PYTHON_BIN push_美股覆盤.py >> $CRON_LOG 2>&1

# 美股盤中（晚場）
30 21 * * 1-5 cd $LIS_DIR && $PYTHON_BIN intraday_real_alert.py >> $CRON_LOG 2>&1
30 22 * * 1-5 cd $LIS_DIR && $PYTHON_BIN push_美股晚場.py >> $CRON_LOG 2>&1

# 台股盤中
30 11 * * 1-5 cd $LIS_DIR && $PYTHON_BIN intraday_real_alert.py >> $CRON_LOG 2>&1
0 13 * * 1-5 cd $LIS_DIR && $PYTHON_BIN intraday_real_alert.py >> $CRON_LOG 2>&1
20 13 * * 1-5 cd $LIS_DIR && $PYTHON_BIN push_台股收盤.py >> $CRON_LOG 2>&1

# 健康掃描（9AM）
0 9 * * * cd $LIS_DIR && $PYTHON_BIN -m modules.health_audit --push >> $CRON_LOG 2>&1
CRONEOF
crontab /tmp/lis_cron
rm /tmp/lis_cron
EOF
ok "cron 排程設定完成（8 條）"

# ════════════════════════════════════════════
# 結尾
# ════════════════════════════════════════════
echo ""
echo "════════════════════════════════════════════"
ok "🎉 LIS 雲端遷移完成！"
echo "════════════════════════════════════════════"
echo ""
echo "📊 狀態檢查："
echo "  - Webhook: $(systemctl is-active lis-webhook)"
echo "  - Nginx:   $(systemctl is-active nginx)"
echo "  - Cron:    $(systemctl is-active cron)"
echo ""
echo "🔗 健康檢查："
curl -sS http://localhost/health 2>&1 | head -1
echo ""
echo "📋 下一步："
echo "  1. 編輯 $ENV_FILE 填入實際 LINE token 等"
echo "     sudo nano $ENV_FILE"
echo "  2. 從本機 scp portfolio.json/watchlist.json/數據/ 過來"
echo "  3. 重啟 webhook: sudo systemctl restart lis-webhook"
echo "  4. 設 LINE webhook URL: https://<你的-domain>/webhook"
echo "  5. 申請 SSL（如有域名）: sudo certbot --nginx -d <你的-domain>"
echo ""
echo "📂 重要路徑："
echo "  - 程式碼:    $LIS_DIR"
echo "  - secrets:   $ENV_FILE"
echo "  - 日誌:     /var/log/lis/"
echo "  - cron 設定: sudo -u $LIS_USER crontab -l"
echo ""
