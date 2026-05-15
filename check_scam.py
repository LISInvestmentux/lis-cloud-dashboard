"""
反詐騙快速檢查 CLI（Phase 33.2）

使用方法：
  雙擊 check_scam.bat (隨便貼一個檔案路徑) 或：
  python check_scam.py <text_or_file>

支援：
  - 直接傳文字
  - 傳檔案路徑（.txt / .md / .pdf 暫不支援需 OCR）
  - 沒參數時讀剪貼簿（Windows）

輸出：紅旗報告 + 推 LINE 通知
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

from modules import scam_detector, line_push


def 讀剪貼簿() -> str:
    """Windows 讀剪貼簿"""
    try:
        import subprocess
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", "Get-Clipboard"],
            capture_output=True, text=True, encoding="utf-8", timeout=5)
        return result.stdout
    except Exception:
        return ""


def 主流程(內容: str, 來源: str = "用戶輸入", 推LINE: bool = True):
    if not 內容 or len(內容) < 10:
        print("❌ 內容太短或為空")
        return

    結果 = scam_detector.分析文字(內容, 來源=來源)
    print(scam_detector.印報告(結果))

    if 推LINE and 結果["紅旗數"] > 0:
        # 推 LINE
        msg = (f"🛡️ 反詐騙檢查 — {來源}\n"
               f"━━━━━━━━━━━━━━━━\n"
               f"風險：{結果['風險等級']}\n"
               f"紅旗：{結果['紅旗數']} 個 / 權重 {結果['總權重']}\n\n"
               + "\n".join(
                   f"• {r['類型']}：{r['範例']}"
                   for r in 結果["紅旗命中"]
               ) + f"\n\n💡 {結果['建議']}")
        try:
            line_push.推播文字訊息(msg)
            print("\n✅ 已推 LINE")
        except Exception as e:
            print(f"\n⚠️ LINE 推送失敗：{e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        path = Path(arg)
        if path.exists() and path.is_file():
            內容 = path.read_text(encoding="utf-8", errors="ignore")
            主流程(內容, 來源=path.name)
        else:
            # 當作直接文字
            主流程(arg, 來源="命令列")
    else:
        # 讀剪貼簿
        print("📋 從剪貼簿讀取內容...")
        內容 = 讀剪貼簿()
        if 內容:
            主流程(內容, 來源="剪貼簿")
        else:
            print("❌ 剪貼簿為空。使用方法：")
            print("  python check_scam.py \"要檢查的文字\"")
            print("  python check_scam.py 文件路徑.txt")
