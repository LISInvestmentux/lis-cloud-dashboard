"""
把握度折扣快速套用 CLI（Phase 33.2）

當系統建議「該買 200 股」時，但你只有 7 成把握 → 實際買 140 股。

使用方法：
  python check_conviction.py <symbol> <把握度>
  python check_conviction.py SATL 7         # 系統建議下，按 7 成套折扣
  python check_conviction.py 0050.TW 5      # 按 5 成

沒參數會列出所有 pending_orders 並讓你套折扣。
"""
import sys
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))
from dotenv import load_dotenv
load_dotenv(專案根.parent / "API" / ".env")

from modules import conviction_discount, capital_planner, technical, forex


def 互動模式():
    """列 watchlist + portfolio，讓 user 選一檔套把握度"""
    cfg = capital_planner.載入資金設定()
    USD_TWD = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32))["rate"]

    pending = cfg.get("pending_orders", [])
    if pending:
        print("\n📋 待處理掛單（pending_orders）：")
        for i, o in enumerate(pending, 1):
            print(f"  {i}. {o.get('symbol')} {o.get('action')} "
                  f"{o.get('shares')} 股 @ {o.get('price')}")

    print("\n💡 使用方法（CLI）：")
    print("  python check_conviction.py <symbol> <把握度1-10> [建議股數] [現價]")
    print("\n例：")
    print("  python check_conviction.py SATL 7 75 8.60")
    print("  python check_conviction.py 0050.TW 5 200 88")

    print("\n📊 把握度等級表：")
    for 等級, info in sorted(
            conviction_discount.等級表.items(), reverse=True):
        print(f"  {等級:2d}/10  {info['標籤']:6s}  ×{info['倍率']:.1f}  — {info['解釋']}")


def 套折扣(symbol: str, 把握度: int, 建議股數: int = None,
            現價: float = None):
    """套把握度折扣，回傳建議"""
    cfg = capital_planner.載入資金設定()
    USD_TWD = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32))["rate"]
    是美股 = not (symbol.endswith(".TW") or symbol.endswith(".TWO"))

    # 試從 pending_orders 找
    pending = cfg.get("pending_orders", [])
    for o in pending:
        if o.get("symbol") == symbol:
            if 建議股數 is None:
                建議股數 = o.get("shares", 0)
            if 現價 is None:
                現價 = o.get("price")
            break

    # 還是沒有就抓現價
    if 現價 is None:
        try:
            歷史, _ = technical.取得每日股價(symbol, period="2d")
            if 歷史:
                現價 = 歷史[0]["close"]
        except Exception:
            現價 = 0

    if 建議股數 is None or 建議股數 == 0:
        print(f"❌ 找不到 {symbol} 的建議股數，請手動指定")
        return

    print(f"\n📊 把握度折扣 — {symbol}")
    print("=" * 50)
    print(f"  系統建議：{建議股數} 股 @ {'$' if 是美股 else 'NT$'}{現價:.2f}")
    print(f"  把握度：{把握度} / 10")

    r = conviction_discount.套折扣股數(建議股數, 把握度)
    print(f"\n  → 實際建議：{r['建議股數']} 股")
    print(f"  少買：{r['折扣股數']} 股")
    print(f"  {r['解釋']}")

    if 現價:
        貨幣 = "$" if 是美股 else "NT$"
        實際金額 = r["建議股數"] * 現價
        twd = 實際金額 * USD_TWD if 是美股 else 實際金額
        print(f"  實際金額：{貨幣}{實際金額:.2f}")
        if 是美股:
            print(f"           ≈ NT$ {twd:,.0f}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        互動模式()
    else:
        symbol = sys.argv[1]
        try:
            把握度 = int(sys.argv[2])
        except ValueError:
            print("❌ 把握度必須是 0-10 整數")
            sys.exit(1)
        建議股數 = int(sys.argv[3]) if len(sys.argv) > 3 else None
        現價 = float(sys.argv[4]) if len(sys.argv) > 4 else None
        套折扣(symbol, 把握度, 建議股數, 現價)
