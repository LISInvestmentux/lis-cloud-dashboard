"""
Sylvie 教學提醒（Phase 32.7）

把 Sylvie 太太示範的 3 個紀律刻進系統提醒：
  1. 每日 DCA — 不論彈藥多少都做（強度 > 完美時機）
  2. 重押勇氣 — 黑天鵝命中 ≥3 時鼓勵動用預備金
  3. 強者繼續抱 — +15% 賣 50% 後，剩 50% 繼續抱衝 +30/+50%

回傳給 holistic_dashboard 顯示，或單獨推卡。
"""
from typing import Optional


# DCA 目標標的（Sylvie 主力 + 你倆共識）
DCA推薦 = [
    {"symbol": "0050.TW",    "name": "元大台灣50",   "理由": "你+Sylvie 共識，台股核心"},
    {"symbol": "00878.TW",   "name": "國泰永續高股息","理由": "Sylvie 17 個月 +27% 範例"},
    {"symbol": "00941.TW",   "name": "中信上游半導體","理由": "Sylvie 1450 股最大部位"},
]


def DCA今日提醒(彈藥資訊: dict, USD_TWD: float = 31.5) -> dict:
    """
    依彈藥狀態給今日 DCA 建議。
    """
    可動用 = 彈藥資訊.get("可動用彈藥_twd", 0)
    模式 = 彈藥資訊.get("模式", "")
    閒錢比 = 彈藥資訊.get("水位", {}).get("閒錢比_pct", 0)

    if 可動用 >= 5000:
        建議金額 = 2000
        強度 = "正常"
        提示 = f"💪 彈藥充足 NT$ {可動用:,.0f} — 每日 NT$ 2,000 DCA 不停手"
    elif 可動用 >= 1000:
        建議金額 = 1000
        強度 = "減量"
        提示 = f"📌 彈藥剩 NT$ {可動用:,.0f} — 每日 NT$ 1,000 微量 DCA"
    elif 閒錢比 >= 30:
        # 接近底線但還沒越線 — 用最小 DCA 維持紀律
        建議金額 = 500
        強度 = "最小"
        提示 = f"🟡 接近底線（{閒錢比:.1f}%） — 每日 NT$ 500 微量保紀律"
    else:
        建議金額 = 0
        強度 = "暫停"
        提示 = "⛔ 越線停 DCA — 等出場釋放彈藥"

    # 推薦標的（Sylvie 風格）
    推薦標的 = DCA推薦[0]  # 預設 0050（最穩）

    return {
        "建議金額_twd": 建議金額,
        "強度": 強度,
        "提示": 提示,
        "推薦標的": 推薦標的,
        "Sylvie格言": "「DCA 永不停手，是最大 alpha」",
    }


def 重押訊號提醒(黑天鵝命中: int, 大盤資訊: dict) -> dict:
    """
    黑天鵝命中 ≥3 → 鼓勵動用預備金。
    用 Sylvie 4/1 重押 0050 正 2 故事作參考。
    """
    vix = 大盤資訊.get("VIX")
    fg = 大盤資訊.get("fear_greed_score") or 大盤資訊.get("fear_greed")

    if 黑天鵝命中 >= 4:
        return {
            "等級": "🚨 重押訊號",
            "強度": "極端",
            "訊息": "黑天鵝確認！動用避險預備金，ARK ALL IN 級 cap $500",
            "Sylvie範例": "她 4/1 一單買 0050 正 2 2,068 股 → 後續 +53%",
            "推訊號": True,
        }
    if 黑天鵝命中 >= 3:
        return {
            "等級": "🔥 接近重押",
            "強度": "強",
            "訊息": "5 指標命中 3 個，再 1 個就確認底部，準備彈藥",
            "Sylvie範例": "等命中 4 個再動，但要先把現金備好",
            "推訊號": True,
        }
    if 黑天鵝命中 >= 2:
        return {
            "等級": "🟡 警戒區",
            "強度": "中",
            "訊息": "命中 2/5，提高觀察頻率",
            "推訊號": False,
        }
    return {
        "等級": "⚪ 正常市場",
        "強度": "弱",
        "訊息": f"VIX {vix} / F&G {fg} / 命中 {黑天鵝命中}/5 — 守紀律 DCA",
        "推訊號": False,
    }


