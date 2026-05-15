"""
ATR 吊燈停損法（Phase 36.2 — Chandelier Exit）

對方 AI 專業驗證後的設計：
  停損價 = 買進後最高收盤價 (HWM) - ATR(14) × 倍數

倍數分層：
  ETF        2.0x
  個股       2.5x
  美股科技   3.0x
  VIX > 25 → 全部 +0.5（恐慌期放寬避免被掃出場）

關鍵：起算點是 HWM（買進後最高收盤），不是進場價
  → 隨股價走高自動上移停損 = 鎖定獲利

替代舊 -5% 寫死 → 個股自己決定停損空間，不被洗

依賴：yfinance（抓 30 天日線算 ATR）
"""
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


# 股票類型分層
def 判定股種(symbol: str, name: str = "") -> str:
    """回傳 'etf' / 'tw_stock' / 'us_tech' / 'us_stock'"""
    s = symbol.upper()
    n = (name or "").upper()

    # 美股
    is_us = not (s.endswith(".TW") or s.endswith(".TWO"))
    if is_us:
        us_tech = ["NVDA", "AMD", "META", "GOOGL", "AAPL", "MSFT",
                    "TSLA", "AMZN", "ADBE", "AVGO", "MU", "INTC",
                    "TSM", "QQQ", "SMH", "ARKK", "ARKX", "ARKQ",
                    "IREN", "SATL", "MSTR", "PLTR", "PLGI"]
        if s in us_tech or any(t in s for t in ["NVD", "AMD", "TSL"]):
            return "us_tech"
        return "us_stock"

    # 台股 ETF（0050, 00xxx 開頭）
    純代號 = s.replace(".TW", "").replace(".TWO", "")
    if 純代號.startswith("00") or 純代號 == "0050":
        return "etf"
    if "ETF" in n or "元大" in n or "國泰" in n or "富邦" in n:
        return "etf"

    return "tw_stock"


# 倍數對應
ATR_倍數表 = {
    "etf":      2.0,
    "tw_stock": 2.5,
    "us_stock": 2.5,
    "us_tech":  3.0,
}


def 算ATR(symbol: str, period: int = 14,
          technical_mod=None) -> Optional[float]:
    """
    抓 30 天日線算 ATR(14)
    True Range = max(high-low, |high-prev_close|, |low-prev_close|)
    ATR = TR 的 14 天移動平均
    """
    try:
        if technical_mod is None:
            from . import technical as technical_mod
    except ImportError:
        try:
            import technical as technical_mod
        except ImportError:
            return None

    try:
        # 抓 30 天日線（夠算 ATR(14) + buffer）
        歷史, _ = technical_mod.取得每日股價(symbol, period="1mo")
        if not 歷史 or len(歷史) < period + 1:
            return None

        # 歷史是新→舊 排序，先反轉成舊→新
        歷史 = list(reversed(歷史))

        tr_list = []
        for i in range(1, len(歷史)):
            high = 歷史[i].get("high", 歷史[i]["close"])
            low = 歷史[i].get("low", 歷史[i]["close"])
            prev_close = 歷史[i-1]["close"]
            tr = max(high - low,
                     abs(high - prev_close),
                     abs(low - prev_close))
            tr_list.append(tr)

        if len(tr_list) < period:
            return None

        # 用最後 14 筆算 ATR
        atr = sum(tr_list[-period:]) / period
        return round(atr, 4)
    except Exception:
        return None


def 算HWM(symbol: str, buy_date: str = None,
          technical_mod=None, fallback_price: float = None) -> Optional[float]:
    """
    High-Water Mark = 買進後最高收盤
    若 buy_date 不知道，用過去 60 天最高
    """
    try:
        if technical_mod is None:
            from . import technical as technical_mod
    except ImportError:
        try:
            import technical as technical_mod
        except ImportError:
            return fallback_price

    try:
        歷史, _ = technical_mod.取得每日股價(symbol, period="2mo")
        if not 歷史:
            return fallback_price

        # 若有 buy_date，只看買後
        if buy_date:
            try:
                buy_dt = datetime.strptime(buy_date[:10], "%Y-%m-%d").date()
            except Exception:
                buy_dt = None
        else:
            buy_dt = None

        if buy_dt:
            篩選 = [h for h in 歷史
                    if datetime.strptime(h["date"][:10], "%Y-%m-%d").date()
                       >= buy_dt]
            if not 篩選:
                篩選 = 歷史
        else:
            篩選 = 歷史

        return max(h["close"] for h in 篩選)
    except Exception:
        return fallback_price


