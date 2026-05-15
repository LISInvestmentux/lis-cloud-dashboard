"""
待掛單提醒（Phase 33.2）

每天 21:25（美股開盤前 5 分鐘）推 LINE 提醒 user 該掛的單。
解決問題：國泰 GTC 需要 $5000+ 門檻，小單需每天手動掛。

存在 portfolio.json `pending_orders` 欄位：
[
  {symbol, market, action, shares, price, order_type,
   rule, note, created_at, note2(可選)}
]

執行：
  python -m modules.order_reminder
"""
import json
from datetime import datetime
from pathlib import Path


專案根 = Path(__file__).resolve().parent.parent.parent
portfolio_path = 專案根 / "API" / "portfolio.json"


def 取得待掛單(filter_market: str = None) -> list:
    """讀取 portfolio.json 的 pending_orders（可篩市場 US/TW）"""
    if not portfolio_path.exists():
        return []
    cfg = json.loads(portfolio_path.read_text(encoding="utf-8"))
    orders = cfg.get("pending_orders", [])
    if filter_market:
        orders = [o for o in orders if o.get("market") == filter_market]
    return orders


def 推美股盤前提醒() -> int:
    """21:25 推 LINE 提醒美股待掛單"""
    us_orders = 取得待掛單(filter_market="US")
    if not us_orders:
        print("無美股待掛單")
        return 0

    try:
        try:
            from . import line_push
        except ImportError:
            import line_push
    except Exception as e:
        print(f"無法 import line_push: {e}")
        return 1

    片段 = [f"⏰ 美股盤前 5 分鐘提醒（{datetime.now():%H:%M}）",
              f"美股 21:30 開盤，請手動掛 {len(us_orders)} 筆單：\n"]
    for o in us_orders:
        片段.append(f"━━━━━━━━━━━━━━━━")
        片段.append(f"📌 {o.get('symbol')} — {o.get('action')}")
        片段.append(f"   股數：{o.get('shares')}")
        片段.append(f"   價格：${o.get('price'):.2f} {o.get('order_type', 'LIMIT')}")
        if o.get('rule'):
            片段.append(f"   規則：{o.get('rule')}")
        if o.get('note'):
            片段.append(f"   備註：{o.get('note')}")

    片段.append("━━━━━━━━━━━━━━━━")
    片段.append("🎯 開國泰複委託 App → 美股 → 下單")
    片段.append("⚠️ GTC 需 $5000+，小單請改「當日有效」")

    訊息 = "\n".join(片段)
    try:
        line_push.推播文字訊息(訊息)
        print("✅ 已推美股盤前提醒")
        return 0
    except Exception as e:
        print(f"❌ 推播失敗：{e}")
        return 1


def 推台股盤前提醒() -> int:
    """08:55 推 LINE 提醒台股待掛單（盤前 5 分鐘）"""
    tw_orders = 取得待掛單(filter_market="TW")
    if not tw_orders:
        return 0

    try:
        try:
            from . import line_push
        except ImportError:
            import line_push
    except Exception:
        return 1

    片段 = [f"⏰ 台股盤前提醒（{datetime.now():%H:%M}）",
              f"台股 09:00 開盤，請掛 {len(tw_orders)} 筆單：\n"]
    for o in tw_orders:
        片段.append(f"━━━━━━━━━━━━━━━━")
        片段.append(f"📌 {o.get('symbol')} — {o.get('action')}")
        片段.append(f"   股數：{o.get('shares')}")
        片段.append(f"   價格：NT$ {o.get('price'):.2f} {o.get('order_type', 'LIMIT')}")
        if o.get('rule'):
            片段.append(f"   規則：{o.get('rule')}")
    片段.append("━━━━━━━━━━━━━━━━")

    訊息 = "\n".join(片段)
    try:
        line_push.推播文字訊息(訊息)
        return 0
    except Exception:
        return 1


def 移除已成交(symbol: str, market: str = None) -> bool:
    """成交後從 pending_orders 移除"""
    cfg = json.loads(portfolio_path.read_text(encoding="utf-8"))
    舊 = cfg.get("pending_orders", [])
    新 = [o for o in 舊
            if not (o.get("symbol") == symbol
                    and (market is None or o.get("market") == market))]
    cfg["pending_orders"] = 新
    portfolio_path.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return len(舊) - len(新) > 0


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

    mode = sys.argv[1] if len(sys.argv) > 1 else "us"
    if mode == "us":
        sys.exit(推美股盤前提醒())
    elif mode == "tw":
        sys.exit(推台股盤前提醒())
    elif mode == "all":
        rc1 = 推美股盤前提醒()
        rc2 = 推台股盤前提醒()
        sys.exit(rc1 + rc2)
    elif mode == "list":
        orders = 取得待掛單()
        print(f"=== 待掛單共 {len(orders)} 筆 ===")
        for o in orders:
            print(f"  {o.get('symbol'):<10} {o.get('action')} {o.get('shares')} @ {o.get('price')}")
    else:
        print("用法: python -m modules.order_reminder [us|tw|all|list]")
        sys.exit(1)
