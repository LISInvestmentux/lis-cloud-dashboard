"""推今日行動卡（Phase 33.2）— 8AM 第一張卡"""
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

from modules import daily_action_card

if __name__ == "__main__":
    ok = daily_action_card.推Flex卡()
    print(f"✅ 推送：{ok}")
    try:
        import sync_to_gist
        if sync_to_gist.自動同步(silent=True):
            print("☁️ Gist 已同步")
    except Exception:
        pass
    sys.exit(0 if ok else 1)
