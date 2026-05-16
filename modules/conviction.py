"""
信念分數（Conviction）+ 停損閾值動態調整（Phase 40 — 5/16）

設計理念（取自方舟系統 + Sylvie 累積大獲利入袋派）：
- 「算給你看，不強制」— 不該機械式 -3%/-5% 全停損
- 高信念股（AI 核心）→ 停損放寬，避免過熱修正被誤判
- 低信念股（短線 swing）→ 維持嚴格停損紀律
- 部位太小（< NT$ 5,000）→ 觀察不強制（停損摩擦成本 > 保護價值）

對應 user 5/16 的對話：
- 「香港朋友說 AI 核心跌 15% 是過熱修正，需求還在」 → conviction=5 給 -9% / -15% 放寬
- 「我每檔只買 1-2 股，部位很小」 → < NT$ 5,000 過濾
"""
from typing import Optional


# ════════════════════════════════════════════
# AI 核心個股清單（高信念，停損放寬）
# ════════════════════════════════════════════
AI_CORE_SYMBOLS = {
    # 美股 AI 核心
    "NVDA", "AMD", "MU", "LRCX", "GEV", "AVGO",
    "SNPS", "CDNS", "AMAT", "TSM", "LITE",
    # 台股核心
    "2330.TW",  # 台積電
    "2454.TW",  # 聯發科
    # 大盤 ETF（永抱信念）
    "0050.TW", "00631L.TW", "00662.TW", "00646.TW", "VOO", "QQQ", "SPY",
    # 半導體 ETF
    "00830.TW", "00911.TW", "00941.TW", "00935.TW",
    # 高股息（穩定信念）
    "00878.TW", "00919.TW", "00876.TW",
}


# ════════════════════════════════════════════
# Phase 40 (5/16) — 部位過小門檻
# ════════════════════════════════════════════
MIN_POSITION_TWD = 5000  # 部位 < NT$ 5,000 不強制停損


# ════════════════════════════════════════════
# 取得信念分數
# ════════════════════════════════════════════
def 取得信念分數(symbol: str, cfg: dict, position: Optional[dict] = None) -> int:
    """
    回傳 1-5 信念分數：
      1: 實驗性 / 流動性差（嚴格停損）
      2: 短線 swing
      3: 標準（預設）
      4: 中信念
      5: 高信念（AI 核心、大盤 ETF）

    優先序：
    1. position 內有 conviction 欄位 → 用它
    2. 在 swing_stocks 內 → 2（短線）
    3. 在 long_term_dca 內 → 5（長期 DCA）
    4. 在 watchlist_grey_list 內 → 1（灰名單）
    5. 在 AI_CORE_SYMBOLS 內 → 5
    6. 預設 → 3
    """
    # 1. position 內有 conviction 欄位
    if position and "conviction" in position:
        try:
            return max(1, min(5, int(position["conviction"])))
        except (ValueError, TypeError):
            pass

    # 2. swing_stocks → 2
    swing = cfg.get("swing_stocks", []) or []
    if symbol in swing:
        return 2

    # 3. long_term_dca → 5
    dca_items = cfg.get("long_term_dca", {}).get("items", []) or []
    if any(item.get("symbol") == symbol for item in dca_items):
        return 5

    # 4. watchlist_grey_list → 1
    grey = cfg.get("watchlist_grey_list", {}) or {}
    if symbol in grey and not symbol.startswith("_"):
        return 1

    # 5. AI 核心 → 5
    if symbol in AI_CORE_SYMBOLS:
        return 5

    # 6. 預設
    return 3


