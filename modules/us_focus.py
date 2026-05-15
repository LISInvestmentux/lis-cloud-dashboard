"""
美股焦點分析（Phase 32.7 加強版）

晚上美股時段獨立看「賣/守/轉倉/加股」4 種動作 + 整體彈藥檢查。

判讀規則 — 已持有：
  pnl ≥ +15%     → 🎯 賣（LIS A 停利，建議賣 1/2 股）
  pnl ≤ -3%      → 💀 賣（美股嚴停損，全停損）
  位階 ≥70 + pnl ≥+8% → 🔄 轉倉（賣 1/3 轉去價值區）
  位階 ≥70 + pnl <+8% → ✋ 守不加（過熱別追）
  位階 ≤30 + 彈藥夠 → 🆕 加股（攤平）
  +12% ≤ pnl <+15% → 📈 接近停利警示
  -3% < pnl ≤-2%  → 📉 接近停損警示
  其他 → ✅ 守

判讀規則 — 未持有（watchlist 位階 <30）：
  彈藥夠 + 黑天鵝 SOP ≥3 → 🚀 重押級加股
  彈藥夠 + 位階 ≤15      → 🔥 加碼級
  彈藥夠 + 位階 ≤25      → ⚡ 順勢級
  彈藥夠                  → 📌 紀律級
  彈藥不足                → 🎯 目標標的（等彈藥）
"""
import json
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


def _ARK等級(score: float, 黑天鵝命中: int = 0) -> str:
    """從位階分數 + 黑天鵝命中數推訊號等級"""
    if 黑天鵝命中 >= 4:
        return "ALL_IN"
    if 黑天鵝命中 >= 3:
        return "重押"
    if score <= 15:
        return "重押"
    if score <= 25:
        return "加碼"
    if score <= 30:
        return "順勢"
    return "紀律"


def _判讀加股(score: float, 彈藥資訊: dict, 黑天鵝命中: int,
              us_cfg: dict, USD_TWD: float) -> dict:
    """
    回傳 {能加: bool, 等級, cap_usd, 理由}
    """
    等級 = _ARK等級(score, 黑天鵝命中)
    cap_usd = us_cfg.get("tier_limits_usd", {}).get(等級, 100)
    可動用_twd = 彈藥資訊.get("可動用彈藥_twd", 0)
    需要_twd = cap_usd * USD_TWD

    if 可動用_twd < 需要_twd:
        return {"能加": False, "等級": 等級, "cap_usd": cap_usd,
                "理由": f"彈藥不足（需 NT${需要_twd:,.0f}/剩 NT${可動用_twd:,.0f}）"}
    return {"能加": True, "等級": 等級, "cap_usd": cap_usd,
            "理由": f"{等級} 級可加 ${cap_usd}"}


def 判讀持股(p: dict, score: float, 彈藥資訊: dict, 黑天鵝命中: int,
              us_cfg: dict, USD_TWD: float) -> dict:
    """單檔美股 verdict — 已持有"""
    pct = p["pnl_pct"]
    shares = p["shares"]
    current = p["current_price"]

    if pct >= 15:
        return {"動作": "🎯 賣",
                "理由": f"達 +15% 停利！賣 {max(1, shares//2)} 股 ≈ "
                        f"${max(1, shares//2) * current:.0f}（策略 D 一半）"}
    if pct <= -3:
        return {"動作": "💀 賣",
                "理由": f"破 -3% 美股嚴停損！全停損 {shares} 股 ≈ ${shares*current:.0f}"}
    # 位階 = 0 意義「未掃描」非「低分」— 跳過位階相關判讀
    if score == 0:
        if pct >= 12:
            return {"動作": "📈 接近停利",
                    "理由": f"距 +15% 還 {15-pct:.1f}%（位階未掃，純漲跌判讀）"}
        if pct <= -2:
            return {"動作": "📉 接近停損",
                    "理由": f"距 -3% 還 {abs(pct+3):.1f}%（位階未掃）"}
        return {"動作": "✅ 守",
                "理由": f"位階未掃描，純靠 +15%/-3% 紀律 — 紀律內繼續抱"}
    if score >= 70 and pct >= 8:
        return {"動作": "🔄 轉倉",
                "理由": f"位階 {score:.0f} 過熱 + 賺 {pct:.1f}%，"
                        f"轉 {max(1, shares//3)} 股 ≈ ${max(1, shares//3)*current:.0f} "
                        f"到價值區"}
    if score >= 70:
        return {"動作": "✋ 守不加",
                "理由": f"位階 {score:.0f} 過熱，不追加買進"}
    if 0 < score <= 30:
        # 已持有 + 位階回到價值區 → 攤平加碼候選
        加股 = _判讀加股(score, 彈藥資訊, 黑天鵝命中, us_cfg, USD_TWD)
        if 加股["能加"]:
            cap = 加股["cap_usd"]
            股數 = max(1, int(cap / current))
            return {"動作": "🆕 加股（攤平）",
                    "理由": f"位階 {score:.0f} 回到價值區，{加股['等級']} 級加 "
                            f"{股數} 股 ≈ ${股數*current:.0f}"}
        else:
            return {"動作": "🆕 加股機會",
                    "理由": f"位階 {score:.0f} 回到價值區但{加股['理由']}"}
    if pct >= 12:
        return {"動作": "📈 接近停利",
                "理由": f"距 +15% 還 {15-pct:.1f}%，準備分批落袋 "
                        f"{max(1, shares//2)} 股"}
    if pct <= -2:
        return {"動作": "📉 接近停損",
                "理由": f"距 -3% 還 {abs(pct+3):.1f}%，盯緊"}
    return {"動作": "✅ 守",
            "理由": "紀律內，繼續抱"}


