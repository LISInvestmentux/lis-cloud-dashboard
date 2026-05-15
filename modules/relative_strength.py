"""
相對強度模組（Phase 7.2 / 相對強度 RS）
個股近 N 日漲幅 - 大盤近 N 日漲幅 = RS 分數

ARK 邏輯：找出**跑贏大盤**的趨勢股，才有超額利潤（Alpha）。
若大盤漲 2%、個股只漲 1% → 在 ARK 邏輯裡其實是相對衰退。

對應市場：
  台股 / ETF → ^TWII（加權指數）
  美股       → ^GSPC（S&P 500）

實作策略（不重抓 K 線）：
  - technical.分析個股 已經算好 漲幅_20日_pct
  - 本模組直接拿那個欄位 + 從 indices 找大盤 20 日漲幅做差

回傳欄位（加在每筆個股 record）：
  rs_20d:        20 日相對強度（個股漲幅 - 大盤漲幅，% pp）
  rs_label:      強勢 / 中性 / 弱勢 / 資料不足
  market_index:  對照的大盤代號
  market_20d_pct:大盤 20 日漲幅（從 indices 撈）
"""
from typing import Optional


TW_大盤代號 = "^TWII"
US_大盤代號 = "^GSPC"

強勢門檻 = 3.0    # > +3pp → 強勢
弱勢門檻 = -3.0   # < -3pp → 弱勢


def _判斷市場(symbol: str, region: Optional[str] = None) -> str:
    """從 symbol 推斷對照大盤。"""
    if symbol.endswith(".TW") or symbol.endswith(".TWO"):
        return TW_大盤代號
    if region and "tw" in region.lower():
        return TW_大盤代號
    return US_大盤代號


def 計算單檔RS(個股漲幅_20日_pct: Optional[float],
                大盤漲幅_台股: Optional[float],
                大盤漲幅_美股: Optional[float],
                symbol: str,
                region: Optional[str] = None) -> dict:
    """單檔 RS 計算（純函數，給 unit test 用）。"""
    對照大盤 = _判斷市場(symbol, region)
    大盤漲幅 = 大盤漲幅_台股 if 對照大盤 == TW_大盤代號 else 大盤漲幅_美股

    if 個股漲幅_20日_pct is None or 大盤漲幅 is None:
        return {
            "rs_20d": None,
            "rs_label": "資料不足",
            "market_index": 對照大盤,
            "market_20d_pct": 大盤漲幅,
        }

    rs = round(個股漲幅_20日_pct - 大盤漲幅, 2)
    if rs >= 強勢門檻:
        標籤 = "強勢"
    elif rs <= 弱勢門檻:
        標籤 = "弱勢"
    else:
        標籤 = "中性"

    return {
        "rs_20d": rs,
        "rs_label": 標籤,
        "market_index": 對照大盤,
        "market_20d_pct": 大盤漲幅,
    }


def 為掃描結果加上RS(掃描結果: dict) -> dict:
    """
    給 main.py 在 掃描完之後、寫入 ledger 之前呼叫。

    從 indices 撈大盤的 漲幅_20日_pct（已由 technical.分析個股 算好），
    對每個 region 的每筆 record 加 rs_* 欄位。

    回傳統計 dict
    """
    # 找大盤 record
    indices = 掃描結果.get("indices", [])
    indices_map = {
        (r.get("original_symbol") or r.get("symbol")): r
        for r in indices if "error" not in r
    }

    def _取漲幅(symbol: str) -> Optional[float]:
        r = indices_map.get(symbol)
        return r.get("漲幅_20日_pct") if r else None

    大盤_台股 = _取漲幅(TW_大盤代號)
    大盤_美股 = _取漲幅(US_大盤代號)

    統計 = {"強勢": 0, "中性": 0, "弱勢": 0, "資料不足": 0}
    處理數 = 0
    強勢清單 = []

    for 區id, 區 in 掃描結果.get("regions", {}).items():
        for r in 區.get("items", []):
            if "error" in r:
                continue
            rs結果 = 計算單檔RS(
                r.get("漲幅_20日_pct"),
                大盤_台股, 大盤_美股,
                r["symbol"], region=區id,
            )
            r.update(rs結果)
            標籤 = rs結果["rs_label"]
            統計[標籤] = 統計.get(標籤, 0) + 1
            處理數 += 1
            if 標籤 == "強勢":
                強勢清單.append({
                    "symbol": r["symbol"],
                    "name": r.get("name", ""),
                    "rs_20d": rs結果["rs_20d"],
                })

    # 強勢清單依 rs_20d 由高到低排序
    強勢清單.sort(key=lambda x: x.get("rs_20d") or 0, reverse=True)

    return {
        **統計,
        "處理數": 處理數,
        "台股大盤20日漲幅": 大盤_台股,
        "美股大盤20日漲幅": 大盤_美股,
        "強勢清單": 強勢清單,
    }
