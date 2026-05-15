"""
全市場自動發現選股（Phase 10）
從 market_universe.json 的「候選池」（200 檔）掃描找錯殺機會。
排除 watchlist 和 portfolio 已有的。

評分機制（綜合分數）：
  +50 震盪低點觸發（shakeout_low）
  +30 金叉突破（bull_signal）
  +30 跌幅 < -5%（3 日內，連鎖恐慌候選）
  +20 量爆（量比 > 2）
  +20 RSI < 30（極端超賣）
  +10 收盤跌破 MA50

頂分 → Top 5 推「🔍 系統挖到的標的」卡
"""
import json
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
候選池路徑 = 專案根 / "API" / "market_universe.json"
WATCHLIST_PATH = 專案根 / "API" / "watchlist.json"


def 載入候選池() -> dict:
    if not 候選池路徑.exists():
        return {}
    with open(候選池路徑, "r", encoding="utf-8") as f:
        return json.load(f)


def 載入已知symbols(設定: Optional[dict] = None) -> set:
    """
    回傳 watchlist + portfolio 已有的 symbols（規範化）。
    給掃描排除用。
    """
    try:
        from . import capital_planner
    except ImportError:
        import capital_planner

    已知 = set()
    # watchlist
    if WATCHLIST_PATH.exists():
        with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
            wl = json.load(f)
        for region in wl.get("regions", []):
            for s in region.get("stocks", []):
                已知.add(capital_planner.規範化代號(s.get("symbol", "")))
    # portfolio
    if 設定 is None:
        設定 = capital_planner.載入資金設定()
    for p in 設定.get("current_positions", []):
        sym = p.get("symbol")
        if sym and sym != "AGGREGATE":
            已知.add(capital_planner.規範化代號(sym))
    return 已知


def 評分(分析: dict, 近3日跌幅: Optional[float] = None) -> tuple[int, list[str]]:
    """
    對單檔給綜合分數 + 命中條件。
    回傳 (分數, 條件 list)
    """
    分 = 0
    條件 = []

    if 分析.get("shakeout_low"):
        分 += 50
        條件.append("震盪低點")
    if 分析.get("bull_signal"):
        分 += 30
        條件.append("金叉突破")

    rsi = 分析.get("rsi14")
    if rsi is not None and rsi < 30:
        分 += 20
        條件.append(f"RSI {rsi:.0f}<30")

    close = 分析.get("close")
    ma50 = 分析.get("ma50")
    if close and ma50 and close < ma50:
        分 += 10
        條件.append("跌破 MA50")

    量爆 = 分析.get("量爆倍數")
    if 量爆 is not None and 量爆 >= 2.0:
        分 += 20
        條件.append(f"量爆 {量爆:.1f}x")

    if 近3日跌幅 is not None and 近3日跌幅 <= -5.0:
        分 += 30
        條件.append(f"3日跌幅 {近3日跌幅:.1f}%")

    return (分, 條件)


def 掃描全市場(設定: Optional[dict] = None,
                Top_N: int = 5,
                延遲秒: float = 0.3) -> dict:
    """
    主入口：掃描候選池，回傳 Top N 黃金錯殺。

    設定: portfolio 設定（用來排除已有持股）
    Top_N: 回傳前幾名
    延遲秒: 每檔之間的延遲（避免 yfinance API 限流）

    回傳：{
      "Top": [{symbol, name, 分數, 條件, close, rsi14, ...}, ...],
      "掃描總數": int,
      "錯誤數": int,
      "排除數": int,
    }
    """
    try:
        from . import technical, black_swan
    except ImportError:
        import technical
        import black_swan

    池 = 載入候選池()
    if not 池:
        return {"Top": [], "掃描總數": 0, "錯誤數": 0, "排除數": 0,
                 "錯誤訊息": "找不到 market_universe.json"}

    # 合併所有候選
    所有候選 = []
    for 池id, 池資 in 池.items():
        if 池id.startswith("_"):
            continue
        for s in 池資.get("stocks", []):
            if s.get("symbol"):
                所有候選.append(s)

    # 排除已知
    已知 = 載入已知symbols(設定)
    新候選 = [s for s in 所有候選 if s["symbol"] not in 已知]
    排除數 = len(所有候選) - len(新候選)

    print(f"  候選池：{len(所有候選)} 檔，"
          f"排除 watchlist/portfolio 已有 {排除數} 檔，"
          f"新掃描 {len(新候選)} 檔")

    # 掃描
    import time
    結果 = []
    錯誤數 = 0
    for i, s in enumerate(新候選):
        sym = s["symbol"]
        try:
            if i > 0:
                time.sleep(延遲秒)
            分析 = technical.分析個股(sym, s.get("name", ""))
            # 算近 3 日跌幅
            K, _ = technical.取得每日股價(sym, period="10d")
            近3日 = black_swan._算近3日跌幅(K)
            分, 條件 = 評分(分析, 近3日)
            if 分 > 0:
                結果.append({
                    "symbol": 分析["symbol"],
                    "name": s.get("name", ""),
                    "close": 分析.get("close"),
                    "rsi14": 分析.get("rsi14"),
                    "量爆倍數": 分析.get("量爆倍數"),
                    "近3日跌幅_pct": 近3日,
                    "分數": 分,
                    "條件": 條件,
                })
        except Exception:
            錯誤數 += 1
            continue

    # 排序
    結果.sort(key=lambda r: r["分數"], reverse=True)

    return {
        "Top": 結果[:Top_N],
        "全部": 結果,
        "掃描總數": len(新候選),
        "錯誤數": 錯誤數,
        "排除數": 排除數,
    }
