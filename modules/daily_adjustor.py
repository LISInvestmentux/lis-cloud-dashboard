"""
每日調節判定（Phase 28）— ARK 方舟核心邏輯：「先決定要不要調節，再進入布局」

ARK 哲學：
  「10 檔不是叫你挑 2、3 檔重壓，
   而是系統算到的標的就布局。最後最大包，應由系統調節後自然累積出來。」

LIS 修正：
  之前太 Kelly 主義 → 改成 ARK「分散布局 + 每日調節」

每日流程：
  1. 抓真倉現況（每檔市值 / 目標佔比）
  2. 比對 ARK 9 檔目標佔比（先前 concentration_planner 算的）
  3. 計算每檔「偏離度」（實際 vs 目標）
  4. 判斷今天該調節哪些：
     偏離 > +5% → 賣一點 (太多)
     偏離 < -5% → 補一點 (太少)
     偏離 ±5% → 不動

  「不調節，才進入新布局」— 沒偏離才開新單

決策輸出：
  {
    "要調節": True/False,
    "調節清單": [{symbol, 動作, 股數, 金額}],
    "可進入新布局": False/True,
  }
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


def 算偏離度(目標佔比清單: dict[str, float],
              實際佔比清單: dict[str, float],
              閾值_pct: float = 5.0) -> dict:
    """
    回傳每檔的偏離度與調節建議。

    目標佔比清單: {symbol: 目標佔比_pct}
    實際佔比清單: {symbol: 現在佔比_pct}
    """
    偏離 = []
    需減碼 = []
    需加碼 = []

    所有檔 = set(目標佔比清單.keys()) | set(實際佔比清單.keys())
    for sym in 所有檔:
        目 = 目標佔比清單.get(sym, 0)
        實 = 實際佔比清單.get(sym, 0)
        差 = 實 - 目  # 正數 = 太多，負數 = 太少
        rec = {
            "symbol": sym,
            "目標_pct": round(目, 2),
            "實際_pct": round(實, 2),
            "差距_pct": round(差, 2),
        }
        偏離.append(rec)
        if 差 > 閾值_pct:
            需減碼.append(rec)
        elif 差 < -閾值_pct:
            需加碼.append(rec)

    偏離.sort(key=lambda r: -abs(r["差距_pct"]))
    需減碼.sort(key=lambda r: -r["差距_pct"])  # 最超出在前
    需加碼.sort(key=lambda r: r["差距_pct"])   # 最不足在前

    return {
        "全部偏離": 偏離,
        "需減碼": 需減碼,
        "需加碼": 需加碼,
        "要調節": bool(需減碼 or 需加碼),
    }


def 每日調節判定(總資產_twd: float, 持股市值: dict[str, float],
                  目標佔比: dict[str, float],
                  閾值_pct: float = 5.0,
                  允許新單: bool = True) -> dict:
    """
    ARK 風格每日調節判定。

    參數：
      總資產_twd — 含現金 + 持股
      持股市值 — {symbol: 市值_twd}
      目標佔比 — {symbol: pct}（從 concentration_planner 來）
      閾值 — 偏離超過 N% 才要調節

    回傳：
      {
        "要調節": bool,
        "可進入新布局": bool,
        "今日動作": "調節" / "新布局" / "觀望",
        "調節清單": [...],
      }
    """
    # 算實際佔比
    實際佔比 = {sym: (市值 / 總資產_twd * 100) if 總資產_twd > 0 else 0
                 for sym, 市值 in 持股市值.items()}

    結果 = 算偏離度(目標佔比, 實際佔比, 閾值_pct)
    要調節 = 結果["要調節"]

    # ARK 邏輯：要調節就先調節，不調節才進新布局
    if 要調節:
        今日動作 = "調節"
        可進入新布局 = False
        建議 = f"⚠️ 有 {len(結果['需減碼']) + len(結果['需加碼'])} 檔偏離 >5%，先調節再說"
    elif 允許新單:
        今日動作 = "新布局"
        可進入新布局 = True
        建議 = "✅ 部位平衡，可進入新訊號布局"
    else:
        今日動作 = "觀望"
        可進入新布局 = False
        建議 = "🟡 不接新單"

    return {
        "要調節": 要調節,
        "可進入新布局": 可進入新布局,
        "今日動作": 今日動作,
        "建議": 建議,
        "偏離詳情": 結果,
        "閾值_pct": 閾值_pct,
    }


# ─────────────────────────────────────────────
# CLI 自測（用你今天真倉測）
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=== Phase 28 每日調節判定（ARK 風） ===\n")

    # 模擬：你今天持股 vs ARK 9 檔目標
    持股 = {
        "0050.TW": 14910,
        "00910.TW": 17570,
        "00911.TW": 5637,
        "00935.TW": 4390,
        "00861.TW": 4272,
        "00876.TW": 3856,
        "00631L.TW": 6422,
        "2890.TW": 15331,
        "2330.TW": 71918,    # 過大 ⚠️
        "00942B.TWO": 1711,  # 過小 ⚠️
        # 不在 ARK 9 檔的（要逐步出）
        "00662.TW": 14316,
        "00830.TW": 7165,
        "00878.TW": 4223,
        "00882.TW": 4876,
        "00920.TW": 5276,
        "00941.TW": 36982,   # 大部位但不在 ARK
        "00981A.TW": 6484,
        "1717.TW": 12584,
        "2891.TW": 16385,
        "SATL_USD": 1215 * 31.5,  # 美股換 TWD
        "AMD_USD": 445 * 31.5,
        "GLW_USD": 207 * 31.5,
        "ADBE_USD": 236 * 31.5,
        "IREN_USD": 441 * 31.5,
    }
    總資產 = sum(持股.values()) + 171500  # 加現金

    # ARK 9 檔目標佔比（從 concentration_planner）
    目標 = {
        "00910.TW": 8.6,
        "00861.TW": 6.5,
        "00911.TW": 6.6,
        "00935.TW": 6.1,
        "0050.TW": 5.1,
        "00631L.TW": 4.4,
        "00876.TW": 3.9,
        "2890.TW": 6.7,
        "2330.TW": 16.9,
        "00942B.TWO": 1.2,
    }

    r = 每日調節判定(總資產, 持股, 目標, 閾值_pct=5.0)
    print(f"📊 今日動作：{r['今日動作']}")
    print(f"💡 {r['建議']}\n")

    if r["偏離詳情"]["需減碼"]:
        print("🔻 需減碼（部位過大）：")
        for r2 in r["偏離詳情"]["需減碼"][:8]:
            print(f"  {r2['symbol']:<14} 實 {r2['實際_pct']:>5.2f}% / "
                  f"目 {r2['目標_pct']:>5.2f}% / 差 {r2['差距_pct']:>+5.2f}%")
    if r["偏離詳情"]["需加碼"]:
        print("\n🔺 需加碼（部位不足）：")
        for r2 in r["偏離詳情"]["需加碼"][:5]:
            print(f"  {r2['symbol']:<14} 實 {r2['實際_pct']:>5.2f}% / "
                  f"目 {r2['目標_pct']:>5.2f}% / 差 {r2['差距_pct']:>+5.2f}%")
