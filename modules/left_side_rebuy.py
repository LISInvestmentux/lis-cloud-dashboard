"""
左側買回 (Phase 36.8) — Sylvie 教學的「波段股」操作

對方 AI 教「右側追回」（賣後突破再加）
Sylvie 教「左側買回」（賣後跌回再買）

兩個都是 LIS 該有的維度。

Sylvie SATL 案例：
  $6.X (低) → 買 → $8.X (高) → 賣
  → 跌回 $6.X → 再買 → $7.X 賣
  → 跌回 → 再買 → ...（3 輪了）

判定條件（全部滿足）：
  1. 標的被標記為「波段股」（在 portfolio.json swing_stocks 清單）
  2. 賣出後 14 天內
  3. 現價 ≤ 賣出價 × 0.85（跌 15% 內回頭）
  4. RSI < 35（超賣）
  5. 量能放大（接刀方確認）

買回後專屬停損：
  - 跌破買回價 -5% → 立刻砍
  - 連 2 天收盤 < MA20 → 出
  - 不適用 ATR 吊燈（容錯率小）

預設買回股數：原賣股數 × 50%
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


def 算技術(symbol: str) -> dict:
    """抓 RSI / MA20 / 量能比"""
    try:
        from . import technical
    except ImportError:
        try:
            import technical
        except ImportError:
            return {}
    try:
        歷史, _ = technical.取得每日股價(symbol, period="1mo")
        if not 歷史 or len(歷史) < 14:
            return {}
        data = list(reversed(歷史))

        # RSI 14
        gains, losses = [], []
        for i in range(1, len(data)):
            chg = data[i]["close"] - data[i-1]["close"]
            gains.append(max(chg, 0))
            losses.append(max(-chg, 0))
        avg_g = sum(gains[-14:]) / 14
        avg_l = sum(losses[-14:]) / 14
        rsi = 100 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)

        # MA20
        ma20 = sum(d["close"] for d in data[-20:]) / 20 if len(data) >= 20 else None

        # 量能比 5 日
        today_vol = data[-1].get("volume", 0)
        past_vols = [d.get("volume", 0) for d in data[-6:-1]]
        avg_vol = sum(past_vols) / 5 if past_vols else 0
        vol_ratio = today_vol / avg_vol if avg_vol > 0 else None

        return {
            "現價": round(data[-1]["close"], 2),
            "RSI": round(rsi, 2),
            "MA20": round(ma20, 2) if ma20 else None,
            "量能比": round(vol_ratio, 2) if vol_ratio else None,
        }
    except Exception:
        return {}


def 找波段股清單(cfg: dict) -> list:
    """從 portfolio.json 讀 swing_stocks 清單"""
    return cfg.get("swing_stocks", [])


def 買回判定(symbol: str, 賣出價: float = None,
              已賣股數: int = None, 賣出日: str = None) -> dict:
    """
    判定某 symbol 是否符合左側買回條件
    """
    技 = 算技術(symbol)
    if not 技:
        return {"可買回": False, "說明": "技術面抓不到"}

    現價 = 技["現價"]
    RSI = 技["RSI"]
    MA20 = 技["MA20"]
    量比 = 技["量能比"]

    條件 = {}

    # 1. 賣出後 14 天內
    if 賣出日:
        try:
            d = datetime.strptime(賣出日[:10], "%Y-%m-%d")
            天數 = (datetime.now() - d).days
            條件["賣出 14 天內"] = 天數 <= 14
        except Exception:
            條件["賣出 14 天內"] = None

    # 2. 跌回 -15% 內
    if 賣出價:
        跌幅 = (現價 / 賣出價 - 1) * 100
        條件["跌回 -15% 內"] = -25 < 跌幅 < -5  # 不能跌太多也不能沒跌
    else:
        跌幅 = None

    # 3. RSI < 35（超賣）
    條件["RSI 超賣"] = RSI is not None and RSI < 35

    # 4. 量能放大
    條件["量能放大"] = 量比 is not None and 量比 >= 1.3

    # 5. 仍在 MA20 之上 = 不要追墜落刀（健康跌不是崩盤）
    if MA20:
        條件["MA20 之上 (非崩盤)"] = 現價 >= MA20 * 0.95

    滿足 = sum(1 for v in 條件.values() if v is True)
    需要 = sum(1 for v in 條件.values() if v is not None)
    可買回 = 滿足 == 需要

    建議股數 = max(1, int((已賣股數 or 0) * 0.5)) if 已賣股數 else None

    return {
        "symbol": symbol,
        "可買回": 可買回,
        "條件": 條件,
        "滿足": f"{滿足}/{需要}",
        "技術": 技,
        "跌幅_pct": round(跌幅, 2) if 跌幅 else None,
        "建議股數": 建議股數,
        "買回後停損": (f"跌破 ${現價 * 0.95:.2f} 立刻砍 / 或連 2 天 close < MA20"
                       if 可買回 else None),
        "說明": (f"✅ 可買回 {建議股數} 股 @ ${現價}（左側買回）"
                 if 可買回 else "條件不足，繼續等"),
    }


def 掃描所有買回機會(cfg: dict = None) -> list:
    """掃 portfolio.json realized_history 內近 14 天的賣出，找可買回的"""
    if cfg is None:
        cfg = json.loads(
            (專案根 / "API" / "portfolio.json").read_text(encoding="utf-8"))

    波段清單 = set(找波段股清單(cfg))
    cutoff = datetime.now() - timedelta(days=14)

    結果 = []
    for r in cfg.get("realized_history", []):
        sym = r.get("symbol")
        if not sym:
            continue
        # 標記為「波段股」才掃（避免長期持有股誤判）
        # 若沒設清單，default 對所有美股小型開放
        if 波段清單 and sym not in 波段清單:
            continue

        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d")
            if d < cutoff:
                continue
        except Exception:
            continue

        判 = 買回判定(sym,
                     賣出價=r.get("sell_price"),
                     已賣股數=r.get("shares"),
                     賣出日=r.get("date"))
        if 判.get("可買回"):
            判["賣出日"] = r.get("date")
            判["賣出價"] = r.get("sell_price")
            結果.append(判)
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
    print("左側買回判定（SATL 教學）")
    print("=" * 60)

    # 測試 SATL（你 5/15 賣 37 股 @ 8.60）
    print("\n[SATL] 5/15 賣 37 股 @ $8.60，看現在能不能買回...")
    r = 買回判定("SATL", 賣出價=8.60, 已賣股數=37, 賣出日="2026-05-15")
    print(f"  滿足: {r['滿足']}")
    for 條件, 結果 in r["條件"].items():
        符 = "✅" if 結果 is True else ("⚠️ N/A" if 結果 is None else "❌")
        print(f"    {符} {條件}")
    技 = r["技術"]
    if 技:
        print(f"  技術：現價 ${技.get('現價')} / "
              f"RSI {技.get('RSI')} / MA20 ${技.get('MA20')} / "
              f"量比 {技.get('量能比')}x")
    if r.get('跌幅_pct') is not None:
        print(f"  vs 賣出 8.60: {r['跌幅_pct']:+.2f}%")
    print(f"  → {r['說明']}")

    # 全掃
    print("\n[全掃描賣後買回機會]")
    機會 = 掃描所有買回機會()
    if not 機會:
        print("  目前無符合左側買回的標的（多半 sell 後沒跌回）")
    for r in 機會:
        print(f"  ✅ {r['symbol']} 賣 {r['賣出日']} → 可買回 {r['建議股數']} 股")
