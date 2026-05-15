"""
快速手動 log 外部訊號（給你截圖太太/可可的 ARK 訊號用）

執行：
  雙擊 log_外部訊號.bat
  或互動模式 python log_外部訊號.py
"""
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

from modules import external_signal_tracker as ext


def 快速 log(來源: str, symbol: str, 類型: str = "BUY",
             進場價: float = None, 說明: str = ""):
    """快速 log 一筆，給其他腳本用"""
    r = ext.記錄外部訊號(
        來源=來源, symbol=symbol, 類型=類型,
        進場價=進場價 or 0, 說明=說明,
    )
    print(f"✅ 記錄：{r['id']}")
    return r


if __name__ == "__main__":
    print("=== 外部訊號手動 log ===\n")
    print("輸入格式（一行）：")
    print("  來源 symbol 類型 進場價 [說明]")
    print("例如：")
    print("  ARK_可可 00911.TW BUY 50.5 兆豐洲際半導體升溫區")
    print("  ARK_大俠 2891.TW BUY 25.0 中信金深價值區重押")
    print()
    print("輸入 'q' 結束")
    print("-" * 50)

    while True:
        try:
            line = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if line.lower() == "q":
            break
        if not line:
            continue

        parts = line.split(maxsplit=4)
        if len(parts) < 4:
            print("❌ 格式錯誤，至少需要：來源 symbol 類型 進場價")
            continue
        try:
            來源, symbol, 類型, 進場價 = parts[0], parts[1], parts[2], float(parts[3])
            說明 = parts[4] if len(parts) > 4 else ""
            r = ext.記錄外部訊號(
                來源=來源, symbol=symbol, 類型=類型,
                進場價=進場價, 說明=說明,
            )
            print(f"✅ 已記錄：{來源} {symbol} {類型} @{進場價}")
        except ValueError:
            print("❌ 進場價要是數字")
        except Exception as e:
            print(f"❌ 記錄失敗：{e}")

    # 列來源排行
    print("\n📊 來源信任分排行：")
    for 來源, s in ext.來源排行(最少樣本=1):
        print(f"  {來源:<20} 總 {s['總數']} 命中率 {s.get('命中率_pct')}")
