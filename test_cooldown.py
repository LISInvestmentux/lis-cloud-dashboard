"""
冷靜期過濾測試（Phase 8.0c）
1. 清空 DB
2. 灌入今日快照（會有 6 檔 BUY）
3. 對其中一檔（南亞 1303.TW）偽造「3 天前剛 STOP_LOSS 出場」紀錄
4. 再灌一次今日快照，驗證該檔變 WATCH
"""
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))

from modules import sim_ledger

# 1. 清空
DB = sim_ledger.資料庫路徑
conn = sqlite3.connect(str(DB))
conn.execute("DELETE FROM signals")
conn.execute("DELETE FROM strategy_results")
conn.commit()
conn.close()
print(f"[清空] {DB}")

# 2. 偽造一筆 3 天前剛 STOP_LOSS 出場的 1303.TW 紀錄
三天前 = (datetime.now() - timedelta(days=3))
三天前_str = 三天前.strftime("%Y-%m-%d")
七天前 = (datetime.now() - timedelta(days=7))
七天前_str = 七天前.strftime("%Y-%m-%d")

conn = sqlite3.connect(str(DB))
conn.execute("""
    INSERT INTO signals (
        signal_time, symbol, name, market,
        signal_type, trigger_reason,
        signal_price, assumed_exec_price, friction_cost_pct,
        closed_date, closed_price, closed_reason, realized_pnl_pct
    ) VALUES (?, '1303.TW', '南亞', 'TW',
              'BUY', '測試偽造紀錄',
              90.0, 90.14, 0.00471,
              ?, 85.0, 'STOP_LOSS', -6.0)
""", (七天前_str + "T08:00:00", 三天前_str))
conn.commit()
conn.close()
print(f"[偽造] 1303.TW 在 {三天前_str} 觸發 STOP_LOSS（3 天前）")

# 3. 載入今日快照
快照路徑 = 專案根.parent / "數據" / "daily" / "2026-05-13.json"
with open(快照路徑, "r", encoding="utf-8") as f:
    快照 = json.load(f)

全部個股 = []
for 區id, items in 快照["regions"].items():
    for r in items:
        r2 = dict(r)
        r2["_region"] = 區id
        全部個股.append(r2)

# 4. 灌入今日訊號
結果 = sim_ledger.寫入今日全部訊號(
    全部個股=全部個股,
    enjoy_index_總分=快照["enjoy_index"]["總分"],
    每檔預算=32000,
)
print(f"\n=== 寫入結果 ===")
for k, v in 結果.items():
    print(f"  {k:>12}: {v}")

# 5. 驗證 1303.TW 今日訊號是否被降級
今日訊號 = sim_ledger.查詢個股歷史("1303.TW", 上限=5)
print(f"\n=== 1303.TW 訊號歷史（最近 5 筆，含偽造）===")
for r in 今日訊號:
    closed = r.get("closed_date") or "未平倉"
    print(f"  signal_time={r['signal_time'][:10]} "
          f"type={r['signal_type']:>5} "
          f"closed={closed}")
    if r.get("trigger_reason"):
        print(f"    reason={r['trigger_reason']}")

# 6. 驗證一檔「沒有冷靜期」的 BUY 訊號還是 BUY（對照）
未平倉 = sim_ledger.查詢未平倉()
print(f"\n=== 今日仍為 BUY 的訊號（前 5）===")
for r in 未平倉[:5]:
    print(f"  {r['symbol']:>12} ({r['name']}) "
          f"type={r['signal_type']:>5}")
