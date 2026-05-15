"""
LIS 持股表單（本機 Streamlit App）
讀寫 portfolio.json，即時抓股價算損益。

啟動：
  雙擊 啟動持股表單.bat
  或 .venv\\Scripts\\streamlit.exe run portfolio_app.py
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))
PORTFOLIO_PATH = 專案根.parent / "API" / "portfolio.json"
WATCHLIST_PATH = 專案根.parent / "API" / "watchlist.json"

from modules import technical, forex


# ─────────────────────────────────────────────
# 代號規範化 + 中文名查表
# ─────────────────────────────────────────────
def 規範化代號(原始: str) -> str:
    """
    自動補 .TW 後綴：
      '0050'    → '0050.TW'
      '00631L'  → '00631L.TW'
      '00981A'  → '00981A.TW'
      '2330'    → '2330.TW'
      '2330.TW' → '2330.TW'（不變）
      'TSLA'    → 'TSLA'（不變，美股）
      'tsm'     → 'TSM'（轉大寫）
    """
    s = (原始 or "").strip().upper()
    if not s:
        return ""
    # 已有後綴
    if s.endswith(".TW") or s.endswith(".TWO"):
        return s
    # 純英文（美股）
    if s.isalpha():
        return s
    # 開頭數字 → 視為台股
    if re.match(r"^\d", s):
        return s + ".TW"
    return s


@st.cache_data
def 載入watchlist_中文表() -> dict:
    """{symbol_normalized: name} 從 watchlist.json 載入。"""
    if not WATCHLIST_PATH.exists():
        return {}
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        wl = json.load(f)
    表 = {}
    for region in wl.get("regions", []):
        for s in region.get("stocks", []):
            sym = 規範化代號(s.get("symbol", ""))
            if sym:
                表[sym] = s.get("name", "")
    # 也加 indices（雖然不會出現在持股，但 normalize 一致性）
    return 表


def 查中文名(代號: str) -> str:
    """從 watchlist 查中文名（規範化後比對）。沒有回空。"""
    if not 代號:
        return ""
    return 載入watchlist_中文表().get(規範化代號(代號), "")


# ─────────────────────────────────────────────
# 頁面設定
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="LIS 持股表單",
    page_icon="💼",
    layout="wide",
)


# ─────────────────────────────────────────────
# 載入 / 儲存
# ─────────────────────────────────────────────
def 載入設定():
    with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def 儲存設定(cfg: dict):
    # 備份舊版
    備份 = PORTFOLIO_PATH.with_suffix(".json.bak")
    if PORTFOLIO_PATH.exists():
        備份.write_bytes(PORTFOLIO_PATH.read_bytes())
    with open(PORTFOLIO_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


@st.cache_data(ttl=300)
def 抓即時價(symbol: str):
    """5 分鐘 cache 抓即時股價。"""
    try:
        每日, _ = technical.取得每日股價(symbol, period="5d")
        if 每日:
            return float(每日[0]["close"])
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────
st.title("💼 LIS 持股表單")
st.caption("買賣後手動更新一次（5 分鐘），系統自動算損益、配合 Enjoy Index 給建議")

cfg = 載入設定()

# 動態匯率顯示（小提示）
固定匯率_顯示 = cfg.get("currency_rates", {}).get("USD_TWD", 32.0)
匯率資訊_顯示 = forex.取得USD_TWD匯率(fallback=固定匯率_顯示)
匯率來源圖示 = {"yfinance": "🟢", "cache": "🟢", "stale_cache": "🟡",
                "fallback": "🔴"}.get(匯率資訊_顯示["source"], "")
st.caption(f"{匯率來源圖示} USD/TWD = **{匯率資訊_顯示['rate']}** "
           f"（{匯率資訊_顯示['source']}, 更新於 {匯率資訊_顯示.get('updated_at', '?')[:16]}）")

# 三欄頂部資訊
col1, col2, col3, col4 = st.columns(4)
col1.metric("總資金", f"NT$ {cfg['total_capital_twd']:,}")
col2.metric("現金", f"NT$ {cfg['current_cash_twd']:,.0f}")
col3.metric("股票配置上限", f"NT$ {cfg['stock_allocation_twd']:,}")

# 計算當前持股市值（即時）
持股清單 = [p for p in cfg.get("current_positions", [])
            if p.get("symbol") != "AGGREGATE"]
持股市值 = 0.0
持股成本 = 0.0
有持股 = bool(持股清單)
# 動態抓即時 USD/TWD（fallback 到 portfolio.json 固定值）
固定匯率 = cfg.get("currency_rates", {}).get("USD_TWD", 32.0)
匯率資訊 = forex.取得USD_TWD匯率(fallback=固定匯率)
USD_TWD = 匯率資訊["rate"]

if 有持股:
    for p in 持股清單:
        sym = 規範化代號(p["symbol"])
        股數 = p.get("shares", 0)
        成本 = p.get("avg_cost", 0)
        現價 = 抓即時價(sym)
        if 現價:
            倍率 = USD_TWD if not (sym.endswith(".TW") or sym.endswith(".TWO")) else 1.0
            持股市值 += 現價 * 股數 * 倍率
            持股成本 += 成本 * 股數 * 倍率

if 有持股 and 持股成本 > 0:
    損益 = 持股市值 - 持股成本
    損益率 = 損益 / 持股成本 * 100
    顏色 = "🟢" if 損益 >= 0 else "🔴"
    col4.metric(f"持股市值 {顏色}",
                f"NT$ {持股市值:,.0f}",
                f"{損益:+,.0f} ({損益率:+.2f}%)")
else:
    col4.metric("持股市值", "等待輸入")


# ─────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📋 持股明細", "⚙️ 基本設定", "📥 CSV 匯入"])

# ─── Tab 1: 持股明細 ───
with tab1:
    st.subheader("持股明細")

    # ─── 快速新增區塊 ───
    with st.expander("➕ 快速新增（輸入代號自動帶中文）", expanded=False):
        st.caption("台股範例：`2330` / `0050` / `00876` ｜ "
                   "美股範例：`NVDA` / `TSLA` / `AAPL`")
        快_col1, 快_col2, 快_col3, 快_col4 = st.columns([2, 2, 1, 1])
        with 快_col1:
            快_sym = st.text_input("代號", key="快_sym",
                                    placeholder="例：2330 / NVDA / 00876")
        with 快_col2:
            # 自動帶中文名
            自動中文 = 查中文名(快_sym) if 快_sym else ""
            # 偵測是台股還美股
            是美股 = (快_sym.strip().isalpha() if 快_sym else False)
            label = ("美股名稱（自動帶）" if 是美股
                     else "中文名（自動帶）")
            快_name = st.text_input(label,
                                     value=自動中文, key="快_name",
                                     placeholder="可手動修改")
        with 快_col3:
            快_股數 = st.number_input("股數", min_value=0, step=1,
                                       key="快_股數")
        with 快_col4:
            幣 = "USD" if 是美股 else "TWD"
            快_成本 = st.number_input(f"成本 ({幣})",
                                       min_value=0.0, step=0.01,
                                       format="%.2f", key="快_成本")

        if st.button("➕ 加入持股", type="secondary"):
            if 快_sym and 快_股數 > 0 and 快_成本 > 0:
                normalized = 規範化代號(快_sym)
                cfg.setdefault("current_positions", [])
                # 過濾 AGGREGATE
                cfg["current_positions"] = [
                    p for p in cfg["current_positions"]
                    if p.get("symbol") != "AGGREGATE"
                ]
                cfg["current_positions"].append({
                    "symbol": normalized,
                    "name": 快_name or 查中文名(normalized) or "",
                    "shares": int(快_股數),
                    "avg_cost": float(快_成本),
                })
                儲存設定(cfg)
                st.success(f"✅ 已加入 {normalized} ({快_name}) "
                           f"{int(快_股數)} 股 @ {快_成本:.2f}")
                st.cache_data.clear()
                st.rerun()
            else:
                st.warning("代號 / 股數 / 成本 都要填")

    st.caption("⬇️ 完整表格（可直接編輯，按表格右下角 ➕ 新增列）")

    # 用 DataFrame 包裝（避免空 list 進 st.data_editor 出錯）
    if 持股清單:
        # 把 symbol 也 normalize 後再 render（讓使用者看到 .TW）
        for p in 持股清單:
            p["symbol"] = 規範化代號(p.get("symbol", ""))
            if not p.get("name"):
                p["name"] = 查中文名(p["symbol"])
        df = pd.DataFrame(持股清單)
        # 補欄位
        for col in ["symbol", "name", "shares", "avg_cost"]:
            if col not in df.columns:
                df[col] = "" if col in ("symbol", "name") else 0
        df = df[["symbol", "name", "shares", "avg_cost"]]
    else:
        df = pd.DataFrame([
            {"symbol": "", "name": "", "shares": 0, "avg_cost": 0.0}
        ])

    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        column_config={
            "symbol": st.column_config.TextColumn(
                "代號",
                help="台股加 .TW（例 2330.TW）、美股直接寫（例 TSLA）",
                width="small",
                required=False,
            ),
            "name": st.column_config.TextColumn(
                "中文名",
                help="可選填",
                width="small",
            ),
            "shares": st.column_config.NumberColumn(
                "股數",
                help="不是張！1 張 = 1000 股",
                min_value=0,
                step=1,
                width="small",
            ),
            "avg_cost": st.column_config.NumberColumn(
                "平均成本",
                help="每股成本（含手續費攤）",
                min_value=0.0,
                step=0.01,
                format="%.2f",
                width="small",
            ),
        },
        use_container_width=True,
        key="持股表",
    )

    # 補上即時股價 / 損益（只讀預覽）
    st.markdown("---")
    st.markdown("##### 📊 即時損益預覽（自動抓股價）")
    st.caption(f"台股自動補 `.TW`（例 `0050` → `0050.TW`）"
               f"、美股純英文（NVDA / TSLA）"
               f"｜匯率 USD/TWD = {USD_TWD}")
    if not edited_df.empty:
        預覽行 = []
        # 分台股 / 美股小計
        台_市值, 台_成本 = 0, 0
        美_市值_usd, 美_成本_usd = 0, 0

        for _, p in edited_df.iterrows():
            原sym = str(p.get("symbol", "")).strip()
            if not 原sym:
                continue
            sym = 規範化代號(原sym)
            try:
                股數 = int(p.get("shares", 0) or 0)
                成本 = float(p.get("avg_cost", 0) or 0)
            except (ValueError, TypeError):
                continue
            if 股數 <= 0 or 成本 <= 0:
                continue

            is_us = not (sym.endswith(".TW") or sym.endswith(".TWO"))
            幣別 = "USD" if is_us else "TWD"
            幣號 = "$" if is_us else "NT$"

            現價 = 抓即時價(sym)
            if 現價:
                市值_原幣 = 現價 * 股數
                損益_原幣 = (現價 - 成本) * 股數
                損益率 = (現價 / 成本 - 1) * 100
                顏色 = "🟢" if 損益_原幣 >= 0 else "🔴"

                # TWD 換算（美股 ×匯率）
                if is_us:
                    市值_twd = 市值_原幣 * USD_TWD
                    損益_twd = 損益_原幣 * USD_TWD
                    美_市值_usd += 市值_原幣
                    美_成本_usd += 成本 * 股數
                else:
                    市值_twd = 市值_原幣
                    損益_twd = 損益_原幣
                    台_市值 += 市值_原幣
                    台_成本 += 成本 * 股數

                預覽行.append({
                    "代號": sym,
                    "中文名": p.get("name", "") or 查中文名(sym) or "",
                    "幣別": 幣別,
                    "股數": 股數,
                    "成本": f"{幣號}{成本:.2f}",
                    "現價": f"{幣號}{現價:.2f}",
                    "市值": (f"{幣號}{市值_原幣:,.0f}"
                              + (f" (≈NT${市值_twd:,.0f})" if is_us else "")),
                    "損益": f"{顏色} {幣號}{損益_原幣:+,.0f}",
                    "損益率": f"{損益率:+.2f}%",
                })
            else:
                預覽行.append({
                    "代號": sym,
                    "中文名": p.get("name", "") or 查中文名(sym) or "",
                    "幣別": 幣別,
                    "股數": 股數,
                    "成本": f"{幣號}{成本:.2f}",
                    "現價": "❌ 抓不到",
                    "市值": "-",
                    "損益": "-",
                    "損益率": "-",
                })

        if 預覽行:
            st.dataframe(pd.DataFrame(預覽行),
                         hide_index=True,
                         use_container_width=True)

            # 台股 + 美股 + 總計三列
            col1, col2, col3 = st.columns(3)
            with col1:
                if 台_成本 > 0:
                    台_損益 = 台_市值 - 台_成本
                    台_率 = 台_損益 / 台_成本 * 100
                    色 = "🟢" if 台_損益 >= 0 else "🔴"
                    st.metric(f"📊 台股小計 {色}",
                              f"NT$ {台_市值:,.0f}",
                              f"{台_損益:+,.0f} ({台_率:+.2f}%)")
                else:
                    st.metric("📊 台股小計", "—", "尚無台股")
            with col2:
                if 美_成本_usd > 0:
                    美_損益_usd = 美_市值_usd - 美_成本_usd
                    美_率 = 美_損益_usd / 美_成本_usd * 100
                    色 = "🟢" if 美_損益_usd >= 0 else "🔴"
                    st.metric(f"🌎 美股小計 {色}",
                              f"$ {美_市值_usd:,.2f}",
                              f"${美_損益_usd:+,.2f} ({美_率:+.2f}%)")
                else:
                    st.metric("🌎 美股小計", "—", "尚無美股")
            with col3:
                總市值_twd = 台_市值 + 美_市值_usd * USD_TWD
                總成本_twd = 台_成本 + 美_成本_usd * USD_TWD
                if 總成本_twd > 0:
                    總損益 = 總市值_twd - 總成本_twd
                    總率 = 總損益 / 總成本_twd * 100
                    色 = "🟢" if 總損益 >= 0 else "🔴"
                    st.metric(f"💰 整體（TWD）{色}",
                              f"NT$ {總市值_twd:,.0f}",
                              f"{總損益:+,.0f} ({總率:+.2f}%)")
        else:
            st.info("還沒有有效持股（請填 代號 + 股數 + 成本）")

    st.markdown("---")

    # 儲存按鈕
    儲存欄1, 儲存欄2 = st.columns([1, 3])
    with 儲存欄1:
        if st.button("💾 儲存到 portfolio.json", type="primary",
                     use_container_width=True):
            # 過濾空白列 + 規範化 symbol
            新持股 = []
            for _, p in edited_df.iterrows():
                原sym = str(p.get("symbol", "")).strip()
                if not 原sym:
                    continue
                sym = 規範化代號(原sym)
                try:
                    股數 = int(p.get("shares", 0) or 0)
                    成本 = float(p.get("avg_cost", 0) or 0)
                except (ValueError, TypeError):
                    continue
                if 股數 <= 0:
                    continue
                # 中文名沒填就自動查
                中文 = str(p.get("name", "")).strip() or 查中文名(sym)
                rec = {"symbol": sym, "shares": 股數, "avg_cost": 成本}
                if 中文:
                    rec["name"] = 中文
                新持股.append(rec)

            cfg["current_positions"] = 新持股
            # 抹除 AGGREGATE 提示說明
            cfg.pop("_持股說明", None)
            儲存設定(cfg)
            st.success(f"✅ 已儲存 {len(新持股)} 檔持股（symbol 已自動補 .TW）！"
                       f" 備份在 portfolio.json.bak")
            st.cache_data.clear()
    with 儲存欄2:
        st.caption("⚠️ 改完按儲存才生效。系統會自動備份舊版到 `.bak`。")


# ─── Tab 2: 基本設定 ───
with tab2:
    st.subheader("基本設定")
    st.caption("資金狀況、FIRE 目標、階段性目標、現金管理 — 一站搞定")

    # ─── 💰 區塊 1：資金狀況 ───
    st.markdown("##### 💰 資金狀況")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        new_total = st.number_input(
            "總資金（TWD）",
            value=int(cfg.get("total_capital_twd", 400000)),
            step=10000, format="%d",
            help="你的總資產（現金 + 持股市值的合計）",
        )
    with col_b:
        new_cash = st.number_input(
            "目前現金（TWD）",
            value=float(cfg.get("current_cash_twd", 170000)),
            step=1000.0, format="%.0f",
            help="未動用的現金（含活存、定存、月光）",
        )
    with col_c:
        new_stock_alloc = st.number_input(
            "股票配置上限（TWD）",
            value=int(cfg.get("stock_allocation_twd", 320000)),
            step=10000, format="%d",
            help="預計最多可放股市的金額（一般 = 總資金 × 80%）",
        )

    # 自動算閒錢比例
    閒錢比例 = (new_cash / new_total * 100) if new_total > 0 else 0
    col_x, col_y = st.columns(2)
    with col_x:
        cm = cfg.get("cash_management", {})
        new_閒錢目標 = st.number_input(
            "閒錢比例目標（%）",
            value=int(cm.get("閒錢比例目標_pct", 35)),
            min_value=0, max_value=80, step=5,
            help="預設 35%。Enjoy 過熱可拉到 45%、恐慌可降到 25%",
        )
    with col_y:
        差 = 閒錢比例 - new_閒錢目標
        色 = "🟢" if abs(差) < 5 else ("🟡" if abs(差) < 15 else "🔴")
        st.metric(f"目前閒錢比例 {色}",
                  f"{閒錢比例:.1f}%",
                  f"{差:+.1f}% vs 目標")

    st.markdown("---")

    # ─── 📅 區塊 2：FIRE 目標設定 ───
    st.markdown("##### 📅 FIRE 目標設定")
    fire = cfg.get("fire_settings", {})

    col_d, col_e, col_f = st.columns(3)
    with col_d:
        new_expense = st.number_input(
            "每月預估支出（TWD）",
            value=int(fire.get("monthly_expense_twd", 40000)),
            step=1000, format="%d",
            help="退休後每月想花多少",
        )
    with col_e:
        new_contrib = st.number_input(
            "每月可投入（TWD）",
            value=int(fire.get("monthly_contribution_twd", 10000)),
            step=1000, format="%d",
            help="每月還能存多少進股市",
        )
    with col_f:
        new_multiplier = st.selectbox(
            "FIRE 倍數（提領率）",
            options=[20, 25, 30, 33],
            index=[20, 25, 30, 33].index(int(fire.get("fire_multiplier", 25)))
                  if int(fire.get("fire_multiplier", 25)) in [20, 25, 30, 33] else 1,
            help="20=5% 較激進 / 25=4% 標準 / 33=3% 最保險",
        )

    col_g, col_h = st.columns(2)
    with col_g:
        new_scenario = st.selectbox(
            "預期年化報酬情境",
            options=["保守", "中等", "積極"],
            index=["保守", "中等", "積極"].index(fire.get("scenario", "中等")),
            help="保守 3% / 中等 6% / 積極 10%",
        )
    with col_h:
        # 即時算 FIRE 目標
        fire_目標 = new_expense * 12 * new_multiplier
        st.metric("FIRE 目標金額",
                  f"NT$ {fire_目標:,.0f}",
                  f"{new_expense:,} × 12 × {new_multiplier}")

    st.markdown("---")

    # ─── 🎯 區塊 3：階段性目標 ───
    st.markdown("##### 🎯 階段性目標")
    goals = cfg.get("goal_targets", {})

    col_i, col_j = st.columns(2)
    with col_i:
        new_短期金額 = st.number_input(
            "短期（1 年）目標金額",
            value=int(goals.get("短期_1年_twd", 500000)),
            step=50000, format="%d",
        )
        new_短期名 = st.text_input(
            "短期目標名稱",
            value=goals.get("短期_目標名", "達 50 萬本金"),
        )
    with col_j:
        new_中期金額 = st.number_input(
            "中期（3 年）目標金額",
            value=int(goals.get("中期_3年_twd", 1500000)),
            step=100000, format="%d",
        )
        new_中期名 = st.text_input(
            "中期目標名稱",
            value=goals.get("中期_目標名", "達 150 萬累積"),
        )

    # 即時算進度
    col_k, col_l, col_m = st.columns(3)
    with col_k:
        短期進度 = min(100, new_total / new_短期金額 * 100) if new_短期金額 > 0 else 0
        st.metric("短期進度", f"{短期進度:.1f}%",
                  f"差 NT$ {max(0, new_短期金額 - new_total):,.0f}")
    with col_l:
        中期進度 = min(100, new_total / new_中期金額 * 100) if new_中期金額 > 0 else 0
        st.metric("中期進度", f"{中期進度:.1f}%",
                  f"差 NT$ {max(0, new_中期金額 - new_total):,.0f}")
    with col_m:
        fire進度 = min(100, new_total / fire_目標 * 100) if fire_目標 > 0 else 0
        st.metric("FIRE 進度", f"{fire進度:.1f}%",
                  f"差 NT$ {max(0, fire_目標 - new_total):,.0f}")

    # 生命週期階段顯示
    if fire進度 < 25:
        階段, 色 = "🚀 衝刺期", "🟢"
        說明 = "離目標遠，系統會自動加碼火力（BE HAPPY +10%）"
    elif fire進度 < 75:
        階段, 色 = "⚖️ 平衡期", "🟡"
        說明 = "穩定累積階段，依紀律操作"
    elif fire進度 < 95:
        階段, 色 = "🛡 守成期", "🟠"
        說明 = "離目標不遠，系統會降低火力（BE HAPPY -10%）"
    else:
        階段, 色 = "🏆 保本期", "🔴"
        說明 = "接近 FIRE，系統會強制 SELL_TAKE 保護成果"

    st.info(f"**生命週期：{階段}** — {說明}")

    st.markdown("---")

    # ─── 儲存按鈕 ───
    if st.button("💾 儲存所有設定", type="primary",
                 use_container_width=True):
        cfg["total_capital_twd"] = new_total
        cfg["current_cash_twd"] = new_cash
        cfg["stock_allocation_twd"] = new_stock_alloc
        cfg.setdefault("fire_settings", {})
        cfg["fire_settings"].update({
            "monthly_expense_twd": new_expense,
            "monthly_contribution_twd": new_contrib,
            "scenario": new_scenario,
            "fire_multiplier": new_multiplier,
        })
        cfg.setdefault("goal_targets", {})
        cfg["goal_targets"].update({
            "短期_1年_twd": new_短期金額,
            "短期_目標名": new_短期名,
            "中期_3年_twd": new_中期金額,
            "中期_目標名": new_中期名,
        })
        cfg.setdefault("cash_management", {})
        cfg["cash_management"]["閒錢比例目標_pct"] = new_閒錢目標
        儲存設定(cfg)
        st.success("✅ 已儲存所有設定！明天 8:00 推播會用新值")
        st.cache_data.clear()


# ─── Tab 3: CSV 匯入 ───
with tab3:
    st.subheader("📥 從國泰證券 CSV 匯入持股")
    st.markdown("""
    **步驟**：
    1. 國泰證券 App → 庫存查詢 → 匯出 Excel/CSV
    2. 上傳到下方
    3. 系統自動 parse 並覆蓋現有持股

    ⚠️ 第一次匯入會請你**手動對映欄位**（不同券商欄位名不同），
    對映完一次後系統會記住格式。
    """)

    uploaded = st.file_uploader("選擇國泰證券對帳單", type=["csv", "xlsx", "xls"])

    if uploaded:
        try:
            if uploaded.name.endswith(".csv"):
                # 嘗試多種編碼
                for enc in ["utf-8", "big5", "cp950"]:
                    try:
                        uploaded.seek(0)
                        raw_df = pd.read_csv(uploaded, encoding=enc)
                        st.success(f"✅ 用 `{enc}` 編碼讀取成功")
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    st.error("❌ 無法讀取，請告訴我你 CSV 的編碼")
                    raw_df = None
            else:
                raw_df = pd.read_excel(uploaded)
                st.success("✅ Excel 讀取成功")

            if raw_df is not None:
                st.markdown("##### 原始資料預覽（前 10 行）")
                st.dataframe(raw_df.head(10), use_container_width=True)

                st.markdown("##### 欄位對映")
                st.caption("把國泰證券的欄位名稱對到 LIS 系統的標準欄位")

                欄位 = list(raw_df.columns)
                col_x, col_y, col_z = st.columns(3)
                with col_x:
                    sym_col = st.selectbox("代號欄位",
                                            options=["（無）"] + 欄位, key="sym_col")
                with col_y:
                    shares_col = st.selectbox("股數欄位",
                                               options=["（無）"] + 欄位, key="shares_col")
                with col_z:
                    cost_col = st.selectbox("成本欄位",
                                             options=["（無）"] + 欄位, key="cost_col")

                if (sym_col != "（無）" and shares_col != "（無）"
                        and cost_col != "（無）"):
                    if st.button("👀 預覽匯入結果"):
                        新持股 = []
                        for _, row in raw_df.iterrows():
                            try:
                                sym = str(row[sym_col]).strip()
                                if not sym or sym.lower() in ("nan", "none"):
                                    continue
                                # 自動加 .TW（若 4 位數字）
                                if sym.isdigit() and len(sym) == 4:
                                    sym = sym + ".TW"
                                股數 = int(float(str(row[shares_col]).replace(",", "")))
                                成本 = float(str(row[cost_col]).replace(",", ""))
                                if 股數 > 0 and 成本 > 0:
                                    新持股.append({
                                        "symbol": sym,
                                        "shares": 股數,
                                        "avg_cost": 成本,
                                    })
                            except Exception as e:
                                st.warning(f"跳過一筆：{e}")

                        if 新持股:
                            st.dataframe(pd.DataFrame(新持股),
                                         hide_index=True,
                                         use_container_width=True)
                            if st.button("✅ 確認覆蓋 portfolio.json",
                                         type="primary"):
                                cfg["current_positions"] = 新持股
                                儲存設定(cfg)
                                st.success(f"✅ 匯入 {len(新持股)} 檔持股！")
                                st.cache_data.clear()
                        else:
                            st.warning("沒有有效持股可匯入")
        except Exception as e:
            st.error(f"讀檔失敗：{e}")


# ─────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────
st.markdown("---")
st.caption(
    f"📁 設定檔：`{PORTFOLIO_PATH}` · "
    f"修改時間：{datetime.fromtimestamp(PORTFOLIO_PATH.stat().st_mtime):%Y-%m-%d %H:%M:%S}"
)