# ════════════════════════════════════════════
# 停損閾值（依信念分數動態調整）
# ════════════════════════════════════════════
def 停損閾值(is_us: bool, conviction: int) -> float:
    """
    回傳該股票的「真實該停損」閾值（百分比）

    基礎閾值：
      美股 -3% / 台股 -5%

    信念權重：
      1: 0.5x（嚴格，灰名單）
      2: 0.8x（短線）
      3: 1.0x（標準）
      4: 1.5x（中信念）
      5: 3.0x（AI 核心、大盤）

    範例：
      AMD (美股 conviction=5)  = -3% × 3.0 = -9%
      SATL (美股 conviction=2) = -3% × 0.8 = -2.4%
      0050 (台股 conviction=5) = -5% × 3.0 = -15%
      PLGI (美股 conviction=1) = -3% × 0.5 = -1.5%（灰名單嚴格）
    """
    base = -3.0 if is_us else -5.0
    multiplier = {
        1: 0.5,
        2: 0.8,
        3: 1.0,
        4: 1.5,
        5: 3.0,
    }.get(conviction, 1.0)
    return base * multiplier


# ════════════════════════════════════════════
# 過濾真倉警示 — 套用 A (部位過濾) + C (信念權重)
# ════════════════════════════════════════════
def 過濾停損警示(警示清單: list, cfg: dict, USD_TWD: float) -> tuple:
    """
    把真倉警示分類成「真的該賣」vs「觀察中」

    Args:
        警示清單: 真倉警示["破停損"] list（每筆有 symbol, shares, current_price, pnl_pct, is_us）
        cfg: portfolio.json 設定（含 swing_stocks / long_term_dca）
        USD_TWD: 匯率（算台幣市值用）

    Returns:
        (該賣list, 觀察中list)
        觀察中的每筆會被加上 _過濾原因 欄位說明為什麼不強制停損
    """
    該賣 = []
    觀察中 = []

    for r in 警示清單:
        symbol = r.get("symbol", "")
        is_us = r.get("is_us", False)
        shares = r.get("shares", 0) or 0
        current_price = r.get("current_price", 0) or 0
        pnl_pct = r.get("pnl_pct", 0) or 0

        # 算市值（台幣）
        market_value_twd = r.get("市值_twd") or (
            shares * current_price * (USD_TWD if is_us else 1)
        )

        # 信念分數 + 真實停損閾值
        conviction = 取得信念分數(symbol, cfg, r)
        threshold = 停損閾值(is_us, conviction)

        # A. 部位過小 → 觀察
        if market_value_twd < MIN_POSITION_TWD:
            r["_過濾原因"] = (
                f"部位小（NT$ {market_value_twd:,.0f} < NT$ {MIN_POSITION_TWD:,}）· "
                f"摩擦成本 > 保護價值 · 觀察不強制"
            )
            r["_conviction"] = conviction
            r["_閾值"] = threshold
            觀察中.append(r)
            continue

        # C. 信念權重 → 還在容忍範圍內
        if pnl_pct > threshold:
            r["_過濾原因"] = (
                f"信念分 {conviction}/5 放寬閾值到 {threshold:.1f}% · "
                f"目前 {pnl_pct:+.2f}% 仍在容忍內 · 觀察不強制"
            )
            r["_conviction"] = conviction
            r["_閾值"] = threshold
            觀察中.append(r)
            continue

        # 真的該賣
        r["_conviction"] = conviction
        r["_閾值"] = threshold
        該賣.append(r)

    return 該賣, 觀察中


# ════════════════════════════════════════════
# CLI 測試
# ════════════════════════════════════════════
if __name__ == "__main__":
    import json
    from pathlib import Path

    cfg_path = Path(__file__).resolve().parent.parent.parent / "API" / "portfolio.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    print("=" * 60)
    print("信念分數測試（每檔持股）")
    print("=" * 60)
    print(f"{'代號':<14} {'conviction':<5} {'停損閾值'}")
    print("-" * 60)
    for p in cfg.get("current_positions", []):
        symbol = p["symbol"]
        is_us = not (symbol.endswith(".TW") or symbol.endswith(".TWO"))
        conv = 取得信念分數(symbol, cfg, p)
        thr = 停損閾值(is_us, conv)
        print(f"{symbol:<14} {conv:<5} {thr:.2f}%")
