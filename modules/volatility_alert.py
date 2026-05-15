"""
震盪預警（Phase 33.2）

監測 F&G 連續 N 天極端值 → 預警反轉風險。

設計理念：
  - F&G 連續 5+ 天 ≥ 70（持續貪婪） → 預警「修正將至」
  - F&G 連續 5+ 天 ≤ 25（持續恐慌） → 預警「反彈將至」
  - 配合 VIX 連續 N 天低/高 → 雙重警報

  歷史經驗：
    - 2021/02 連續 12 天 ≥ 80 → 隨後 Q1 修正 7%
    - 2020/03 連續 10 天 ≤ 20 → 反彈起點

資料來源：fg_history.json（每天 8AM 寫入）

依賴：fear_greed.py
"""
import json
from datetime import datetime, timedelta
from pathlib import Path


專案根 = Path(__file__).resolve().parent.parent.parent
HISTORY_PATH = 專案根 / "數據" / "cache" / "fg_history.json"


def 載入歷史() -> list:
    if not HISTORY_PATH.exists():
        return []
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def 寫入歷史(score: float, vix: float = None,
              date_str: str = None) -> None:
    """每天 8AM 跑：把今天的 F&G + VIX 存進歷史"""
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    歷史 = 載入歷史()
    今天 = date_str or datetime.now().strftime("%Y-%m-%d")

    # 同一天只記一次（覆寫）
    歷史 = [h for h in 歷史 if h.get("date") != 今天]
    歷史.append({
        "date": 今天,
        "fg": round(score, 1) if score is not None else None,
        "vix": round(vix, 2) if vix is not None else None,
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    })

    # 只保留最近 90 天
    歷史.sort(key=lambda h: h.get("date", ""))
    歷史 = 歷史[-90:]
    HISTORY_PATH.write_text(
        json.dumps(歷史, ensure_ascii=False, indent=2),
        encoding="utf-8")


def 查連續(threshold: float, direction: str = "above",
            field: str = "fg") -> dict:
    """
    查最近連續幾天 fg/vix 在 threshold 之上/之下。

    Args:
        threshold: 門檻
        direction: "above" / "below"
        field: "fg" / "vix"

    Returns:
        {
            連續天數: int,
            起點: "YYYY-MM-DD",
            目前值: float,
            極值: float,  # 該期間的極值
            極值日: str,
        }
    """
    歷史 = 載入歷史()
    if not 歷史:
        return {"連續天數": 0, "起點": None, "目前值": None,
                "極值": None, "極值日": None}

    歷史.sort(key=lambda h: h.get("date", ""), reverse=True)
    連續 = []
    for h in 歷史:
        v = h.get(field)
        if v is None:
            break
        命中 = (v >= threshold) if direction == "above" else (v <= threshold)
        if 命中:
            連續.append(h)
        else:
            break

    if not 連續:
        return {"連續天數": 0, "起點": None, "目前值": None,
                "極值": None, "極值日": None}

    if direction == "above":
        極 = max(連續, key=lambda h: h[field])
    else:
        極 = min(連續, key=lambda h: h[field])

    return {
        "連續天數": len(連續),
        "起點": 連續[-1]["date"],
        "目前值": 連續[0][field],
        "極值": 極[field],
        "極值日": 極["date"],
    }


