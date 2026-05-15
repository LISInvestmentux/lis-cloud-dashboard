"""
峰值追蹤器（Phase 32.7）— A 機制

追蹤每檔股票的「最近觀察期高點」，算當前回檔 %。
讓 LIS 發現「從高點跌深」的標的 → 進入價值區候選。

存放：數據/peak_tracker.json
格式：
{
  "symbol": {
    "daily_peak": float,
    "daily_peak_date": "YYYY-MM-DD",
    "weekly_peak": float,
    "weekly_peak_date": "YYYY-MM-DD",
    "all_time_peak": float,
    "all_time_peak_date": "YYYY-MM-DD",
    "last_update": "YYYY-MM-DD HH:MM"
  }
}

判讀規則：
  從 weekly peak 回檔 ≥15% → 🟢 進入價值區候選（推 LINE）
  從 weekly peak 回檔 ≥10% → ⚠️ 回檔中觀察
  從 weekly peak 回檔 ≥5%  → 📉 微回
  其他 → ✅ 強勢
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
紀錄檔 = 專案根 / "數據" / "peak_tracker.json"


def _載入() -> dict:
    if not 紀錄檔.exists():
        return {}
    try:
        return json.loads(紀錄檔.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _存(data: dict):
    紀錄檔.parent.mkdir(parents=True, exist_ok=True)
    紀錄檔.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")


def 更新峰值(symbol: str, current_price: float) -> dict:
    """每次掃描股價時呼叫，自動更新各週期峰值。"""
    if not symbol or current_price <= 0:
        return {}
    data = _載入()
    今天 = datetime.now().strftime("%Y-%m-%d")
    當下 = datetime.now().strftime("%Y-%m-%d %H:%M")

    entry = data.setdefault(symbol, {})

    # daily peak — 同天才更新，跨天重設
    if entry.get("daily_peak_date") != 今天:
        entry["daily_peak"] = current_price
        entry["daily_peak_date"] = 今天
    elif current_price > entry.get("daily_peak", 0):
        entry["daily_peak"] = current_price

    # weekly peak — 7 天內
    weekly_cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    if not entry.get("weekly_peak_date") or entry["weekly_peak_date"] < weekly_cutoff:
        entry["weekly_peak"] = current_price
        entry["weekly_peak_date"] = 今天
    elif current_price > entry.get("weekly_peak", 0):
        entry["weekly_peak"] = current_price
        entry["weekly_peak_date"] = 今天

    # all-time peak (since tracking started)
    if current_price > entry.get("all_time_peak", 0):
        entry["all_time_peak"] = current_price
        entry["all_time_peak_date"] = 今天

    entry["last_price"] = current_price
    entry["last_update"] = 當下
    _存(data)
    return entry


def 算回檔(symbol: str, current_price: Optional[float] = None) -> dict:
    """
    算當前 vs 各週期峰值的回檔 %。
    回傳：{
      daily_drawdown_pct, weekly_drawdown_pct, all_time_drawdown_pct,
      level, 訊號
    }
    """
    data = _載入()
    entry = data.get(symbol)
    if not entry:
        return {"無資料": True}
    if current_price is None:
        current_price = entry.get("last_price")
    if not current_price or current_price <= 0:
        return {"無資料": True}

    def _dd(peak):
        if not peak or peak <= 0:
            return None
        return round((current_price - peak) / peak * 100, 2)

    daily = _dd(entry.get("daily_peak"))
    weekly = _dd(entry.get("weekly_peak"))
    all_time = _dd(entry.get("all_time_peak"))

    # 訊號分級（以 weekly 為準）
    if weekly is not None and weekly <= -15:
        level = "🟢 進入價值區候選"
        訊號 = True
    elif weekly is not None and weekly <= -10:
        level = "⚠️ 回檔中觀察"
        訊號 = True
    elif weekly is not None and weekly <= -5:
        level = "📉 微回"
        訊號 = False
    else:
        level = "✅ 強勢"
        訊號 = False

    return {
        "current": current_price,
        "daily_peak": entry.get("daily_peak"),
        "daily_drawdown_pct": daily,
        "weekly_peak": entry.get("weekly_peak"),
        "weekly_drawdown_pct": weekly,
        "all_time_peak": entry.get("all_time_peak"),
        "all_time_drawdown_pct": all_time,
        "level": level,
        "推訊號": 訊號,
    }


def 掃描清單(symbols: list[str], 現價映射: dict) -> list[dict]:
    """
    對多個 symbol 一次掃描 — 更新峰值 + 算回檔。
    現價映射: {symbol: 現價}
    回傳 [{symbol, ...drawdown info}, ...]
    """
    結果 = []
    for sym in symbols:
        現價 = 現價映射.get(sym)
        if 現價 is None or 現價 <= 0:
            continue
        更新峰值(sym, 現價)
        r = 算回檔(sym, 現價)
        r["symbol"] = sym
        結果.append(r)
    # 排序：訊號高的優先
    結果.sort(key=lambda x: x.get("weekly_drawdown_pct", 0) or 0)
    return 結果


def 進入價值區候選(symbols: list[str], 現價映射: dict,
                     threshold_pct: float = -15) -> list[dict]:
    """快速取「回檔 ≥threshold% 的標的」"""
    結果 = 掃描清單(symbols, 現價映射)
    return [r for r in 結果
            if r.get("weekly_drawdown_pct") is not None
            and r["weekly_drawdown_pct"] <= threshold_pct]


# ─────────────────────────────────────────────
# CLI 自測
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # 用 user 截圖數據模擬
    # CRCL 從高點 ($120.83) 跌到 $120.83 with -4.5% 回檔
    # SWMR 從高點跌 -3.43%
    print("=== peak_tracker 模擬 ===\n")
    # 模擬 CRCL：先存高點 (Enjoy 截圖 $118.66 → 但 user 提到 $120.83 是高點)
    更新峰值("CRCL", 120.83)
    # 然後現在 $115.4 (回檔 4.5%)
    更新峰值("CRCL", 120.83 * 0.955)
    r = 算回檔("CRCL", 120.83 * 0.955)
    print(f"CRCL: {r}")

    # 模擬 SWMR
    更新峰值("SWMR", 29.48)
    更新峰值("SWMR", 29.48 * 0.9657)
    r = 算回檔("SWMR")
    print(f"SWMR: {r}")
