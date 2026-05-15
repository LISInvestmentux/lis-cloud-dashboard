"""
連鎖恐慌偵測 / 黑天鵝機會（Phase 7.2b）
對應 LIS 心法第 5 條：「市場『亂殺』= 『錯殺價值區』」

五階段連鎖：
  散戶恐慌賣 → 程式停損 → ETF 被動賣 → 機構減碼 → 股價脫離財報

判定 5 個維度（達 4 個 → 黃金錯殺）：
  ① 個股短期跌幅 > 5%（近 3 日內）
  ② 成交量爆量（量比 > 2 倍均量 = 賣壓）
  ③ F&G < 30（全市場恐慌氣氛）
  ④ 個股技術崩跌（RSI < 30 + 跌破 MA50）
  ⑤ 大盤同步下跌（^TWII 或 ^GSPC 當日 -1%）

回傳：
{
  "黑天鵝清單": [{symbol, name, 命中條件, 分數, ...}, ...],
  "市場恐慌等級": 0-5（達幾個全市場條件）,
  "全市場警示": str,
}
"""
from typing import Optional


# ─────────────────────────────────────────────
# 閾值
# ─────────────────────────────────────────────
個股跌幅閾值_pct = -5.0      # 3 日內跌幅
量爆倍數閾值 = 2.0           # 量能 vs 20 日均量
FG恐慌閾值 = 30              # F&G 分數
RSI崩跌閾值 = 30
大盤跌幅閾值_pct = -1.0      # 當日

達標分數 = 4                  # 5 個中達 4 個 → 觸發


def _算近3日跌幅(每日K線: list[dict]) -> Optional[float]:
    """3 日跌幅 = (今日 close / 3 日前 close - 1) × 100"""
    if len(每日K線) < 4:
        return None
    今日 = 每日K線[0].get("close")
    三日前 = 每日K線[3].get("close")
    if not 今日 or not 三日前 or 三日前 <= 0:
        return None
    return round((今日 / 三日前 - 1) * 100, 2)


def _算大盤當日漲幅(indices: list[dict], symbol: str) -> Optional[float]:
    """從 indices 找大盤近 1 日漲幅。"""
    for r in indices:
        if "error" in r:
            continue
        sym = r.get("original_symbol") or r.get("symbol")
        if sym != symbol:
            continue
        # 用 prev_close 算
        close = r.get("close")
        prev = r.get("prev_close")
        if close and prev and prev > 0:
            return round((close / prev - 1) * 100, 2)
    return None


def 判定黑天鵝(個股: dict,
                fear_greed_score: Optional[float],
                台股大盤_漲幅_pct: Optional[float],
                美股大盤_漲幅_pct: Optional[float],
                近3日跌幅_pct: Optional[float] = None) -> dict:
    """
    對單一個股判定是否為黑天鵝機會。
    回傳：{符合條件數, 命中條件, 分數, 是否黑天鵝}
    """
    命中 = []
    分數 = 0

    # ① 個股跌幅
    if 近3日跌幅_pct is not None and 近3日跌幅_pct <= 個股跌幅閾值_pct:
        命中.append(f"3日跌幅 {近3日跌幅_pct:.1f}%")
        分數 += 1

    # ② 量爆
    量爆 = 個股.get("量爆倍數")
    if 量爆 is not None and 量爆 >= 量爆倍數閾值:
        命中.append(f"量爆 {量爆:.1f}x")
        分數 += 1

    # ③ F&G 恐慌
    if fear_greed_score is not None and fear_greed_score < FG恐慌閾值:
        命中.append(f"F&G {fear_greed_score:.0f}<30")
        分數 += 1

    # ④ 個股技術崩跌（RSI < 30 + 跌破 MA50）
    rsi = 個股.get("rsi14")
    ma50 = 個股.get("ma50")
    close = 個股.get("close")
    if (rsi is not None and rsi < RSI崩跌閾值 and
        close and ma50 and close < ma50):
        命中.append(f"RSI {rsi:.0f}<30 + 跌破MA50")
        分數 += 1

    # ⑤ 大盤同步下跌
    symbol = 個股.get("symbol", "")
    is_us = not (symbol.endswith(".TW") or symbol.endswith(".TWO"))
    大盤_pct = 美股大盤_漲幅_pct if is_us else 台股大盤_漲幅_pct
    if 大盤_pct is not None and 大盤_pct <= 大盤跌幅閾值_pct:
        命中.append(f"大盤 {大盤_pct:.1f}%")
        分數 += 1

    return {
        "符合條件數": 分數,
        "命中條件": 命中,
        "分數": 分數,
        "是否黑天鵝": 分數 >= 達標分數,
    }


