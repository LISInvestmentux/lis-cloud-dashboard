"""每日 KOL YouTube 掃描 wrapper（Phase 49）"""
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

from modules import daily_kol_scan

if __name__ == "__main__":
    try:
        result = daily_kol_scan.跑全部()
        print(f"\n✅ 掃了 {len(result.get('kols', []))} 位 KOL")
        sys.exit(0)
    except Exception as e:
        import traceback
        print(f"❌ KOL 掃描失敗：{e}")
        traceback.print_exc()
        sys.exit(1)
