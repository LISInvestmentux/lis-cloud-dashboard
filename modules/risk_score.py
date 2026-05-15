"""
LIS 多因子風控分 (Phase 36.15) — 仿方舟「風控變化圖」

分數越高 = 越過熱 = 越該減碼
分數越低 = 越健康 = 越該加碼

4 維度合成（0-100）：
  1. RSI(14)  — 動能過熱
  2. MA60 乖離 — 技術過熱
  3. 距 60 天高 % — 位階過熱
  4. 量能比 — 量能爆衝

公式：
  風控分 = (RSI 加權 + 乖離加權 + 距高加權 + 量能加權) clamp 0-100

歷史對應：
  方舟 60.5 → 65.2 → 68.2 → 84.4 是漸進升高（5/4 → 5/15）
  LIS 跟這樣算
"""
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


def 算RSI(closes: list, period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        chg = closes[i] - closes[i-1]
        gains.append(max(chg, 0))
        losses.append(max(-chg, 0))
    avg_g = sum(gains[-period:]) / period
    avg_l = sum(losses[-period:]) / period
    if avg_l == 0:
        return 100
    rs = avg_g / avg_l
    return round(100 - 100 / (1 + rs), 2)


def 算每日風控分(data: list, idx: int) -> Optional[float]:
    """
    data: 日線（舊→新）
    idx: 要算第幾天的風控分
    """
    if idx < 30:
        return None  # 樣本不夠

    歷史 = data[:idx + 1]
    今 = 歷史[-1]
    今價 = 今["close"]

    # 1. RSI(14)
    rsi = 算RSI([d["close"] for d in 歷史[-15:]])
    if rsi is None:
        return None

    # 2. MA60 乖離（樣本足夠才算）
    ma_period = min(60, len(歷史))
    ma60 = sum(d["close"] for d in 歷史[-ma_period:]) / ma_period
    乖離 = (今價 / ma60 - 1) * 100  # 可正可負

    # 3. 距期間高 %
    高_period = max(d.get("high", d["close"]) for d in 歷史[-ma_period:])
    距高 = (今價 / 高_period) * 100  # 99 → 接近高點，70 → 已修正 30%

    # 4. 量能比 vs 過去 20 天均量
    過去20vol = [d.get("volume", 0) for d in 歷史[-21:-1]]
    avg_vol = sum(過去20vol) / 20 if 過去20vol else 1
    今vol = 今.get("volume", 0)
    量比 = 今vol / avg_vol if avg_vol > 0 else 1
    量分 = min(20, 量比 * 8)  # 量比 2.5x → 20 分

    # 合成（各佔權重）
    rsi_score = max(0, rsi - 40) * 0.6  # RSI > 40 開始算（0-36 分）
    乖離_score = max(0, 乖離) * 1.2  # 正乖離才算（0-24 分典型）
    距高_score = max(0, (距高 - 70) * 1.5)  # 距高 70%+ 開始算（0-45 分）
    量能_score = 量分

    總分 = rsi_score + 乖離_score + 距高_score + 量能_score
    return round(max(0, min(100, 總分)), 1)


def 算K線歷史風控(symbol: str = "^TWII", period: str = "3mo",
                  每幾天標一點: int = 5) -> dict:
    """
    主入口：抓 K 線 + 算每幾天的風控分

    Returns:
        {
          "data": [{date, open, high, low, close, volume}, ...],
          "marks": [{date, close, score, 等級}, ...]
        }
    """
    try:
        from . import technical
    except ImportError:
        try:
            import technical
        except ImportError:
            return {"data": [], "marks": []}

    try:
        h, _ = technical.取得每日股價(symbol, period=period)
        if not h:
            return {"data": [], "marks": []}
        data = list(reversed(h))  # 舊→新

        marks = []
        for i in range(30, len(data), 每幾天標一點):
            score = 算每日風控分(data, i)
            if score is None:
                continue
            d = data[i]
            等級 = ("過熱" if score >= 70
                    else "警戒" if score >= 50
                    else "健康")
            marks.append({
                "date": d["date"][:10],
                "close": d["close"],
                "score": score,
                "等級": 等級,
            })

        # 最後一天一定要標
        last_score = 算每日風控分(data, len(data) - 1)
        if last_score is not None:
            等級 = ("過熱" if last_score >= 70
                    else "警戒" if last_score >= 50
                    else "健康")
            last_mark = {
                "date": data[-1]["date"][:10],
                "close": data[-1]["close"],
                "score": last_score,
                "等級": 等級,
            }
            if not marks or marks[-1]["date"] != last_mark["date"]:
                marks.append(last_mark)

        return {"data": data, "marks": marks}
    except Exception as e:
        return {"data": [], "marks": [], "error": str(e)}


def 當前風控(symbol: str = "^TWII") -> dict:
    """快速查當前風控分 + 解讀"""
    r = 算K線歷史風控(symbol, period="3mo")
    if not r["marks"]:
        return {"score": None, "等級": "?", "說明": "資料不足"}
    latest = r["marks"][-1]
    score = latest["score"]
    等級 = latest["等級"]

    說明對照 = {
        "過熱": "減碼 / 拉高閒錢比 / 不追高",
        "警戒": "停止加碼 / 觀察",
        "健康": "可正常依訊號操作",
    }
    return {
        "score": score,
        "等級": 等級,
        "說明": 說明對照[等級],
        "date": latest["date"],
        "close": latest["close"],
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
    print("LIS 多因子風控分（仿方舟）")
    print("=" * 60)

    r = 算K線歷史風控("^TWII", period="3mo", 每幾天標一點=7)
    print(f"\n抓 K 線: {len(r['data'])} 天")
    print(f"風控標記點: {len(r['marks'])} 個\n")

    print(f"{'日期':12s} {'收盤':>10s} {'風控':>6s} {'等級':>6s}")
    print("-" * 40)
    for m in r["marks"]:
        色標 = ("🔴" if m["等級"] == "過熱"
                else "🟡" if m["等級"] == "警戒"
                else "🟢")
        print(f'{m["date"]:12s} {m["close"]:>10,.2f} {m["score"]:>6.1f} {色標} {m["等級"]}')

    現 = 當前風控()
    if 現.get('score') is not None:
        print(f"\n當前風控: {現['score']:.1f} {現['等級']}")
        print(f"  → {現['說明']}")
    else:
        print(f"\n當前風控: 資料不足")
