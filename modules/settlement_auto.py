"""
T+2 自動交割（Phase 33.1）

每天 8AM 排程跑時自動執行：
  1. 檢查 portfolio.json `pending_settlement`
  2. 若 settlement_date ≤ today → 直接加進 current_cash_twd
  3. 從 pending 移除，log 進 realized_history
  4. 推 LINE 通知「資金到位」

簡化前提（user 確認）：
  - 國泰整買零賣方案，**台幣扣款 + 賣後台幣入帳**
  - 不需追蹤 USD 現金欄位
  - pending 用 net_twd 即可
"""
import json
from datetime import datetime
from pathlib import Path


專案根 = Path(__file__).resolve().parent.parent.parent
portfolio_path = 專案根 / "API" / "portfolio.json"


def 自動入帳(模擬: bool = False) -> dict:
    """
    檢查 pending_settlement，若 settlement_date ≤ today 則自動加進現金。
    模擬=True 只算不寫檔（給 UI 顯示用）。
    回傳：{已入帳[], 待入帳[], 入帳總額_twd}
    """
    if not portfolio_path.exists():
        return {"已入帳": [], "待入帳": [], "入帳總額_twd": 0}
    cfg = json.loads(portfolio_path.read_text(encoding="utf-8"))
    pending = cfg.get("pending_settlement", [])
    if not pending:
        return {"已入帳": [], "待入帳": [], "入帳總額_twd": 0}

    今天 = datetime.now().strftime("%Y-%m-%d")
    已入帳 = []
    剩餘 = []
    入帳總額 = 0
    for p in pending:
        if p.get("settlement_date", "9999") <= 今天:
            已入帳.append(p)
            入帳總額 += p.get("net_twd", 0)
        else:
            剩餘.append(p)

    if 模擬:
        return {"已入帳": 已入帳, "待入帳": 剩餘, "入帳總額_twd": 入帳總額}

    if 已入帳:
        # 真的寫檔：加進現金、清掉 pending、log realized_history
        舊現金 = cfg.get("current_cash_twd", 0)
        新現金 = 舊現金 + 入帳總額
        cfg["current_cash_twd"] = 新現金
        cfg["pending_settlement"] = 剩餘
        cfg.setdefault("settlement_history", [])
        for p in 已入帳:
            p["actual_settle_at"] = datetime.now().isoformat(timespec="seconds")
            p["cash_before_twd"] = 舊現金
            p["cash_after_twd"] = 新現金
            cfg["settlement_history"].append(p)
        portfolio_path.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return {"已入帳": 已入帳, "待入帳": 剩餘, "入帳總額_twd": 入帳總額}


def 推LINE通知(已入帳: list, 入帳總額: int) -> bool:
    """資金到位 LINE 通知"""
    if not 已入帳:
        return False
    try:
        try:
            from . import line_push
        except ImportError:
            import line_push
    except Exception:
        return False

    明細 = "\n".join(
        f"  • {p['symbol']} {p.get('shares', '?')} 股 → NT$ {p.get('net_twd', 0):+,}"
        for p in 已入帳
    )
    訊息 = (
        f"💰 LIS 資金到位（T+2 交割完成）\n"
        f"今日入帳 {len(已入帳)} 筆 / NT$ {入帳總額:,}\n"
        f"———\n{明細}\n"
        f"———\n"
        f"彈藥已釋放，等下次 LIS 訊號"
    )
    try:
        line_push.推播文字訊息(訊息)
        return True
    except Exception:
        return False


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

    print(f"=== T+2 自動交割（{datetime.now():%Y-%m-%d %H:%M}）===\n")
    r = 自動入帳(模擬=False)
    if r["已入帳"]:
        print(f"✅ 入帳 {len(r['已入帳'])} 筆 / NT$ {r['入帳總額_twd']:,}")
        for p in r["已入帳"]:
            print(f"  {p['symbol']} {p.get('shares','?')} 股 NT$ {p.get('net_twd',0):+,}")
        if 推LINE通知(r["已入帳"], r["入帳總額_twd"]):
            print("📱 已推 LINE 通知")
    else:
        print("（無到期需入帳的單）")
    if r["待入帳"]:
        print(f"\n📅 還在交割中 {len(r['待入帳'])} 筆：")
        for p in r["待入帳"]:
            print(f"  {p['symbol']} → {p['settlement_date']} (NT$ {p.get('net_twd',0):,})")
