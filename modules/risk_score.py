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
import json
from datetime import datetime, timedelta
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


def 算每日風控分(data: list, idx: int,
                  vix: Optional[float] = None,
                  法人連買天數: int = 0) -> Optional[float]:
    """
    data: 日線（舊→新）
    idx: 要算第幾天的風控分
    vix: 當日 VIX（可選 — 加降溫因子）
    法人連買天數: 可選

    新版（Phase 36.15 v2）：加 3 個降溫因子
      - VIX 配合度：VIX < 20 + 大盤漲 = 健康（風控降）
      - 連續性：慢漲 vs 爆衝
      - 廣度：用「過去 N 天日波動標準差」估
    """
    if idx < 30:
        return None

    歷史 = data[:idx + 1]
    今 = 歷史[-1]
    今價 = 今["close"]

    # === 過熱因子（加分）===
    # 1. RSI(14)
    rsi = 算RSI([d["close"] for d in 歷史[-15:]])
    if rsi is None:
        return None

    # 2. MA60 乖離
    ma_period = min(60, len(歷史))
    ma60 = sum(d["close"] for d in 歷史[-ma_period:]) / ma_period
    乖離 = (今價 / ma60 - 1) * 100

    # 3. 距期間高 %
    高_period = max(d.get("high", d["close"]) for d in 歷史[-ma_period:])
    距高 = (今價 / 高_period) * 100

    # 4. 量能比
    過去20vol = [d.get("volume", 0) for d in 歷史[-21:-1]]
    avg_vol = sum(過去20vol) / 20 if 過去20vol else 1
    今vol = 今.get("volume", 0)
    量比 = 今vol / avg_vol if avg_vol > 0 else 1
    量分 = min(20, 量比 * 8)

    # 過熱分
    過熱_rsi = max(0, rsi - 40) * 0.6
    過熱_乖離 = max(0, 乖離) * 1.2
    過熱_距高 = max(0, (距高 - 70) * 1.5)
    過熱_量能 = 量分

    過熱合計 = 過熱_rsi + 過熱_乖離 + 過熱_距高 + 過熱_量能

    # === 降溫因子（扣分）— 仿方舟加上 ===

    # 5. 慢漲 vs 爆衝：算過去 30 天日波動標準差
    # 慢慢漲（低波動）= 健康；爆衝（高波動）= 風險
    最近30 = 歷史[-30:]
    每日漲幅 = []
    for i in range(1, len(最近30)):
        chg = (最近30[i]["close"] / 最近30[i-1]["close"] - 1) * 100
        每日漲幅.append(chg)
    avg_chg = sum(每日漲幅) / len(每日漲幅) if 每日漲幅 else 0
    variance = sum((c - avg_chg) ** 2 for c in 每日漲幅) / len(每日漲幅) if 每日漲幅 else 0
    波動 = variance ** 0.5  # 標準差
    # 波動 < 1% = 健康慢漲，扣 8 分；> 2.5% = 爆衝，不扣
    降溫_穩定 = max(0, (1.5 - 波動) * 6)  # 波動 0.5% → 扣 6 分

    # 6. 連續性：過去 5 天累積漲幅 vs 過去 30 天累積
    # 短期漲多但長期溫和 = 過熱訊號；短期長期同步漲 = 健康
    if len(歷史) >= 30:
        漲5 = (歷史[-1]["close"] / 歷史[-6]["close"] - 1) * 100
        漲30 = (歷史[-1]["close"] / 歷史[-30]["close"] - 1) * 100
        if 漲30 > 0:
            短長比 = (漲5 * 6) / 漲30  # 5 天年化 vs 30 天年化
            # 短長比 ≈ 1 = 同步健康；> 2 = 短期爆衝
            降溫_連續性 = max(0, (2 - 短長比) * 5) if 短長比 > 0 else 5
        else:
            降溫_連續性 = 5
    else:
        降溫_連續性 = 0

    # 7. VIX 配合度（如有 VIX 資料）
    降溫_vix = 0
    if vix is not None:
        # VIX < 20 = 市場平靜（健康），扣 5-10 分
        # VIX > 25 = 恐慌（已警戒），不扣
        if vix < 15:
            降溫_vix = 10
        elif vix < 20:
            降溫_vix = 5

    # 8. 法人連買降溫
    降溫_法人 = min(8, 法人連買天數 * 2) if 法人連買天數 >= 3 else 0

    降溫合計 = 降溫_穩定 + 降溫_連續性 + 降溫_vix + 降溫_法人

    # 總分 = 過熱 - 降溫
    總分 = 過熱合計 - 降溫合計
    return round(max(0, min(100, 總分)), 1)


def 算K線歷史風控(symbol: str = "^TWII", period: str = "3mo",
                  每幾天標一點: int = 5) -> dict:
    """
    主入口：抓 K 線 + 算每幾天的風控分（含 VIX + 法人連買降溫）
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
        data = list(reversed(h))

        # 同步抓 VIX 歷史
        vix_data = {}
        try:
            vix_h, _ = technical.取得每日股價("^VIX", period=period)
            if vix_h:
                vix_data = {v["date"][:10]: v["close"]
                            for v in vix_h}
        except Exception:
            pass

        # 抓法人連買（只能算「當下」不能算歷史，所以只給最後 1 點）
        當前法人連買 = 0
        try:
            from . import institutional_tracker
            from datetime import timedelta as _td
            連 = 0
            for i in range(5):
                d = (datetime.now() - _td(days=i)).strftime("%Y%m%d")
                r = institutional_tracker.抓今日法人籌碼(d)
                if r and r.get("資料"):
                    # 看大盤外資（簡化用 2330 的外資）
                    stock = r["資料"].get("2330")
                    if stock and stock.get("外資", 0) > 0:
                        連 += 1
                    else:
                        break
            當前法人連買 = 連
        except Exception:
            pass

        marks = []
        for i in range(30, len(data), 每幾天標一點):
            d = data[i]
            date_str = d["date"][:10]
            vix_v = vix_data.get(date_str)
            # 歷史不知道法人連買，只給 0
            score = 算每日風控分(data, i, vix=vix_v, 法人連買天數=0)
            if score is None:
                continue
            等級 = ("過熱" if score >= 70
                    else "警戒" if score >= 50
                    else "健康")
            marks.append({
                "date": date_str,
                "close": d["close"],
                "score": score,
                "等級": 等級,
                "vix": vix_v,
            })

        # 最後一天加 VIX + 法人連買
        last_idx = len(data) - 1
        last_date = data[last_idx]["date"][:10]
        last_vix = vix_data.get(last_date)
        last_score = 算每日風控分(data, last_idx,
                                    vix=last_vix,
                                    法人連買天數=當前法人連買)
        if last_score is not None:
            等級 = ("過熱" if last_score >= 70
                    else "警戒" if last_score >= 50
                    else "健康")
            last_mark = {
                "date": last_date,
                "close": data[last_idx]["close"],
                "score": last_score,
                "等級": 等級,
                "vix": last_vix,
                "法人連買": 當前法人連買,
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
