"""
Sylvie 非對稱權重 (Phase 36.6 — Q5)

對方 AI 設計：4 個情境表 + 我加的第 5 個

| 情境 | Sylvie | LIS | 動作 |
|---|---|---|---|
| 防禦危機 | 全清/大減碼 | 系統算持股 | **強制跟賣**（Sylvie 100%）|
| 攻擊共振 | 買進/加碼 | 強烈買進 | **雙重確認 ×1.5 加碼** |
| 系統獨走 | 沒動作 | 強烈買進 | 獨立試單（LIS 基礎）|
| 人為干擾 | 買進/加碼 | 破線/過熱 | 系統攔截（LIS 拒絕跟）|
| 持續加碼 N 週 | 連 4 週加碼 | - | ARK 派長期信念 ×2.0 |

依賴：sylvie_tracker（snapshot 比對） + positional_state（LIS 訊號）
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


def 載入sylvie歷史() -> dict:
    """讀 sylvie_snapshot.json + sylvie_portfolio.json"""
    cur_path = 專案根 / "數據" / "sylvie_portfolio.json"
    snap_path = 專案根 / "數據" / "sylvie_snapshot.json"
    current = json.loads(cur_path.read_text(encoding="utf-8")) if cur_path.exists() else {}
    snap = json.loads(snap_path.read_text(encoding="utf-8")) if snap_path.exists() else {}
    return {"current": current, "snapshot": snap}


def 載入LIS訊號() -> dict:
    """讀 positional_state.json 看 LIS 當前訊號"""
    path = 專案根 / "數據" / "positional_state.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def 判定sylvie動作(symbol: str) -> str:
    """
    比對 snapshot vs current 看 Sylvie 對該 symbol 的動作：
      "全清" / "大減碼" / "加碼" / "新買" / "沒動作"
    """
    data = 載入sylvie歷史()
    cur = data["current"]
    snap = data["snapshot"]

    cur_hold = {p["symbol"]: p for p in cur.get("持股", [])}
    snap_hold = {p["symbol"]: p for p in snap.get("持股", [])}

    in_cur = symbol in cur_hold
    in_snap = symbol in snap_hold

    if not in_cur and in_snap:
        return "全清"
    if in_cur and not in_snap:
        return "新買"
    if in_cur and in_snap:
        cur_股 = cur_hold[symbol]["股數"]
        snap_股 = snap_hold[symbol]["股數"]
        if cur_股 > snap_股:
            增加比 = (cur_股 - snap_股) / snap_股 * 100
            return "加碼" if 增加比 < 30 else "大加碼"
        elif cur_股 < snap_股:
            減少比 = (snap_股 - cur_股) / snap_股 * 100
            return "大減碼" if 減少比 >= 30 else "減碼"
    return "沒動作"


def 判定LIS訊號(symbol: str) -> str:
    """
    依 positional_state 判定 LIS 對該 symbol 的訊號：
      "強烈買進" / "持有" / "破線過熱" / "沒訊號"
    """
    state = 載入LIS訊號()
    scores = state.get("scores", {})
    details = state.get("details", {})

    位階 = scores.get(symbol)
    if 位階 is None:
        return "沒訊號"

    detail = details.get(symbol, {})
    rsi = detail.get("rsi14") or detail.get("RSI14") or 50
    型態 = detail.get("型態") or ""

    if 位階 <= 35:
        return "強烈買進"  # 深價值
    if 位階 >= 80 and rsi >= 80:
        return "破線過熱"
    if 位階 >= 75:
        return "過熱"
    return "持有"


def 非對稱權重決策(symbol: str) -> dict:
    """
    主入口：依 Sylvie + LIS 兩邊判斷給最終動作

    Returns:
        {
            symbol: str,
            sylvie動作: str,
            lis訊號: str,
            情境: str (5 種情境),
            最終動作: str,
            加碼倍率: float,
            說明: str,
        }
    """
    s = 判定sylvie動作(symbol)
    l = 判定LIS訊號(symbol)

    # 情境 1：防禦危機（一票否決）⭐ 最關鍵
    if s in ("全清", "大減碼"):
        return {
            "symbol": symbol,
            "sylvie動作": s,
            "lis訊號": l,
            "情境": "🚨 防禦危機（Sylvie 一票否決）",
            "最終動作": f"強制跟賣 — Sylvie 對總經/政策直覺領先",
            "加碼倍率": 0,
            "權重": "Sylvie 100%",
            "說明": (f"Sylvie {s}，不論 LIS 訊號 {l}，"
                     "風控優先 → 跟著降部位"),
        }

    # 情境 2：攻擊共振（雙重確認）
    if s in ("加碼", "大加碼", "新買") and l == "強烈買進":
        倍 = 2.0 if s == "大加碼" else 1.5
        return {
            "symbol": symbol,
            "sylvie動作": s,
            "lis訊號": l,
            "情境": "🔥 攻擊共振（雙重確認）",
            "最終動作": f"加碼倍率 ×{倍}",
            "加碼倍率": 倍,
            "權重": "Sylvie + LIS 共識",
            "說明": "信念極高，conviction_discount 用最大值",
        }

    # 情境 3：系統獨走（LIS 挖到 Sylvie 沒注意）
    if s == "沒動作" and l == "強烈買進":
        return {
            "symbol": symbol,
            "sylvie動作": s,
            "lis訊號": l,
            "情境": "🤖 系統獨走（LIS 挖訊號）",
            "最終動作": "獨立試單 — LIS 基礎倍率 ×1.0",
            "加碼倍率": 1.0,
            "權重": "LIS 100%（試單驗證）",
            "說明": "LIS 挖到 Sylvie 沒注意的錯殺，基礎倍率試單證明演算法",
        }

    # 情境 4：人為干擾（LIS 攔截）
    if s in ("加碼", "大加碼", "新買") and l in ("破線過熱", "過熱"):
        return {
            "symbol": symbol,
            "sylvie動作": s,
            "lis訊號": l,
            "情境": "🛑 人為干擾（LIS 攔截）",
            "最終動作": "系統攔截 — 拒絕跟 Sylvie 加碼",
            "加碼倍率": 0,
            "權重": "LIS 100%（風控優先）",
            "說明": ("Sylvie 也會 FOMO 買在高點。"
                     "LIS 判定過熱 → 系統發出警告"),
        }

    # 情境 5（我加的）：持續加碼 N 週 = ARK 派長期信念
    # （需要 Sylvie 歷史紀錄，目前簡化判斷）
    # ...

    # 預設：跟 Sylvie 但小倉位
    if s in ("加碼", "新買"):
        return {
            "symbol": symbol,
            "sylvie動作": s,
            "lis訊號": l,
            "情境": "📊 一般跟單",
            "最終動作": "Sylvie 跟單 — 倍率 ×1.0",
            "加碼倍率": 1.0,
            "權重": "Sylvie 60% / LIS 40%",
            "說明": "Sylvie 有動作但 LIS 中性，跟小倉位",
        }

    return {
        "symbol": symbol,
        "sylvie動作": s,
        "lis訊號": l,
        "情境": "💤 無共識",
        "最終動作": "暫不動",
        "加碼倍率": 0,
        "權重": "-",
        "說明": "雙邊都沒明顯訊號",
    }


def 掃描所有共識訊號() -> list:
    """掃 Sylvie 持股 + LIS watchlist 找所有有訊號的"""
    data = 載入sylvie歷史()
    cur_syms = set(p["symbol"] for p in data["current"].get("持股", []))
    snap_syms = set(p["symbol"] for p in data["snapshot"].get("持股", []))
    all_syms = cur_syms | snap_syms

    state = 載入LIS訊號()
    all_syms = all_syms | set(state.get("scores", {}).keys())

    結果 = []
    for sym in all_syms:
        r = 非對稱權重決策(sym)
        # 只保留有觸發情境的
        if r["情境"] not in ("💤 無共識", "📊 一般跟單"):
            結果.append(r)
    return 結果


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from dotenv import load_dotenv
    load_dotenv(專案根 / "API" / ".env")

    print("=" * 60)
    print("Sylvie 非對稱權重決策（Q5）")
    print("=" * 60)

    # 測試 4 個情境
    測試 = ["00910.TW", "00893.TW", "00631L.TW", "0050.TW", "SATL"]
    for sym in 測試:
        r = 非對稱權重決策(sym)
        print(f"\n{sym}")
        print(f"  Sylvie: {r['sylvie動作']} / LIS: {r['lis訊號']}")
        print(f"  情境: {r['情境']}")
        print(f"  動作: {r['最終動作']}")
        if r['加碼倍率'] != 1.0:
            print(f"  倍率: ×{r['加碼倍率']}")

    # 全掃
    print(f"\n{'='*60}")
    print("全掃描有觸發情境的訊號")
    print('='*60)
    全部 = 掃描所有共識訊號()
    if 全部:
        for r in 全部[:10]:
            print(f"  {r['symbol']}: {r['情境']} → {r['最終動作']}")
    else:
        print("  （目前無觸發特殊情境的訊號）")
