"""
調節後重佈局 (Phase 36.10) — Sylvie 5/15 揭示的關鍵維度

Sylvie 親口（22:50）：
  「最近調節比較多 → 所以再重新佈局」
  「用調節的再去買」

LIS 派之前**完全缺這個維度**：
  賣高 → 鎖利 → 錢擺在那 = 機會成本

加入這個維度後：
  賣高 → 鎖利 → 自動找下一個價值區 → 重佈局 → 累積複利

設計邏輯：

1. **算可動用調節資金**
   - 最近 14 天 realized_history 已實現獲利
   - + pending_settlement 待入帳
   - - 最近 14 天已重佈局買入（避免重複）

2. **找候選標的**（從 watchlist + 策略池）
   - 排除：已重壓（單檔 > 15% 總資產）
   - 排除：過熱（位階分數 >= 70）
   - 排序：位階分數由低到高（最便宜的優先）
   - 加分：跟 Sylvie 共識 + 產業熱度

3. **建議分配**
   - Top 3 候選
   - 每檔 25-33% 調節資金
   - 顯示「賣 X 後，重佈局 Y」

4. **跟手續費**
   - 用 friction.py 算每筆摩擦
   - 提示是否值得（金額 > NT$ 5,000 才推薦）

依賴：
  - portfolio.json (realized_history / pending_settlement / current_positions)
  - 數據/positional_state.json (位階分數)
  - API/watchlist.json (候選池)
  - 數據/sylvie_portfolio.json (Sylvie 共識)
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


def 算調節資金(cfg: dict, USD_TWD: float = 31.5,
                lookback_days: int = 14) -> dict:
    """
    算最近 N 天可重佈局的調節資金
    = (realized 已實現) + (pending_settlement 待入帳) - (近期已重佈局)
    """
    today = datetime.now().date()
    cutoff = today - timedelta(days=lookback_days)

    # 1. 已實現獲利
    realized_twd = 0
    for r in cfg.get("realized_history", []):
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            if d < cutoff:
                continue
            # 美股用 pnl_usd × 匯率，台股用 pnl_twd
            pnl_usd = r.get("pnl_usd")
            pnl_twd = r.get("pnl_twd")
            if pnl_usd:
                realized_twd += pnl_usd * USD_TWD
            elif pnl_twd:
                realized_twd += pnl_twd
        except Exception:
            continue

    # 2. 賣出本金（已實現的「不是獲利」也包含進來，因為這部分要重新佈局）
    # 例：賣 75 股 SATL @ 8.43 = $632 → 進帳近 $19,912 = 全部要找去處
    realized_本金_twd = 0
    for r in cfg.get("realized_history", []):
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            if d < cutoff:
                continue
            股 = r.get("shares", 0)
            賣價 = r.get("sell_price", 0)
            是美股 = not (r.get("symbol", "").endswith(".TW") or
                          r.get("symbol", "").endswith(".TWO"))
            倍率 = USD_TWD if 是美股 else 1.0
            realized_本金_twd += 股 * 賣價 * 倍率
        except Exception:
            continue

    # 3. 待交割（pending_settlement）
    pending_twd = sum(p.get("net_twd", 0)
                       for p in cfg.get("pending_settlement", []))

    # 4. 近期已重佈局（從 capital_inflow_history 抓負值 = 買入）
    已重佈局_twd = 0
    for r in cfg.get("capital_inflow_history", []):
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            if d < cutoff:
                continue
            amt = r.get("amount_twd", 0)
            note = r.get("note", "")
            if amt < 0 and "買" in note:  # 買入紀錄
                已重佈局_twd += abs(amt)
        except Exception:
            continue

    可動用 = realized_本金_twd + pending_twd - 已重佈局_twd

    return {
        "已實現獲利_twd": round(realized_twd, 0),
        "賣出本金_twd": round(realized_本金_twd, 0),
        "待入帳_twd": round(pending_twd, 0),
        "已重佈局_twd": round(已重佈局_twd, 0),
        "可動用調節資金_twd": round(max(0, 可動用), 0),
        "lookback_days": lookback_days,
    }


def 載入位階分數() -> dict:
    """讀 positional_state.json 的位階分數"""
    path = 專案根 / "數據" / "positional_state.json"
    if not path.exists():
        return {}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d.get("scores", {})
    except Exception:
        return {}


def 載入Sylvie持股() -> set:
    """讀 Sylvie 當前持股代號"""
    path = 專案根 / "數據" / "sylvie_portfolio.json"
    if not path.exists():
        return set()
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return set(p["symbol"] for p in d.get("持股", []))
    except Exception:
        return set()


def 找候選標的(cfg: dict, 已重壓上限_pct: float = 15) -> list:
    """
    從 watchlist + 策略池找重佈局候選
    排序：熟悉度 + 位階分數低 + Sylvie 共識
    """
    位階 = 載入位階分數()
    sylvie_syms = 載入Sylvie持股()

    持股dict = {p["symbol"]: p
                for p in cfg.get("current_positions", [])
                if p.get("symbol") != "AGGREGATE"}

    總資產_twd = cfg.get("total_capital_twd", 500000)

    wl_path = 專案根 / "API" / "watchlist.json"
    if not wl_path.exists():
        return []
    wl = json.loads(wl_path.read_text(encoding="utf-8"))

    候選 = []
    for region in wl.get("regions", []):
        for s in region.get("stocks", []):
            sym = s["symbol"]

            score = 位階.get(sym)
            if score is None or score >= 70:
                continue

            # 熟悉度評估（user 不熟的標的 = 不推薦）
            是台股 = sym.endswith(".TW") or sym.endswith(".TWO")
            是ETF = (sym.startswith("00") or sym == "0050.TW" or
                     "ETF" in s.get("name", ""))
            你已持 = sym in 持股dict
            sylvie持 = sym in sylvie_syms

            # 熟悉度分數
            if 你已持:
                熟悉 = 30  # 自己有的最熟
            elif sylvie持:
                熟悉 = 20  # Sylvie 有的次熟
            elif 是台股 and 是ETF:
                熟悉 = 15  # 台股 ETF 一般有概念
            elif 是台股:
                熟悉 = 8   # 台股個股 中等
            else:
                熟悉 = 0   # 美股冷門 = 不推

            # 排除：完全不熟
            if 熟悉 == 0:
                continue

            # 排除：已重壓
            if 你已持:
                p = 持股dict[sym]
                cost_twd = (p.get("avg_cost", 0) * p.get("shares", 0))
                if not 是台股:
                    cost_twd *= 31.5
                持股_pct = cost_twd / 總資產_twd * 100
                if 持股_pct >= 已重壓上限_pct:
                    continue

            # 總分：(100 - 位階分數) + 熟悉度 + Sylvie 加分
            sylvie加分 = 15 if sylvie持 else 0
            總分 = (100 - score) + 熟悉 + sylvie加分

            候選.append({
                "symbol": sym,
                "name": s.get("name", ""),
                "位階分數": score,
                "熟悉度": 熟悉,
                "Sylvie持有": sylvie持,
                "你已持": 你已持,
                "是ETF": 是ETF,
                "總分": 總分,
            })

    候選.sort(key=lambda r: -r["總分"])
    return 候選[:10]


def 算建議分配(可動用_twd: float, 候選: list,
                top_n: int = 3) -> list:
    """把可動用資金分配給 Top N 候選"""
    if 可動用_twd <= 0 or not 候選:
        return []

    top = 候選[:top_n]
    每檔_twd = 可動用_twd / len(top)

    建議 = []
    for c in top:
        建議.append({
            **c,
            "分配_twd": round(每檔_twd, 0),
        })
    return 建議


def 重佈局建議(cfg: dict = None, USD_TWD: float = 31.5) -> dict:
    """主入口"""
    if cfg is None:
        cfg = json.loads(
            (專案根 / "API" / "portfolio.json").read_text(encoding="utf-8"))

    資金 = 算調節資金(cfg, USD_TWD)

    # 分「立刻可動」vs「未來可動」
    # 立刻可動 = 已實現獲利（淨賺的）+ 還沒重佈局的（賣出本金 - 待入帳部分）
    待入帳 = 資金["待入帳_twd"]
    已實現獲利 = 資金["已實現獲利_twd"]
    立刻可動 = 已實現獲利  # 保守：只算已實現
    未來可動 = 待入帳  # 5/18-5/19 入帳後可加

    if 立刻可動 + 未來可動 < 5000:
        return {
            "可重佈局": False,
            "資金狀況": 資金,
            "立刻可動_twd": 立刻可動,
            "未來可動_twd": 未來可動,
            "說明": f"資金 NT$ {立刻可動 + 未來可動:,.0f} < 最低 NT$ 5,000 摩擦門檻",
            "建議": [],
        }

    候選 = 找候選標的(cfg)
    if not 候選:
        return {
            "可重佈局": False,
            "資金狀況": 資金,
            "立刻可動_twd": 立刻可動,
            "未來可動_twd": 未來可動,
            "說明": "目前無位階分數低的候選（市場偏熱）",
            "建議": [],
        }

    # 用「立刻 + 未來」總額分配，但標記哪部分要等
    總可用 = 立刻可動 + 未來可動
    分配 = 算建議分配(總可用, 候選)

    return {
        "可重佈局": True,
        "資金狀況": 資金,
        "立刻可動_twd": 立刻可動,
        "未來可動_twd": 未來可動,
        "總可動_twd": 總可用,
        "候選池": 候選,
        "建議": 分配,
        "說明": (f"立刻 NT$ {立刻可動:,.0f} + 未來 5/18-5/19 入帳 "
                 f"NT$ {未來可動:,.0f} = 合計 NT$ {總可用:,.0f}"),
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
    print("調節後重佈局建議（Sylvie 教學）")
    print("=" * 60)

    r = 重佈局建議()
    資 = r["資金狀況"]

    print(f"\n💰 資金狀況（最近 {資['lookback_days']} 天）：")
    print(f"  已實現獲利:   NT$ {資['已實現獲利_twd']:,.0f}")
    print(f"  賣出本金:     NT$ {資['賣出本金_twd']:,.0f}")
    print(f"  待入帳:       NT$ {資['待入帳_twd']:,.0f}")
    print(f"  已重佈局:   - NT$ {資['已重佈局_twd']:,.0f}")
    print(f"  ─────────────────────────────")
    print(f"  可動用:       NT$ {資['可動用調節資金_twd']:,.0f}")

    if r["可重佈局"]:
        print(f"\n🎯 重佈局建議（Top 3）:")
        for i, c in enumerate(r["建議"], 1):
            sylvie_mark = " ⭐Sylvie 共識" if c["Sylvie持有"] else ""
            held_mark = " ✓ 你已持" if c["你已持"] else ""
            print(f"  {i}. {c['symbol']} {c['name'][:10]}")
            print(f"     位階 {c['位階分數']:.0f}{sylvie_mark}{held_mark}")
            print(f"     分配 NT$ {c['分配_twd']:,.0f}")
    else:
        print(f"\n  ❌ {r['說明']}")
