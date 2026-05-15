"""
社群共識訊號（Phase 32.7）

整合多來源持股，找跨來源共識：
  - 你（portfolio.json）
  - Sylvie 太太（數據/sylvie_portfolio.json）
  - Enjoy 老哥（hardcoded 從 5/14 截圖）

共識越強 = 訊號越可信
"""
import json
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent

# Enjoy 5/14 截圖持股（每次有新資訊更新）
ENJOY持股 = [
    {"symbol": "IREN", "name": "Iris Energy"},
    {"symbol": "NVDA", "name": "NVIDIA"},
    {"symbol": "CRWV", "name": "CoreWeave"},
    {"symbol": "TSLA", "name": "Tesla"},
    {"symbol": "SWMR", "name": "Sionna"},
    {"symbol": "CRCL", "name": "Circle"},
]


def 載入你的持股() -> list[dict]:
    p = 專案根 / "API" / "portfolio.json"
    cfg = json.loads(p.read_text(encoding="utf-8"))
    return [pos for pos in cfg.get("current_positions", [])
            if pos.get("symbol") != "AGGREGATE"]


def 載入Sylvie持股() -> dict:
    p = 專案根 / "數據" / "sylvie_portfolio.json"
    if not p.exists():
        return {"持股": [], "DCA帳戶高報酬": {}, "已實現": []}
    return json.loads(p.read_text(encoding="utf-8"))


def 算共識(我的: list, sylvie: list, enjoy: list) -> dict:
    """
    回傳：
      {
        "你+Sylvie+Enjoy": [],  # 三方共識（最強）
        "你+Sylvie": [],         # 你和太太
        "你+Enjoy": [],          # 你和老哥
        "Sylvie+Enjoy": [],      # 太太和老哥（你沒有，可考慮）
        "你獨有": [],
        "Sylvie獨有": [],
        "Enjoy獨有": [],
      }
    """
    我 = {p["symbol"] for p in 我的}
    S = {p["symbol"] for p in sylvie}
    E = {p["symbol"] for p in enjoy}

    def _name(sym, source):
        for p in source:
            if p["symbol"] == sym:
                return p.get("name", "")
        return ""

    return {
        "你+Sylvie+Enjoy": [
            {"symbol": s, "name": _name(s, 我的) or _name(s, sylvie) or _name(s, enjoy)}
            for s in sorted(我 & S & E)
        ],
        "你+Sylvie": [
            {"symbol": s, "name": _name(s, 我的) or _name(s, sylvie)}
            for s in sorted((我 & S) - E)
        ],
        "你+Enjoy": [
            {"symbol": s, "name": _name(s, 我的) or _name(s, enjoy)}
            for s in sorted((我 & E) - S)
        ],
        "Sylvie+Enjoy": [
            {"symbol": s, "name": _name(s, sylvie) or _name(s, enjoy)}
            for s in sorted((S & E) - 我)
        ],
        "你獨有": [
            {"symbol": s, "name": _name(s, 我的)}
            for s in sorted(我 - S - E)
        ],
        "Sylvie獨有": [
            {"symbol": s, "name": _name(s, sylvie)}
            for s in sorted(S - 我 - E)
        ],
        "Enjoy獨有": [
            {"symbol": s, "name": _name(s, enjoy)}
            for s in sorted(E - 我 - S)
        ],
    }


def 共識報告() -> dict:
    """主入口：跑全部來源 + 算共識"""
    你 = 載入你的持股()
    sylvie_data = 載入Sylvie持股()
    sylvie持股 = sylvie_data.get("持股", [])
    enjoy = ENJOY持股

    共識 = 算共識(你, sylvie持股, enjoy)
    return {
        "更新日": sylvie_data.get("更新日"),
        "你的持股數": len(你),
        "Sylvie 持股數": len(sylvie持股),
        "Enjoy 持股數": len(enjoy),
        "共識": 共識,
        "Sylvie已實現": sylvie_data.get("已實現", []),
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

    r = 共識報告()
    print("=" * 60)
    print(f"🤝 社群共識報告 ({r['更新日']})")
    print("=" * 60)
    print(f"你 {r['你的持股數']} 檔 / Sylvie {r['Sylvie 持股數']} 檔 / "
          f"Enjoy {r['Enjoy 持股數']} 檔\n")

    c = r["共識"]
    if c["你+Sylvie+Enjoy"]:
        print(f"⭐⭐⭐ 三方共識（最強）: {len(c['你+Sylvie+Enjoy'])} 檔")
        for x in c["你+Sylvie+Enjoy"]:
            print(f"   {x['symbol']:<10} {x['name']}")

    if c["你+Sylvie"]:
        print(f"\n⭐⭐ 你+Sylvie 共識: {len(c['你+Sylvie'])} 檔")
        for x in c["你+Sylvie"]:
            print(f"   {x['symbol']:<10} {x['name']}")

    if c["你+Enjoy"]:
        print(f"\n⭐⭐ 你+Enjoy 共識: {len(c['你+Enjoy'])} 檔")
        for x in c["你+Enjoy"]:
            print(f"   {x['symbol']:<10} {x['name']}")

    if c["Sylvie+Enjoy"]:
        print(f"\n💡 Sylvie+Enjoy（你沒有，可參考）: {len(c['Sylvie+Enjoy'])} 檔")
        for x in c["Sylvie+Enjoy"]:
            print(f"   {x['symbol']:<10} {x['name']}")

    if r["Sylvie已實現"]:
        print(f"\n📝 Sylvie 近期已實現：")
        for e in r["Sylvie已實現"]:
            sign = "+" if e['報酬率_pct'] >= 0 else ""
            print(f"   {e['賣出日']}  {e['symbol']:<8} {e.get('name',''):<10}"
                  f" {sign}{e['報酬率_pct']:.2f}%  {e.get('備註','')}")
