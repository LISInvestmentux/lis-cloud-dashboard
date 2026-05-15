"""
訊號狀態追蹤（Phase 14）
給「你關心的標的」明確顯示「訊號還在 / 訊號消失 / 加碼進行中」狀態。

追蹤對象（合併）：
  1. 持股（portfolio.json current_positions）
  2. 長期 DCA 清單（portfolio.json long_term_dca.items）
  3. 集中模式關注標的（single_focus_symbols）

每檔顯示：
  - 目前位階分數
  - 訊號狀態（🟢 還在 / 🟡 減弱 / 🔴 消失）
  - 訊號持續天數（從進入價值區那天起算）
  - 建議動作
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
進場日紀錄 = 專案根 / "數據" / "signal_entry_dates.json"


def _載入進場日() -> dict:
    """{symbol: '2026-01-12'}  訊號最初進入價值區的日期"""
    if not 進場日紀錄.exists():
        return {}
    try:
        with open(進場日紀錄, "r", encoding="utf-8") as f:
            return json.load(f).get("entries", {})
    except Exception:
        return {}


def _更新進場日(分數表: dict, 今日: str) -> None:
    """
    若某 symbol 今日首次跌入 50 線下 → 記錄今日為進場日
    若某 symbol 已脫離 → 標記離場
    """
    紀錄 = {}
    if 進場日紀錄.exists():
        try:
            with open(進場日紀錄, "r", encoding="utf-8") as f:
                紀錄 = json.load(f)
        except Exception:
            pass

    entries = 紀錄.get("entries", {})
    for sym, 分 in 分數表.items():
        if 分 < 50:
            # 訊號還在
            if sym not in entries:
                entries[sym] = 今日   # 首次進入
        else:
            # 訊號消失
            if sym in entries:
                # 不刪 — 保留歷史，但加個 exit_date
                pass

    紀錄["entries"] = entries
    紀錄["updated_at"] = 今日
    進場日紀錄.parent.mkdir(parents=True, exist_ok=True)
    with open(進場日紀錄, "w", encoding="utf-8") as f:
        json.dump(紀錄, f, ensure_ascii=False, indent=2)


def 訊號狀態(分數: Optional[float]) -> dict:
    """位階分數 → 訊號狀態判讀"""
    if 分數 is None:
        return {"狀態": "資料不足", "色": "subtle", "動作": "n/a",
                "emoji": "❓"}
    if 分數 < 25:
        return {"狀態": "強訊號", "色": "bull", "動作": "加倍加碼",
                "emoji": "🟢🟢"}
    if 分數 < 45:
        return {"狀態": "訊號還在", "色": "bull", "動作": "持續加碼",
                "emoji": "🟢"}
    if 分數 < 55:
        return {"狀態": "訊號減弱", "色": "wait", "動作": "維持不加",
                "emoji": "🟡"}
    if 分數 < 75:
        return {"狀態": "訊號消失", "色": "wait", "動作": "停止加碼",
                "emoji": "🔴"}
    return {"狀態": "嚴重過熱", "色": "bear", "動作": "考慮減碼",
            "emoji": "🔥"}


def 追蹤關心標的(設定: dict,
                  位階: dict) -> dict:
    """
    主入口。
    設定：portfolio.json
    位階：positional_signal.掃描位階() 結果

    回傳：
    {
      "持股追蹤": [...],
      "長期DCA追蹤": [...],
      "單押追蹤": [...],
      "今日新進入": [...],  # 新跨入 50 線下
      "今日新消失": [...],  # 新跨上 50 線
    }
    """
    if not 位階:
        return {"持股追蹤": [], "長期DCA追蹤": [], "單押追蹤": [],
                "今日新進入": [], "今日新消失": []}

    所有分數 = {r["symbol"]: r["分數"]
                  for r in 位階.get("所有", [])
                  if r.get("分數") is not None}

    今日 = datetime.now().strftime("%Y-%m-%d")
    進場日map = _載入進場日()

    def _追蹤(symbol: str, name: str = "",
              extra: Optional[dict] = None) -> dict:
        分 = 所有分數.get(symbol)
        狀 = 訊號狀態(分)
        進場日 = 進場日map.get(symbol)
        if 進場日 and 分 is not None and 分 < 55:
            try:
                d0 = datetime.strptime(進場日, "%Y-%m-%d").date()
                d1 = datetime.strptime(今日, "%Y-%m-%d").date()
                持續天數 = (d1 - d0).days
            except Exception:
                持續天數 = None
        else:
            持續天數 = None

        rec = {
            "symbol": symbol,
            "name": name,
            "分數": 分,
            "狀態": 狀["狀態"],
            "emoji": 狀["emoji"],
            "動作": 狀["動作"],
            "進場日": 進場日,
            "持續天數": 持續天數,
        }
        if extra:
            rec.update(extra)
        return rec

    # 1. 持股追蹤
    持股追蹤 = []
    for p in 設定.get("current_positions", []):
        sym = p.get("symbol")
        if not sym or sym == "AGGREGATE":
            continue
        持股追蹤.append(_追蹤(sym, p.get("name", ""),
                                {"shares": p.get("shares")}))

    # 2. 長期 DCA 追蹤
    長期DCA = []
    for item in 設定.get("long_term_dca", {}).get("items", []):
        sym = item.get("symbol")
        if not sym:
            continue
        長期DCA.append(_追蹤(sym, item.get("name", ""),
                                {"monthly_twd": item.get("monthly_twd")}))

    # 3. 單押模式追蹤
    單押追蹤 = []
    集中 = 設定.get("concentration_mode", {})
    if 集中.get("mode") == "single":
        for sym in 集中.get("single_focus_symbols", []):
            單押追蹤.append(_追蹤(sym))

    # 4. 偵測「今日新進入 / 今日新消失」（用昨天紀錄對比）
    今日新進入 = []
    今日新消失 = []
    for r in 位階.get("所有", []):
        sym = r.get("symbol")
        昨分 = r.get("昨分")
        分 = r.get("分數")
        if 分 is None or 昨分 is None:
            continue
        if 昨分 >= 50 and 分 < 50:
            今日新進入.append({
                "symbol": sym, "name": r.get("name", ""),
                "昨分": 昨分, "今分": 分,
            })
        elif 昨分 < 50 and 分 >= 50:
            今日新消失.append({
                "symbol": sym, "name": r.get("name", ""),
                "昨分": 昨分, "今分": 分,
            })

    # 5. 更新進場日紀錄
    _更新進場日(所有分數, 今日)

    return {
        "持股追蹤": 持股追蹤,
        "長期DCA追蹤": 長期DCA,
        "單押追蹤": 單押追蹤,
        "今日新進入": 今日新進入,
        "今日新消失": 今日新消失,
    }
