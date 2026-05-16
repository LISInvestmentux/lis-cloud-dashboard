"""
冷門錯殺股篩選器（Phase 43 — 5/16）

仿方舟系統「找冷門但基本面好」的邏輯。

冷門錯殺定義（4 個必要條件）:
  1. PE Ratio < 過去 5 年平均（被市場低估）
  2. 近 1 月平均成交量 < 過去 1 年平均（冷門）
  3. RSI(14) < 35（超賣）
  4. 距 52 週高點 < 70%（沒在追高）

加分（任 1 條件加 1 分）:
  + 股價 < MA200（長期均線下方 — 真正深跌）
  + 殖利率 > 4%（防守）
  + 三大法人連 5 日買超（聰明錢進場）

打分制（4 必要 + 3 加分 = 最高 7 分）
  ≥ 6 分 → 🟢 「強錯殺訊號」
  4-5 分 → 🟡 「弱錯殺訊號」
  < 4 分 → ⚪ 「不算錯殺」

掃描 watchlist 內所有標的，給出 Top 5 強錯殺。
"""
from typing import Optional
from datetime import datetime, timedelta


def 計算錯殺分數(技術資料: dict, 基本面: Optional[dict] = None) -> dict:
    """
    Args:
        技術資料: 從 technical 模組來的個股分析結果
          需要: rsi14, current_price, ma200, 52w_high, volume_avg_1m, volume_avg_1y
        基本面: 從 fundamentals_engine 來（可選）
          需要: pe_ratio, pe_5y_avg, dividend_yield

    Returns:
        {
            "分數": 5,
            "等級": "🟡 弱錯殺",
            "命中條件": [...],
            "未命中": [...],
        }
    """
    必要條件 = []
    加分條件 = []

    if not 技術資料:
        return {"分數": 0, "等級": "⚪ 無資料",
                "命中條件": [], "未命中": ["technical 資料缺"]}

    # 必要條件 1: PE 低於 5 年平均
    if 基本面:
        pe = 基本面.get("pe_ratio")
        pe_5y = 基本面.get("pe_5y_avg")
        if pe and pe_5y and pe < pe_5y:
            必要條件.append(f"PE {pe:.1f} < 5年均 {pe_5y:.1f}")
        elif pe and pe_5y:
            pass  # 未命中
    else:
        # 沒基本面資料時跳過
        pass

    # 必要條件 2: 近月量縮（冷門）
    vol_1m = 技術資料.get("volume_avg_1m") or 技術資料.get("近月均量")
    vol_1y = 技術資料.get("volume_avg_1y") or 技術資料.get("近年均量")
    if vol_1m and vol_1y and vol_1m < vol_1y * 0.8:
        ratio = vol_1m / vol_1y
        必要條件.append(f"近月量 {ratio*100:.0f}% < 80% 均（冷門）")

    # 必要條件 3: RSI 超賣
    rsi = 技術資料.get("rsi14") or 技術資料.get("RSI")
    if rsi and rsi < 35:
        必要條件.append(f"RSI {rsi:.1f} < 35（超賣）")

    # 必要條件 4: 距 52 週高點 < 70%
    current = 技術資料.get("current_price") or 技術資料.get("close")
    high_52w = 技術資料.get("52w_high") or 技術資料.get("year_high")
    if current and high_52w:
        ratio = current / high_52w
        if ratio < 0.7:
            必要條件.append(f"距 52w 高 {ratio*100:.0f}% < 70%")

    # 加分 1: 跌破 MA200
    ma200 = 技術資料.get("ma200") or 技術資料.get("MA200")
    if current and ma200 and current < ma200:
        加分條件.append(f"現價 < MA200（長期均線下方）")

    # 加分 2: 高殖利率
    if 基本面:
        yield_pct = 基本面.get("dividend_yield")
        if yield_pct and yield_pct > 4:
            加分條件.append(f"殖利率 {yield_pct:.1f}% > 4%（防守）")

    # 加分 3: 法人連續買超（從技術資料 / 機構資料）
    inst_5d_buy = 技術資料.get("法人連5日買超") or 技術資料.get("inst_5d_net_buy")
    if inst_5d_buy and inst_5d_buy > 0:
        加分條件.append(f"法人連 5 日買超")

    總分 = len(必要條件) + len(加分條件)

    if 總分 >= 6:
        等級 = "🟢 強錯殺訊號"
    elif 總分 >= 4:
        等級 = "🟡 弱錯殺訊號"
    else:
        等級 = "⚪ 不算錯殺"

    return {
        "分數": 總分,
        "等級": 等級,
        "必要命中": 必要條件,
        "加分": 加分條件,
        "總命中數": len(必要條件) + len(加分條件),
    }


def 掃描watchlist錯殺(掃描結果: dict, 基本面快取: Optional[dict] = None,
                       top_n: int = 5) -> list:
    """
    掃 watchlist 內所有標的，回傳錯殺分數 Top N

    Args:
        掃描結果: technical.掃描全部() 的結果（含 regions.us / regions.tw_stocks / regions.tw_etfs）
        基本面快取: {symbol: {pe_ratio, pe_5y_avg, dividend_yield}, ...}
        top_n: 回傳前幾名

    Returns:
        [{symbol, name, 分數, 等級, 命中條件, ...}, ...]
    """
    results = []
    基本面快取 = 基本面快取 or {}

    regions = 掃描結果.get("regions", {})
    for region_id, region_data in regions.items():
        items = region_data.get("items", []) if isinstance(region_data, dict) else []
        for item in items:
            sym = item.get("symbol", "")
            if not sym or item.get("error"):
                continue

            fund = 基本面快取.get(sym, {})
            分析 = 計算錯殺分數(item, fund)

            if 分析["分數"] > 0:
                results.append({
                    "symbol": sym,
                    "name": item.get("name", "")[:10],
                    "current_price": item.get("close"),
                    **分析,
                })

    results.sort(key=lambda r: -r["分數"])
    return results[:top_n]


# ════════════════════════════════════════════
# CLI 測試
# ════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # 用一個假資料測算法
    print("=" * 60)
    print("冷門錯殺股篩選器測試")
    print("=" * 60)

    test_cases = [
        {
            "name": "假設 A — 完美錯殺股",
            "技術": {
                "rsi14": 28, "current_price": 50, "ma200": 60, "52w_high": 100,
                "volume_avg_1m": 1000, "volume_avg_1y": 2000,
                "法人連5日買超": 5000,
            },
            "基本面": {"pe_ratio": 8, "pe_5y_avg": 15, "dividend_yield": 5.5},
        },
        {
            "name": "假設 B — 中等錯殺",
            "技術": {
                "rsi14": 32, "current_price": 80, "ma200": 75, "52w_high": 120,
                "volume_avg_1m": 1500, "volume_avg_1y": 1800,
            },
            "基本面": {"pe_ratio": 18, "pe_5y_avg": 15},
        },
        {
            "name": "假設 C — 過熱股（不是錯殺）",
            "技術": {
                "rsi14": 75, "current_price": 200, "ma200": 100, "52w_high": 205,
                "volume_avg_1m": 5000, "volume_avg_1y": 3000,
            },
            "基本面": {"pe_ratio": 50, "pe_5y_avg": 20},
        },
    ]

    for case in test_cases:
        print(f"\n[{case['name']}]")
        r = 計算錯殺分數(case["技術"], case["基本面"])
        print(f"  分數: {r['分數']} / {r['等級']}")
        for c in r["必要命中"]:
            print(f"    ✓ {c}")
        for c in r["加分"]:
            print(f"    + {c}")