def 判讀新進場(sym: str, score: float, 彈藥資訊: dict, 黑天鵝命中: int,
                us_cfg: dict, USD_TWD: float, 現價_usd: Optional[float] = None) -> dict:
    """價值區未持有 → 加股新進場 verdict"""
    加股 = _判讀加股(score, 彈藥資訊, 黑天鵝命中, us_cfg, USD_TWD)
    if 加股["能加"]:
        cap = 加股["cap_usd"]
        if 現價_usd and 現價_usd > 0:
            股數 = max(1, int(cap / 現價_usd))
            金額 = 股數 * 現價_usd
            return {"動作": f"🆕 進場（{加股['等級']}）",
                    "理由": f"位階 {score:.0f} 深價值區，{加股['等級']} 級買 "
                            f"{股數} 股 ≈ ${金額:.0f}"}
        return {"動作": f"🆕 進場（{加股['等級']}）",
                "理由": f"位階 {score:.0f}，{加股['等級']} 級買 ≈ ${cap}"}
    return {"動作": "🎯 目標標的",
            "理由": f"位階 {score:.0f} 深價值區但{加股['理由']}"}


def 美股焦點分析() -> dict:
    """主入口"""
    try:
        from . import (portfolio_tracker, capital_planner, forex,
                       money_manager, bottom_detector, fear_greed, technical,
                       peak_tracker)
    except ImportError:
        import portfolio_tracker
        import capital_planner
        import forex
        import money_manager
        import bottom_detector
        import fear_greed
        import technical
        import peak_tracker

    cfg = capital_planner.載入資金設定()
    USD_TWD = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32))["rate"]
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=USD_TWD)

    # 持股市值總（含台股+美股）
    現金 = cfg.get("current_cash_twd", 0)
    持股市值總 = 真倉["總計"]["市值_twd"]
    總資產 = 持股市值總 + 現金

    # 彈藥資訊
    彈藥資訊 = money_manager.計算可用彈藥(
        總資金=總資產, 現金=現金, 持股成本_twd=持股市值總,
        目標閒錢比_pct=cfg.get("cash_management", {}).get("閒錢比例目標_pct", 35),
    )

    # 黑天鵝命中數
    黑天鵝命中 = 0
    try:
        sop = bottom_detector.即時底部判定()
        黑天鵝命中 = sop.get("命中數", 0)
    except Exception:
        pass

    # 大盤資訊
    大盤 = {}
    try:
        fg = fear_greed.取得恐慌貪婪指數()
        大盤["fear_greed"] = fg.get("score") if fg else None
    except Exception:
        pass
    try:
        vix_data, _ = technical.取得每日股價("^VIX", period="5d")
        大盤["VIX"] = round(vix_data[0]["close"], 2) if vix_data else None
    except Exception:
        pass

    # us_strategy
    us_cfg = cfg.get("us_strategy", {})

    # 位階分數
    state_path = 專案根 / "數據" / "positional_state.json"
    scores = {}
    if state_path.exists():
        scores = json.loads(state_path.read_text(encoding="utf-8")).get("scores", {})

    # 篩美股
    美股 = [p for p in 真倉["持股"]
             if p.get("is_us") and not p.get("error")]
    持股代號集 = {p["symbol"] for p in 美股}

    # 已持有 判讀（同步更新 peak_tracker）
    持股結果 = []
    for p in 美股:
        score = scores.get(p["symbol"], 0) or 0
        try:
            peak_tracker.更新峰值(p["symbol"], p["current_price"])
        except Exception:
            pass
        verdict = 判讀持股(p, score, 彈藥資訊, 黑天鵝命中, us_cfg, USD_TWD)
        # 加回檔資訊
        try:
            回檔 = peak_tracker.算回檔(p["symbol"], p["current_price"])
        except Exception:
            回檔 = {}
        持股結果.append({
            "回檔_pct": 回檔.get("weekly_drawdown_pct"),
            "回檔等級": 回檔.get("level"),
            "symbol": p["symbol"], "name": p.get("name", "")[:10],
            "shares": p["shares"], "avg_cost": p["avg_cost"],
            "current_price": p["current_price"],
            "pnl_pct": p["pnl_pct"], "pnl_twd": p.get("pnl_twd", 0),
            "market_value_twd": p.get("market_value_twd", 0),
            "score": score, **verdict,
        })

    # 排序：賣→停損→轉倉→警示→加股→守
    動作優先 = {"🎯 賣": 0, "💀 賣": 0,
                "🔄 轉倉": 1,
                "📈 接近停利": 2, "📉 接近停損": 2,
                "🆕 加股（攤平）": 3, "🆕 加股機會": 3,
                "✋ 守不加": 4, "✅ 守": 5}
    持股結果.sort(key=lambda r: 動作優先.get(r["動作"], 99))

    # 未持有的價值區候選
    新進場結果 = []
    for sym, score in scores.items():
        if not sym:
            continue
        if sym.endswith(".TW") or sym.endswith(".TWO"):
            continue
        if sym in 持股代號集:
            continue
        if score >= 30:
            continue
        if sym.startswith("^"):
            continue  # 跳過指數
        verdict = 判讀新進場(sym, score, 彈藥資訊, 黑天鵝命中, us_cfg, USD_TWD)
        新進場結果.append({"symbol": sym, "score": score, **verdict})
    新進場結果.sort(key=lambda r: r["score"])
    新進場結果 = 新進場結果[:5]

    # 統計
    動作數 = {}
    for r in 持股結果:
        動作數[r["動作"]] = 動作數.get(r["動作"], 0) + 1
    美股市值 = sum(p.get("market_value_twd", 0) for p in 美股)

    return {
        "持股結果": 持股結果,
        "新進場結果": 新進場結果,
        "統計": {
            "持股數": len(美股),
            "美股市值_twd": round(美股市值, 0),
            "動作分佈": 動作數,
        },
        "彈藥資訊": 彈藥資訊,
        "大盤": 大盤,
        "黑天鵝命中": 黑天鵝命中,
        "us_mode": us_cfg.get("mode", "stepped"),
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
    sys.path.insert(0, str(專案根 / "程式碼"))

    r = 美股焦點分析()
    print("=" * 70)
    print(f"🇺🇸 美股焦點（即時觀察）")
    print("=" * 70)

    s = r["統計"]
    print(f"\n📊 持股 {s['持股數']} 檔 / 美股市值 NT$ {s['美股市值_twd']:,.0f}")
    彈 = r["彈藥資訊"]
    print(f"💰 可動用彈藥 NT$ {彈['可動用彈藥_twd']:,.0f} / "
          f"閒錢比 {彈['水位']['閒錢比_pct']:.1f}% / 模式 {彈['模式emoji']}{彈['模式']}")
    if r["大盤"].get("VIX") or r["大盤"].get("fear_greed"):
        print(f"📈 大盤：VIX {r['大盤'].get('VIX')} / "
              f"F&G {r['大盤'].get('fear_greed')} / 黑天鵝命中 {r['黑天鵝命中']}/5")
    print(f"🎚️ ARK mode = {r['us_mode']}")
    print(f"動作分佈：{s['動作分佈']}")

    print("\n=== 📋 已持有逐檔判讀 ===")
    for p in r["持股結果"]:
        位階_str = "未掃" if p['score'] == 0 else f"{p['score']:.0f}"
        print(f"\n  {p['動作']}  {p['symbol']:<6} {p['name']:<10}"
              f" {p['shares']} 股 @ ${p['avg_cost']:.2f}")
        print(f"    現價 ${p['current_price']:.2f}  {p['pnl_pct']:+.2f}%"
              f"  位階 {位階_str}")
        print(f"    → {p['理由']}")

    if r["新進場結果"]:
        print(f"\n=== 🆕 價值區未持有候選（位階 <30）===")
        for c in r["新進場結果"]:
            print(f"  {c['動作']}  {c['symbol']:<6}  位階 {c['score']:.1f}")
            print(f"    → {c['理由']}")
