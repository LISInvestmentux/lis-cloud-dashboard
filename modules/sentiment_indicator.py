"""
散戶反指 (Phase 36.5) — Q4 對方 AI 校正版

用「融資餘額月變化 %」當散戶情緒反指
（台灣沒公開融資維持率官方資料，用變化率替代）

歷史閾值（對方 AI 提供，5 個事件驗證）：
  2018 中美貿易戰：-33.0% 長線底
  2020 COVID:    -36.8% 黑天鵝買點
  2021/5 本土疫情：-20.6%（10 天閃崩）
  2022 升息熊市：-43.3% 最終洗盤
  2024/8 套利股災：-14.7% V 型反轉

加分條件（散戶恐慌 = 買點）：
  ✅ 近 10 日急減 >10% 且大盤跌 >5% → Enjoy +15（短線閃崩）
  ✅ 距近半年高點減幅 >30% → Enjoy +25 ALL_IN（長線大底）

扣分條件（散戶瘋狂 = 賣訊號）：
  🔴 近 20 日大盤漲 <2% 但融資月增 >8% → Enjoy -15（主力倒貨）
  🔴 融資餘額單月暴增 >15% → Enjoy -10（絕對過熱）

資料源：TWSE 融資餘額（已存於 數據/cache/margin_balance/）
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = 專案根 / "數據" / "cache" / "margin_balance"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def 載入融資歷史(days: int = 180) -> list:
    """讀 cache 內最近 N 天的融資餘額"""
    if not CACHE_DIR.exists():
        return []
    cutoff = datetime.now() - timedelta(days=days)
    歷史 = []
    for f in CACHE_DIR.glob("*.json"):
        try:
            day = datetime.strptime(f.stem, "%Y-%m-%d")
            if day < cutoff:
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            value = d.get("融資餘額_千元") or d.get("融資餘額_億")
            if value is not None:
                # 規範化成「億元」
                if value > 1e6:  # 千元
                    value = value / 1e5
                歷史.append({
                    "date": f.stem,
                    "value_億": round(value, 1),
                })
        except Exception:
            continue
    歷史.sort(key=lambda r: r["date"])
    return 歷史


def 寫今日融資(value_億: float, date_str: str = None):
    """寫今日融資餘額到 cache（給歷史累積）"""
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    path = CACHE_DIR / f"{date_str}.json"
    path.write_text(
        json.dumps({"date": date_str, "融資餘額_億": round(value_億, 1)},
                   ensure_ascii=False),
        encoding="utf-8")


def 算融資變化 (歷史: list, 今日_億: float = None) -> dict:
    """
    算 3 個關鍵指標：
      1. 近 10 日變化 %
      2. 近 30 日變化 %
      3. 距近半年高點減幅 %
    """
    if not 歷史:
        return {"err": "無歷史"}
    今日 = 今日_億 if 今日_億 is not None else 歷史[-1].get("value_億")
    if 今日 is None:
        return {"err": "無今日值"}

    # 近 10 日對比
    十日_target = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    十日_data = [h for h in 歷史 if h["date"] <= 十日_target]
    十日_value = 十日_data[-1]["value_億"] if 十日_data else None
    十日_pct = ((今日 / 十日_value - 1) * 100) if 十日_value else None

    # 近 30 日對比
    三十日_target = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    三十日_data = [h for h in 歷史 if h["date"] <= 三十日_target]
    三十日_value = 三十日_data[-1]["value_億"] if 三十日_data else None
    三十日_pct = ((今日 / 三十日_value - 1) * 100) if 三十日_value else None

    # 近半年高點
    半年_target = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
    半年_data = [h for h in 歷史 if h["date"] >= 半年_target]
    半年高點 = max(h["value_億"] for h in 半年_data) if 半年_data else None
    高點減幅_pct = ((今日 / 半年高點 - 1) * 100) if 半年高點 else None

    return {
        "今日_億": 今日,
        "十日前_億": 十日_value,
        "十日變化_pct": round(十日_pct, 2) if 十日_pct else None,
        "三十日前_億": 三十日_value,
        "三十日變化_pct": round(三十日_pct, 2) if 三十日_pct else None,
        "半年高點_億": 半年高點,
        "高點減幅_pct": round(高點減幅_pct, 2) if 高點減幅_pct else None,
        "歷史天數": len(歷史),
    }


def 算大盤變化(技術mod=None) -> dict:
    """抓加權指數近 20 日變化（給散戶反指判定）"""
    try:
        if 技術mod is None:
            from . import technical as 技術mod
    except ImportError:
        try:
            import technical as 技術mod
        except ImportError:
            return {}
    try:
        歷史, _ = 技術mod.取得每日股價("^TWII", period="1mo")
        if not 歷史 or len(歷史) < 5:
            return {}
        # 歷史是新→舊
        today = 歷史[0]["close"]
        five_days = 歷史[4]["close"] if len(歷史) >= 5 else None
        twenty_days = 歷史[19]["close"] if len(歷史) >= 20 else None
        return {
            "今日": round(today, 2),
            "5日變化_pct": round((today / five_days - 1) * 100, 2)
                              if five_days else None,
            "20日變化_pct": round((today / twenty_days - 1) * 100, 2)
                              if twenty_days else None,
        }
    except Exception:
        return {}


def 散戶反指評分(融資_今日_億: float = None) -> dict:
    """
    主入口：依對方 AI 5 個歷史閾值打 Enjoy 加減分
    """
    歷史 = 載入融資歷史()
    if 融資_今日_億:
        寫今日融資(融資_今日_億)

    融資變化 = 算融資變化(歷史, 融資_今日_億)
    大盤變化 = 算大盤變化()

    加分 = 0
    扣分 = 0
    觸發 = []

    if "err" not in 融資變化:
        十日 = 融資變化.get("十日變化_pct")
        三十日 = 融資變化.get("三十日變化_pct")
        高點減 = 融資變化.get("高點減幅_pct")
        大盤5日 = 大盤變化.get("5日變化_pct")
        大盤20日 = 大盤變化.get("20日變化_pct")

        # 🟢 加分：散戶恐慌 = 買點
        if 十日 is not None and 大盤5日 is not None:
            if 十日 < -10 and 大盤5日 < -5:
                加分 += 15
                觸發.append({
                    "類型": "🟢 短線閃崩買點",
                    "說明": f"近 10 日融資 {十日:+.1f}% + 大盤 {大盤5日:+.1f}%",
                    "對比": "2021/5 本土疫情 / 2024/8 套利股災",
                    "Enjoy 影響": "+15",
                })

        if 高點減 is not None and 高點減 < -30:
            加分 += 25
            等級 = ("黑天鵝級 ALL_IN" if 高點減 < -40
                    else "歷史級買點")
            觸發.append({
                "類型": f"🟢 長線大底買點（{等級}）",
                "說明": f"距半年高點減 {高點減:+.1f}%",
                "對比": ("2020 COVID -36.8% / 2022 熊市底 -43.3%"),
                "Enjoy 影響": "+25",
            })

        # 🔴 扣分：散戶瘋狂 = 賣訊號
        if 三十日 is not None and 大盤20日 is not None:
            if 大盤20日 < 2 and 三十日 > 8:
                扣分 += 15
                觸發.append({
                    "類型": "🔴 主力倒貨警戒",
                    "說明": f"大盤 20 日只漲 {大盤20日:+.1f}%，融資 30 日卻 {三十日:+.1f}%",
                    "對比": "歷史過熱頂部前兆",
                    "Enjoy 影響": "-15",
                })

        if 三十日 is not None and 三十日 > 15:
            扣分 += 10
            觸發.append({
                "類型": "🔴 絕對過熱",
                "說明": f"融資 30 日暴增 {三十日:+.1f}%",
                "對比": "散戶開槓桿接刀",
                "Enjoy 影響": "-10",
            })

    淨影響 = 加分 - 扣分

    return {
        "融資": 融資變化,
        "大盤": 大盤變化,
        "加分": 加分,
        "扣分": 扣分,
        "淨Enjoy影響": 淨影響,
        "觸發": 觸發,
        "等級": ("✅ 散戶極度恐慌（買點）" if 淨影響 >= 20
                else "🟢 散戶偏恐慌" if 淨影響 >= 10
                else "📊 中性" if abs(淨影響) < 10
                else "⚠️ 散戶偏樂觀" if 淨影響 >= -10
                else "🔴 散戶過熱（賣訊號）"),
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
    print("散戶反指評分（Q4）")
    print("=" * 60)

    # 第一次跑：用 bottom_detector 抓今日融資
    try:
        from modules import bottom_detector
        margin = bottom_detector.抓融資餘額_TWSE()
        if margin:
            today_億 = (margin.get("融資餘額_千元", 0) / 1e5)
            print(f"\n今日融資餘額: {today_億:.1f} 億")
            寫今日融資(today_億)
        else:
            today_億 = None
            print("\n⚠️ 抓融資失敗")
    except Exception as e:
        print(f"\n⚠️ 抓融資失敗：{e}")
        today_億 = None

    r = 散戶反指評分(today_億)
    print(f"\n📊 融資變化:")
    f = r["融資"]
    if "err" not in f:
        print(f"  今日: {f.get('今日_億')} 億")
        if f.get('十日變化_pct') is not None:
            print(f"  10 日變化: {f['十日變化_pct']:+.1f}%")
        if f.get('三十日變化_pct') is not None:
            print(f"  30 日變化: {f['三十日變化_pct']:+.1f}%")
        if f.get('高點減幅_pct') is not None:
            print(f"  距半年高點: {f['高點減幅_pct']:+.1f}%")
        print(f"  歷史天數: {f.get('歷史天數', 0)}")
    else:
        print(f"  {f['err']}")

    print(f"\n📈 大盤變化:")
    d = r["大盤"]
    if d:
        print(f"  今日: {d.get('今日')}")
        if d.get('5日變化_pct') is not None:
            print(f"  5 日變化: {d['5日變化_pct']:+.2f}%")
        if d.get('20日變化_pct') is not None:
            print(f"  20 日變化: {d['20日變化_pct']:+.2f}%")

    print(f"\n🎯 散戶反指結果")
    print(f"  加分 +{r['加分']} / 扣分 -{r['扣分']} = {r['淨Enjoy影響']:+d}")
    print(f"  等級: {r['等級']}")
    if r["觸發"]:
        print(f"\n  觸發訊號:")
        for t in r["觸發"]:
            print(f"    {t['類型']}")
            print(f"      {t['說明']}")
            print(f"      對比: {t['對比']}")
            print(f"      Enjoy: {t['Enjoy 影響']}")
    else:
        print(f"\n  （無觸發 — 等更多歷史累積後重評）")
