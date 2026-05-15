"""
美股盤勢深度分析（Phase 11）
晚間推播時用，把美股市場狀況濃縮成一張卡。

包含：
  - 4 大美股指數（S&P 500 / NASDAQ / DJIA / SOX 費城半導體）
  - VIX 恐慌指數判讀
  - 美股 watchlist 整體溫度（RSI 平均、訊號數）
  - 加碼建議（依 VIX + 整體 RSI）
"""
from typing import Optional


def 美股盤勢綜合(indices: list[dict],
                  美股清單: list[dict]) -> dict:
    """
    indices: technical.掃描全部觀察清單()['indices']
    美股清單: 美股 watchlist 掃描結果
    """
    # 抓主要指數
    def _找(sym: str) -> Optional[dict]:
        for r in indices:
            if "error" in r:
                continue
            if (r.get("original_symbol") or r.get("symbol")) == sym:
                return r
        return None

    sp500 = _找("^GSPC")
    nasdaq = _找("^IXIC")
    sox = _找("^SOX")
    vix = _找("^VIX")

    指數摘要 = []
    for 名, r, 過熱閾值 in [
        ("S&P 500", sp500, 70),
        ("NASDAQ", nasdaq, 70),
        ("費城半導體", sox, 70),
    ]:
        if not r:
            指數摘要.append({"名": 名, "close": None})
            continue
        rsi = r.get("rsi14")
        漲幅20 = r.get("漲幅_20日_pct")
        # 判斷狀態
        if rsi is not None and rsi > 過熱閾值:
            狀態 = "過熱"
        elif rsi is not None and rsi < 30:
            狀態 = "超賣"
        elif rsi is not None and rsi < 50:
            狀態 = "偏冷"
        else:
            狀態 = "中性"
        指數摘要.append({
            "名": 名,
            "close": r.get("close"),
            "rsi": rsi,
            "漲幅20日_pct": 漲幅20,
            "狀態": 狀態,
        })

    # VIX 判讀
    vix_close = vix.get("close") if vix else None
    if vix_close is None:
        vix判讀 = {"等級": "n/a", "建議": "n/a", "色": "subtle"}
    elif vix_close >= 30:
        vix判讀 = {"等級": "🔥 極度恐慌", "色": "bull",
                    "建議": "黃金錯殺機會！考慮加碼大盤 ETF"}
    elif vix_close >= 25:
        vix判讀 = {"等級": "😰 恐慌", "色": "bull",
                    "建議": "市場震盪，逢低分批進"}
    elif vix_close >= 20:
        vix判讀 = {"等級": "😐 警示", "色": "wait",
                    "建議": "情緒緊張，謹慎進場"}
    elif vix_close >= 15:
        vix判讀 = {"等級": "🙂 平穩", "色": "main",
                    "建議": "市場中性，依紀律操作"}
    else:
        vix判讀 = {"等級": "😴 過度自滿", "色": "bear",
                    "建議": "市場太冷靜，準備減碼"}

    # 美股 watchlist 聚合
    有效 = [r for r in 美股清單 if "error" not in r]
    if 有效:
        rsi_list = [r.get("rsi14") for r in 有效 if r.get("rsi14") is not None]
        平均rsi = round(sum(rsi_list) / len(rsi_list), 1) if rsi_list else None
        震盪 = sum(1 for r in 有效 if r.get("shakeout_low"))
        金叉 = sum(1 for r in 有效 if r.get("bull_signal"))
        錯殺 = sum(1 for r in 有效 if r.get("shit_signal"))
        量爆 = sum(1 for r in 有效 if r.get("量爆訊號"))
    else:
        平均rsi = None
        震盪 = 金叉 = 錯殺 = 量爆 = 0

    # 整體判斷
    if vix_close and vix_close >= 30 and 震盪 + 錯殺 >= 3:
        整體 = "🌟 黃金錯殺日"
        建議火力 = 90
    elif vix_close and vix_close >= 20:
        整體 = "😰 機會浮現"
        建議火力 = 60
    elif 平均rsi and 平均rsi > 65:
        整體 = "🔥 過熱應減碼"
        建議火力 = 20
    elif 平均rsi and 平均rsi < 45:
        整體 = "🥶 等錯殺中"
        建議火力 = 30
    else:
        整體 = "⚖️ 平淡持有"
        建議火力 = 40

    return {
        "指數摘要": 指數摘要,
        "VIX": vix_close,
        "VIX判讀": vix判讀,
        "美股聚合": {
            "平均RSI": 平均rsi,
            "震盪低點": 震盪,
            "金叉突破": 金叉,
            "錯殺": 錯殺,
            "量爆": 量爆,
            "有效檔數": len(有效),
        },
        "整體判斷": 整體,
        "建議火力_pct": 建議火力,
    }
