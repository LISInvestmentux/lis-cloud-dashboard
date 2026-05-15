"""
每日加碼計算機（Phase 13）
仿 ARK 的「每天進入價值區就買」邏輯，但用 LIS 心法：
  - 平時 0.15% 彈藥 / 衝刺期 0.3% / 黑天鵝 1%
  - 分配給「進入價值區」+「深價值區」+「黑天鵝」標的
  - 每檔精算股數（用金額除以現價）
  - **每天少量分散，不是一次大額** = 太太那種玩法

輸出：
  每筆建議含「symbol / name / 現價 / 建議股數 / 金額 / 位階 / 原因」
"""
from typing import Optional


# 彈藥比例（總資產的 %）
彈藥比例_平時 = 0.0015   # 0.15% (40 萬 → 600 元)
彈藥比例_衝刺 = 0.0030   # 0.3%  (40 萬 → 1,200)
彈藥比例_黑天鵝 = 0.0100  # 1.0%  (40 萬 → 4,000)
彈藥比例_過熱 = 0.0005   # 0.05% (40 萬 → 200 — 幾乎不買)

# 單檔最低金額（避免摩擦過高）
單檔最低_台股 = 500       # NT$ 500（台股最低，0.47% 摩擦 OK）
單檔最低_美股_usd = 100   # $100 USD（美股 0.16% 摩擦 OK）


def 計算今日彈藥(總資產_twd: float, 加碼模式: str) -> dict:
    """根據加碼模式算今天可動用彈藥。"""
    比例 = {
        "🛑 過熱觀望": 彈藥比例_過熱,
        "⚖️ 平時紀律": 彈藥比例_平時,
        "🚀 衝刺加碼": 彈藥比例_衝刺,
        "🌟 黑天鵝 ALL IN": 彈藥比例_黑天鵝,
    }.get(加碼模式, 彈藥比例_平時)
    彈藥 = round(總資產_twd * 比例, 0)
    return {
        "比例_pct": 比例 * 100,
        "彈藥_twd": 彈藥,
        "加碼模式": 加碼模式,
    }


def 計算每日加碼(位階: dict,
                  黑天鵝: Optional[dict] = None,
                  全部個股: Optional[list[dict]] = None,
                  總資產_twd: float = 400000,
                  加碼模式: str = "⚖️ 平時紀律",
                  USD_TWD: float = 31.5,
                  集中模式: str = "balanced",
                  single_focus_symbols: Optional[list[str]] = None) -> dict:
    """
    主入口：算出今天該加碼的清單。

    位階: positional_signal.掃描位階() 結果
    黑天鵝: black_swan.掃描黑天鵝() 結果（可選）
    全部個股: 用來查 close（位階沒給就 fallback）
    總資產_twd: 從 portfolio.json
    加碼模式: 從 daily_decision 拿
    USD_TWD: 動態匯率

    回傳：
    {
      "彈藥_twd": float,
      "加碼模式": str,
      "建議清單": [{
        "symbol", "name", "現價", "建議股數", "金額_twd",
        "位階分數", "位階區", "權重", "幣別",
      }],
      "說明": str,
    }
    """
    彈藥資訊 = 計算今日彈藥(總資產_twd, 加碼模式)
    彈藥 = 彈藥資訊["彈藥_twd"]

    if 彈藥 <= 0:
        return {**彈藥資訊, "建議清單": [], "說明": "今日彈藥為 0"}

    # 收集候選（深價值區雙權重、進入價值區單權重、黑天鵝三權重）
    候選 = []

    if 位階:
        # 深價值區
        for r in 位階.get("深價值區", [])[:5]:
            候選.append({"r": r, "權重": 2.0, "來源": "深價值區"})
        # 今日新進入
        for r in 位階.get("今日_進入價值區", [])[:5]:
            候選.append({"r": r, "權重": 1.5, "來源": "新進入"})
        # 中性偏低（35-50 分）也可加（次優先）
        for r in 位階.get("所有", []):
            if 35 < r.get("分數", 100) < 50:
                # 避免跟上面重複
                if not any(c["r"]["symbol"] == r["symbol"] for c in 候選):
                    候選.append({"r": r, "權重": 1.0, "來源": "中性偏低"})
                    if len(候選) >= 10:
                        break

    # 黑天鵝候選（最高權重）
    if 黑天鵝:
        for r in 黑天鵝.get("黑天鵝清單", [])[:3]:
            # 取代既有的（如果有）
            候選 = [c for c in 候選 if c["r"]["symbol"] != r["symbol"]]
            候選.insert(0, {
                "r": {"symbol": r["symbol"], "name": r.get("name", ""),
                       "close": r.get("close"), "分數": None, "區": "黑天鵝"},
                "權重": 3.0,
                "來源": "黑天鵝錯殺",
            })

    if not 候選:
        return {**彈藥資訊, "建議清單": [],
                 "說明": "今日無進入價值區個股"}

    # Phase 14：依集中模式限定候選數量
    if 集中模式 == "single" and single_focus_symbols:
        # 單押模式：只保留 single_focus_symbols 裡的
        focus_set = set(single_focus_symbols)
        過濾後 = [c for c in 候選 if c["r"].get("symbol") in focus_set]
        if 過濾後:
            候選 = 過濾後
        # 若 focus 沒中訊號 → 退回前 1-2 檔
        else:
            候選 = 候選[:1]
    elif 集中模式 == "focused":
        # 集中模式：只取前 2-3 檔最強訊號
        候選 = 候選[:3]
    else:
        # balanced 預設：前 6 檔
        候選 = 候選[:6]

    # 算每檔金額
    總權重 = sum(c["權重"] for c in 候選)
    建議清單 = []
    for c in 候選:
        r = c["r"]
        sym = r["symbol"]
        現價 = r.get("close")
        if 現價 is None or 現價 <= 0:
            continue

        is_us = not (sym.endswith(".TW") or sym.endswith(".TWO"))
        分配金額_twd = round(彈藥 * (c["權重"] / 總權重), 0)

        if is_us:
            分配金額_usd = 分配金額_twd / USD_TWD
            if 分配金額_usd < 單檔最低_美股_usd:
                continue
            建議股數 = max(1, int(分配金額_usd / 現價))
            實際金額_usd = round(建議股數 * 現價, 2)
            實際金額_twd = round(實際金額_usd * USD_TWD, 0)
            幣 = "USD"
            幣號 = "$"
        else:
            if 分配金額_twd < 單檔最低_台股:
                continue
            建議股數 = max(1, int(分配金額_twd / 現價))
            實際金額_twd = round(建議股數 * 現價, 0)
            幣 = "TWD"
            幣號 = "NT$"

        建議清單.append({
            "symbol": sym,
            "name": r.get("name", ""),
            "現價": 現價,
            "建議股數": 建議股數,
            "金額_twd": 實際金額_twd,
            "幣別": 幣,
            "幣號": 幣號,
            "位階分數": r.get("分數"),
            "位階區": r.get("區", "?"),
            "權重": c["權重"],
            "來源": c["來源"],
        })

    if not 建議清單:
        return {**彈藥資訊, "建議清單": [],
                 "說明": "彈藥不足以分配（單檔最低金額限制）"}

    說明 = (f"今日彈藥 NT$ {彈藥:,.0f}（總資產 {彈藥資訊['比例_pct']:.2f}%）"
              f"，分配給 {len(建議清單)} 檔")

    return {
        **彈藥資訊,
        "建議清單": 建議清單,
        "說明": 說明,
    }
