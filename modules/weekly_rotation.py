"""
每週位階輪動 (Phase 36.12) — LIS 派吸收 Sylvie 美股輪動但降頻

Sylvie 美股「每天輪動 10 檔」對 LIS 太頻繁（摩擦 5%/年）
LIS 版降頻成「**每週 1-2 筆**」（摩擦 < 0.5%/年）

核心邏輯：
  1. 你已持的 → 找位階 >= 70（過熱）的 1-2 檔 → 賣建議
  2. watchlist → 找位階 <= 30（價值區）的 1-2 檔 → 買建議
  3. 賣的錢買新的 → 重佈局（不增加總部位）

保護機制：
  - 剛買 7 天內不賣（避免短進短出）
  - 每週最多 2 筆換股（控摩擦）
  - 預估摩擦 > 預估漲幅差 → 不建議
  - 只在週一推（每週 1 次）

整合：
  - daily_action_card 週一 8AM 推
  - 顯示「本週輪動：賣 X 換 Y」
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


def 載入位階分數() -> dict:
    path = 專案根 / "數據" / "positional_state.json"
    if not path.exists():
        return {}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d.get("scores", {})
    except Exception:
        return {}


def 載入Sylvie持股() -> set:
    path = 專案根 / "數據" / "sylvie_portfolio.json"
    if not path.exists():
        return set()
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return set(p["symbol"] for p in d.get("持股", []))
    except Exception:
        return set()


def 是否剛買(symbol: str, cfg: dict, days: int = 7) -> bool:
    """看 capital_inflow_history 找最近 N 天有沒有買進該 symbol"""
    cutoff = datetime.now() - timedelta(days=days)
    for r in cfg.get("capital_inflow_history", []):
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d")
            if d < cutoff:
                continue
            note = r.get("note", "")
            if symbol in note and ("買" in note or "加" in note):
                return True
        except Exception:
            continue
    return False


def 找賣候選(cfg: dict, 過熱閾值: float = 70,
              max_n: int = 2) -> list:
    """從你持股找位階最高的（過熱）建議賣"""
    位階 = 載入位階分數()
    持股 = [p for p in cfg.get("current_positions", [])
            if p.get("symbol") != "AGGREGATE"]

    候選 = []
    for p in 持股:
        sym = p["symbol"]
        score = 位階.get(sym)
        if score is None or score < 過熱閾值:
            continue
        # 排除剛買 7 天內的
        if 是否剛買(sym, cfg):
            continue
        候選.append({
            "symbol": sym,
            "name": p.get("name", ""),
            "shares": p.get("shares", 0),
            "avg_cost": p.get("avg_cost", 0),
            "位階分數": score,
        })
    候選.sort(key=lambda r: -r["位階分數"])
    return 候選[:max_n]


def 找買候選(cfg: dict, 價值閾值: float = 30,
              max_n: int = 2) -> list:
    """從 watchlist 找位階最低的（價值區）建議買"""
    位階 = 載入位階分數()
    sylvie_syms = 載入Sylvie持股()
    持股syms = {p["symbol"] for p in cfg.get("current_positions", [])
                 if p.get("symbol") != "AGGREGATE"}

    wl_path = 專案根 / "API" / "watchlist.json"
    if not wl_path.exists():
        return []
    wl = json.loads(wl_path.read_text(encoding="utf-8"))

    候選 = []
    for region in wl.get("regions", []):
        for s in region.get("stocks", []):
            sym = s["symbol"]
            score = 位階.get(sym)
            if score is None or score > 價值閾值:
                continue

            # 排除：完全冷門美股（你不熟）
            是台股 = sym.endswith(".TW") or sym.endswith(".TWO")
            是熟悉美股 = sym in {"NVDA", "AMD", "ADBE", "MU", "LRCX", "AMAT",
                                  "GEV", "SATL", "IREN", "GLW", "META",
                                  "GOOGL", "AAPL", "MSFT", "TSM"}
            if not 是台股 and not 是熟悉美股 and sym not in sylvie_syms:
                continue

            候選.append({
                "symbol": sym,
                "name": s.get("name", ""),
                "位階分數": score,
                "你已持": sym in 持股syms,
                "Sylvie共識": sym in sylvie_syms,
            })

    # 排序：位階低 + Sylvie 共識加分
    for c in 候選:
        c["排序分"] = (100 - c["位階分數"]) + (15 if c["Sylvie共識"] else 0)
    候選.sort(key=lambda r: -r["排序分"])
    return 候選[:max_n]


def 算輪動預期(賣: dict, 買: dict) -> dict:
    """估算這筆輪動是否值得"""
    # 位階差 = 賣高 - 買低（差越大越值得）
    位階差 = 賣.get("位階分數", 0) - 買.get("位階分數", 0)

    # 預估摩擦（賣方 + 買方手續費 + 稅）
    # 簡化用 1% 整體摩擦（賣 0.5% + 買 0.5%）
    摩擦_pct = 1.0

    # 預期效益：位階差 5 分 ≈ 預期未來 ~5% 報酬差
    預期效益_pct = 位階差 * 0.5  # 保守估

    值得 = 預期效益_pct > 摩擦_pct * 2  # 至少要 2 倍摩擦

    return {
        "位階差": 位階差,
        "預估摩擦_pct": 摩擦_pct,
        "預期效益_pct": round(預期效益_pct, 1),
        "值得": 值得,
        "說明": (f"賣位階 {賣['位階分數']:.0f} → 買位階 {買['位階分數']:.0f} = "
                 f"差 {位階差:.0f} 分（預期 +{預期效益_pct:.1f}%）")
    }


def 週輪動建議(cfg: dict = None, 強制執行: bool = False) -> dict:
    """
    主入口：每週 1 次的輪動建議
    強制執行=True 時忽略「只週一」限制
    """
    if cfg is None:
        cfg = json.loads(
            (專案根 / "API" / "portfolio.json").read_text(encoding="utf-8"))

    # 只週一推（除非強制）
    weekday = datetime.now().weekday()  # 0=週一
    if weekday != 0 and not 強制執行:
        return {
            "週輪動": False,
            "說明": f"今天週{weekday + 1}，週輪動建議只在週一推",
            "下次": "下週一 8AM",
        }

    賣候選 = 找賣候選(cfg)
    買候選 = 找買候選(cfg)

    if not 賣候選 or not 買候選:
        return {
            "週輪動": True,
            "建議": [],
            "說明": ("無賣候選（無持股位階 >= 70）" if not 賣候選
                     else "無買候選（無 watchlist 位階 <= 30）"),
        }

    # 配對：1 對 1
    建議 = []
    for i, (賣, 買) in enumerate(zip(賣候選, 買候選)):
        分析 = 算輪動預期(賣, 買)
        建議.append({
            "賣": 賣,
            "買": 買,
            "分析": 分析,
            "推薦": 分析["值得"],
        })

    值得的 = [r for r in 建議 if r["推薦"]]

    return {
        "週輪動": True,
        "今天是週一": weekday == 0,
        "建議數": len(建議),
        "值得執行": len(值得的),
        "建議": 建議,
        "說明": (f"本週 {len(值得的)} 筆值得輪動 "
                 if 值得的 else "本週無值得輪動的標的"),
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
    print("每週位階輪動建議（LIS 派吸收 Sylvie）")
    print("=" * 60)

    r = 週輪動建議(強制執行=True)

    if not r.get("週輪動"):
        print(f"\n  {r['說明']}")
    elif not r.get("建議"):
        print(f"\n  {r['說明']}")
    else:
        print(f"\n  {r['說明']}")
        for i, b in enumerate(r["建議"], 1):
            賣 = b["賣"]
            買 = b["買"]
            分 = b["分析"]
            推 = "✅ 推薦" if b["推薦"] else "⚠️ 不推薦"
            print(f"\n  輪動 {i}：{推}")
            print(f"    🔴 賣 {賣['symbol']} {賣['name'][:10]} ({賣['shares']} 股)")
            print(f"       位階 {賣['位階分數']:.0f}（過熱）")
            print(f"    🟢 買 {買['symbol']} {買['name'][:10]}")
            print(f"       位階 {買['位階分數']:.0f}（價值區）")
            if 買.get("Sylvie共識"):
                print(f"       ⭐ Sylvie 共識")
            if 買.get("你已持"):
                print(f"       ✓ 你已持")
            print(f"    分析: {分['說明']}")
            print(f"          預估效益 +{分['預期效益_pct']:.1f}% > 摩擦 {分['預估摩擦_pct']:.1f}%")
