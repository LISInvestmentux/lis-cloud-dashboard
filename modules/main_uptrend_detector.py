"""
主升段判定 (Phase 36.7 — Q3)

對方 AI 設計：
  主升段 = 法人連買 3 天 + 佔比 >10% + MA60 乖離 10-15%
  短期過熱 = MA60 乖離 >30%（個股）或 >15%（大盤 ETF）

主升段觸發時：
  +15% 停利**延後到 +20% 或 +25%**
  強制 ATR 吊燈保護鎖利

統計：+15% → +50% 不回檔機率 < 15%
所以「賣 50% 鎖利 + 留 50% 抓魚尾」是期望值最高的做法
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


def 算MA(data: list, period: int = 60) -> Optional[float]:
    """data: 日線（舊→新）算 MA"""
    if len(data) < period:
        return None
    closes = [d["close"] for d in data[-period:]]
    return sum(closes) / period


def 抓技術面(symbol: str) -> dict:
    """抓 60+ 天日線算 MA60 乖離"""
    try:
        from . import technical as technical_mod
    except ImportError:
        try:
            import technical as technical_mod
        except ImportError:
            return {}
    try:
        歷史, _ = technical_mod.取得每日股價(symbol, period="6mo")
        if not 歷史 or len(歷史) < 60:
            return {}
        data = list(reversed(歷史))  # 舊→新
        現價 = data[-1]["close"]
        ma60 = 算MA(data, 60)
        ma20 = 算MA(data, 20)
        ma60_bias = ((現價 / ma60 - 1) * 100) if ma60 else None
        ma20_bias = ((現價 / ma20 - 1) * 100) if ma20 else None
        return {
            "現價": round(現價, 2),
            "MA60": round(ma60, 2) if ma60 else None,
            "MA20": round(ma20, 2) if ma20 else None,
            "MA60_乖離_pct": round(ma60_bias, 2) if ma60_bias else None,
            "MA20_乖離_pct": round(ma20_bias, 2) if ma20_bias else None,
        }
    except Exception:
        return {}


def 抓法人連買(symbol: str, days: int = 5) -> dict:
    """
    抓近 N 日法人籌碼，看是否連買 3 天以上
    （只台股有資料 — 美股回 None）
    """
    if not (symbol.endswith(".TW") or symbol.endswith(".TWO")):
        return {"連買天數": None, "佔比_pct": None, "說明": "美股無法人資料"}

    try:
        from . import institutional_tracker
    except ImportError:
        try:
            import institutional_tracker
        except ImportError:
            return {"連買天數": None}

    sym_純 = symbol.replace(".TW", "").replace(".TWO", "")

    連買 = 0
    淨買_累計 = 0
    成交_累計 = 0

    today = datetime.now()
    for i in range(days):
        d = (today - timedelta(days=i)).strftime("%Y%m%d")
        try:
            r = institutional_tracker.抓今日法人籌碼(d)
            if not r or not r.get("資料"):
                continue
            stock_data = r["資料"].get(sym_純)
            if not stock_data:
                continue
            三大 = stock_data.get("三大法人合計", 0) or stock_data.get("外資", 0) or 0
            if 三大 > 0:
                連買 += 1
                淨買_累計 += 三大
                # 成交量（需另抓，這裡先用淨買代算）
                成交_累計 += stock_data.get("成交張數", abs(三大))
            else:
                break  # 中斷連買
        except Exception:
            continue

    佔比 = (淨買_累計 / 成交_累計 * 100) if 成交_累計 > 0 else None
    return {
        "連買天數": 連買,
        "淨買_累計張": 淨買_累計,
        "成交_累計張": 成交_累計,
        "佔比_pct": round(佔比, 2) if 佔比 else None,
    }


def 判定(symbol: str) -> dict:
    """
    主入口：判斷某 symbol 是否處於主升段
    Returns:
        {
            symbol, 狀態 (主升段 / 過熱 / 中性),
            是主升段: bool,
            建議下次停利_pct: int,
            說明
        }
    """
    技 = 抓技術面(symbol)
    籌 = 抓法人連買(symbol, days=5)

    if not 技:
        return {"symbol": symbol, "狀態": "無法判定", "說明": "技術面抓不到"}

    ma60_乖 = 技.get("MA60_乖離_pct")
    連買 = 籌.get("連買天數")
    佔比 = 籌.get("佔比_pct")

    # 是 ETF 嗎？影響乖離過熱閾值
    is_etf = symbol.startswith("00") or symbol == "0050.TW"
    過熱閾值 = 15 if is_etf else 30

    # 籌碼面確認主升段
    籌碼確認 = (連買 is not None and 連買 >= 3 and
              佔比 is not None and 佔比 > 10)

    # 技術面適合的乖離
    技術適合 = (ma60_乖 is not None and 10 <= ma60_乖 < 過熱閾值)

    if ma60_乖 is not None and ma60_乖 >= 過熱閾值:
        return {
            "symbol": symbol,
            "狀態": "🔴 過熱",
            "是主升段": False,
            "MA60_乖離": ma60_乖,
            "建議": f"乖離 {ma60_乖:.1f}% > {過熱閾值}%，均值回歸引力大",
            "建議下次停利_pct": 15,  # 維持原本 +15% 賣
            "說明": "短線過熱，達 +15% 直接賣 50%",
        }

    if 籌碼確認 and 技術適合:
        return {
            "symbol": symbol,
            "狀態": "🚀 主升段（雙確認）",
            "是主升段": True,
            "MA60_乖離": ma60_乖,
            "法人連買": 連買,
            "法人佔比": 佔比,
            "建議下次停利_pct": 25,  # 延後到 +25%
            "說明": (f"法人連 {連買} 天買 + 佔比 {佔比:.1f}% + "
                     f"乖離 {ma60_乖:.1f}% 健康 → 主升段，延後賣"),
        }

    if 技術適合 and not 籌碼確認:
        return {
            "symbol": symbol,
            "狀態": "🟡 弱主升段（技術 only）",
            "是主升段": False,
            "MA60_乖離": ma60_乖,
            "法人連買": 連買,
            "建議下次停利_pct": 20,  # 折衷到 +20%
            "說明": "技術面適合但籌碼面沒確認，折衷 +20%",
        }

    return {
        "symbol": symbol,
        "狀態": "📊 中性",
        "是主升段": False,
        "MA60_乖離": ma60_乖,
        "建議下次停利_pct": 15,
        "說明": "未進入主升段範圍",
    }


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
    print("主升段判定（Q3）")
    print("=" * 60)

    測試 = ["2330.TW", "0050.TW", "00910.TW", "00876.TW",
              "SATL", "NVDA"]
    for sym in 測試:
        r = 判定(sym)
        print(f"\n{sym}")
        print(f"  狀態: {r['狀態']}")
        if r.get('MA60_乖離') is not None:
            print(f"  MA60 乖離: {r['MA60_乖離']:+.2f}%")
        if r.get('法人連買') is not None:
            print(f"  法人連買: {r['法人連買']} 天 / 佔比 {r.get('法人佔比', '?')}%")
        print(f"  下次停利: +{r['建議下次停利_pct']}%")
        print(f"  說明: {r['說明']}")
