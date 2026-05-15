"""
盤中多時段推播（Phase 26.3）

每天自動跑 3 次（盤中關鍵時刻）：
  10:30 — 開盤後 1 小時，看當日方向
  12:00 — 午盤後，看是否有翻轉
  13:20 — 收盤前 10 分鐘，最後決策窗口

每次推「即時決策 + 策略池變動」carousel 到 LINE。

排程方式（Task Scheduler）：
  schtasks /create /sc DAILY /tn "LIS_盤中_10:30" /tr "..." /st 10:30
  ...
"""
import sys
from pathlib import Path
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))

from dotenv import load_dotenv
load_dotenv(專案根.parent / "API" / ".env")


def 主流程():
    """盤中執行 → 跑即時決策 + 策略池 → 推 LINE"""
    現在 = datetime.now()
    時段標籤 = "盤中早盤"
    if 現在.hour >= 13:
        時段標籤 = "盤中收前"
    elif 現在.hour >= 12:
        時段標籤 = "盤中午盤"
    elif 現在.hour >= 10:
        時段標籤 = "盤中早盤"

    print(f"=== 盤中掃描 ({時段標籤}) {現在:%H:%M} ===")

    # 1. 跑 instant_decision
    import subprocess
    print("執行 instant_decision...")
    r = subprocess.run(
        [str(專案根 / ".venv/Scripts/python.exe"), "instant_decision.py"],
        cwd=str(專案根), capture_output=True, text=True, encoding="utf-8"
    )
    if r.returncode == 0:
        print("✅ instant_decision 推送成功")
    else:
        print(f"❌ instant_decision 失敗: {r.stderr[:200]}")

    # 2. 跑 strategy_pool push（不要太密集，避免 LINE 限流）
    if 現在.hour in (10, 13):  # 只在早盤+收前推策略池
        print("執行 strategy_pool...")
        r = subprocess.run(
            [str(專案根 / ".venv/Scripts/python.exe"), "push_strategy_pool.py"],
            cwd=str(專案根), capture_output=True, text=True, encoding="utf-8"
        )
        if r.returncode == 0:
            print("✅ strategy_pool 推送成功")

    print(f"=== 完成 ({時段標籤}) ===")


if __name__ == "__main__":
    主流程()
