"""
處理 LINE 對話 TXT 匯出檔

使用方式：
  1. 在 LINE 群組裡點「⋮」→ 設定 → 傳送聊天記錄 → 選 TXT
  2. 把 TXT 放到 D:/LIS股票投資系統/輸入/對話TXT/
     檔名建議：可可群_2026-05-14.txt
  3. 雙擊 處理對話TXT.bat
  4. LIS 兩階段過濾（關鍵詞 + Gemini）+ 自動 log 訊號

說明：
  weight = 0.1（低權重）
  只當 trend confirmation，不當主訊號
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

from modules import chat_export_parser as cep


if __name__ == "__main__":
    txt_dir = 專案根.parent / "輸入" / "對話TXT"
    txt_dir.mkdir(parents=True, exist_ok=True)

    txts = list(txt_dir.glob("*.txt"))
    if not txts:
        print(f"❌ 沒檔可處理")
        print(f"📁 請把 LINE TXT 放到：{txt_dir}")
        print(f"📝 檔名建議：可可群_2026-05-14.txt")
        sys.exit(0)

    # 社群權重配置（依用戶說明）
    社群設定 = {
        "紙箱戰隊": {"weight": 0.3, "重點發言者": ["Enjoy", "Ryan", "太太"],
                     "近期天數": 90},  # 朋友傳奇實單
        "方舟運算": {"weight": 0.15, "重點發言者": None,
                     "近期天數": 30},  # ARK 用戶但雜訊多
        "小散戶": {"weight": 0.2, "重點發言者": None,
                   "近期天數": 60},
        "default": {"weight": 0.1, "重點發言者": None,
                    "近期天數": 60},
    }

    print(f"=== 處理 {len(txts)} 個 TXT ===\n")
    所有結果 = []
    for txt_path in txts:
        print(f"\n📂 處理 {txt_path.name}...")
        # 從檔名匹配設定
        檔名 = txt_path.stem
        cfg = 社群設定["default"]
        for key, c in 社群設定.items():
            if key in 檔名:
                cfg = c
                print(f"  套用設定：{key} (weight={c['weight']})")
                break

        社群名 = txt_path.stem.replace("[LINE]", "").strip()
        r = cep.處理對話TXT(
            txt_path, 社群名=社群名,
            weight=cfg["weight"],
            近期天數=cfg["近期天數"],
            重點發言者=cfg["重點發言者"],
            最大訊號數=300,
            用AI=True,  # Phase 30：付費版啟用後改用 AI
        )
        所有結果.append(r)

        # 印重點
        print(f"  ✅ 總 {r['總筆數']} → 過濾 {r['過濾後']} → 訊號 {r['有效訊號數']}")
        if r.get("統計", {}).get("最常提標的"):
            最常 = r["統計"]["最常提標的"][:5]
            print(f"  🎯 最常提：{', '.join(f'{s}({c})' for s,c in 最常)}")

        # 移到已處理
        done_dir = txt_dir / "已處理"
        done_dir.mkdir(exist_ok=True)
        txt_path.rename(done_dir / txt_path.name)

    # 跨社群共識
    print("\n\n📊 跨社群共識（過去 7 天）：")
    try:
        from modules import external_signal_tracker as ext
        共識 = ext.多來源共識(近期天數=7)
        for c in 共識[:10]:
            if c["來源數"] >= 2:
                print(f"  {c['symbol']:<10} 被 {c['來源數']} 個來源提到")
    except Exception as e:
        print(f"  共識計算失敗：{e}")

    print(f"\n⚠️ 反CC 提醒：群組訊號 weight 僅 0.1，不可主導決策")
