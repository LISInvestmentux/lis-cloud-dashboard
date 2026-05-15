"""
模擬盤 ledger 端到端測試（Phase 8.0a）
1. 清空 ledger
2. 用今日快照 + 手動模擬一檔跳空漲停 + 一檔跳空跌停 → 驗證可成交性檢查
3. 列出 BUY 與 WATCH 統計
"""
import json
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

# ─── 0. 清空 ledger（保留 schema）───
DB = sim_ledger.資料庫路徑
if DB.exists():
    conn = sqlite3.connect(str(DB))
    conn.execute("DELETE FROM signals")
    conn.execute("DELETE FROM strategy_results")
    conn.commit()
    conn.close()
    print(f"[清空] {DB}（主表 + 策略副表）")

# ─── 1. 載入今日快照 ───
快照路徑 = 專案根.parent / "數據" / "daily" / "2026-05-13.json"
with open(快照路徑, "r", encoding="utf-8") as f:
    快照 = json.load(f)

全部個股 = []
for 區id, items in 快照["regions"].items():
    for r in items:
        r2 = dict(r)
        r2["_region"] = 區id
        全部個股.append(r2)

# ─── 2. 注入測試樣本：模擬跳空漲停 / 跌停 ───
# 注意：今日快照是舊版 technical 產出（沒有 open/high/low/prev_close 欄位），
# 所以這次主要看「注入樣本」是否觸發可成交性檢查
全部個股.append({
    "symbol": "TEST_LIMIT_UP.TW",
    "name": "測試跳空漲停股",
    "_region": "tw_stocks",
    "close": 110.0,
    "open": 110.0,       # 開盤就 +10%
    "high": 110.0,
    "low": 110.0,
    "prev_close": 100.0,  # 昨收
    "shakeout_low": True,
    "shakeout_reasons": ["測試樣本"],
    "bull_signal": False,
    "shit_signal": False,
})
全部個股.append({
    "symbol": "TEST_LIMIT_DOWN.TW",
    "name": "測試跳空跌停股",
    "_region": "tw_stocks",
    "close": 90.0,
    "open": 90.0,        # 開盤就 -10%
    "high": 92.0,
    "low": 90.0,
    "prev_close": 100.0,
    "shakeout_low": True,
    "shakeout_reasons": ["測試樣本"],
    "bull_signal": False,
    "shit_signal": False,
})
全部個股.append({
    "symbol": "TEST_NORMAL.TW",
    "name": "測試正常股",
    "_region": "tw_stocks",
    "close": 102.0,
    "open": 100.5,
    "high": 102.5,
    "low": 100.0,
    "prev_close": 100.0,
    "shakeout_low": True,
    "shakeout_reasons": ["測試樣本"],
    "bull_signal": False,
    "shit_signal": False,
})

print(f"載入：{len(全部個股)} 檔（含 3 檔測試樣本）")

結果 = sim_ledger.寫入今日全部訊號(
    全部個股=全部個股,
    enjoy_index_總分=快照["enjoy_index"]["總分"],
    每檔預算=32000,
)

print(f"\n=== 寫入結果 ===")
for k, v in 結果.items():
    print(f"  {k:>10}: {v}")

print(f"\n=== 統計概覽 ===")
for k, v in sim_ledger.統計概覽().items():
    print(f"  {k:>14}: {v}")

print(f"\n=== 測試樣本訊號驗證 ===")
for sym in ["TEST_LIMIT_UP.TW", "TEST_LIMIT_DOWN.TW", "TEST_NORMAL.TW"]:
    rows = sim_ledger.查詢個股歷史(sym, 1)
    if not rows:
        print(f"  ❌ {sym} 未找到")
        continue
    r = rows[0]
    print(f"  {r['symbol']:>22}: type={r['signal_type']:>6} "
          f"訊號價={r['signal_price']:>6.2f} → 成交價={r['assumed_exec_price']:>6.2f} "
          f"摩擦={r['friction_cost_pct']*100:.3f}%")
    print(f"  {'':>22}  reason={r['trigger_reason']}")

print(f"\n=== 真實 BUY 訊號（前 5）===")
for r in sim_ledger.查詢未平倉()[:5]:
    if r["symbol"].startswith("TEST_"):
        continue
    print(f"  {r['symbol']:>12} ({r['name']}) "
          f"訊號={r['signal_price']:>7.2f} 成交={r['assumed_exec_price']:>7.2f} "
          f"建議={r['suggested_shares']}股 | {r['trigger_reason']}")
