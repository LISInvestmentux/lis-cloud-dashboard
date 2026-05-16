"""
進場勝率引擎（Phase 45 — 5/16）

整合 LIS 既有 4 大訊號 → 給每檔標的「進場勝率分數」

4 大訊號加權:
  1. 位階分數 (0-100, 越低越好) — Phase 12
  2. 黑天鵝命中 (0-5) — Phase 7.2
  3. 冷門錯殺分 (0-7) — Phase 43（剛做）
  4. 驚喜因子 — Phase 44（剛做）

滿分 10 分:
  ≥ 8 分: 🟢 高勝率（建議用 Kelly 算的足量部位）
  5-7:    🟡 中勝率（標準部位 / 觀察）
  < 5:    ⚪ 低勝率（小部位試水）

對應另一個 AI 提的「進場前勝率過濾網」缺口。
"""
import json
from pathlib import Path
from typing import Optional

專案根 = Path(__file__).resolve().parent.parent.parent


def _載入位階() -> dict:
    path = 專案根 / "數據" / "positional_state.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("scores", {})
    except Exception:
        return {}


def _位階加分(score: float) -> tuple:
    """位階 0-30 加分（越低越好）"""
    if score <= 0:
        return (0, "")  # 沒掃描
    if score <= 15:
        return (3, f"位階 {score:.0f} 深價值區 (+3)")
    if score <= 25:
        return (2, f"位階 {score:.0f} 偏低 (+2)")
    if score <= 35:
        return (1, f"位階 {score:.0f} 中下 (+1)")
    return (0, "")


def _黑天鵝加分(命中: int) -> tuple:
    """黑天鵝 SOP 命中加分"""
    if 命中 >= 4:
        return (3, f"黑天鵝 {命中}/5 ALL IN 級 (+3)")
    if 命中 >= 3:
        return (2, f"黑天鵝 {命中}/5 加碼級 (+2)")
    if 命中 >= 2:
        return (1, f"黑天鵝 {命中}/5 留意 (+1)")
    return (0, "")


def _錯殺加分(錯殺結果: dict) -> tuple:
    """冷門錯殺分加分"""
    分 = 錯殺結果.get("分數", 0) if 錯殺結果 else 0
    if 分 >= 6:
        return (3, f"錯殺 {分}/7 強訊號 (+3)")
    if 分 >= 4:
        return (2, f"錯殺 {分}/7 弱訊號 (+2)")
    if 分 >= 2:
        return (1, f"錯殺 {分}/7 (+1)")
    return (0, "")


def _驚喜加分(es: dict) -> tuple:
    """驚喜因子加分"""
    if not es or not es.get("歷史"):
        return (0, "")
    歷史 = es["歷史"]
    if len(歷史) < 3:
        return (0, "")
    beats = sum(1 for h in 歷史 if h.get("type") == "BEAT")
    avg = es.get("平均_surprise_pct", 0) or 0
    if beats == len(歷史) and avg > 5:
        return (1, f"驚喜 {beats}/{len(歷史)} 持續超預期 (+1)")
    if beats == len(歷史):
        return (1, f"驚喜 {beats}/{len(歷史)} BEAT (+1)")
    return (0, "")


