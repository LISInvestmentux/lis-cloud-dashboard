"""
LIS Investment Dashboard v3.0 — 專業金融儀表板
靈感：Bloomberg Terminal + Stripe + Linear
"""
import os
import json
import sys
import io
import contextlib
from datetime import datetime
from pathlib import Path
from collections import defaultdict

import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))
from dotenv import load_dotenv
load_dotenv(專案根.parent / "API" / ".env")


st.set_page_config(
    page_title="LIS",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ════════════════════════════════════════════
# Phase 33.3 — PWA 化：手機加入主畫面變 app
# ════════════════════════════════════════════
# PWA icon: LIS 漸層黃色「L」(SVG → data URI，避免 host 靜態檔)
import base64 as _b64
_LIS_ICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0%" stop-color="#FBBF24"/>
<stop offset="100%" stop-color="#A855F7"/>
</linearGradient></defs>
<rect width="512" height="512" rx="96" fill="#000"/>
<text x="256" y="340" font-family="Inter,sans-serif" font-size="320"
      font-weight="900" fill="url(#g)" text-anchor="middle">L</text>
<circle cx="400" cy="140" r="36" fill="#22C55E"/>
</svg>'''
_ICON_DATA_URI = "data:image/svg+xml;base64," + _b64.b64encode(_LIS_ICON_SVG.encode()).decode()

_MANIFEST = {
    "name": "LIS Investment",
    "short_name": "LIS",
    "description": "Life Is Shit Investment Dashboard",
    "start_url": ".",
    "display": "standalone",
    "background_color": "#000000",
    "theme_color": "#FBBF24",
    "orientation": "portrait",
    "icons": [
        {"src": _ICON_DATA_URI, "sizes": "192x192", "type": "image/svg+xml"},
        {"src": _ICON_DATA_URI, "sizes": "512x512", "type": "image/svg+xml"},
    ],
}
import json as _json
_MANIFEST_DATA_URI = ("data:application/json;base64," +
                      _b64.b64encode(_json.dumps(_MANIFEST).encode()).decode())

# 注入 PWA meta tags（用 markdown 注入到 body，瀏覽器仍會讀）
st.markdown(f"""
<link rel="manifest" href="{_MANIFEST_DATA_URI}">
<link rel="apple-touch-icon" href="{_ICON_DATA_URI}">
<link rel="icon" type="image/svg+xml" href="{_ICON_DATA_URI}">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="LIS">
<meta name="mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#000000">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
""", unsafe_allow_html=True)

# ════════════════════════════════════════════
# 專業 CSS（Bloomberg/Stripe 級）
# ════════════════════════════════════════════
st.markdown("""
<style>
/* ===== Reset & Base ===== */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, "PingFang TC", "Microsoft JhengHei", sans-serif !important;
    color: #E5E7EB !important;
}
body { -webkit-font-smoothing: antialiased; }

/* Hide Streamlit chrome */
header[data-testid="stHeader"],
.stDeployButton, footer, #MainMenu { display: none !important; }

/* Main background */
.stApp {
    background:
        radial-gradient(ellipse 80% 50% at 50% -20%, rgba(251,191,36,0.08), transparent),
        radial-gradient(ellipse 60% 40% at 80% 80%, rgba(168,85,247,0.06), transparent),
        #07070C !important;
}

.block-container {
    padding-top: 2rem !important;
    max-width: 1400px !important;
}

/* Force text colors */
p, span, label, div, td, th, li { color: #E5E7EB !important; }
small { color: #6B7280 !important; }

/* ===== Hero Header ===== */
.hero-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 24px 0 16px 0;
    border-bottom: 1px solid rgba(251,191,36,0.15);
    margin-bottom: 32px;
}
.brand {
    display: flex;
    align-items: center;
    gap: 16px;
}
.brand-logo {
    width: 48px; height: 48px;
    background: linear-gradient(135deg, #FBBF24 0%, #A855F7 100%);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    box-shadow: 0 8px 24px rgba(251,191,36,0.3);
}
.brand-text h1 {
    font-size: 24px !important;
    font-weight: 800 !important;
    margin: 0 !important;
    color: #FFFFFF !important;
    border: none !important;
    padding: 0 !important;
    letter-spacing: -0.02em;
}
.brand-text p {
    font-size: 11px !important;
    color: #6B7280 !important;
    margin: 2px 0 0 0 !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 500;
}
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: rgba(34,197,94,0.15);
    border: 1px solid rgba(34,197,94,0.3);
    border-radius: 100px;
    font-size: 11px;
    font-weight: 600;
    color: #22C55E !important;
}
.status-dot {
    width: 6px; height: 6px;
    background: #22C55E;
    border-radius: 50%;
    box-shadow: 0 0 8px #22C55E;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

/* ===== Hero Metrics (4 大數字) — Phase 33.2 responsive ===== */
.metric-grid {
    display: grid;
    grid-template-columns: 2fr 1fr 1fr 1fr;
    gap: 16px;
    margin-bottom: 32px;
}
/* 平板 (≤ 1024px): 2 columns */
@media (max-width: 1024px) {
    .metric-grid {
        grid-template-columns: 1fr 1fr;
    }
    .metric-value { font-size: 28px !important; }
    .metric-value.hero { font-size: 32px !important; }
}
/* 手機 (≤ 640px): 1 column (vertical stack) */
@media (max-width: 640px) {
    .metric-grid {
        grid-template-columns: 1fr;
        gap: 12px;
    }
    .metric-card {
        padding: 16px !important;
    }
    .metric-value { font-size: 24px !important; }
    .metric-value.hero { font-size: 28px !important; }
    .metric-sub { font-size: 11px !important; }
}
.metric-card {
    background: linear-gradient(135deg,
        rgba(255,255,255,0.03) 0%,
        rgba(255,255,255,0.01) 100%);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    padding: 24px;
    transition: all 0.3s;
    position: relative;
    overflow: hidden;
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(251,191,36,0.5), transparent);
}
.metric-card:hover {
    border-color: rgba(251,191,36,0.3);
    transform: translateY(-2px);
    box-shadow: 0 12px 32px rgba(0,0,0,0.4);
}
.metric-label {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #6B7280 !important;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 12px;
}
.metric-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 32px;
    font-weight: 700;
    color: #FFFFFF;
    line-height: 1;
    letter-spacing: -0.02em;
}
.metric-value.hero {
    font-size: 40px;
    background: linear-gradient(90deg, #FBBF24 0%, #F59E0B 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.metric-sub {
    margin-top: 8px;
    font-size: 12px;
    color: #9CA3AF !important;
}
.up { color: #22C55E !important; }
.down { color: #EF4444 !important; }
.warn { color: #F59E0B !important; }

/* ===== Section Headers ===== */
.section-title {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 40px 0 20px 0;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
.section-title h2 {
    font-size: 18px !important;
    font-weight: 700 !important;
    color: #FFFFFF !important;
    margin: 0 !important;
    border: none !important;
    padding: 0 !important;
    letter-spacing: -0.01em;
}
.section-title .badge {
    padding: 3px 10px;
    background: rgba(251,191,36,0.15);
    color: #FBBF24 !important;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
}

/* ===== Alert / Brief Cards ===== */
.brief-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}
.brief-card {
    background: linear-gradient(135deg,
        rgba(251,191,36,0.08) 0%,
        rgba(251,191,36,0.02) 100%);
    border: 1px solid rgba(251,191,36,0.2);
    border-radius: 12px;
    padding: 20px;
    position: relative;
}
.brief-card.success {
    background: linear-gradient(135deg,
        rgba(34,197,94,0.08) 0%,
        rgba(34,197,94,0.02) 100%);
    border-color: rgba(34,197,94,0.2);
}
.brief-card.danger {
    background: linear-gradient(135deg,
        rgba(239,68,68,0.08) 0%,
        rgba(239,68,68,0.02) 100%);
    border-color: rgba(239,68,68,0.2);
}
.brief-card h4 {
    font-size: 14px !important;
    font-weight: 600 !important;
    margin: 0 0 12px 0 !important;
    display: flex;
    align-items: center;
    gap: 8px;
}
.brief-card.success h4 { color: #22C55E !important; }
.brief-card.danger h4 { color: #EF4444 !important; }
.brief-card:not(.success):not(.danger) h4 { color: #FBBF24 !important; }
.brief-card ul {
    margin: 0;
    padding-left: 0;
    list-style: none;
}
.brief-card li {
    font-size: 13px;
    color: #D1D5DB !important;
    padding: 6px 0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}
.brief-card li:last-child { border: none; }
.brief-card li b { color: #FBBF24 !important; }

/* ===== Stock Cards ===== */
.stock-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 12px;
}
.stock-card {
    background: linear-gradient(135deg,
        rgba(255,255,255,0.03) 0%,
        rgba(255,255,255,0.01) 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-left-width: 3px;
    border-radius: 12px;
    padding: 16px;
    transition: all 0.2s;
    cursor: pointer;
}
.stock-card:hover {
    transform: translateY(-2px);
    border-color: rgba(251,191,36,0.3);
    box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}
.stock-card.up { border-left-color: #22C55E; }
.stock-card.down { border-left-color: #EF4444; }
.stock-card.tp { border-left-color: #FBBF24; background: linear-gradient(135deg, rgba(251,191,36,0.08), rgba(251,191,36,0.02)); }
.stock-card.near-tp { border-left-color: #F59E0B; }
.stock-card.flat { border-left-color: #4B5563; }

.stock-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 12px;
}
.stock-sym {
    font-family: 'JetBrains Mono', monospace;
    font-size: 16px;
    font-weight: 700;
    color: #FFFFFF !important;
    display: flex;
    align-items: center;
    gap: 6px;
}
.stock-sym .star {
    color: #FBBF24 !important;
    filter: drop-shadow(0 0 4px rgba(251,191,36,0.5));
}
.stock-name {
    font-size: 11px;
    color: #6B7280 !important;
    margin-top: 2px;
}
.stock-price-block { text-align: right; }
.stock-price {
    font-family: 'JetBrains Mono', monospace;
    font-size: 18px;
    font-weight: 700;
    color: #FFFFFF !important;
}
.stock-change { font-size: 14px; font-weight: 600; }
.stock-meta {
    display: flex;
    justify-content: space-between;
    padding-top: 12px;
    border-top: 1px solid rgba(255,255,255,0.06);
    font-size: 11px;
    color: #9CA3AF !important;
}
.stock-meta .kelly { color: #FBBF24 !important; font-weight: 600; }
.stock-meta .pl-up { color: #22C55E !important; font-weight: 600; }
.stock-meta .pl-down { color: #EF4444 !important; font-weight: 600; }
.stock-badge {
    margin-top: 10px;
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 10px;
    font-weight: 600;
    text-align: center;
    background: linear-gradient(90deg, #FBBF24, #F59E0B);
    color: #000 !important;
}

/* ===== SOP indicator bars ===== */
.sop-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
    margin: 16px 0;
}
.sop-item {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 14px;
    text-align: center;
}
.sop-item.hit { border-color: rgba(239,68,68,0.5); background: rgba(239,68,68,0.08); }
.sop-item.warn { border-color: rgba(245,158,11,0.5); background: rgba(245,158,11,0.08); }
.sop-item.safe { border-color: rgba(34,197,94,0.3); background: rgba(34,197,94,0.05); }
.sop-item.no-data { opacity: 0.4; }
.sop-icon { font-size: 24px; margin-bottom: 6px; }
.sop-label { font-size: 11px; color: #9CA3AF !important; text-transform: uppercase; letter-spacing: 0.05em; }
.sop-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 18px;
    font-weight: 700;
    color: #FFFFFF !important;
    margin-top: 4px;
}
.sop-item.hit .sop-value { color: #EF4444 !important; }
.sop-item.safe .sop-value { color: #22C55E !important; }

/* ===== News items ===== */
.news-item {
    padding: 12px 16px;
    border-left: 3px solid;
    margin: 8px 0;
    background: rgba(255,255,255,0.02);
    border-radius: 0 8px 8px 0;
    display: flex;
    gap: 12px;
    align-items: flex-start;
}
.news-item.urgent { border-color: #EF4444; background: rgba(239,68,68,0.08); }
.news-item.high { border-color: #F59E0B; background: rgba(245,158,11,0.06); }
.news-item.bull { border-color: #22C55E; background: rgba(34,197,94,0.06); }
.news-tag {
    font-size: 10px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    white-space: nowrap;
}
.news-tag.urgent { background: #EF4444; color: #FFF !important; }
.news-tag.high { background: #F59E0B; color: #000 !important; }
.news-tag.bull { background: #22C55E; color: #000 !important; }
.news-text { font-size: 13px; color: #E5E7EB !important; line-height: 1.5; }

/* ===== Buttons ===== */
.stButton button {
    background: linear-gradient(90deg, #FBBF24 0%, #F59E0B 100%) !important;
    color: #000 !important;
    border: none !important;
    font-weight: 600 !important;
    border-radius: 10px !important;
    padding: 8px 16px !important;
    font-size: 13px !important;
    transition: all 0.2s !important;
    box-shadow: 0 2px 8px rgba(251,191,36,0.3) !important;
}
.stButton button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(251,191,36,0.5) !important;
}

/* ===== Selectbox ===== */
.stSelectbox > div > div {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important;
    color: #FFFFFF !important;
}
.stSelectbox > div > div > div {
    color: #FFFFFF !important;
}
.stSelectbox label { color: #9CA3AF !important; font-size: 11px !important; }

/* Dropdown popover (when opened) */
[data-baseweb="popover"] {
    background: #1a1a22 !important;
    border: 1px solid rgba(251,191,36,0.3) !important;
    border-radius: 10px !important;
    box-shadow: 0 12px 32px rgba(0,0,0,0.6) !important;
}
[data-baseweb="popover"] * {
    background: transparent !important;
}
[data-baseweb="menu"] {
    background: #1a1a22 !important;
    color: #E5E7EB !important;
    padding: 4px !important;
}
[data-baseweb="menu"] li {
    color: #E5E7EB !important;
    background: transparent !important;
    padding: 10px 14px !important;
    border-radius: 6px !important;
    transition: all 0.15s !important;
    font-weight: 500 !important;
}
[data-baseweb="menu"] li * {
    color: #E5E7EB !important;
    background: transparent !important;
}
[data-baseweb="menu"] li:hover,
[data-baseweb="menu"] li[aria-selected="true"],
[data-baseweb="menu"] li:focus {
    background: rgba(251,191,36,0.15) !important;
    color: #FBBF24 !important;
}
[data-baseweb="menu"] li:hover *,
[data-baseweb="menu"] li[aria-selected="true"] *,
[data-baseweb="menu"] li:focus * {
    color: #FBBF24 !important;
}

/* Selectbox input text (顯示中的) */
[data-baseweb="select"] [data-baseweb="tag"],
[data-baseweb="select"] span {
    color: #FFFFFF !important;
}

/* ===== Expander ===== */
.streamlit-expanderHeader {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 10px !important;
    padding: 16px 20px !important;
    color: #FBBF24 !important;
    font-weight: 600 !important;
    font-size: 14px !important;
}
.streamlit-expanderHeader:hover {
    border-color: rgba(251,191,36,0.3) !important;
}
.streamlit-expanderContent {
    background: rgba(0,0,0,0.2) !important;
    border-radius: 0 0 10px 10px;
    padding: 16px !important;
}
.streamlit-expanderContent * { color: #E5E7EB !important; }

/* ===== Sidebar ===== */
[data-testid="stSidebar"] {
    background: #0a0a14 !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
}
[data-testid="stSidebar"] * { color: #E5E7EB !important; }
[data-testid="stSidebar"] h3 { color: #FBBF24 !important; font-size: 13px !important; text-transform: uppercase; letter-spacing: 0.1em; }

/* ===== Dataframe ===== */
.stDataFrame { background: transparent !important; }
.stDataFrame * { color: #E5E7EB !important; }
.stDataFrame thead tr th {
    background: rgba(251,191,36,0.1) !important;
    color: #FBBF24 !important;
    font-weight: 600 !important;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.stDataFrame tbody tr {
    background: rgba(255,255,255,0.02) !important;
    border-bottom: 1px solid rgba(255,255,255,0.04) !important;
}
.stDataFrame tbody tr:hover {
    background: rgba(251,191,36,0.05) !important;
}

/* ===== Markdown ===== */
hr {
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg, transparent, rgba(251,191,36,0.2), transparent) !important;
    margin: 32px 0 !important;
}

/* ===== Metric (st.metric) ===== */
[data-testid="metric-container"] {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 16px;
}
[data-testid="metric-container"] label { color: #9CA3AF !important; font-size: 11px !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #FFFFFF !important;
    font-family: 'JetBrains Mono', monospace !important;
}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════
# 載入資料
# ════════════════════════════════════════════
@st.cache_data(ttl=600)
def 載入Kelly_DB():
    p = 專案根.parent / "數據" / "win_rate_db.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"標的": {}}


@st.cache_data(ttl=600)
def 載入共識():
    p = 專案根.parent / "數據" / "external_signal_history.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"訊號": []}


@st.cache_data(ttl=60)
def 算彈藥():
    from modules import capital_planner, forex, money_manager, portfolio_tracker
    cfg = capital_planner.載入資金設定()
    現金 = cfg.get("current_cash_twd", 0)
    持股 = [p for p in cfg.get("current_positions", []) if p.get("symbol") != "AGGREGATE"]
    匯率 = forex.取得USD_TWD匯率(fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32.0))["rate"]
    # Phase 32.5：用即時市值，不用成本
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=匯率)
    市值總 = 真倉["總計"]["市值_twd"]
    成本總 = 真倉["總計"]["成本_twd"]
    損益_twd = 真倉["總計"]["損益_twd"]
    損益率 = 真倉["總計"]["損益率_pct"]
    彈藥 = money_manager.計算可用彈藥(總資金=市值總 + 現金, 現金=現金, 持股成本_twd=市值總, 目標閒錢比_pct=35)
    return {"總資產": 市值總 + 現金, "現金": 現金, "持股市值": 市值總, "持股成本": 成本總,
            "投資損益_twd": 損益_twd, "投資損益率": 損益率,
            "持股數": len(持股), "彈藥": 彈藥}


@st.cache_data(ttl=120)
def 抓即時持股():
    from modules import capital_planner, fugle_market, forex
    cfg = capital_planner.載入資金設定()
    持股 = [p for p in cfg.get("current_positions", []) if p.get("symbol") != "AGGREGATE"]
    匯率 = forex.取得USD_TWD匯率(fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32.0))["rate"]
    結果 = []
    for p in 持股:
        sym = p["symbol"]
        q = fugle_market.即時報價_fallback(sym)
        現價 = q.get("close") if q else p.get("avg_cost", 0)
        成本 = p.get("avg_cost", 0)
        股數 = p.get("shares", 0)
        漲幅 = (現價 / 成本 - 1) * 100 if 成本 > 0 else 0
        is_us = not (sym.endswith(".TW") or sym.endswith(".TWO"))
        倍率 = 匯率 if is_us else 1.0
        市值 = 現價 * 股數 * 倍率
        損益 = (現價 - 成本) * 股數 * 倍率
        結果.append({"symbol": sym, "name": p.get("name", ""), "shares": 股數, "avg_cost": 成本, "現價": 現價, "漲幅": 漲幅, "市值": 市值, "損益": 損益, "is_us": is_us})
    return 結果


def 套用深色主題(fig):
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(255,255,255,0.02)',
        font=dict(color='#E5E7EB', family='Inter, "Microsoft JhengHei"'),
        xaxis=dict(gridcolor='rgba(255,255,255,0.06)', color='#9CA3AF', zerolinecolor='rgba(255,255,255,0.1)'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.06)', color='#9CA3AF', zerolinecolor='rgba(255,255,255,0.1)'),
        legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color='#E5E7EB')),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


# ════════════════════════════════════════════
# Hero Header
# ════════════════════════════════════════════
st.markdown(f"""
<div class='hero-header'>
    <div class='brand'>
        <div class='brand-logo'>📈</div>
        <div class='brand-text'>
            <h1>LIS Investment</h1>
            <p>Investment Intelligence · v1.1</p>
        </div>
    </div>
    <div class='status-pill'>
        <span class='status-dot'></span>
        系統運行中 · {datetime.now():%H:%M:%S}
    </div>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════
# Hero Metrics
# ════════════════════════════════════════════
彈藥資 = 算彈藥()
持股表 = 抓即時持股()
總損益 = sum(h["損益"] for h in 持股表)
總市值 = sum(h["市值"] for h in 持股表)
總資產_即時 = 總市值 + 彈藥資["現金"]
總報酬_pct = (總損益 / 彈藥資["持股成本"] * 100) if 彈藥資["持股成本"] > 0 else 0

# Phase 33.1：待交割款（T+2 未入帳的賣出款）
待交割款_twd = 0
try:
    cfg_raw = json.loads((專案根.parent / "API" / "portfolio.json").read_text(encoding="utf-8"))
    待交割款_twd = sum(p.get("net_twd", 0) for p in cfg_raw.get("pending_settlement", []))
except Exception:
    pass
真實財富 = 總資產_即時 + 待交割款_twd

模式 = 彈藥資['彈藥']['模式']
模式emoji = {"平衡": "⚪", "充足": "🟢", "接近底線": "🟡", "越線": "🔴"}.get(模式, "⚪")

主資產顯示 = (
    f"NT$ {真實財富:,.0f}"
    if 待交割款_twd > 0 else
    f"NT$ {總資產_即時:,.0f}"
)
資產說明 = (
    f"持股 NT$ {總市值:,.0f} + 現金 NT$ {彈藥資['現金']:,.0f} + 待交割 NT$ {待交割款_twd:,.0f}"
    if 待交割款_twd > 0 else
    f"持股 NT$ {總市值:,.0f} + 現金 NT$ {彈藥資['現金']:,.0f}"
)

st.markdown(f"""
<div class='metric-grid'>
    <div class='metric-card'>
        <div class='metric-label'>💰 總資產（真實財富）</div>
        <div class='metric-value hero'>{主資產顯示}</div>
        <div class='metric-sub'>{資產說明}</div>
    </div>
    <div class='metric-card'>
        <div class='metric-label'>📊 未實現損益</div>
        <div class='metric-value {"up" if 總損益 >= 0 else "down"}'>{總損益:+,.0f}</div>
        <div class='metric-sub {"up" if 總損益 >= 0 else "down"}'>{總報酬_pct:+.2f}%</div>
    </div>
    <div class='metric-card'>
        <div class='metric-label'>💵 閒錢比</div>
        <div class='metric-value'>{彈藥資['彈藥']['水位']['閒錢比_pct']:.1f}<span style='font-size:20px;color:#6B7280'>%</span></div>
        <div class='metric-sub'>目標 35% · 差 {彈藥資['彈藥']['水位']['差距_pct']:+.1f}%</div>
    </div>
    <div class='metric-card'>
        <div class='metric-label'>⚡ 可動用彈藥</div>
        <div class='metric-value warn'>NT$ {彈藥資['彈藥']['可動用彈藥_twd']:,.0f}</div>
        <div class='metric-sub warn'>{模式emoji} {模式}模式</div>
        {("<div class='metric-sub' style='color:#22C55E;margin-top:6px'>⏰ 待交割 NT$ " + f"{待交割款_twd:,.0f}" + " 入帳後解鎖</div>") if 待交割款_twd > 0 else ""}
    </div>
</div>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════
# Phase 33.1：ARK 級 Gauges 儀表板
# ════════════════════════════════════════════
st.markdown("<div class='section-title'><h2>🎯 ARK 級儀表盤</h2><span class='badge'>Real-time Gauges</span></div>", unsafe_allow_html=True)

# 抓 gauges 所需資料
@st.cache_data(ttl=120)
def 抓Gauge資料():
    """5+1 個 gauges 所需資料"""
    data = {
        "持股配置_pct": 0,
        "FG_score": None,
        "VIX": None,
        "黑天鵝命中": 0,
        "位階平均": None,
        "LIS_vs_0050": None,
    }
    try:
        from modules import fear_greed
        fg = fear_greed.取得恐慌貪婪指數()
        if fg:
            data["FG_score"] = fg.get("score")
    except Exception:
        pass
    try:
        from modules import bottom_detector
        sop = bottom_detector.即時底部判定()
        data["黑天鵝命中"] = sop.get("命中數", 0)
        if sop.get("原始資料", {}).get("VIX"):
            data["VIX"] = round(sop["原始資料"]["VIX"], 2)
    except Exception:
        pass
    # VIX fallback — yfinance 限流時讀底部偵測快取
    if data["VIX"] is None:
        try:
            from datetime import datetime as _dt, timedelta as _td
            cache_dir = 專案根.parent / "數據" / "底部偵測"
            for i in range(0, 5):
                d = _dt.now() - _td(days=i)
                f = cache_dir / f"{d:%Y-%m-%d}.json"
                if f.exists():
                    j = json.loads(f.read_text(encoding="utf-8"))
                    v = (j.get("原始資料") or {}).get("VIX")
                    if v:
                        data["VIX"] = round(v, 2)
                        break
        except Exception:
            pass
    try:
        state_path = 專案根.parent / "數據" / "positional_state.json"
        if state_path.exists():
            scores = json.loads(state_path.read_text(encoding="utf-8")).get("scores", {})
            活躍 = [s for s in scores.values() if 0 < s < 100]
            if 活躍:
                data["位階平均"] = round(sum(活躍) / len(活躍), 1)
    except Exception:
        pass
    try:
        from modules import benchmark_compare
        c = benchmark_compare.算LIS_vs_0050(總資產_即時,
                                                投資內部報酬率_pct=總報酬_pct)
        if c:
            data["LIS_vs_0050"] = c.get("投資超額報酬_pct")
    except Exception:
        pass
    # 持股配置 (市值/總資產 × 100)
    if 總資產_即時 > 0:
        data["持股配置_pct"] = round(總市值 / 總資產_即時 * 100, 1)
    return data


def _圓環(value, title, suffix="", min_v=0, max_v=100,
          綠範圍=(0, 30), 紅範圍=(80, 100), 反向=False,
          height=200):
    """單個 Plotly gauge"""
    if value is None:
        # 未知狀態
        fig = go.Figure(go.Indicator(
            mode="gauge",
            value=0,
            title={"text": f"{title}<br><span style='font-size:11px;color:#6B7280'>無資料</span>",
                   "font": {"size": 13, "color": "#9CA3AF"}},
            gauge={"axis": {"range": [min_v, max_v], "tickwidth": 0,
                             "tickcolor": "#374151"},
                    "bar": {"color": "#374151"},
                    "bgcolor": "#0a0e15",
                    "borderwidth": 0,
                    "bordercolor": "#0a0e15",
                    "steps": []},
        ))
    else:
        # 用顏色帶
        綠色 = "rgba(34,197,94,0.4)"
        黃色 = "rgba(251,191,36,0.4)"
        紅色 = "rgba(239,68,68,0.4)"
        steps = [
            {"range": [min_v, 綠範圍[1]], "color": 綠色 if not 反向 else 紅色},
            {"range": [綠範圍[1], 紅範圍[0]], "color": 黃色},
            {"range": [紅範圍[0], max_v], "color": 紅色 if not 反向 else 綠色},
        ]
        # 數字顯示顏色
        if 反向:
            數字色 = "#22C55E" if value >= 紅範圍[0] else "#EF4444" if value <= 綠範圍[1] else "#FBBF24"
        else:
            數字色 = "#22C55E" if value <= 綠範圍[1] else "#EF4444" if value >= 紅範圍[0] else "#FBBF24"
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": suffix, "font": {"size": 28, "color": 數字色, "family": "JetBrains Mono"}},
            title={"text": title,
                   "font": {"size": 13, "color": "#9CA3AF"}},
            gauge={
                "axis": {"range": [min_v, max_v], "tickwidth": 1,
                          "tickcolor": "#374151",
                          "tickfont": {"size": 9, "color": "#6B7280"}},
                "bar": {"color": "#FBBF24", "thickness": 0.25},
                "bgcolor": "#0a0e15",
                "borderwidth": 1,
                "bordercolor": "rgba(251,191,36,0.2)",
                "steps": steps,
                "threshold": {
                    "line": {"color": "#F59E0B", "width": 3},
                    "thickness": 0.8,
                    "value": value,
                },
            },
        ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=10, r=10, t=40, b=10),
        font=dict(color="#E5E7EB"),
    )
    return fig


gauge_data = 抓Gauge資料()

# 主圓環（大）+ 5 小錶盤
col_main, col_2, col_3, col_4, col_5, col_6 = st.columns([2, 1, 1, 1, 1, 1])

with col_main:
    # 持股配置 — 大圓環
    fig_main = _圓環(
        gauge_data["持股配置_pct"],
        title="持股配置 %",
        suffix="%",
        綠範圍=(35, 65),  # 35-65% 健康
        紅範圍=(75, 100), # >75 過度動用
        height=240,
    )
    st.plotly_chart(fig_main, use_container_width=True, config={"displayModeBar": False})

with col_2:
    # F&G 情緒
    fig = _圓環(
        gauge_data["FG_score"],
        title="🎭 大盤情緒 F&G",
        綠範圍=(0, 25),  # 極度恐懼 = 買點 (綠)
        紅範圍=(75, 100), # 極度貪婪 = 賣點 (紅)
        反向=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with col_3:
    # VIX
    fig = _圓環(
        gauge_data["VIX"],
        title="📊 VIX 恐慌指數",
        min_v=0, max_v=50,
        綠範圍=(0, 15),
        紅範圍=(30, 50),
        反向=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with col_4:
    # 黑天鵝命中
    fig = _圓環(
        gauge_data["黑天鵝命中"],
        title="🦢 黑天鵝命中",
        suffix="/5",
        min_v=0, max_v=5,
        綠範圍=(0, 1),
        紅範圍=(3, 5),
        反向=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with col_5:
    # 持股位階平均
    fig = _圓環(
        gauge_data["位階平均"],
        title="📈 位階平均",
        綠範圍=(0, 30),  # 低位 = 價值區 (綠)
        紅範圍=(70, 100),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with col_6:
    # LIS vs 0050 超額報酬
    超額 = gauge_data["LIS_vs_0050"]
    if 超額 is not None:
        # 從 -30~+30 映射到 0~100
        clamped = max(-30, min(30, 超額))
        gauge_val = (clamped + 30) / 60 * 100
        fig = _圓環(
            gauge_val,
            title=f"🆚 LIS vs 0050<br><span style='font-size:10px;color:#6B7280'>{超額:+.2f}%</span>",
            min_v=0, max_v=100,
            綠範圍=(60, 100),  # 贏大盤
            紅範圍=(0, 40),  # 輸大盤
            反向=True,
        )
    else:
        fig = _圓環(None, title="🆚 LIS vs 0050")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ════════════════════════════════════════════
# Phase 36.14：K 線 + 風控分數變化圖（仿方舟）
# ════════════════════════════════════════════
st.markdown("<div class='section-title'><h2>📈 大盤 K 線 + 風控變化</h2><span class='badge'>過熱不需亂追，看風控怎麼變化</span></div>", unsafe_allow_html=True)

@st.cache_data(ttl=600)
def 抓K線風控():
    """LIS 多因子風控分（RSI + 乖離 + 距高 + 量能）— 仿方舟"""
    try:
        from modules import risk_score
        r = risk_score.算K線歷史風控("^TWII", period="3mo", 每幾天標一點=7)
        return r
    except Exception as e:
        return {"data": [], "marks": [], "error": str(e)}


k_data = 抓K線風控()

if k_data.get("data"):
    data = k_data["data"]
    marks = k_data.get("marks", [])

    # 仿方舟：即時大盤資訊條（K 線上方）
    今 = data[-1]
    昨 = data[-2] if len(data) >= 2 else 今
    今價 = 今["close"]
    今漲 = 今價 - 昨["close"]
    今漲_pct = (今價 / 昨["close"] - 1) * 100
    今vol = 今.get("volume", 0)

    # 算 5MA / 20MA / 60MA
    ma5_v = (sum(d["close"] for d in data[-5:]) / 5) if len(data) >= 5 else 今價
    ma20_v = (sum(d["close"] for d in data[-20:]) / 20) if len(data) >= 20 else 今價
    ma60_v = (sum(d["close"] for d in data[-60:]) / 60) if len(data) >= 60 else (
        sum(d["close"] for d in data) / len(data))

    # 量能換算（億元 — 但 yfinance 是股數，台股近似換算）
    今單量_億 = (今vol * 今價 / 1e8) if 今vol else 0

    # 算過去 20 天平均（總量近似）
    過去20_vol = sum(d.get("volume", 0) * d["close"] for d in data[-20:])
    過去20_億 = 過去20_vol / 1e8 / 20

    # 漲跌顏色
    漲色 = "#22C55E" if 今漲 >= 0 else "#EF4444"
    漲符 = "▲" if 今漲 >= 0 else "▼"

    日期str = datetime.fromisoformat(今["date"][:10]).strftime("%m/%d (%a)")

    st.markdown(f"""
<div style='background:rgba(0,0,0,0.5);border:1px solid rgba(255,255,255,0.08);
            border-radius:12px;padding:16px 20px;margin-bottom:12px;
            display:flex;flex-wrap:wrap;align-items:center;gap:24px;'>
  <div style='display:flex;flex-direction:column;'>
    <div style='font-size:12px;color:#888;'>加權指數</div>
    <div style='font-family:JetBrains Mono;font-size:32px;font-weight:900;color:#FBBF24;
                line-height:1;'>{今價:,.2f}</div>
  </div>
  <div style='display:flex;flex-direction:column;'>
    <div style='font-size:12px;color:#888;'>漲跌</div>
    <div style='font-family:JetBrains Mono;font-size:20px;font-weight:700;color:{漲色};'>
      {漲符} {今漲:+,.2f} ({今漲_pct:+.2f}%)
    </div>
  </div>
  <div style='display:flex;flex-direction:column;border-left:1px solid rgba(255,255,255,0.1);padding-left:24px;'>
    <div style='font-size:12px;color:#888;'>單量</div>
    <div style='font-family:JetBrains Mono;font-size:18px;color:#fff;'>{今單量_億:,.0f} 億</div>
  </div>
  <div style='display:flex;flex-direction:column;'>
    <div style='font-size:12px;color:#888;'>20 日均量</div>
    <div style='font-family:JetBrains Mono;font-size:18px;color:#fff;'>{過去20_億:,.0f} 億</div>
  </div>
  <div style='display:flex;flex-direction:column;margin-left:auto;text-align:right;'>
    <div style='font-size:12px;color:#888;'>{日期str}</div>
    <div style='font-family:JetBrains Mono;font-size:14px;color:#A855F7;'>更新 {datetime.now().strftime('%H:%M:%S')}</div>
  </div>
</div>

<div style='background:rgba(0,0,0,0.3);border-radius:8px;padding:10px 16px;margin-bottom:14px;
            display:flex;flex-wrap:wrap;gap:20px;font-family:JetBrains Mono;font-size:13px;'>
  <span style='color:#888;'>開 <span style='color:#fff;font-weight:700;'>{今.get("open", 今價):,.2f}</span></span>
  <span style='color:#888;'>高 <span style='color:#22C55E;font-weight:700;'>{今.get("high", 今價):,.2f}</span></span>
  <span style='color:#888;'>低 <span style='color:#EF4444;font-weight:700;'>{今.get("low", 今價):,.2f}</span></span>
  <span style='color:#888;'>收 <span style='color:#FBBF24;font-weight:700;'>{今價:,.2f}</span></span>
  <span style='border-left:1px solid rgba(255,255,255,0.1);padding-left:20px;color:#888;'>5MA <span style='color:#22C55E;font-weight:700;'>{ma5_v:,.2f}</span></span>
  <span style='color:#888;'>20MA <span style='color:#A855F7;font-weight:700;'>{ma20_v:,.2f}</span></span>
  <span style='color:#888;'>60MA <span style='color:#FBBF24;font-weight:700;'>{ma60_v:,.2f}</span></span>
</div>
""", unsafe_allow_html=True)

    fig_k = go.Figure(data=[go.Candlestick(
        x=[d["date"][:10] for d in data],
        open=[d.get("open", d["close"]) for d in data],
        high=[d.get("high", d["close"]) for d in data],
        low=[d.get("low", d["close"]) for d in data],
        close=[d["close"] for d in data],
        increasing_line_color='#22C55E',
        decreasing_line_color='#EF4444',
        name="加權指數",
    )])

    # 加 5MA 線（補仿方舟）
    if len(data) >= 5:
        ma5 = []
        dates_all = [d["date"][:10] for d in data]
        for i in range(len(data)):
            if i >= 4:
                ma5.append(sum(d["close"] for d in data[i-4:i+1]) / 5)
            else:
                ma5.append(None)
        fig_k.add_trace(go.Scatter(x=dates_all, y=ma5, name="5MA",
                                    line=dict(color='#22C55E', width=1)))

    # 加 MA20 / MA60
    if len(data) >= 60:
        ma20 = []
        ma60 = []
        dates = [d["date"][:10] for d in data]
        for i in range(len(data)):
            if i >= 19:
                ma20.append(sum(d["close"] for d in data[i-19:i+1]) / 20)
            else:
                ma20.append(None)
            if i >= 59:
                ma60.append(sum(d["close"] for d in data[i-59:i+1]) / 60)
            else:
                ma60.append(None)
        fig_k.add_trace(go.Scatter(x=dates, y=ma20, name="MA20",
                                    line=dict(color='#A855F7', width=1.5)))
        fig_k.add_trace(go.Scatter(x=dates, y=ma60, name="MA60",
                                    line=dict(color='#FBBF24', width=1.5)))

    # 加多因子風控分圓圈標記（仿方舟）
    for m in marks:
        色 = ("#EF4444" if m["score"] >= 70 else
              "#F59E0B" if m["score"] >= 50 else
              "#22C55E")
        fig_k.add_annotation(
            x=m["date"], y=m["close"] * 1.02,
            text=f"<b>{m['score']:.1f}</b>",
            showarrow=True, arrowhead=2, arrowcolor=色,
            arrowwidth=2, arrowsize=1.2,
            font=dict(color=色, size=14, family='JetBrains Mono'),
            bgcolor="rgba(0,0,0,0.7)",
            bordercolor=色, borderwidth=1.5,
            borderpad=6,
        )

    fig_k.update_layout(
        title=dict(
            text='<b>加權指數 K 線 — 風控分數變化（接近高點 % = 過熱度）</b>',
            font=dict(color='#FBBF24', size=14)),
        height=480,
        xaxis_rangeslider_visible=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#E5E7EB'),
        legend=dict(bgcolor='rgba(0,0,0,0.3)',
                     bordercolor='rgba(255,255,255,0.1)'),
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
        margin=dict(l=10, r=10, t=50, b=10),
    )
    st.plotly_chart(fig_k, use_container_width=True,
                     config={'displayModeBar': False})

    # 風控解讀（多因子綜合）
    if marks:
        latest = marks[-1]
        score = latest["score"]
        if score >= 70:
            st.markdown(
                f"<div style='padding:12px;background:rgba(239,68,68,0.1);"
                f"border-left:3px solid #EF4444;border-radius:6px;margin-top:10px;'>"
                f"🚨 <b>當前風控 {score:.1f}</b> — 過熱區（RSI/MA60乖離/距高/量能 多因子綜合）"
                f"<br>建議：減碼 / 拉高閒錢比 / 不追高</div>",
                unsafe_allow_html=True)
        elif score >= 50:
            st.markdown(
                f"<div style='padding:12px;background:rgba(245,158,11,0.1);"
                f"border-left:3px solid #F59E0B;border-radius:6px;margin-top:10px;'>"
                f"⚠️ <b>當前風控 {score:.1f}</b> — 警戒（停止加碼觀察）</div>",
                unsafe_allow_html=True)
        else:
            st.markdown(
                f"<div style='padding:12px;background:rgba(34,197,94,0.1);"
                f"border-left:3px solid #22C55E;border-radius:6px;margin-top:10px;'>"
                f"✅ <b>當前風控 {score:.1f}</b> — 健康（可正常依訊號操作）</div>",
                unsafe_allow_html=True)

        # 顯示風控分變化軌跡（仿方舟）
        if len(marks) >= 3:
            軌跡 = " → ".join([f"<span style='color:{'#EF4444' if m['score']>=70 else '#F59E0B' if m['score']>=50 else '#22C55E'};font-weight:bold'>{m['score']:.1f}</span>" for m in marks[-5:]])
            st.markdown(
                f"<div style='padding:10px;margin-top:6px;color:#888;font-size:13px'>"
                f"📊 風控漸進軌跡：{軌跡}（越右越新）</div>",
                unsafe_allow_html=True)
else:
    st.info("K 線資料載入中...")


# ════════════════════════════════════════════
# Daily Brief
# ════════════════════════════════════════════
st.markdown("<div class='section-title'><h2>🎯 今日重點</h2><span class='badge'>Daily Brief</span></div>", unsafe_allow_html=True)

接近停利 = [h for h in 持股表 if 12 <= h["漲幅"] < 15]
達停利 = [h for h in 持股表 if h["漲幅"] >= 15]
破停損 = [h for h in 持股表 if h["漲幅"] <= -5]

left_html = ""
right_html = ""

if 達停利 or 接近停利:
    items = ""
    for h in 達停利:
        items += f"<li>🎯 <b>{h['symbol']}</b> 達 +{h['漲幅']:.2f}% Strategy A 觸發！賣 50%</li>"
    for h in 接近停利:
        items += f"<li>📈 <b>{h['symbol']}</b> +{h['漲幅']:.2f}% 接近 +15%（差 {15-h['漲幅']:.2f}%）</li>"
    left_html = f"""<div class='brief-card success'>
        <h4>✅ Strategy A 監測</h4><ul>{items}</ul></div>"""
else:
    left_html = """<div class='brief-card'>
        <h4>📊 持股動態</h4>
        <ul><li>無持股觸發 Strategy A，<b>繼續紀律持有</b></li></ul></div>"""

if 破停損:
    items = ""
    for h in 破停損:
        items += f"<li>🛑 <b>{h['symbol']}</b> 跌 {h['漲幅']:.2f}% 強制停損！</li>"
    right_html = f"""<div class='brief-card danger'>
        <h4>⚠️ 停損警示</h4><ul>{items}</ul></div>"""
else:
    right_html = """<div class='brief-card'>
        <h4>📋 今日行動</h4>
        <ul>
            <li>🪓 賣 <b>00882 + 00920</b>（釋出 NT$ 10K）</li>
            <li>🎯 加碼 <b>00910 / 00935</b>（高 Kelly）</li>
            <li>⏰ DCA 6 號 NT$ 8,000 自動扣款</li>
        </ul></div>"""

st.markdown(f"<div class='brief-grid'>{left_html}{right_html}</div>", unsafe_allow_html=True)


# ════════════════════════════════════════════
# 視覺化圖表
# ════════════════════════════════════════════
st.markdown("<div class='section-title'><h2>📊 視覺化分析</h2><span class='badge'>Real-time</span></div>", unsafe_allow_html=True)

col_g1, col_g2 = st.columns([1, 1])

with col_g1:
    持股_排 = sorted(持股表, key=lambda x: x["漲幅"])
    fig_bar = go.Figure(data=[go.Bar(
        x=[h["漲幅"] for h in 持股_排],
        y=[h["symbol"] for h in 持股_排],
        orientation='h',
        marker=dict(color=['#22C55E' if h["漲幅"] >= 0 else '#EF4444' for h in 持股_排]),
        text=[f"{h['漲幅']:+.2f}%" for h in 持股_排],
        textposition='outside',
        textfont=dict(color='#E5E7EB', size=11, family='JetBrains Mono'),
    )])
    fig_bar.update_layout(
        title=dict(text='<b>持股漲跌幅排行</b>', font=dict(color='#FBBF24', size=14)),
        height=460,
        showlegend=False,
    )
    fig_bar = 套用深色主題(fig_bar)
    st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

with col_g2:
    持股_市值 = sorted(持股表, key=lambda x: -x["市值"])[:12]
    fig_pie = go.Figure(data=[go.Pie(
        labels=[h["symbol"] for h in 持股_市值],
        values=[h["市值"] for h in 持股_市值],
        hole=0.6,
        marker=dict(
            colors=['#FBBF24', '#F59E0B', '#A855F7', '#3B82F6', '#22C55E',
                    '#EC4899', '#06B6D4', '#84CC16', '#F97316', '#8B5CF6',
                    '#10B981', '#6366F1'],
            line=dict(color='#0a0a14', width=2),
        ),
        textfont=dict(color='#FFFFFF', size=10),
        textposition='outside',
    )])
    fig_pie.update_layout(
        title=dict(text='<b>持股佔比</b>', font=dict(color='#FBBF24', size=14)),
        height=460,
        legend=dict(orientation='v', x=1.05),
    )
    fig_pie = 套用深色主題(fig_pie)
    st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})


# Kelly 對比
kelly_db = 載入Kelly_DB()
kelly_map = {sym: r.get("統計", {}).get("Kelly_pct", 0)
             for sym, r in kelly_db.get("標的", {}).items() if "error" not in r}

col_g3, col_g4 = st.columns([1, 1])

with col_g3:
    持股_kelly = sorted(
        [(h["symbol"], kelly_map.get(h["symbol"], 0))
         for h in 持股表 if kelly_map.get(h["symbol"], 0) > 0],
        key=lambda x: -x[1]
    )[:15]
    if 持股_kelly:
        fig_k = go.Figure(data=[go.Bar(
            x=[k[1] for k in 持股_kelly],
            y=[k[0] for k in 持股_kelly],
            orientation='h',
            marker=dict(
                color=[k[1] for k in 持股_kelly],
                colorscale=[[0, '#3B0764'], [0.5, '#A855F7'], [1, '#FBBF24']],
                line=dict(color='#0a0a14', width=1),
            ),
            text=[f"{k[1]:.1f}%" for k in 持股_kelly],
            textposition='outside',
            textfont=dict(color='#E5E7EB', family='JetBrains Mono'),
        )])
        fig_k.update_layout(
            title=dict(text='<b>持股 Kelly% 排行</b>', font=dict(color='#FBBF24', size=14)),
            height=440,
        )
        fig_k = 套用深色主題(fig_k)
        st.plotly_chart(fig_k, use_container_width=True, config={'displayModeBar': False})

with col_g4:
    持股_損益 = sorted(持股表, key=lambda x: x["損益"], reverse=True)
    fig_pl = go.Figure(data=[go.Bar(
        x=[h["symbol"] for h in 持股_損益],
        y=[h["損益"] for h in 持股_損益],
        marker=dict(color=['#22C55E' if h["損益"] >= 0 else '#EF4444' for h in 持股_損益]),
        text=[f"{h['損益']:+,.0f}" for h in 持股_損益],
        textposition='outside',
        textfont=dict(color='#E5E7EB', size=9, family='JetBrains Mono'),
    )])
    fig_pl.update_layout(
        title=dict(text='<b>個股損益 (NT$)</b>', font=dict(color='#FBBF24', size=14)),
        height=440,
        xaxis=dict(tickangle=-45),
    )
    fig_pl = 套用深色主題(fig_pl)
    st.plotly_chart(fig_pl, use_container_width=True, config={'displayModeBar': False})


# ════════════════════════════════════════════
# 持股清單卡片
# ════════════════════════════════════════════
st.markdown(f"<div class='section-title'><h2>💼 持股清單</h2><span class='badge'>{len(持股表)} 檔</span></div>", unsafe_allow_html=True)

排序 = st.selectbox("", ["漲幅 ↓", "漲幅 ↑", "市值 ↓", "Kelly ↓", "損益 ↓"],
                    label_visibility="collapsed", key="sort_v3")

for h in 持股表:
    h["Kelly"] = kelly_map.get(h["symbol"], 0)

if "漲幅 ↓" in 排序:
    持股表_排 = sorted(持股表, key=lambda x: -x["漲幅"])
elif "漲幅 ↑" in 排序:
    持股表_排 = sorted(持股表, key=lambda x: x["漲幅"])
elif "市值 ↓" in 排序:
    持股表_排 = sorted(持股表, key=lambda x: -x["市值"])
elif "Kelly ↓" in 排序:
    持股表_排 = sorted(持股表, key=lambda x: -x["Kelly"])
else:
    持股表_排 = sorted(持股表, key=lambda x: -x["損益"])

# 卡片網格（用 single-line HTML 避免 markdown 解析錯誤）
cards_parts = []
for h in 持股表_排:
    if h["漲幅"] >= 15:
        css = "tp"; badge = "<div class='stock-badge'>🎯 Strategy A 觸發</div>"
    elif h["漲幅"] >= 12:
        css = "near-tp"; badge = "<div class='stock-badge'>📈 接近停利</div>"
    elif h["漲幅"] <= -5:
        css = "down"; badge = "<div class='stock-badge' style='background:#EF4444;color:#FFF'>🛑 停損</div>"
    elif h["漲幅"] > 1:
        css = "up"; badge = ""
    elif h["漲幅"] < -1:
        css = "down"; badge = ""
    else:
        css = "flat"; badge = ""

    star = "<span class='star'>⭐</span>" if h["Kelly"] >= 8 else ""
    change_cls = "up" if h["漲幅"] >= 0 else "down"
    pl_cls = "pl-up" if h["損益"] >= 0 else "pl-down"

    # 合成單行 HTML（無換行）
    card = (
        f"<div class='stock-card {css}'>"
        f"<div class='stock-head'>"
        f"<div><div class='stock-sym'>{star}{h['symbol']}</div>"
        f"<div class='stock-name'>{h['name'][:14]}</div></div>"
        f"<div class='stock-price-block'>"
        f"<div class='stock-price'>{h['現價']:,.2f}</div>"
        f"<div class='stock-change {change_cls}'>{h['漲幅']:+.2f}%</div>"
        f"</div></div>"
        f"<div class='stock-meta'>"
        f"<span>{h['shares']} 股</span>"
        f"<span class='kelly'>K {h['Kelly']:.1f}%</span>"
        f"<span class='{pl_cls}'>{h['損益']:+,.0f}</span>"
        f"</div>{badge}</div>"
    )
    cards_parts.append(card)

cards_html = "<div class='stock-grid'>" + "".join(cards_parts) + "</div>"

# 用 components.html 避免 markdown 解析問題
import streamlit.components.v1 as components

# 算需要的高度
rows_needed = (len(持股表_排) + 3) // 4   # 每行 4 個
estimated_height = max(400, rows_needed * 145 + 50)

# 包入完整 HTML 含 CSS
full_html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
* {{ box-sizing: border-box; font-family: -apple-system, 'Microsoft JhengHei', sans-serif; }}
body {{ margin: 0; padding: 0; background: transparent; color: #E5E7EB; }}
.stock-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 12px;
}}
.stock-card {{
    background: linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.02) 100%);
    border: 1px solid rgba(255,255,255,0.08);
    border-left: 3px solid #4B5563;
    border-radius: 12px;
    padding: 14px;
    transition: all 0.2s;
}}
.stock-card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.4); }}
.stock-card.up {{ border-left-color: #22C55E; }}
.stock-card.down {{ border-left-color: #EF4444; }}
.stock-card.tp {{ border-left-color: #FBBF24; background: linear-gradient(135deg, rgba(251,191,36,0.1), rgba(251,191,36,0.02)); }}
.stock-card.near-tp {{ border-left-color: #F59E0B; }}
.stock-head {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }}
.stock-sym {{ font-size: 15px; font-weight: 700; color: #FFFFFF; display: flex; align-items: center; gap: 4px; }}
.star {{ color: #FBBF24; }}
.stock-name {{ font-size: 11px; color: #9CA3AF; margin-top: 2px; }}
.stock-price-block {{ text-align: right; }}
.stock-price {{ font-size: 17px; font-weight: 700; color: #FFFFFF; font-variant-numeric: tabular-nums; }}
.stock-change {{ font-size: 13px; font-weight: 600; }}
.stock-change.up {{ color: #22C55E; }}
.stock-change.down {{ color: #EF4444; }}
.stock-meta {{
    display: flex; justify-content: space-between;
    padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.06);
    font-size: 11px; color: #9CA3AF;
}}
.kelly {{ color: #FBBF24 !important; font-weight: 600; }}
.pl-up {{ color: #22C55E !important; font-weight: 600; }}
.pl-down {{ color: #EF4444 !important; font-weight: 600; }}
.stock-badge {{
    margin-top: 10px; padding: 4px 8px; border-radius: 6px;
    font-size: 10px; font-weight: 600; text-align: center;
    background: linear-gradient(90deg, #FBBF24, #F59E0B); color: #000;
}}
</style>
</head>
<body>
{cards_html}
</body>
</html>
"""

components.html(full_html, height=estimated_height, scrolling=False)


# ════════════════════════════════════════════
# 深度分析
# ════════════════════════════════════════════
st.markdown("<div class='section-title'><h2>🧠 LIS 深度分析</h2><span class='badge'>Smart Intelligence</span></div>", unsafe_allow_html=True)

with st.expander("🏆 跨來源共識排行（305 訊號）"):
    共識資料 = 載入共識()
    sym_info = defaultdict(lambda: {"sources": set(), "BUY": 0, "SELL": 0})
    for s in 共識資料.get("訊號", []):
        sym = s.get("symbol", "")
        if not sym or sym == "NONE":
            continue
        sym_info[sym]["sources"].add(s.get("來源", ""))
        if s.get("類型") == "BUY":
            sym_info[sym]["BUY"] += 1
        elif s.get("類型") == "SELL":
            sym_info[sym]["SELL"] += 1
    共識表 = [{"代號": sym, "來源數": len(info["sources"]),
              "BUY": info["BUY"], "SELL": info["SELL"],
              "淨向": info["BUY"] - info["SELL"]}
             for sym, info in sym_info.items() if len(info["sources"]) >= 2]
    共識表.sort(key=lambda r: (-r["來源數"], -r["淨向"]))

    if 共識表:
        top15 = 共識表[:15]
        fig = go.Figure()
        fig.add_trace(go.Bar(name='BUY', x=[r["代號"] for r in top15],
                             y=[r["BUY"] for r in top15],
                             marker_color='#22C55E'))
        fig.add_trace(go.Bar(name='SELL', x=[r["代號"] for r in top15],
                             y=[-r["SELL"] for r in top15],
                             marker_color='#EF4444'))
        fig.update_layout(barmode='relative', height=400,
                          title=dict(text='<b>BUY vs SELL by 來源</b>',
                                     font=dict(color='#FBBF24')))
        fig = 套用深色主題(fig)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    elif os.getenv("LIS_PORTFOLIO_PATH"):
        st.info("☁️ **雲端無共識訊號資料** — 此功能需本機每日累積的 community_consensus.json。")


with st.expander("🏆 Kelly TOP15 數學驗證核心持股"):
    rows = []
    for sym, r in kelly_db.get("標的", {}).items():
        if "error" in r:
            continue
        s = r.get("統計", {})
        if s.get("交易數", 0) < 10:
            continue
        rows.append({"symbol": sym, "name": r.get("name", "")[:12],
                     "交易數": s["交易數"], "勝率": s['勝率']*100,
                     "Kelly": s["Kelly_pct"]})
    rows.sort(key=lambda r: -r["Kelly"])
    top15 = rows[:15]

    if top15:
        fig = go.Figure(data=[go.Bar(
            x=[r["Kelly"] for r in top15],
            y=[f"{r['symbol']} · {r['name']}" for r in top15],
            orientation='h',
            marker=dict(color=[r["Kelly"] for r in top15],
                        colorscale=[[0, '#3B0764'], [1, '#FBBF24']],
                        line=dict(color='#0a0a14', width=1)),
            text=[f"{r['Kelly']:.2f}% · 勝率 {r['勝率']:.0f}%" for r in top15],
            textposition='outside',
            textfont=dict(color='#E5E7EB', family='JetBrains Mono', size=10),
        )])
        fig.update_layout(
            title=dict(text='<b>Kelly% TOP 15</b>', font=dict(color='#FBBF24')),
            height=520,
        )
        fig = 套用深色主題(fig)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    elif os.getenv("LIS_PORTFOLIO_PATH"):
        st.info("☁️ **雲端無 Kelly 資料** — 此功能需本機每日累積的 win_rate_db.json（需 10+ 筆交易歷史）。")


with st.expander("🎯 策略池 8 種獨立掃描"):
    if st.button("🔍 開始掃描", key="scan_pool_v3"):
        from modules import strategy_pool, fugle_market, capital_planner
        cfg = capital_planner.載入資金設定()
        with st.spinner("掃描中..."):
            全部 = strategy_pool.組裝標的清單(
                取得現價=lambda s: (fugle_market.即時報價_fallback(s) or {}).get("close"),
            )
            持股集 = {p["symbol"] for p in cfg.get("current_positions", [])
                      if p.get("symbol") != "AGGREGATE"}
            DCA = [it["symbol"] for it in cfg.get("long_term_dca", {}).get("items", []) if it.get("symbol")]
            結果 = strategy_pool.掃描策略池(全部, 持股代號集=持股集, DCA清單=DCA)

        # Phase 33.2 — 雲端 placeholder 偵測
        is_cloud = bool(os.getenv("LIS_PORTFOLIO_PATH"))
        總入選 = sum(設["總數"] for 設 in 結果.values())

        if is_cloud and 總入選 == 0:
            st.info(
                "☁️ **雲端無位階資料** — 策略池需要本機每日 8AM 算出的「positional_state.json」"
                "（VIX/RSI/MACD/位階分數等）才能掃描入選標的。\n\n"
                "**雲端 dashboard 主要看**：部位 / 損益 / ARK gauges / 持股配置 / 累計獲利。\n\n"
                "**想看策略池入選**：去看 8AM LINE 推播的「全息儀表板」或開本機 web_dashboard。"
            )
        elif 總入選 == 0:
            st.warning("⚠️ 今日策略池無入選標的（市場觀望中）")
        else:
            for 策名, 設 in 結果.items():
                if 設["總數"] > 0:
                    st.markdown(f"### {設['emoji']} {策名} <span style='color:#9CA3AF;font-size:13px'>{設['總數']} 檔</span>", unsafe_allow_html=True)
                    inner = "<div class='stock-grid'>"
                    for r in 設["入選"][:4]:
                        inner += f"""<div class='stock-card flat'>
                        <div class='stock-sym'>{r['symbol']}</div>
                        <div class='stock-name'>{r.get('name', '')[:14]}</div>
                        <div style='margin-top:6px;font-size:11px;color:#9CA3AF'>位階 {r.get('位階', 0):.0f}</div>
                        </div>"""
                    inner += "</div>"
                    st.markdown(inner, unsafe_allow_html=True)


with st.expander("📐 市場底部 SOP（Sylvie 5 指標）"):
    col1, col2 = st.columns([1, 4])
    with col1:
        run_sop = st.button("🔍 跑掃描", key="sop_v3")

    if run_sop:
        from modules import bottom_detector
        with st.spinner("抓 VIX..."):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                r = bottom_detector.即時底部判定()

        # 等級顏色
        命中 = r["命中數"]
        if 命中 >= 4:
            等級色 = "#EF4444"; 等級背 = "rgba(239,68,68,0.15)"
        elif 命中 >= 2:
            等級色 = "#F59E0B"; 等級背 = "rgba(245,158,11,0.15)"
        else:
            等級色 = "#22C55E"; 等級背 = "rgba(34,197,94,0.1)"

        st.markdown(f"""
        <div style='background:{等級背};border:1px solid {等級色}40;border-radius:12px;padding:24px;margin:16px 0'>
            <div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px'>
                <div>
                    <div style='font-size:11px;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.1em'>命中數</div>
                    <div style='font-family:JetBrains Mono;font-size:48px;font-weight:700;color:{等級色};line-height:1'>{命中}<span style='font-size:20px;color:#9CA3AF'>/5</span></div>
                </div>
                <div>
                    <div style='font-size:11px;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.1em'>等級</div>
                    <div style='font-size:24px;font-weight:700;color:{等級色};margin-top:8px'>{r['等級']}</div>
                </div>
                <div>
                    <div style='font-size:11px;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.1em'>部位倍率</div>
                    <div style='font-family:JetBrains Mono;font-size:40px;font-weight:700;color:{等級色};line-height:1'>×{r['部位倍率']}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 5 指標 — 用 components.html 避免渲染問題
        指標映 = {
            "VIX": ("📊", "VIX"),
            "Put/Call": ("⚖️", "Put/Call"),
            "融資": ("💳", "融資餘額"),
            "外資淨空": ("🏦", "外資淨空"),
            "技術": ("📐", "技術背離"),
        }
        指標卡 = []
        for d in r["詳情"]:
            for key, (icon, label) in 指標映.items():
                if key in d:
                    is_data = "無資料" not in d
                    is_warn = "⚠️" in d
                    is_critical = "🚨" in d
                    css = "no-data" if not is_data else ("hit" if is_critical else "warn" if is_warn else "safe")
                    # 正確提取值：格式「emoji name value status」
                    parts = d.split(" ")
                    if not is_data:
                        值 = "—"
                        # Phase 33.2 — 雲端模式：台灣 TAIFEX/TWSE API 限國內 IP
                        # 區分「真的 API 沒設」vs「雲端網路限制」
                        is_cloud = bool(os.getenv("LIS_PORTFOLIO_PATH"))
                        if is_cloud and key in ("Put/Call", "融資", "外資淨空"):
                            補充 = "本機資料 ☁️"
                        else:
                            補充 = "API 待補"
                    elif key == "技術":
                        值 = "✓"
                        補充 = "無背離"
                    else:
                        # parts: ['emoji', name, value, ...rest]
                        值 = parts[2] if len(parts) > 2 else "?"
                        補充 = " ".join(parts[3:]) if len(parts) > 3 else ""
                    指標卡.append((css, icon, label, 值, 補充))
                    break

        # 用 components.html 直接渲染
        sop_html = (
            "<style>"
            "body{margin:0;padding:0;background:transparent;font-family:-apple-system,sans-serif;}"
            ".grid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;}"
            ".item{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:16px;text-align:center;}"
            ".item.hit{border-color:rgba(239,68,68,0.5);background:rgba(239,68,68,0.08);}"
            ".item.warn{border-color:rgba(245,158,11,0.5);background:rgba(245,158,11,0.08);}"
            ".item.safe{border-color:rgba(34,197,94,0.3);background:rgba(34,197,94,0.05);}"
            ".item.no-data{opacity:0.4;}"
            ".icon{font-size:24px;margin-bottom:6px;}"
            ".label{font-size:11px;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.05em;}"
            ".value{font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:700;color:#FFFFFF;margin:6px 0 4px 0;}"
            ".item.hit .value{color:#EF4444;}"
            ".item.safe .value{color:#22C55E;}"
            ".sub{font-size:10px;color:#6B7280;}"
            "</style>"
            "<div class='grid'>"
        )
        for css, icon, label, 值, 補充 in 指標卡:
            sop_html += (
                f"<div class='item {css}'>"
                f"<div class='icon'>{icon}</div>"
                f"<div class='label'>{label}</div>"
                f"<div class='value'>{值}</div>"
                f"<div class='sub'>{補充}</div>"
                f"</div>"
            )
        sop_html += "</div>"
        components.html(sop_html, height=140, scrolling=False)


with st.expander("📰 今日新聞情緒"):
    path = 專案根.parent / "數據" / "daily" / f"news_{datetime.now():%Y-%m-%d}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        st.markdown(f"""
        <div style='display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0'>
            <div class='metric-card' style='padding:16px'>
                <div class='metric-label'>📰 總新聞</div>
                <div class='metric-value' style='font-size:28px'>{data.get("新聞數", 0)}</div>
            </div>
            <div class='metric-card' style='padding:16px;border-color:rgba(239,68,68,0.3)'>
                <div class='metric-label'>🚨 緊急</div>
                <div class='metric-value down' style='font-size:28px'>{data.get("緊急數", 0)}</div>
            </div>
            <div class='metric-card' style='padding:16px;border-color:rgba(245,158,11,0.3)'>
                <div class='metric-label'>⚠️ 高風險</div>
                <div class='metric-value warn' style='font-size:28px'>{data.get("高風險數", 0)}</div>
            </div>
            <div class='metric-card' style='padding:16px;border-color:rgba(34,197,94,0.3)'>
                <div class='metric-label'>📈 利多</div>
                <div class='metric-value up' style='font-size:28px'>{data.get("利多數", 0)}</div>
            </div>
        </div>
        <h3 style='margin:24px 0 12px 0;color:#FBBF24'>{data.get('情緒等級', '?')}</h3>
        """, unsafe_allow_html=True)

        # 高警示新聞
        高警示 = [n for n in data.get("新聞列表", []) if n["分數"] <= -2][:6]
        if 高警示:
            st.markdown("<div style='font-size:13px;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.1em;margin:16px 0 8px 0'>🚨 高警示</div>", unsafe_allow_html=True)
            for n in 高警示:
                tag_css = "urgent" if n["分數"] <= -3 else "high"
                st.markdown(f"""<div class='news-item {tag_css}'>
                <span class='news-tag {tag_css}'>{"緊急" if n["分數"] <= -3 else "高風險"}</span>
                <span class='news-text'>{n['標題'][:80]}</span>
                </div>""", unsafe_allow_html=True)

        利多 = [n for n in data.get("新聞列表", []) if n["分數"] >= 1][:4]
        if 利多:
            st.markdown("<div style='font-size:13px;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.1em;margin:16px 0 8px 0'>📈 利多新聞</div>", unsafe_allow_html=True)
            for n in 利多:
                st.markdown(f"""<div class='news-item bull'>
                <span class='news-tag bull'>利多</span>
                <span class='news-text'>{n['標題'][:80]}</span>
                </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════
# Sidebar
# ════════════════════════════════════════════
with st.sidebar:
    st.markdown("### Quick Actions")
    if st.button("📡 推全息儀表板", use_container_width=True):
        import subprocess
        with st.spinner("推送..."):
            subprocess.run([str(專案根 / ".venv/Scripts/python.exe"), "push_holistic.py"], cwd=str(專案根))
        st.success("✅ 已推 LINE")
    if st.button("🎯 推即時決策", use_container_width=True):
        import subprocess
        with st.spinner("推送..."):
            subprocess.run([str(專案根 / ".venv/Scripts/python.exe"), "instant_decision.py"], cwd=str(專案根))
        st.success("✅ 已推 LINE")
    if st.button("⚡ 跑盤中警示", use_container_width=True):
        import subprocess
        with st.spinner("掃描..."):
            r = subprocess.run([str(專案根 / ".venv/Scripts/python.exe"), "-m", "modules.intraday_alerts"],
                              cwd=str(專案根), capture_output=True, text=True, encoding="utf-8")
        if "觸發" in (r.stdout or ""):
            st.success("✅ 推 LINE")
        else:
            st.info("⚪ 無警示")

    st.markdown("---")
    st.markdown("### System Status")
    st.markdown(f"""<div style='padding:12px;background:rgba(255,255,255,0.03);border-radius:8px'>
    <div style='font-size:11px;color:#6B7280'>Kelly DB</div>
    <div style='font-size:18px;font-weight:600;color:#FBBF24'>{len([r for r in kelly_db.get('標的', {}).values() if 'error' not in r])} 檔</div>
    </div>""", unsafe_allow_html=True)

    st.markdown(f"""<div style='padding:12px;background:rgba(255,255,255,0.03);border-radius:8px;margin-top:8px'>
    <div style='font-size:11px;color:#6B7280'>外部訊號</div>
    <div style='font-size:18px;font-weight:600;color:#FBBF24'>{len(共識資料.get('訊號', []))} 筆</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.caption("LIS v1.1 · Phase 1-36")
    st.caption("Professional Investment Intelligence")
