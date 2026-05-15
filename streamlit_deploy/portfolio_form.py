"""
L.I.S 持股配置表單（雲端版 / Phase 2.7b-1）
跑在 Streamlit Cloud：https://share.streamlit.io

跟本機版的差異：
- 不寫入檔案系統（雲端是無狀態的）
- 用 st.session_state 暫存
- 提供「下載 JSON」按鈕讓使用者存到自己電腦
- 字型用 Noto Sans CJK（透過 packages.txt 安裝）
"""
import json
import io
from datetime import datetime

import streamlit as st

from modules import chart_generator


# ─── 頁面設定 ───
LIS_LOGO_URL = "https://files.catbox.moe/g9quk5.png"
LIFF_ID = "2010070081-6wmnysUD"

st.set_page_config(
    page_title="L.I.S 持股配置",
    page_icon=LIS_LOGO_URL,
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─── LIFF SDK：自動拿 LINE 身分（Phase 2.7c-2）───
import streamlit.components.v1 as components

components.html(f"""
<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="background:#000;color:#FBBF24;font-family:sans-serif;margin:0;padding:8px;">
<div id="liff-status" style="font-size:13px;color:#888;">🔄 載入中...</div>
<script charset="utf-8" src="https://static.line-scdn.net/liff/edge/2/sdk.js"></script>
<script>
function setStatus(html, color) {{
    const el = document.getElementById('liff-status');
    el.innerHTML = html;
    if (color) el.style.color = color;
}}

// 5 秒 timeout：避免 Streamlit iframe 內 LIFF SDK 永遠 hang
const TIMEOUT_MS = 5000;
function withTimeout(p, ms) {{
    return Promise.race([
        p,
        new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), ms))
    ]);
}}

async function initLiff() {{
    try {{
        await withTimeout(liff.init({{ liffId: '{LIFF_ID}' }}), TIMEOUT_MS);
        if (!liff.isInClient()) {{
            setStatus('🌐 瀏覽器開啟（非 LINE）— 可手動填寫', '#888');
            return;
        }}
        const profile = await withTimeout(liff.getProfile(), TIMEOUT_MS);
        setStatus(
            '<img src="' + profile.pictureUrl + '" style="height:24px;border-radius:50%;vertical-align:middle;"> ' +
            '<b style="color:#FBBF24;">' + profile.displayName + '</b> ' +
            '<span style="color:#888;"> 已透過 LINE 自動登入</span>',
            '#FFFFFF'
        );
        sessionStorage.setItem('lis_uid', profile.userId);
        sessionStorage.setItem('lis_name', profile.displayName);
    }} catch (e) {{
        // SDK 在 Streamlit 巢狀 iframe 內常掛起，5 秒後顯示靜態訊息
        setStatus('💡 LIFF 環境受限（Streamlit iframe）— 表單仍可手動使用', '#888');
    }}
}}
initLiff();
</script>
</body></html>
""", height=42)

# 從 query params 讀使用者身分
_uid = st.query_params.get("uid", "")
_name = st.query_params.get("name", "")
if _name:
    import urllib.parse
    _name = urllib.parse.unquote(_name)

# ─── 加入主畫面（PWA / Apple Touch Icon）所需 meta ───
st.markdown(f"""
<link rel="apple-touch-icon" sizes="180x180" href="{LIS_LOGO_URL}">
<link rel="apple-touch-icon" sizes="167x167" href="{LIS_LOGO_URL}">
<link rel="apple-touch-icon" sizes="152x152" href="{LIS_LOGO_URL}">
<link rel="apple-touch-icon" href="{LIS_LOGO_URL}">
<link rel="icon" type="image/png" sizes="512x512" href="{LIS_LOGO_URL}">
<link rel="shortcut icon" href="{LIS_LOGO_URL}">
<meta name="apple-mobile-web-app-title" content="LIS">
<meta name="application-name" content="LIS">
""", unsafe_allow_html=True)

# ─── 方舟黑黃 CSS（手機優先）───
st.markdown("""
<style>
.stApp { background-color: #000000; }
section.main > div { background-color: #000000; padding-top: 1rem; }
h1, h2, h3, h4, p, label, span, div { color: #FFFFFF !important; }
.stTextInput input, .stNumberInput input {
    background-color: #0F0F14 !important;
    color: #FFFFFF !important;
    border: 1.5px solid #2A2A35 !important;
    border-radius: 12px !important;
    font-size: 18px !important;
    height: 52px !important;
    padding: 12px 16px !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: #FBBF24 !important;
    box-shadow: 0 0 0 3px rgba(251, 191, 36, 0.2) !important;
}
.stSelectbox > div > div {
    background-color: #0F0F14 !important;
    color: #FFFFFF !important;
    border: 1.5px solid #2A2A35 !important;
    border-radius: 12px !important;
    min-height: 52px !important;
}
.stNumberInput button {
    background-color: #1A1A22 !important;
    color: #FBBF24 !important;
    border: none !important;
    width: 36px !important; height: 36px !important;
}
.stTextInput label, .stNumberInput label, .stSelectbox label {
    color: #A0A4B8 !important; font-size: 14px !important;
    font-weight: 600 !important; margin-bottom: 6px !important;
}
.stFormSubmitButton button, .stButton button, .stDownloadButton button {
    background-color: #FBBF24 !important; color: #000000 !important;
    font-weight: 800 !important; font-size: 18px !important;
    height: 56px !important; border: none !important;
    border-radius: 14px !important;
    box-shadow: 0 4px 12px rgba(251, 191, 36, 0.25);
}
.stFormSubmitButton button:hover, .stButton button:hover, .stDownloadButton button:hover {
    background-color: #FFD55E !important; transform: translateY(-1px);
}
.dim { color: #888888 !important; font-size: 13px; }
.gauge-box { background: linear-gradient(180deg, #000 0%, #0A0A12 100%);
             padding: 16px 0 4px 0; border-radius: 16px; }
.divider-yellow { border-top: 1px solid #2A2A35; margin: 20px 0; }
[data-testid="stExpander"] {
    background-color: #0A0A12 !important;
    border: 1px solid #2A2A35 !important;
    border-radius: 12px !important;
}
@media (max-width: 768px) {
    section.main > div { padding-left: 1rem !important; padding-right: 1rem !important; }
    h2 { font-size: 22px !important; }
}
#MainMenu, footer, header { visibility: hidden; }
</style>

<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#000000">
""", unsafe_allow_html=True)


# ─── 預設設定 ───
DEFAULT = {
    "user_name": "",
    "total_capital_twd": 0,
    "current_cash_twd": 0,
    "holdings_value_twd": 0,
    "usd_cash": 0,
    "usd_twd_rate": 32.0,
    "strategy_mode": "balanced",
    "risk_rules": {
        "max_per_stock_pct": 20,
        "min_cash_reserve_pct": 20,
    },
    "deployment_by_enjoy_index": {
        "be_happy_min_score": 70, "be_happy_deploy_pct": 70,
        "wait_min_score": 40, "wait_deploy_pct": 30,
        "hold_deploy_pct": 10,
    },
}

if "portfolio" not in st.session_state:
    st.session_state.portfolio = DEFAULT.copy()
p = st.session_state.portfolio


# ─── 標題列 ───
col_title, col_meta = st.columns([3, 1])
with col_title:
    st.markdown('<h2 style="color:#FFF; margin:0;">L.I.S 持股配置</h2>',
                unsafe_allow_html=True)
    if _name:
        st.markdown(f'<p class="dim">歡迎 {_name}（LINE 身分已自動帶入）</p>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<p class="dim">Life Is Shit. I should enjoy it.</p>',
                    unsafe_allow_html=True)
with col_meta:
    st.markdown(
        f'<p style="text-align:right; margin-top:8px;" class="dim">{datetime.now():%Y/%m/%d}</p>',
        unsafe_allow_html=True)

st.markdown('<div class="divider-yellow"></div>', unsafe_allow_html=True)


# ─── 頂部圓環圖 ───
持股 = max(0, p.get("holdings_value_twd", 0))
總資 = max(1, p.get("total_capital_twd", 0))
配置比例 = round(持股 / 總資 * 100, 1) if 總資 > 0 else 0

st.markdown('<div class="gauge-box">', unsafe_allow_html=True)
png = chart_generator.生成Enjoy圓環(
    配置比例,
    status=(f"{持股/10000:.1f} 萬 / {總資/10000:.0f} 萬" if 總資 > 0 else "尚未設定"),
    副標="持股配置比例",
)
st.image(png, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)


# ─── 表單 ───
st.markdown("### 📝 更新你的資金與持股")

with st.form("portfolio_form"):
    name = st.text_input(
        "🙋 你的暱稱（隨便取，方便辨識）",
        value=p.get("user_name", ""),
        max_chars=30,
    )
    col1, col2 = st.columns(2)
    with col1:
        twd_cash = st.number_input(
            "💵 台幣現金 (TWD)",
            value=int(p["current_cash_twd"]),
            step=10000, format="%d",
            help="目前未動用的台幣現金"
        )
        total_capital = st.number_input(
            "💰 總資金 (TWD)",
            value=int(p["total_capital_twd"]),
            step=10000, format="%d",
        )
    with col2:
        usd_cash = st.number_input(
            "💵 美元現金 (USD)",
            value=int(p.get("usd_cash", 0)),
            step=100, format="%d",
        )
        usd_twd_rate = st.number_input(
            "💱 USD/TWD 匯率",
            value=float(p["usd_twd_rate"]),
            step=0.1, format="%.2f",
        )
    holdings = st.number_input(
        "📈 目前持股市值 (TWD)",
        value=int(p["holdings_value_twd"]),
        step=10000, format="%d",
        help="所有股票今日市值合計"
    )
    strategy_opts = {
        "current":     "🎯 LIS 預設（多檔分散 + Enjoy Index 訊號）",
        "passive_etf": "🪙 無腦投資大盤 ETF",
        "balanced":    "⚖️ 一半存股 + 一半短線",
        "all_in_one":  "🚀 重壓一檔最看好的股票",
    }
    strategy = st.selectbox(
        "📊 策略模式",
        options=list(strategy_opts.keys()),
        format_func=lambda k: strategy_opts[k],
        index=list(strategy_opts.keys()).index(p.get("strategy_mode", "balanced")),
    )

    submit = st.form_submit_button("💾 計算並更新", use_container_width=True)


if submit:
    p["user_name"] = name
    p["current_cash_twd"] = twd_cash
    p["total_capital_twd"] = total_capital
    p["usd_cash"] = usd_cash
    p["usd_twd_rate"] = usd_twd_rate
    p["holdings_value_twd"] = holdings
    p["strategy_mode"] = strategy
    st.session_state.portfolio = p
    st.success(f"✅ 已更新 {name or '你'} 的配置！")
    st.rerun()


# ─── 計算建議 ───
st.markdown('<div class="divider-yellow"></div>', unsafe_allow_html=True)
st.markdown("### 🎯 系統建議（依目前 Enjoy Index 模擬）")

模擬enjoy = st.slider("假設今日 Enjoy Index（之後會接真實系統）",
                       0, 100, 50, step=5,
                       help="模擬不同行情下，系統會建議你動用多少火力")

d = p["deployment_by_enjoy_index"]
if 模擬enjoy >= d["be_happy_min_score"]:
    建議, 火力 = "BE HAPPY", d["be_happy_deploy_pct"]
elif 模擬enjoy >= d["wait_min_score"]:
    建議, 火力 = "WAIT", d["wait_deploy_pct"]
else:
    建議, 火力 = "HOLD", d["hold_deploy_pct"]

股票配置上限 = p["total_capital_twd"] * 0.8
最小現金保留 = p["total_capital_twd"] * p["risk_rules"]["min_cash_reserve_pct"] / 100
火力上限 = 股票配置上限 * 火力 / 100
現金上限 = max(0, p["current_cash_twd"] - 最小現金保留)
今日子彈 = round(min(火力上限, 現金上限), 0)

st.markdown('<div class="gauge-box">', unsafe_allow_html=True)
png2 = chart_generator.生成資金規劃圓環(火力, 今日子彈, 建議)
st.image(png2, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.metric("可動用子彈", f"NT$ {今日子彈:,.0f}")
with col_b:
    st.metric("火力比例", f"{火力}%")
with col_c:
    st.metric("單檔上限", f"NT$ {p['total_capital_twd']*0.2:,.0f}")


# ─── 下載 JSON ───
st.markdown('<div class="divider-yellow"></div>', unsafe_allow_html=True)
json_bytes = json.dumps(p, ensure_ascii=False, indent=2).encode("utf-8")
st.download_button(
    label="📥 下載我的配置 JSON",
    data=json_bytes,
    file_name=f"portfolio_{p.get('user_name', 'user') or 'user'}_{datetime.now():%Y%m%d}.json",
    mime="application/json",
    use_container_width=True,
)
st.markdown(
    '<p class="dim" style="text-align:center;">下載後可放進你本機 LIS 系統的 API 資料夾，'
    '或 email 給 Ryan 加入自動推播。</p>',
    unsafe_allow_html=True
)