def 算進場勝率(symbol: str, 黑天鵝命中: int = 0,
                技術資料: Optional[dict] = None,
                基本面: Optional[dict] = None,
                抓驚喜: bool = False) -> dict:
    """
    算單檔進場勝率分數

    Args:
        symbol: 股票代號（"NVDA" / "0050.TW"）
        黑天鵝命中: 0-5（從 bottom_detector.即時底部判定 來）
        技術資料: 從 technical 掃描來（含 rsi14 / current_price / ma200 / 52w_high）
        基本面: 從 fundamentals 來（含 pe_ratio / pe_5y_avg / dividend_yield）
        抓驚喜: 是否同時去 yfinance 抓 earnings surprise（會慢）

    Returns:
        {
            "symbol": "NVDA",
            "分數": 7,
            "滿分": 10,
            "等級": "🟡 中勝率",
            "明細": [(分數, 理由), ...],
        }
    """
    try:
        from . import oversold_filter
    except ImportError:
        import oversold_filter

    明細 = []
    總分 = 0

    # 1. 位階
    位階dict = _載入位階()
    score = 位階dict.get(symbol, 0) or 0
    pts, reason = _位階加分(score)
    if pts > 0:
        明細.append((pts, reason))
        總分 += pts

    # 2. 黑天鵝（共用，所有股票同個分數）
    pts, reason = _黑天鵝加分(黑天鵝命中)
    if pts > 0:
        明細.append((pts, reason))
        總分 += pts

    # 3. 冷門錯殺
    if 技術資料:
        錯殺 = oversold_filter.計算錯殺分數(技術資料, 基本面)
        pts, reason = _錯殺加分(錯殺)
        if pts > 0:
            明細.append((pts, reason))
            總分 += pts

    # 4. 驚喜因子（要 fetch yfinance，慢，預設關）
    if 抓驚喜:
        try:
            from . import earnings_surprise
            es = earnings_surprise.取得財報歷史(symbol)
            pts, reason = _驚喜加分(es)
            if pts > 0:
                明細.append((pts, reason))
                總分 += pts
        except Exception:
            pass

    # 等級
    if 總分 >= 8:
        等級 = "🟢 高勝率"
    elif 總分 >= 5:
        等級 = "🟡 中勝率"
    elif 總分 >= 2:
        等級 = "⚪ 弱勝率"
    else:
        等級 = "⚫ 無訊號"

    return {
        "symbol": symbol,
        "分數": 總分,
        "滿分": 10,
        "等級": 等級,
        "明細": 明細,
    }


def 排序候選清單(symbols: list, 黑天鵝命中: int = 0,
                  技術資料map: Optional[dict] = None,
                  基本面map: Optional[dict] = None,
                  top_n: int = 5,
                  抓驚喜: bool = False) -> list:
    """
    對一堆 symbols 算進場勝率分數，排序取 Top N

    Args:
        symbols: 候選股票清單
        黑天鵝命中: SOP 命中數（所有股票共用）
        技術資料map: {symbol: 技術資料dict}
        基本面map: {symbol: 基本面dict}
        top_n: 取前幾名
        抓驚喜: 是否 fetch earnings surprise

    Returns:
        [{symbol, 分數, 等級, 明細}, ...] 按分數降冪排序
    """
    技術資料map = 技術資料map or {}
    基本面map = 基本面map or {}

    results = []
    for sym in symbols:
        tech = 技術資料map.get(sym)
        fund = 基本面map.get(sym)
        r = 算進場勝率(sym, 黑天鵝命中, tech, fund, 抓驚喜=抓驚喜)
        results.append(r)

    results.sort(key=lambda r: -r["分數"])
    return results[:top_n]


# CLI 測試
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=" * 60)
    print("進場勝率引擎測試（user 持股美股）")
    print("=" * 60)

    # 假設黑天鵝命中 = 1
    BLACK_SWAN = 1

    # 假數據（模擬不同情境）
    技術_完美錯殺 = {
        "rsi14": 28, "current_price": 50, "ma200": 60, "52w_high": 100,
        "volume_avg_1m": 1000, "volume_avg_1y": 2000,
    }
    技術_普通 = {
        "rsi14": 55, "current_price": 90, "ma200": 80, "52w_high": 100,
    }
    技術_過熱 = {
        "rsi14": 75, "current_price": 200, "ma200": 100, "52w_high": 205,
    }
    基本面_便宜 = {"pe_ratio": 8, "pe_5y_avg": 15, "dividend_yield": 5}
    基本面_普通 = {"pe_ratio": 15, "pe_5y_avg": 15}

    test_cases = [
        ("假股 A — 完美錯殺", 技術_完美錯殺, 基本面_便宜),
        ("假股 B — 普通中性", 技術_普通, 基本面_普通),
        ("假股 C — 過熱", 技術_過熱, 基本面_普通),
    ]

    for name, tech, fund in test_cases:
        r = 算進場勝率(name, BLACK_SWAN, tech, fund)
        print(f"\n[{name}]")
        print(f"  總分: {r['分數']} / {r['滿分']} · {r['等級']}")
        for pts, reason in r["明細"]:
            print(f"    {reason}")
