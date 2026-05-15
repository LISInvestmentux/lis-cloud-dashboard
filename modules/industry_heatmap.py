"""
產業氣溫表（Phase 6.3 簡化版）
把 watchlist 個股按產業聚合，算出：
  - 平均 RSI（情緒溫度）
  - 平均 20 日漲幅
  - 訊號數（震盪低點 / 金叉 / 錯殺）
  - 量爆檔數

不依賴外部買賣超資料（證交所沒給）。
純從 watchlist 已抓回的個股分析聚合，零外部 API。

回傳給 flex_builder 用的結構：
{
  "產業": [
    {"產業": 半導體, "檔數": x, "平均RSI": y, "平均漲幅20d": z,
     "震盪低點": a, "金叉": b, "錯殺": c, "量爆": d, "溫度": 'hot/warm/cold'},
    ...
  ],
  "最熱產業": ...,
  "最冷產業": ...,
}

溫度判定：
  hot:  RSI 平均 > 65 或量爆 > 50%
  cold: RSI 平均 < 40 或震盪低點 > 30%
  warm: 其他
"""
from typing import Optional


def _查產業(symbol: str, 對映: dict) -> str:
    """從預設對映表查產業。"""
    sym = (symbol or "").strip()
    if sym in 對映:
        return 對映[sym]
    return "其他"


def 聚合產業氣溫(全部個股: list[dict],
                  產業對映: Optional[dict] = None) -> dict:
    """
    全部個股: main.py 的 _合併個股() 結果（含 RSI、訊號等）
    產業對映: dict[symbol]=產業名（若 None 從 portfolio_health 載入預設）
    """
    if 產業對映 is None:
        try:
            from . import portfolio_health
        except ImportError:
            import portfolio_health
        產業對映 = portfolio_health.產業對映_預設

    # 按產業分桶
    桶 = {}  # 產業 → [r, r, ...]
    for r in 全部個股:
        if "error" in r:
            continue
        sym = r.get("symbol", "")
        if not sym:
            continue
        產業 = _查產業(sym, 產業對映)
        桶.setdefault(產業, []).append(r)

    產業列 = []
    for 產業, 個股們 in 桶.items():
        if not 個股們:
            continue
        檔數 = len(個股們)
        rsi清單 = [r.get("rsi14") for r in 個股們 if r.get("rsi14") is not None]
        漲幅清單 = [r.get("漲幅_20日_pct") for r in 個股們
                    if r.get("漲幅_20日_pct") is not None]
        震盪 = sum(1 for r in 個股們 if r.get("shakeout_low"))
        金叉 = sum(1 for r in 個股們 if r.get("bull_signal"))
        錯殺 = sum(1 for r in 個股們 if r.get("shit_signal"))
        量爆 = sum(1 for r in 個股們 if r.get("量爆訊號"))

        平均RSI = round(sum(rsi清單) / len(rsi清單), 1) if rsi清單 else None
        平均漲幅 = round(sum(漲幅清單) / len(漲幅清單), 2) if 漲幅清單 else None

        # 溫度判定
        量爆率 = 量爆 / 檔數
        震盪率 = 震盪 / 檔數
        if (平均RSI is not None and 平均RSI > 65) or 量爆率 > 0.5:
            溫度 = "hot"
        elif (平均RSI is not None and 平均RSI < 40) or 震盪率 > 0.3:
            溫度 = "cold"
        else:
            溫度 = "warm"

        產業列.append({
            "產業": 產業,
            "檔數": 檔數,
            "平均RSI": 平均RSI,
            "平均漲幅20d": 平均漲幅,
            "震盪低點": 震盪,
            "金叉": 金叉,
            "錯殺": 錯殺,
            "量爆": 量爆,
            "量爆率": round(量爆率 * 100, 0),
            "震盪率": round(震盪率 * 100, 0),
            "溫度": 溫度,
        })

    # 按平均 RSI 由高到低排序（最熱在前）
    產業列.sort(
        key=lambda r: r["平均RSI"] if r["平均RSI"] is not None else 50,
        reverse=True,
    )

    最熱 = 產業列[0] if 產業列 else None
    最冷 = 產業列[-1] if 產業列 else None

    return {
        "產業": 產業列,
        "最熱": 最熱,
        "最冷": 最冷,
        "產業數": len(產業列),
    }
