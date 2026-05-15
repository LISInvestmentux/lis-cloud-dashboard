"""
從歷史快照重灌模擬盤 ledger（Phase 8.0）
用途：
  - 第一次部署模擬盤時，把過去幾天的 daily snapshot 灌進 DB
  - 主程式跑壞時手動補資料
  - 修改策略邏輯後重新跑歷史對照

執行：
  python seed_ledger_from_snapshot.py             # 灌今天的快照
  python seed_ledger_from_snapshot.py 2026-05-12  # 灌指定日期
  python seed_ledger_from_snapshot.py --all       # 灌所有快照
  python seed_ledger_from_snapshot.py --reset     # 清空 DB 後灌今天
"""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))

from modules import sim_ledger


數據根 = 專案根.parent / "數據"
每日資料夾 = 數據根 / "daily"


def _清空DB() -> None:
    DB = sim_ledger.資料庫路徑
    if not DB.exists():
        return
    conn = sqlite3.connect(str(DB))
    conn.execute("DELETE FROM signals")
    conn.execute("DELETE FROM strategy_results")
    conn.commit()
    conn.close()
    print(f"[清空] {DB}（主表 + 策略副表）")


def _載入快照(日期: str) -> dict:
    路徑 = 每日資料夾 / f"{日期}.json"
    if not 路徑.exists():
        raise FileNotFoundError(f"找不到 {路徑}")
    with open(路徑, "r", encoding="utf-8") as f:
        return json.load(f)


def _合併個股(快照: dict) -> list[dict]:
    """模擬 main.py 的 _合併個股"""
    全部 = []
    for 區id, items in 快照["regions"].items():
        for r in items:
            r2 = dict(r)
            r2["_region"] = 區id
            全部.append(r2)
    return 全部


def 灌一天(日期: str, 預算: int = 32000) -> dict:
    """灌一天的快照到 ledger。"""
    快照 = _載入快照(日期)
    全部個股 = _合併個股(快照)
    enjoy總分 = 快照.get("enjoy_index", {}).get("總分")
    pushed = 快照.get("generated_at")

    結果 = sim_ledger.寫入今日全部訊號(
        全部個股=全部個股,
        enjoy_index_總分=enjoy總分,
        每檔預算=預算,
        pushed_time=pushed,
    )
    return 結果


def 列出所有快照() -> list[str]:
    """回傳 daily/ 下所有快照日期（按時間排）。"""
    if not 每日資料夾.exists():
        return []
    日期清單 = []
    for f in 每日資料夾.glob("*.json"):
        # 跳過 kol_*.json 之類的非主快照
        name = f.stem
        if name.startswith("kol_"):
            continue
        try:
            datetime.strptime(name, "%Y-%m-%d")
            日期清單.append(name)
        except ValueError:
            pass
    return sorted(日期清單)


def 主流程(args: list[str]) -> int:
    if "--reset" in args:
        _清空DB()
        args = [a for a in args if a != "--reset"]

    日期清單 = []
    if "--all" in args:
        日期清單 = 列出所有快照()
        print(f"[全部模式] 找到 {len(日期清單)} 個快照")
    elif args:
        日期清單 = [args[0]]
    else:
        日期清單 = [datetime.now().strftime("%Y-%m-%d")]

    總計 = {"BUY": 0, "WATCH": 0, "NONE": 0, "失敗": 0,
             "跳空漲停": 0, "跳空跌停": 0}

    for 日期 in 日期清單:
        try:
            print(f"\n灌入 {日期}...")
            結果 = 灌一天(日期)
            for k, v in 結果.items():
                總計[k] = 總計.get(k, 0) + v
                print(f"  {k:>10}: {v}")
        except FileNotFoundError as e:
            print(f"  ⚠️ {e}")
        except Exception as e:
            print(f"  ❌ 錯誤：{e}")
            import traceback
            traceback.print_exc()

    print(f"\n=== 灌入總計 ===")
    for k, v in 總計.items():
        print(f"  {k:>10}: {v}")

    print(f"\n=== Ledger 狀態 ===")
    for k, v in sim_ledger.統計概覽().items():
        print(f"  {k:>14}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(主流程(sys.argv[1:]))
