"""
右側追回紀律（Phase 36.3）— 賣飛了怎麼救

對方 AI 專業驗證後的設計：
  Strategy D 賣 50% 後，若強勢突破則追回

追回條件（4 項全部滿足）：
  1. MA20 突破（價 > MA20 + 連續 2 天）
  2. 順勢分 ≥ 85（強勢確認）
  3. RSI 60-75（剛發動有肉，不是末升段）
  4. 量能 ≥ 5 日均量 × 1.8 倍（法人實質買盤）

追回後專屬停損 SOP（比一般部位嚴格）：
  條件 A: 跌破「爆量突破那天的最低點」→ 立刻砍
  條件 B: 連續 2 天收盤 < MA20 → 直接出場
  容錯率: 1 × ATR（比一般 2.5 × ATR 緊得多）

追回股數：賣出股數 × 50%（追一半即可）

依賴：
  - yfinance（抓 30 天日線算 MA20/RSI/量能）
  - portfolio.json realized_history 找賣出記錄
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


def 算MA(data: list, period: int = 20) -> Optional[float]:
    """data: 日線清單（舊→新），算 MA"""
    if len(data) < period:
        return None
    closes = [d["close"] for d in data[-period:]]
    return sum(closes) / period


def 算RSI(data: list, period: int = 14) -> Optional[float]:
    """data: 日線清單（舊→新），算 RSI"""
    if len(data) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(data)):
        chg = data[i]["close"] - data[i-1]["close"]
        gains.append(max(chg, 0))
        losses.append(max(-chg, 0))
    avg_g = sum(gains[-period:]) / period
    avg_l = sum(losses[-period:]) / period
    if avg_l == 0:
        return 100
    rs = avg_g / avg_l
    return round(100 - 100 / (1 + rs), 2)


def 算量能比(data: list, period: int = 5) -> Optional[float]:
    """data: 日線（舊→新），最新日 vol vs 過去 5 天均量"""
    if len(data) < period + 1:
        return None
    today_vol = data[-1].get("volume", 0)
    past_vols = [d.get("volume", 0) for d in data[-period-1:-1]]
    avg = sum(past_vols) / period if past_vols else 0
    if avg == 0:
        return None
    return round(today_vol / avg, 2)


def 抓技術面(symbol: str) -> dict:
    """抓所需所有技術指標"""
    try:
        from . import technical as technical_mod
    except ImportError:
        try:
            import technical as technical_mod
        except ImportError:
            return {}

    try:
        歷史, _ = technical_mod.取得每日股價(symbol, period="2mo")
        if not 歷史 or len(歷史) < 21:
            return {}

        # 歷史是新→舊，反轉成舊→新
        data = list(reversed(歷史))
        現價 = data[-1]["close"]
        昨收 = data[-2]["close"] if len(data) >= 2 else 現價

        ma20 = 算MA(data, 20)
        ma60 = 算MA(data, 60) if len(data) >= 60 else None
        rsi = 算RSI(data, 14)
        vol_ratio = 算量能比(data, 5)

        # 是否連 2 天 close > MA20
        ma20_pre = 算MA(data[:-1], 20) if len(data) >= 21 else None
        連續突破 = (現價 > ma20 if ma20 else False) and \
                     (data[-2]["close"] > ma20_pre if (ma20_pre and len(data) >= 2) else False)

        return {
            "現價": round(現價, 2),
            "MA20": round(ma20, 2) if ma20 else None,
            "MA60": round(ma60, 2) if ma60 else None,
            "RSI14": rsi,
            "量能比": vol_ratio,
            "連2日突破MA20": 連續突破,
            "data": data,  # 保留給後續用
        }
    except Exception:
        return {}


def 追回判定(symbol: str, 賣出價: float = None,
              已賣股數: int = None) -> dict:
    """
    主入口：判斷某 symbol 是否符合右側追回條件

    Returns:
        {
            可追回: bool,
            條件滿足: dict (4 項條件各自結果),
            建議股數: int (賣出 × 0.5),
            進場價: float (現價),
            追回後停損: dict (條件 A + B),
            說明: str,
        }
    """
    技 = 抓技術面(symbol)
    if not 技:
        return {"可追回": False, "說明": "技術面抓不到"}

    現價 = 技["現價"]
    MA20 = 技.get("MA20")
    RSI = 技.get("RSI14")
    量比 = 技.get("量能比")
    連2 = 技.get("連2日突破MA20", False)

    # 4 項條件
    條件 = {
        "MA20連2日突破": 連2,
        "RSI_60_75": (RSI is not None and 60 <= RSI <= 75),
        "量能_1.8x": (量比 is not None and 量比 >= 1.8),
        "順勢分_85": None,  # 沒接 positional_state 時 None
    }

    # 試讀順勢分
    state_path = 專案根 / "數據" / "positional_state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            details = state.get("details", {}).get(symbol, {})
            順勢分 = details.get("順勢分") or details.get("trend_score")
            if 順勢分:
                條件["順勢分_85"] = 順勢分 >= 85
        except Exception:
            pass

    # 沒順勢分時：只要其他 3 個滿足也可以
    必要_count = sum(1 for v in 條件.values() if v is True)
    需要 = 3 if 條件["順勢分_85"] is None else 4

    可追回 = 必要_count >= 需要

    # 算追回後專屬停損
    停損SOP = None
    if 可追回:
        # 找「爆量突破日」的最低點（過去 5 天最高量那天）
        data = 技.get("data", [])
        if len(data) >= 5:
            最近5 = data[-5:]
            爆量日 = max(最近5, key=lambda d: d.get("volume", 0))
            爆量日_low = 爆量日.get("low", 爆量日["close"])
            停損SOP = {
                "條件A": f"跌破爆量日最低 ${爆量日_low:.2f} 立刻砍",
                "條件B": f"連 2 天收盤 < MA20 (${MA20:.2f}) 出場",
                "爆量日_low": round(爆量日_low, 2),
                "MA20": round(MA20, 2),
                "緊度": "1×ATR（比一般 2.5×ATR 嚴）",
            }

    建議股數 = max(1, int((已賣股數 or 0) * 0.5)) if 已賣股數 else None

    return {
        "symbol": symbol,
        "可追回": 可追回,
        "條件": 條件,
        "滿足數": f"{必要_count}/{需要}",
        "技術": {
            "現價": 現價,
            "MA20": MA20,
            "RSI": RSI,
            "量能比": 量比,
            "連2日突破": 連2,
        },
        "進場價": 現價,
        "建議股數": 建議股數,
        "追回後停損": 停損SOP,
        "說明": (f"可追回 {建議股數} 股 @ ${現價}（追一半）"
                if 可追回 and 建議股數
                else "條件不足，繼續等"),
    }


def 掃描所有賣出後追回機會(realized_history: list) -> list:
    """
    對 realized_history 內所有已賣出標的，掃描有沒有追回機會
    回傳：符合條件的清單
    """
    結果 = []
    # 取最近 30 天賣出的
    cutoff = datetime.now() - timedelta(days=30)
    for r in realized_history:
        try:
            d = datetime.strptime(r.get("date", ""), "%Y-%m-%d")
            if d < cutoff:
                continue
        except Exception:
            continue

        sym = r.get("symbol")
        if not sym:
            continue

        判定 = 追回判定(sym,
                       賣出價=r.get("sell_price"),
                       已賣股數=r.get("shares"))
        if 判定.get("可追回"):
            判定["賣出日"] = r.get("date")
            判定["賣出價"] = r.get("sell_price")
            結果.append(判定)
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
    print("右側追回紀律測試")
    print("=" * 60)

    # 測試 SATL（你 5/14 賣 75 股 @8.43）
    print("\n[SATL] 5/14 賣 75 股 @8.43，看現在能不能追回...")
    r = 追回判定("SATL", 賣出價=8.43, 已賣股數=75)
    print(f"  滿足: {r['滿足數']}")
    for 條件, 結果 in r["條件"].items():
        符 = "✅" if 結果 is True else ("⚠️ N/A" if 結果 is None else "❌")
        print(f"    {符} {條件}")
    技 = r.get("技術", {})
    print(f"  技術：現價 ${技.get('現價')} / MA20 ${技.get('MA20')} / "
          f"RSI {技.get('RSI')} / 量比 {技.get('量能比')}x / "
          f"連2日 {技.get('連2日突破')}")
    print(f"  → {r['說明']}")
    if r.get("追回後停損"):
        s = r["追回後停損"]
        print(f"  追回後停損 SOP:")
        print(f"    條件A: {s['條件A']}")
        print(f"    條件B: {s['條件B']}")

    # 掃所有賣出歷史
    print("\n[掃描所有賣出後追回機會]")
    import json
    try:
        cfg = json.loads(
            (專案根 / "API" / "portfolio.json").read_text(encoding="utf-8"))
        機會 = 掃描所有賣出後追回機會(cfg.get("realized_history", []))
        if not 機會:
            print("  目前無符合追回條件的標的")
        for r in 機會:
            print(f"  ✅ {r['symbol']} 賣於 {r['賣出日']}，現在可追回 {r['建議股數']} 股")
    except Exception as e:
        print(f"  讀 portfolio 失敗：{e}")
