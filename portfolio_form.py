"""
L.I.S 持股配置表單 — Phase 2.7a 本機版
跑法：在 venv 裡執行
    streamlit run D:\LIS股票投資系統\程式碼\portfolio_form.py
打開瀏覽器到 http://localhost:8501 即可填寫。

設計仿方舟黑底黃色：上方持股配置建議圓環 + 下方表單。
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

# 把 modules 加進 path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from modules import chart_generator


PORTFOLIO_PATH = Path(__file__).resolve().parent.parent / "API" / "portfolio.json"
SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "數據" / "daily"


# ─── 頁面設定 ───
st.set_page_config(
    page_title="L.I.S 持股配置",
    page_icon="💰",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─── 方舟黑黃 CSS（手機優先） ───
st.markdown("""
<style>
/* 全頁 */
.stApp { background-color: #000000; }
section.main > div { background-color: #000000; padding-top: 1rem; }
h1, h2, h3, h4, p, label, span, div { color: #FFFFFF !important; }

/* 輸入框：手機觸控大區域 */
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
    font-size: 16px !important;
}

/* 數字 +/- 按鈕 */
.stNumberInput button {
    background-color: #1A1A22 !important;
    color: #FBBF24 !important;
    border: none !important;
    width: 36px !important;
    height: 36px !important;
}

/* 標籤 */
.stTextInput label, .stNumberInput label, .stSelectbox label {
    color: #A0A4B8 !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    margin-bottom: 6px !important;
}

/* 主要儲存按鈕：大、亮、明顯 */
.stFormSubmitButton button, .stButton button {
    background-color: #FBBF24 !important;
    color: #000000 !important;
    font-weight: 800 !important;
    font-size: 18px !important;
    height: 56px !important;
    border: none !important;
    border-radius: 14px !important;
    box-shadow: 0 4px 12px rgba(251, 191, 36, 0.25);
}
.stFormSubmitButton button:hover, .stButton button:hover {
    background-color: #FFD55E !important;
    transform: translateY(-1px);
}

/* 小幫手 class */
.dim { color: #888888 !important; font-size: 13px; }
.big-yellow { color: #FBBF24 !important; font-size: 36px; font-weight: bold; }
.gauge-box {
    background: linear-gradient(180deg, #000000 0%, #0A0A12 100%);
    padding: 16px 0 4px 0;
    border-radius: 16px;
}
.divider-yellow { border-top: 1px solid #2A2A35; margin: 20px 0; }

/* Expander 樣式 */
[data-testid="stExpander"] {
    background-color: #0A0A12 !important;
    border: 1px solid #2A2A35 !important;
    border-radius: 12px !important;
    margin-top: 8px;
}

/* 手機特別優化（寬度 ≤ 768px） */
@media (max-width: 768px) {
    section.main > div { padding-left: 1rem !important; padding-right: 1rem !important; }
    h2 { font-size: 22px !important; }
    h3 { font-size: 18px !important; }
    .stNumberInput input, .stTextInput input { font-size: 18px !important; }
}

/* 隱藏 Streamlit 預設工具列（更乾淨） */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }
</style>

<!-- PWA + 行動版視窗 -->
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#000000">
""", unsafe_allow_html=True)


# ─── 載入現有設定 ───
def 載入設定():
    with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def 存設定(設定):
    with open(PORTFOLIO_PATH, "w", encoding="utf-8") as f:
        json.dump(設定, f, ensure_ascii=False, indent=2)


def 取最新Enjoy分數():
    """從最新一份快照讀 Enjoy Index 分數。"""
    if not SNAPSHOT_DIR.exists():
        return None
    files = sorted(SNAPSHOT_DIR.glob("*.json"), reverse=True)
    if not files:
        return None
    try:
        with open(files[0], "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("enjoy_index", {}).get("總分")
    except Exception:
        return None


設定 = 載入設定()
最新Enjoy = 取最新Enjoy分數()


# ─── 頂部：標題 ───
col_title, col_status = st.columns([3, 1])
with col_title:
    st.markdown('<h2 style="color:#FFF; margin:0;">L.I.S 持股配置</h2>',
                unsafe_allow_html=True)
    st.markdown(f'<p class="dim">最後更新 {datetime.now():%Y-%m-%d %H:%M}</p>',
                unsafe_allow_html=True)
with col_status:
    if 最新Enjoy is not None:
        色 = ("#FBBF24" if 最新Enjoy >= 70
              else "#F59E0B" if 最新Enjoy >= 40
              else "#EF4444")
        st.markdown(
            f'<div style="text-align:right;">'
            f'<p class="dim" style="margin:0;">當前 Enjoy</p>'
            f'<p style="color:{色}; font-size:28px; font-weight:bold; margin:0;">'
            f'{最新Enjoy}</p></div>',
            unsafe_allow_html=True
        )

st.markdown('<div class="divider-yellow"></div>', unsafe_allow_html=True)


# ─── 圓環圖（持股配置建議）放最上面 ───
# 用目前的持股市值 / 總資金 × 100 算（Phase 32.5：改用即時市值不用成本）
持股 = 設定.get("current_positions", [])
try:
    from modules import portfolio_tracker
    真倉 = portfolio_tracker.追蹤真倉(設定)
    總持股市值 = 真倉["總計"]["市值_twd"]
except Exception:
    # Fallback：抓不到即時就用成本估
    總持股市值 = sum(p.get("shares", 0) * p.get("avg_cost", 0) for p in 持股)
# 如果使用者尚未細列持股，用 total - cash 推估
if 總持股市值 == 0:
    總持股市值 = max(0, 設定["total_capital_twd"] - 設定["current_cash_twd"])

if 設定["total_capital_twd"] > 0:
    配置比例 = 總持股市值 / 設定["total_capital_twd"] * 100
else:
    配置比例 = 0

st.markdown('<div class="gauge-box">', unsafe_allow_html=True)
with st.spinner("繪製持股配置圓環..."):
    png = chart_generator.生成Enjoy圓環(
        round(配置比例, 1),
        status=f"{總持股市值/10000:.1f} 萬 / {設定['total_capital_twd']/10000:.0f} 萬",
        副標="持股配置建議",
    )
    st.image(png, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)


# ─── 表單 ───
st.markdown("### 📝 更新你的資金與持股")

with st.form("portfolio_form"):
    col1, col2 = st.columns(2)

    with col1:
        twd_cash = st.number_input(
            "💵 台幣現金 (TWD)",
            value=int(設定["current_cash_twd"]),
            step=10000,
            format="%d",
            help="目前未動用的台幣現金"
        )

        total_capital = st.number_input(
            "💰 總資金 (TWD)",
            value=int(設定["total_capital_twd"]),
            step=10000,
            format="%d",
            help="總資金水位"
        )

    with col2:
        usd_cash = st.number_input(
            "💵 美元現金 (USD)",
            value=0,
            step=100,
            format="%d",
            help="目前未動用的美元現金"
        )

        usd_twd_rate = st.number_input(
            "💱 USD/TWD 匯率",
            value=float(設定["currency_rates"]["USD_TWD"]),
            step=0.1,
            format="%.2f",
        )

    持股市值 = st.number_input(
        "📈 目前持股市值 (TWD)",
        value=int(max(0, 總持股市值)),
        step=10000,
        format="%d",
        help="所有股票今日市值合計（如果不確定，可從 LINE 報表抓今日收盤估算）"
    )

    strategy_options = {
        "current":     "🎯 LIS 預設（多檔分散 + Enjoy Index 訊號）",
        "passive_etf": "🪙 無腦投資大盤 ETF",
        "balanced":    "⚖️ 一半存股 + 一半短線",
        "all_in_one":  "🚀 重壓一檔最看好的股票",
    }
    strategy = st.selectbox(
        "📊 策略模式",
        options=list(strategy_options.keys()),
        format_func=lambda k: strategy_options[k],
        index=list(strategy_options.keys()).index(設定.get("strategy_mode", "current")),
    )

    st.markdown('<p class="dim">點下方按鈕儲存，明天的報表就會用新數字計算建議部位。</p>',
                unsafe_allow_html=True)

    submit = st.form_submit_button("💾 儲存配置", use_container_width=True)


if submit:
    # 算出總現金（含美元換算）
    twd_from_usd = usd_cash * usd_twd_rate
    總現金 = twd_cash + twd_from_usd

    # 寫回設定
    設定["total_capital_twd"] = total_capital
    設定["current_cash_twd"] = 總現金
    設定["currency_rates"]["USD_TWD"] = usd_twd_rate
    設定["strategy_mode"] = strategy
    # 持股市值若大於 0 且還沒有 current_positions 細項，記一個彙總項
    if 持股市值 > 0 and not 持股:
        設定["current_positions"] = [{
            "_note": "彙總市值（待補個股明細）",
            "shares": 1,
            "avg_cost": 持股市值,
            "symbol": "AGGREGATE",
        }]
    # 重算 stock_allocation_twd（80% 規則）
    設定["stock_allocation_twd"] = int(total_capital * 0.8)

    存設定(設定)
    st.success(
        f"✅ 已更新！\n\n"
        f"- 總資金：NT$ {total_capital:,.0f}\n"
        f"- 總現金：NT$ {總現金:,.0f}（含美元 {usd_cash} × {usd_twd_rate:.2f}）\n"
        f"- 持股市值：NT$ {持股市值:,.0f}\n"
        f"- 持股配置：{(持股市值 / total_capital * 100):.1f}%\n"
        f"- 策略：{strategy_options[strategy]}\n\n"
        f"檔案位置：`{PORTFOLIO_PATH}`"
    )
    st.balloons()


# ─── 底部小工具區 ───
st.markdown('<div class="divider-yellow"></div>', unsafe_allow_html=True)

with st.expander("📋 進階：分檔列出持股（給來日自動計算用）"):
    st.markdown(
        '<p class="dim">這裡可以列出每一檔的股數和成本。MVP 階段先用上方「持股市值」彙總即可。</p>',
        unsafe_allow_html=True
    )
    st.json(設定.get("current_positions", []))

with st.expander("⚙️ 風控規則（藍圖第二章）"):
    rules = 設定.get("risk_rules", {})
    st.markdown(f"""
    - 單一股票上限：**{rules.get('max_per_stock_pct', 20)}% 總資金**
    - 最小現金保留：**{rules.get('min_cash_reserve_pct', 20)}%**
    - 槓桿上限：**{rules.get('max_leverage_pct', 30)}%**
    - 維持率下限：**{rules.get('min_maintain_ratio', 200)}%**
    """)
