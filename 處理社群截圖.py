"""
處理社群截圖（Phase 29 helper）
雙擊 處理社群截圖.bat 即可

流程：
  1. 你把 LINE 社群截圖丟到 D:/LIS股票投資系統/輸入/社群/
     檔名建議：可可群_2026-05-14.png / 朋友群_2026-05-14.png
  2. 雙擊 處理社群截圖.bat
  3. LIS 用 Gemini Vision OCR + 摘要 + 自動 log 訊號
  4. 推 LINE 通知摘要結果

完成後截圖會自動搬到 「已處理」子資料夾。
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

from modules import community_intel as ci


if __name__ == "__main__":
    print("=== 處理 LINE 社群截圖 ===\n")
    print(f"截圖目錄：{ci.社群輸入目錄}")
    print()
    r = ci.處理截圖目錄()
    print(f"✅ {r['說明']}")
    print(f"處理數：{r['處理數']}")

    if r["處理數"] > 0:
        print("\n📊 多社群共識（近 7 天）：")
        共識 = ci.跨社群共識(近期天數=7)
        for c in 共識[:10]:
            print(f"  {c['symbol']:<14} 被 {c['社群數']} 個社群提到 — {c['社群清單']}")
