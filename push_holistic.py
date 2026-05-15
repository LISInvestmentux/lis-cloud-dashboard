"""推全息儀表板（Phase 33）— wrapper for subprocess use"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))

from dotenv import load_dotenv
load_dotenv(專案根.parent / "API" / ".env")

from modules import holistic_dashboard, line_push
from datetime import datetime


if __name__ == "__main__":
    print("組裝 5 張卡 carousel...")
    car = holistic_dashboard.建構全息儀表板()
    alt = f"🎯 LIS 全息儀表板 {datetime.now():%H:%M}"
    line_push.推播Flex訊息(替代文字=alt, flex內容=car)
    print(f"✅ 已推 LINE：{alt}")