def 震盪預警判定() -> dict:
    """
    主入口：判斷現在是否該震盪預警。

    觸發條件：
      🟢 持續貪婪：F&G 連 5+ 天 ≥ 70 → 修正將至
      🔴 持續恐慌：F&G 連 5+ 天 ≤ 25 → 反彈將至
      ⚠️ VIX 沉睡：VIX 連 10+ 天 < 13 → 震盪可能突然爆發
    """
    警報 = []

    # F&G 持續貪婪
    fg_high = 查連續(70, "above", "fg")
    if fg_high["連續天數"] >= 5:
        警報.append({
            "等級": "高度警戒" if fg_high["連續天數"] >= 10 else "預警",
            "類型": "🔥 持續貪婪",
            "色": "bear" if fg_high["連續天數"] >= 10 else "wait",
            "訊息": (f"F&G 連續 {fg_high['連續天數']} 天 ≥ 70 "
                     f"(極值 {fg_high['極值']} on {fg_high['極值日']})"),
            "建議": (f"減碼 / 拉高閒錢比 / 停利優先" if fg_high["連續天數"] >= 10
                     else f"留意過熱 / 別追高"),
            "連續天數": fg_high["連續天數"],
            "起點": fg_high["起點"],
        })

    # F&G 持續恐慌
    fg_low = 查連續(25, "below", "fg")
    if fg_low["連續天數"] >= 5:
        警報.append({
            "等級": "歷史機會" if fg_low["連續天數"] >= 10 else "進場機會",
            "類型": "💀 持續恐慌",
            "色": "bull",
            "訊息": (f"F&G 連續 {fg_low['連續天數']} 天 ≤ 25 "
                     f"(極值 {fg_low['極值']} on {fg_low['極值日']})"),
            "建議": (f"歷史級進場 / 動用緊急資金加碼" if fg_low["連續天數"] >= 10
                     else f"分批進場 / 加倉訊號"),
            "連續天數": fg_low["連續天數"],
            "起點": fg_low["起點"],
        })

    # VIX 沉睡
    vix_sleep = 查連續(13, "below", "vix")
    if vix_sleep["連續天數"] >= 10:
        警報.append({
            "等級": "震盪警戒",
            "類型": "😴 VIX 沉睡",
            "色": "wait",
            "訊息": (f"VIX 連續 {vix_sleep['連續天數']} 天 < 13 "
                     f"(最低 {vix_sleep['極值']} on {vix_sleep['極值日']})"),
            "建議": "市場過於平靜，留意黑天鵝突發",
            "連續天數": vix_sleep["連續天數"],
            "起點": vix_sleep["起點"],
        })

    return {
        "警報": 警報,
        "有警報": len(警報) > 0,
        "最高等級": _最高等級(警報),
    }


def _最高等級(警報: list) -> str:
    if not 警報:
        return "正常"
    等級_排序 = {"高度警戒": 0, "歷史機會": 0, "預警": 1,
                  "進場機會": 1, "震盪警戒": 2}
    sorted_alerts = sorted(警報,
                            key=lambda a: 等級_排序.get(a["等級"], 9))
    return sorted_alerts[0]["等級"]


def 每日記錄() -> dict:
    """每天 8AM 跑：抓 F&G + VIX，寫入歷史，回傳震盪預警"""
    try:
        from . import fear_greed, bottom_detector
    except ImportError:
        import fear_greed
        import bottom_detector

    fg = None
    try:
        fg_data = fear_greed.取得恐慌貪婪指數()
        fg = fg_data.get("score") if fg_data else None
    except Exception:
        pass

    vix = None
    try:
        sop = bottom_detector.即時底部判定()
        vix = (sop.get("原始資料") or {}).get("VIX")
    except Exception:
        pass

    if fg is not None or vix is not None:
        寫入歷史(fg, vix)

    return {
        "今日F&G": fg,
        "今日VIX": vix,
        "震盪預警": 震盪預警判定(),
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
    print("震盪預警系統")
    print("=" * 60)

    # 1. 每日記錄
    print("\n[1] 抓今日 F&G + VIX，寫入歷史...")
    結果 = 每日記錄()
    print(f"   F&G {結果['今日F&G']} / VIX {結果['今日VIX']}")

    # 2. 印歷史
    歷史 = 載入歷史()
    print(f"\n[2] 歷史紀錄：共 {len(歷史)} 天")
    for h in 歷史[-7:]:
        print(f"   {h['date']}: F&G {h.get('fg')} / VIX {h.get('vix')}")

    # 3. 警報
    預警 = 結果["震盪預警"]
    print(f"\n[3] 震盪預警：{預警['最高等級']}")
    if 預警["有警報"]:
        for a in 預警["警報"]:
            print(f"   [{a['等級']}] {a['類型']}")
            print(f"      {a['訊息']}")
            print(f"      → {a['建議']}")
    else:
        print("   無警報（紀律觀察）")
