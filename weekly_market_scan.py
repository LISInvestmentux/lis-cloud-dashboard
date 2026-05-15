"""
每週全市場自動發現選股（Phase 10）
週日跑一次，掃 200 檔候選池找黃金錯殺，結果存檔給 main.py 讀。

執行方式：
  .venv\\Scripts\\python.exe weekly_market_scan.py

Windows 排程任務：
  LIS_Weekly_MarketScan: 每週日 07:30（在 08:00 main.py 之前）
"""
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))

from dotenv import load_dotenv
load_dotenv(專案根.parent / "API" / ".env")

from modules import market_scanner, capital_planner


數據根 = 專案根.parent / "數據"
結果路徑 = 數據根 / "market_scan_latest.json"


def 主流程() -> int:
    開始 = datetime.now()
    print(f"=== 全市場掃描 [{開始:%Y-%m-%d %H:%M:%S}] ===")

    cfg = capital_planner.載入資金設定()
    結果 = market_scanner.掃描全市場(cfg, Top_N=10, 延遲秒=0.3)

    print(f"\n=== 掃描結果 ===")
    print(f"  掃描總數：{結果['掃描總數']}")
    print(f"  排除已知：{結果['排除數']}")
    print(f"  錯誤數：{結果['錯誤數']}")
    print(f"  有訊號：{len(結果.get('全部', []))}")
    print(f"  Top {len(結果['Top'])}：")
    for r in 結果["Top"]:
        條件 = ", ".join(r["條件"])
        print(f"    {r['symbol']:>12} {r.get('name', ''):<15} "
              f"{r['分數']:>3} 分: {條件}")

    # 存檔（給 main.py 讀）
    payload = {
        "updated_at": 開始.isoformat(timespec="seconds"),
        **結果,
    }
    結果路徑.parent.mkdir(parents=True, exist_ok=True)
    with open(結果路徑, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 結果已存：{結果路徑}")

    耗時 = (datetime.now() - 開始).total_seconds()
    print(f"耗時 {耗時:.0f} 秒（約 {耗時/60:.1f} 分鐘）")
    return 0


if __name__ == "__main__":
    sys.exit(主流程())
