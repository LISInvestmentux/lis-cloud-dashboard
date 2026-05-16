"""快速移除待掛單 CLI（Phase 41）

用法：
  python rm_pending_order.py NVDA              # 移除所有 NVDA 待掛單
  python rm_pending_order.py NVDA BUY          # 移除 NVDA BUY 單（保留 SELL）
  python rm_pending_order.py --list            # 列出所有待掛單
"""
import sys
import json
from pathlib import Path

專案根 = Path(__file__).resolve().parent.parent
PORTFOLIO_PATH = 專案根 / "API" / "portfolio.json"


def 列出():
    cfg = json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
    pending = cfg.get("pending_orders", []) or []
    print(f"📋 待掛單共 {len(pending)} 筆：")
    for i, o in enumerate(pending, 1):
        sym = o.get("symbol", "?")
        market = o.get("market", "TW")
        符 = "$" if market == "US" else "NT$"
        action = o.get("action", "?")
        shares = o.get("shares", 0)
        price = o.get("price", 0)
        created = o.get("created_at", "")
        note = o.get("note", "")[:40]
        print(f"  {i}. {sym} {action} {shares} 股 @ {符}{price}")
        print(f"     建立 {created} · {note}")


def 移除(symbol: str, action: str = None):
    cfg = json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
    pending = cfg.get("pending_orders", []) or []
    symbol_upper = symbol.upper()

    before = len(pending)
    if action:
        kept = [o for o in pending
                if not (o.get("symbol") == symbol_upper
                        and o.get("action") == action.upper())]
    else:
        kept = [o for o in pending if o.get("symbol") != symbol_upper]
    removed = before - len(kept)

    if removed == 0:
        print(f"⚠️ 找不到 {symbol_upper}" + (f" {action}" if action else ""))
        sys.exit(1)

    cfg["pending_orders"] = kept
    PORTFOLIO_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8")

    print(f"✅ 移除 {removed} 筆 {symbol_upper}" + (f" {action}" if action else "") + " 待掛單")
    print(f"   剩 {len(kept)} 筆")

    # Sync
    try:
        sys.path.insert(0, str(專案根 / "程式碼"))
        import sync_to_gist
        sync_to_gist.自動同步(silent=False)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if len(sys.argv) < 2:
        print("用法: python rm_pending_order.py <symbol> [BUY|SELL]")
        print("      python rm_pending_order.py --list")
        sys.exit(1)

    if sys.argv[1] == "--list":
        列出()
    else:
        symbol = sys.argv[1]
        action = sys.argv[2] if len(sys.argv) > 2 else None
        移除(symbol, action)
