"""
快速加待掛單 CLI（Phase 41 — 5/16）

用法：
  python add_pending_order.py BUY  NVDA 1 225.50 [備註]
  python add_pending_order.py SELL SATL 19 9.84 +15% Strategy D
  python add_pending_order.py BUY  0050.TW 100 88.5 [備註]

自動偵測 .TW/.TWO 後綴設定 market="TW"，否則 market="US"。
寫入 portfolio.json 的 pending_orders + 自動 sync Gist。

防忘刪單建議：
  1. 在國泰 App 掛單後立刻跑這個 CLI 記錄
  2. 主卡每天會顯示「⏰ 待掛單 N 筆」提醒
  3. 成交後手動跑 python rm_pending_order.py <symbol> 移除
"""
import sys
import json
from datetime import datetime
from pathlib import Path

專案根 = Path(__file__).resolve().parent.parent
PORTFOLIO_PATH = 專案根 / "API" / "portfolio.json"


def 加入單(action: str, symbol: str, shares: float, price: float,
            note: str = "") -> None:
    if action.upper() not in ("BUY", "SELL"):
        print(f"❌ action 必須是 BUY 或 SELL，目前 {action}")
        sys.exit(1)

    symbol_upper = symbol.upper()
    is_tw = symbol_upper.endswith(".TW") or symbol_upper.endswith(".TWO")
    market = "TW" if is_tw else "US"
    currency = "NT$" if is_tw else "$"

    new_order = {
        "symbol": symbol_upper,
        "market": market,
        "action": action.upper(),
        "shares": int(shares) if shares == int(shares) else shares,
        "price": float(price),
        "order_type": "LIMIT",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "note": note or f"手動加入：{action.upper()} {currency}{price}",
    }

    # 讀現有 portfolio.json
    cfg = json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
    pending = cfg.get("pending_orders", []) or []

    # 檢查重複（同 symbol + action + price）
    for o in pending:
        if (o.get("symbol") == symbol_upper
                and o.get("action") == action.upper()
                and abs(o.get("price", 0) - float(price)) < 0.01):
            print(f"⚠️ 重複單：{symbol_upper} {action} @ {currency}{price}")
            print(f"   現有 note: {o.get('note', '')}")
            resp = input("仍要加？(y/N): ").strip().lower()
            if resp != "y":
                sys.exit(0)

    pending.append(new_order)
    cfg["pending_orders"] = pending

    # 寫回
    PORTFOLIO_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8")

    print(f"✅ 加入待掛單：")
    print(f"   {action.upper()} {symbol_upper} {shares} 股 @ {currency}{price}")
    print(f"   市場: {market}")
    print(f"   備註: {new_order['note']}")
    print(f"   目前共 {len(pending)} 筆待掛單")

    # 自動 sync Gist
    try:
        sys.path.insert(0, str(專案根 / "程式碼"))
        import sync_to_gist
        if sync_to_gist.自動同步(silent=False):
            print("☁️  已同步 Gist")
    except Exception as e:
        print(f"⚠️ Gist sync 失敗（不影響本機）: {e}")


def 用法():
    print("用法:")
    print("  python add_pending_order.py BUY  <symbol> <shares> <price> [備註]")
    print("  python add_pending_order.py SELL <symbol> <shares> <price> [備註]")
    print()
    print("範例:")
    print("  python add_pending_order.py BUY  NVDA 1 225.50 跌深加碼")
    print("  python add_pending_order.py SELL SATL 19 9.84 達+15% Strategy D")
    print("  python add_pending_order.py BUY  0050.TW 100 88.5 月扣定期定額")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if len(sys.argv) < 5:
        用法()
        sys.exit(1)

    action = sys.argv[1]
    symbol = sys.argv[2]
    shares = float(sys.argv[3])
    price = float(sys.argv[4])
    note = " ".join(sys.argv[5:]) if len(sys.argv) > 5 else ""

    加入單(action, symbol, shares, price, note)
