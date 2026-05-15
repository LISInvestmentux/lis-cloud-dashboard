"""
處置股檢查端到端測試（Phase 8.0d）
注入 1597.TW（直得，目前正在處置中）作為 BUY 訊號，驗證：
1. 訊號 reason 應該標記「處置股」
2. exec_price 應該明顯比一般滑價貴（用 2.5×）
"""
import sqlite3
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))

from modules import sim_ledger

# 清空 DB
DB = sim_ledger.資料庫路徑
conn = sqlite3.connect(str(DB))
conn.execute("DELETE FROM signals")
conn.execute("DELETE FROM strategy_results")
conn.commit()
conn.close()
print(f"[清空] {DB}")

# 注入兩檔模擬 BUY 訊號：
# 一檔處置股（1597 直得）+ 一檔正常股（2330 台積電）
測試樣本 = [
    {
        "symbol": "1597.TW", "name": "直得（處置股）",
        "_region": "tw_stocks",
        "close": 50.0, "open": 49.5, "high": 51.0, "low": 49.0,
        "prev_close": 50.0,
        "shakeout_low": True,
        "shakeout_reasons": ["測試樣本"],
        "bull_signal": False, "shit_signal": False,
    },
    {
        "symbol": "2330.TW", "name": "台積電（對照組）",
        "_region": "tw_stocks",
        "close": 1250.0, "open": 1240.0, "high": 1260.0, "low": 1235.0,
        "prev_close": 1245.0,
        "shakeout_low": True,
        "shakeout_reasons": ["測試樣本"],
        "bull_signal": False, "shit_signal": False,
    },
]

結果 = sim_ledger.寫入今日全部訊號(
    全部個股=測試樣本,
    enjoy_index_總分=50,
    每檔預算=32000,
)

print(f"\n=== 寫入結果 ===")
for k, v in 結果.items():
    print(f"  {k:>12}: {v}")

print(f"\n=== 處置股 vs 對照組訊號 ===")
for sym, 標籤 in [("1597.TW", "處置股"), ("2330.TW", "對照組")]:
    rows = sim_ledger.查詢個股歷史(sym, 上限=1)
    if not rows:
        print(f"  {sym} 找不到")
        continue
    r = rows[0]
    # 滑價多少 %
    滑價_pct = (r["assumed_exec_price"] / r["signal_price"] - 1) * 100
    print(f"  {sym} [{標籤}]:")
    print(f"    type={r['signal_type']}, 訊號價={r['signal_price']} → "
          f"成交價={r['assumed_exec_price']}")
    print(f"    含滑價：+{滑價_pct:.2f}%（一般 0.15%、處置 0.375%）")
    print(f"    reason: {r['trigger_reason']}")
