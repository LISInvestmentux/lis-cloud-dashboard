"""
本金注入歷史記錄（Phase 32.5）

用途：每次 user 從外帳轉錢進證券戶，記錄一筆「投資本金注入」。
未來算「淨投資報酬」= (總資產 - 累計注入) / 累計注入

存放：portfolio.json 的 `capital_inflow_history` 欄位
格式：[{date, amount_twd, note, recorded_at}, ...]
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
portfolio_path = 專案根 / "API" / "portfolio.json"


def 載入歷史() -> list:
    if not portfolio_path.exists():
        return []
    cfg = json.loads(portfolio_path.read_text(encoding="utf-8"))
    return cfg.get("capital_inflow_history", [])


def 加入注入(金額: int, 日期: Optional[str] = None,
              備註: str = "") -> dict:
    """
    記錄一筆本金注入。
    金額: 正數 = 注入；負數 = 提領（賺到拿出來）
    日期: YYYY-MM-DD；None = 今天
    """
    日 = 日期 or datetime.now().strftime("%Y-%m-%d")
    cfg = json.loads(portfolio_path.read_text(encoding="utf-8"))
    cfg.setdefault("capital_inflow_history", [])
    entry = {
        "date": 日,
        "amount_twd": int(金額),
        "note": 備註,
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    }
    cfg["capital_inflow_history"].append(entry)
    cfg["capital_inflow_history"].sort(key=lambda e: e.get("date", ""))
    portfolio_path.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return entry


def 總注入() -> dict:
    """回傳累計注入摘要"""
    歷史 = 載入歷史()
    total = sum(e.get("amount_twd", 0) for e in 歷史)
    return {
        "累計注入_twd": total,
        "筆數": len(歷史),
        "首筆日期": 歷史[0]["date"] if 歷史 else None,
        "最新日期": 歷史[-1]["date"] if 歷史 else None,
        "明細": 歷史,
    }


def 算淨報酬(總資產_twd: float) -> dict:
    """
    淨投資報酬 = (總資產 - 累計注入) / 累計注入 × 100
    需要先有 capital_inflow_history 才能算。
    """
    摘要 = 總注入()
    累計 = 摘要["累計注入_twd"]
    if 累計 <= 0:
        return {"可計算": False, "原因": "尚無注入紀錄"}
    淨損益 = 總資產_twd - 累計
    return {
        "可計算": True,
        "累計注入_twd": 累計,
        "目前總資產_twd": 總資產_twd,
        "淨損益_twd": round(淨損益, 0),
        "淨報酬率_pct": round(淨損益 / 累計 * 100, 2),
        "筆數": 摘要["筆數"],
    }


# ─────────────────────────────────────────────
# CLI（互動模式）
# ─────────────────────────────────────────────
def 主CLI():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=" * 50)
    print("📥 LIS 本金注入記錄")
    print("=" * 50)

    摘要 = 總注入()
    print(f"\n目前累計注入：NT$ {摘要['累計注入_twd']:,}（{摘要['筆數']} 筆）")
    if 摘要["筆數"] > 0:
        print(f"  首筆 {摘要['首筆日期']} → 最新 {摘要['最新日期']}")

    print("\n[1] 新增一筆")
    print("[2] 查看歷史")
    print("[3] 退出")
    選 = input("\n選擇 [1/2/3]: ").strip()

    if 選 == "1":
        try:
            金額_str = input("注入金額 NT$（正數=轉入，負數=提領）: ").strip()
            金額 = int(金額_str.replace(",", ""))
        except ValueError:
            print("❌ 金額格式錯誤")
            return

        日期_str = input("日期 YYYY-MM-DD（按 Enter 用今天）: ").strip()
        if 日期_str:
            try:
                datetime.strptime(日期_str, "%Y-%m-%d")
            except ValueError:
                print("❌ 日期格式錯誤")
                return
            日期 = 日期_str
        else:
            日期 = None

        備註 = input("備註（選填）: ").strip()

        e = 加入注入(金額, 日期=日期, 備註=備註)
        print(f"\n✅ 已記錄：{e['date']}  NT$ {e['amount_twd']:+,}  {e['note']}")

        摘要 = 總注入()
        print(f"📊 更新後累計：NT$ {摘要['累計注入_twd']:,}（{摘要['筆數']} 筆）")

    elif 選 == "2":
        歷史 = 載入歷史()
        if not 歷史:
            print("\n（無紀錄）")
        else:
            print(f"\n📋 共 {len(歷史)} 筆：")
            for e in 歷史:
                note = f"  // {e.get('note','')}" if e.get("note") else ""
                print(f"  {e['date']}  NT$ {e['amount_twd']:+,}{note}")
            print(f"\n小計：NT$ {sum(e['amount_twd'] for e in 歷史):,}")
    else:
        print("退出")


if __name__ == "__main__":
    主CLI()