def 強者繼續抱提醒(真倉: dict) -> list:
    """
    對已賣 50% 的持股、或接近 +12% 的持股，提醒「剩餘繼續抱衝 +30%」。
    """
    提醒清單 = []
    for p in 真倉.get("持股", []):
        if p.get("error"):
            continue
        pct = p.get("pnl_pct", 0)
        shares = p.get("shares", 0)
        if pct >= 15:
            # 達 +15% 觸發
            剩餘 = max(1, shares - max(1, shares // 2))
            提醒清單.append({
                "symbol": p["symbol"],
                "name": p.get("name", ""),
                "pnl_pct": pct,
                "建議": f"賣 {max(1, shares//2)} 股後，剩 {剩餘} 股繼續抱",
                "下一階段": "等 +30% 再賣 25% / 等 +50% 再賣 25%",
                "Sylvie範例": "她 00878 抱 17 個月 +27% 才出，強者繼續抱",
            })
        elif pct >= 12:
            # 接近 +15% 預警
            提醒清單.append({
                "symbol": p["symbol"],
                "name": p.get("name", ""),
                "pnl_pct": pct,
                "建議": f"近 +15%（差 {15-pct:.1f}%），準備分批",
                "下一階段": "達 +15% 賣 50%，剩 50% 繼續抱",
                "Sylvie範例": "她不急 +15% 就清倉，看 ARK 系統強者繼續抱",
            })
    return 提醒清單


def 取得全部教學(彈藥資訊: dict, 黑天鵝命中: int,
                  大盤資訊: dict, 真倉: dict, USD_TWD: float = 31.5) -> dict:
    """主入口：一次跑 3 個教學"""
    return {
        "DCA今日": DCA今日提醒(彈藥資訊, USD_TWD),
        "重押訊號": 重押訊號提醒(黑天鵝命中, 大盤資訊),
        "強者繼續抱": 強者繼續抱提醒(真倉),
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
    from pathlib import Path
    from dotenv import load_dotenv
    專案根 = Path(__file__).resolve().parent.parent.parent
    load_dotenv(專案根 / "API" / ".env")
    sys.path.insert(0, str(專案根 / "程式碼"))

    from modules import (capital_planner, portfolio_tracker, forex,
                          money_manager, bottom_detector, fear_greed)

    cfg = capital_planner.載入資金設定()
    USD_TWD = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32))["rate"]
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=USD_TWD)
    現金 = cfg.get("current_cash_twd", 0)
    持股市值 = 真倉["總計"]["市值_twd"]
    總資產 = 持股市值 + 現金
    彈藥 = money_manager.計算可用彈藥(
        總資金=總資產, 現金=現金, 持股成本_twd=持股市值, 目標閒錢比_pct=35)
    try:
        sop = bottom_detector.即時底部判定()
        命中 = sop.get("命中數", 0)
    except Exception:
        命中 = 0
    大盤 = {}
    try:
        fg = fear_greed.取得恐慌貪婪指數()
        大盤["fear_greed"] = fg.get("score") if fg else None
    except Exception:
        pass

    教 = 取得全部教學(彈藥, 命中, 大盤, 真倉, USD_TWD)

    print("=" * 60)
    print("🎓 Sylvie 教學提醒")
    print("=" * 60)

    print(f"\n📌 今日 DCA")
    d = 教["DCA今日"]
    print(f"   {d['提示']}")
    print(f"   建議標的：{d['推薦標的']['name']} ({d['推薦標的']['symbol']})")
    print(f"   理由：{d['推薦標的']['理由']}")
    print(f"   {d['Sylvie格言']}")

    print(f"\n💪 重押訊號")
    r = 教["重押訊號"]
    print(f"   {r['等級']} — {r['訊息']}")
    if r.get("Sylvie範例"):
        print(f"   📚 {r['Sylvie範例']}")

    print(f"\n🚀 強者繼續抱（{len(教['強者繼續抱'])} 檔）")
    for h in 教["強者繼續抱"]:
        print(f"   {h['symbol']:<10} {h['name']:<10} {h['pnl_pct']:+.2f}%")
        print(f"     → {h['建議']}")
        print(f"     📚 {h['Sylvie範例']}")
