"""推 ARK 策略池 carousel 到 LINE"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))

from dotenv import load_dotenv
load_dotenv(專案根.parent / "API" / ".env")

from modules import (strategy_pool, line_push, fugle_market,
                     capital_planner)


if __name__ == "__main__":
    cfg = capital_planner.載入資金設定()
    現金 = cfg.get("current_cash_twd", 0)
    持股集 = {p["symbol"] for p in cfg.get("current_positions", [])
              if p.get("symbol") != "AGGREGATE"}
    DCA清單 = [it["symbol"] for it in
                cfg.get("long_term_dca", {}).get("items", [])
                if it.get("symbol")]

    # 即時報價（給卡片用）
    def 取得現價(sym):
        q = fugle_market.即時報價_fallback(sym)
        return q.get("close") if q else None

    全部 = strategy_pool.組裝標的清單(取得現價=取得現價)

    # 大盤 + 黑天鵝（簡化版）
    大盤 = {"VIX": None, "fear_greed_score": None}
    黑天鵝 = None

    結果 = strategy_pool.掃描策略池(
        全部, 大盤=大盤, 黑天鵝=黑天鵝,
        持股代號集=持股集, DCA清單=DCA清單,
    )

    print("=== ARK 風策略池掃描 ===")
    for 名, 設 in 結果.items():
        if 設["總數"] > 0:
            print(f"  {設['emoji']} {名:<18} {設['總數']} 檔")

    carousel = strategy_pool.建構策略池Carousel(結果, 現金=現金)
    if not carousel:
        print("⚠️ 沒有策略入選")
        sys.exit(0)

    sum_count = sum(設["總數"] for 設 in 結果.values())
    alt = f"🎯 ARK 策略池 — 6 策略共入選 {sum_count} 檔"
    line_push.推播Flex訊息(替代文字=alt, flex內容=carousel)
    print(f"\n✅ 推到 LINE — {alt}")
