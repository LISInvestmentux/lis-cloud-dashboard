"""
ARK 6 大調節法觀察模組（Phase 32.7）

依大俠 ARK 教學 6 大法則掃真倉，給「可考慮調節」清單。
**這只是觀察建議，不強制執行** — LIS Strategy A (+15%/-5%) 仍是主紀律。

6 大法則：
  ① 位階排序     — 賣最熱的（先賣最貴的）
  ② 升溫區排序   — 已脫離價值區的
  ③ 總報酬率排序 — 漲多的（部分了結）
  ④ 總報酬金額排序 — 賺最多金額的（落袋首選）
  ⑤ 風控         — 單檔比例過大
  ⑥ 修剪枯枝     — 表現差但未破停損的
"""


def 算ARK調節建議(真倉: dict,
                    scores: dict,
                    總資產_twd: float) -> dict:
    """
    參數：
      真倉: portfolio_tracker.追蹤真倉() 結果
      scores: positional_state.json 的 scores（位階分數）
      總資產_twd: 總資產 = 持股市值 + 現金

    回傳 dict，6 個 key 對應 6 大法則，各裝清單（top 3）。
    """
    持股 = [p for p in 真倉.get("持股", []) if not p.get("error")]
    if not 持股:
        return {}

    # 補位階分數
    for p in 持股:
        p["_score"] = scores.get(p.get("symbol", ""), 0) or 0

    結果 = {}

    # ① 位階排序 — 過熱可調 (≥70 分)
    過熱 = sorted([p for p in 持股 if p["_score"] >= 70],
                  key=lambda r: -r["_score"])
    結果["位階排序"] = [{
        "symbol": p["symbol"], "name": p.get("name", "")[:6],
        "score": p["_score"], "pnl_pct": p["pnl_pct"],
        "shares": p["shares"],
        "建議": f"調 {max(1, p['shares']//3)} 股"
    } for p in 過熱[:3]]

    # ② 升溫區排序 — 已脫離價值區 (50-70 分) 且有賺
    升溫 = sorted([p for p in 持股
                     if 50 <= p["_score"] < 70 and p["pnl_pct"] > 5],
                    key=lambda r: -r["pnl_pct"])
    結果["升溫區排序"] = [{
        "symbol": p["symbol"], "name": p.get("name", "")[:6],
        "score": p["_score"], "pnl_pct": p["pnl_pct"],
        "shares": p["shares"],
        "建議": "觀察"
    } for p in 升溫[:3]]

    # ③ 總報酬率排序 — 漲最多 (>5%)
    by_pct = sorted([p for p in 持股 if p["pnl_pct"] > 5],
                     key=lambda r: -r["pnl_pct"])
    結果["總報酬率排序"] = [{
        "symbol": p["symbol"], "name": p.get("name", "")[:6],
        "pnl_pct": p["pnl_pct"], "shares": p["shares"],
        "建議": (f"近 +15%，賣 {max(1, p['shares']//3)} 股"
                 if p["pnl_pct"] >= 12 else "繼續抱")
    } for p in by_pct[:3]]

    # ④ 總報酬金額排序 — 賺最多 TWD
    by_twd = sorted([p for p in 持股 if p.get("pnl_twd", 0) > 1000],
                     key=lambda r: -r["pnl_twd"])
    結果["總報酬金額排序"] = [{
        "symbol": p["symbol"], "name": p.get("name", "")[:6],
        "pnl_twd": p.get("pnl_twd", 0), "pnl_pct": p["pnl_pct"],
        "shares": p["shares"],
        "建議": "落袋首選"
    } for p in by_twd[:3]]

    # ⑤ 風控 — 單檔市值占總資產 ≥15%
    超集中 = []
    for p in 持股:
        市值 = p.get("market_value_twd", 0)
        占比 = 市值 / 總資產_twd * 100 if 總資產_twd > 0 else 0
        if 占比 >= 15:
            超集中.append({
                "symbol": p["symbol"], "name": p.get("name", "")[:6],
                "占比_pct": round(占比, 1), "shares": p["shares"],
                "建議": f"占 {占比:.0f}% 過重，減 {max(1, p['shares']//4)} 股"
            })
    結果["風控"] = sorted(超集中, key=lambda r: -r["占比_pct"])[:3]

    # ⑥ 修剪枯枝 — 跌但未破停損
    跌的 = []
    for p in 持股:
        pct = p["pnl_pct"]
        是美股 = p.get("is_us", False)
        停損 = -3.0 if 是美股 else -5.0
        if 停損 < pct < 0:  # 跌但還沒破
            離停損 = abs(pct - 停損)
            跌的.append({
                "symbol": p["symbol"], "name": p.get("name", "")[:6],
                "pnl_pct": pct, "shares": p["shares"],
                "離停損_pct": round(離停損, 2),
                "建議": (f"距停損僅 {離停損:.1f}%，考慮減"
                         if 離停損 <= 1 else "觀察")
            })
    結果["修剪枯枝"] = sorted(跌的, key=lambda r: r["pnl_pct"])[:3]

    return 結果


def 摘要文字(調節結果: dict) -> str:
    """一句話摘要：幾個類別有候選"""
    有效 = [(k, len(v)) for k, v in 調節結果.items() if v]
    if not 有效:
        return "全部持股紀律內，無需調節"
    return " / ".join(f"{k} {n}" for k, n in 有效)


# ─────────────────────────────────────────────
# CLI 自測
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import json
    from pathlib import Path
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from dotenv import load_dotenv
    專案根 = Path(__file__).resolve().parent.parent.parent
    load_dotenv(專案根 / "API" / ".env")
    sys.path.insert(0, str(專案根 / "程式碼"))

    from modules import capital_planner, portfolio_tracker, forex

    cfg = capital_planner.載入資金設定()
    USD_TWD = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32))["rate"]
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=USD_TWD)

    state_path = 專案根 / "數據" / "positional_state.json"
    scores = {}
    if state_path.exists():
        scores = json.loads(state_path.read_text(encoding="utf-8")).get("scores", {})

    總資產 = 真倉["總計"]["市值_twd"] + cfg.get("current_cash_twd", 0)

    調節 = 算ARK調節建議(真倉, scores, 總資產)
    print("=== ARK 6 大調節法觀察 ===\n")
    print(f"摘要：{摘要文字(調節)}\n")
    法則名 = {
        "位階排序": "① 位階最熱（過熱可調）",
        "升溫區排序": "② 升溫區（脫離價值區）",
        "總報酬率排序": "③ 漲最多（部分了結）",
        "總報酬金額排序": "④ 賺最多金額（落袋首選）",
        "風控": "⑤ 風控（單檔過集中）",
        "修剪枯枝": "⑥ 修剪枯枝（接近停損）",
    }
    for key, label in 法則名.items():
        清單 = 調節.get(key, [])
        if not 清單:
            continue
        print(f"\n{label}")
        for r in 清單:
            extra = ""
            if "score" in r:
                extra = f"位階 {r['score']:.0f} / "
            if "pnl_pct" in r:
                extra += f"{r['pnl_pct']:+.2f}% / "
            if "pnl_twd" in r:
                extra += f"+NT$ {r['pnl_twd']:,.0f} / "
            if "占比_pct" in r:
                extra += f"占 {r['占比_pct']:.0f}% / "
            print(f"  {r['symbol']:<10} {r['name']:<8} {extra}{r['建議']}")