def 掃描黑天鵝(全部個股: list[dict],
                indices: list[dict],
                fear_greed_score: Optional[float],
                個股近3日跌幅: Optional[dict] = None) -> dict:
    """
    掃描整個 watchlist 找出黑天鵝機會。

    全部個股: main.py 的 _合併個股() 結果
    indices: technical.掃描全部觀察清單()['indices']
    fear_greed_score: 全市場 F&G 分數
    個股近3日跌幅: {symbol: pct} 預先算好的近 3 日跌幅（None 則嘗試從 K 線抓）

    回傳：見模組 docstring
    """
    # 抓大盤當日漲幅
    台股大盤_pct = _算大盤當日漲幅(indices, "^TWII")
    美股大盤_pct = (_算大盤當日漲幅(indices, "^GSPC") or
                   _算大盤當日漲幅(indices, "^IXIC"))

    # 全市場恐慌等級（5 個條件中達幾個 — 不分個股）
    全市場分 = 0
    if fear_greed_score is not None and fear_greed_score < FG恐慌閾值:
        全市場分 += 1
    if 台股大盤_pct is not None and 台股大盤_pct <= 大盤跌幅閾值_pct:
        全市場分 += 1
    if 美股大盤_pct is not None and 美股大盤_pct <= 大盤跌幅閾值_pct:
        全市場分 += 1

    if 全市場分 >= 2:
        全市場警示 = "🚨 連鎖恐慌進行中"
    elif 全市場分 == 1:
        全市場警示 = "⚠️ 部分恐慌訊號"
    else:
        全市場警示 = "🟢 市場平穩"

    # 個股級判定
    黑天鵝清單 = []
    個股近3日跌幅 = 個股近3日跌幅 or {}

    for 個股 in 全部個股:
        if "error" in 個股:
            continue
        symbol = 個股.get("symbol")
        if not symbol:
            continue

        近3日 = 個股近3日跌幅.get(symbol)
        # 沒給就用 prev_close 估（粗略）
        if 近3日 is None and 個股.get("prev_close") and 個股.get("close"):
            # 用前一日近似（簡化版）
            近3日 = (個股["close"] / 個股["prev_close"] - 1) * 100

        結果 = 判定黑天鵝(個股, fear_greed_score, 台股大盤_pct,
                          美股大盤_pct, 近3日)
        if 結果["是否黑天鵝"]:
            黑天鵝清單.append({
                "symbol": symbol,
                "name": 個股.get("name", ""),
                "close": 個股.get("close"),
                "rsi14": 個股.get("rsi14"),
                "量爆倍數": 個股.get("量爆倍數"),
                "近3日跌幅_pct": 近3日,
                "符合條件數": 結果["符合條件數"],
                "命中條件": 結果["命中條件"],
            })

    # 按符合條件數由高到低排序
    黑天鵝清單.sort(key=lambda r: r["符合條件數"], reverse=True)

    return {
        "黑天鵝清單": 黑天鵝清單,
        "市場恐慌等級": 全市場分,
        "全市場警示": 全市場警示,
        "全市場條件": {
            "F&G": fear_greed_score,
            "台股大盤_pct": 台股大盤_pct,
            "美股大盤_pct": 美股大盤_pct,
        },
    }


def 預先計算近3日跌幅(symbols: list[str]) -> dict:
    """
    對 symbols 抓 5 日 K 線，算近 3 日跌幅。
    給 main.py 一次性預載用（避免 _合併個股 沒這資料）。
    """
    try:
        from . import technical
    except ImportError:
        import technical
    結果 = {}
    for sym in symbols:
        try:
            K, _ = technical.取得每日股價(sym, period="10d")
            跌幅 = _算近3日跌幅(K)
            if 跌幅 is not None:
                結果[sym] = 跌幅
        except Exception:
            pass
    return 結果
