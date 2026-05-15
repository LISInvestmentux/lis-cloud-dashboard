"""推美股收盤覆盤卡（Phase 36.13）— 04:05 自動推"""
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
from modules import us_close_card

if __name__ == "__main__":
    ok = us_close_card.推Flex卡()
    print(f"✅ 推送：{ok}")
    sys.exit(0 if ok else 1)