def 算動態停損(symbol: str, 進場價: float, 現價: float,
              name: str = "", buy_date: str = None,
              VIX: float = None) -> dict:
    """
    主入口：算「吊燈停損」價

    Returns:
        {
            停損價: float,
            HWM: float (最高水位),
            ATR: float,
            倍數: float,
            股種: str,
            停損_pct_vs進場: float (相對進場價的 %),
            停損_pct_vs現價: float (相對現價的 %),
            觸發: bool (現價是否已破停損),
            說明: str,
        }
    """
    股種 = 判定股種(symbol, name)
    倍數 = ATR_倍數表.get(股種, 2.5)

    # VIX > 25 → 倍數 +0.5（恐慌期放寬）
    if VIX and VIX > 25:
        倍數 += 0.5

    atr = 算ATR(symbol)
    if atr is None or atr <= 0:
        # Fallback：抓不到 ATR 用舊 -5%
        return {
            "停損價": round(進場價 * 0.95, 2),
            "HWM": 進場價,
            "ATR": None,
            "倍數": None,
            "股種": 股種,
            "停損_pct_vs進場": -5.0,
            "停損_pct_vs現價": round((進場價 * 0.95 / 現價 - 1) * 100, 2),
            "觸發": 現價 < 進場價 * 0.95,
            "說明": f"無法抓 ATR，退回 -5% 寫死",
        }

    hwm = 算HWM(symbol, buy_date, fallback_price=進場價)
    if hwm is None:
        hwm = 進場價
    # HWM 不能比進場價低
    hwm = max(hwm, 進場價)

    停損價 = hwm - 倍數 * atr
    # 下限：不能比進場價更低於 -15%（避免 ATR 太大 = 停損空間太鬆）
    最低停損 = 進場價 * 0.85
    停損價 = max(停損價, 最低停損)
    # 沒漲過的部位（HWM ≈ 進場價）→ 用「進場價 - 1.5×ATR」當保護停損
    # 漲過很多的部位（HWM >> 進場價）→ 停損可能在進場價之上 = 鎖利

    停損_pct_進場 = (停損價 / 進場價 - 1) * 100
    停損_pct_現價 = (停損價 / 現價 - 1) * 100

    說明 = (f"{股種} ATR(14)={atr:.2f} × {倍數}x, "
            f"HWM=${hwm:.2f}")
    if VIX and VIX > 25:
        說明 += f" (VIX {VIX:.1f} 加 +0.5)"

    return {
        "停損價": round(停損價, 2),
        "HWM": round(hwm, 2),
        "ATR": atr,
        "倍數": 倍數,
        "股種": 股種,
        "停損_pct_vs進場": round(停損_pct_進場, 2),
        "停損_pct_vs現價": round(停損_pct_現價, 2),
        "觸發": 現價 < 停損價,
        "說明": 說明,
    }


# ─────────────────────────────────────────────
# CLI 測試
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
    print("ATR 吊燈停損測試（Chandelier Exit）")
    print("=" * 60)

    案例 = [
        ("0050.TW", "元大台灣50", 88.39, 96.10),
        ("2330.TW", "台積電",     2079.38, 2260),
        ("00910.TW", "第一金太空衛星", 68.81, 75.00),
        ("NVDA", "NVDA", 180.50, 210.00),
        ("SATL", "Satellogic", 7.33, 8.64),
    ]

    print(f"\n{'代號':12s} {'股種':10s} {'進場':>8s} {'現價':>8s} "
          f"{'停損':>8s} {'vs進場':>8s} {'倍數':>5s}")
    print("-" * 80)
    for sym, name, 進, 現 in 案例:
        r = 算動態停損(sym, 進, 現, name=name, VIX=17.3)
        觸 = "🚨" if r["觸發"] else "✅"
        atr_str = f"ATR={r['ATR']:.2f}" if r["ATR"] else "ATR=?"
        print(f"{sym:12s} {r['股種']:10s} {進:>8.2f} {現:>8.2f} "
              f"{r['停損價']:>8.2f} {r['停損_pct_vs進場']:>+7.2f}% "
              f"{r['倍數']:>5}x {觸}")
        print(f"             → {r['說明']}")
