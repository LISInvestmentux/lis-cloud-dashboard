"""
LINE 社群情報摘要（Phase 29）

整合用戶在 4-5 個 LINE 社群的訊息，自動摘要 + 提取訊號。

社群分類：
  ark_group_1   方舟系統用戶群 1（含可可、太太）
  ark_group_2   方舟系統用戶群 2
  ark_group_3   方舟系統用戶群 3
  ark_group_4   方舟系統用戶群 4
  friends       朋友群（你、太太、朋友）

實作方式：
  方法 A：截圖上傳
    - 你截圖社群訊息 → 放 D:/LIS股票投資系統/輸入/社群截圖/
    - LIS 用 Gemini Vision 讀圖 + 提取訊號
    - 自動 log 到 external_signal_tracker

  方法 B：文字貼上
    - 把社群訊息複製貼到 community_paste.txt
    - LIS 讀檔 + Gemini 摘要

  方法 C：日 / 週摘要
    - 每天結束 → 你把當天看到的訊號統一輸入
    - LIS 自動歸類 + 比對 LIS 訊號 + 累積信任分

輸出：
  - 每社群當日訊號摘要
  - 多社群「共識買賣」標的（被多個群同時提到）
  - 對比 LIS 自有訊號的差異
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
社群輸入目錄 = 專案根 / "輸入" / "社群"
社群歷史檔 = 專案根 / "數據" / "community_intel_history.json"


def _載入歷史() -> dict:
    if not 社群歷史檔.exists():
        return {
            "說明": "LINE 社群情報歷史",
            "建立日": datetime.now().strftime("%Y-%m-%d"),
            "社群清單": {
                "ark_可可群": {"_說明": "可可在的 ARK 群"},
                "ark_太太群": {"_說明": "太太在的 ARK 群"},
                "ark_其他群1": {"_說明": "ARK 群 3"},
                "ark_其他群2": {"_說明": "ARK 群 4"},
                "朋友群": {"_說明": "朋友 + 太太 + 你"},
            },
            "每日摘要": {},  # {日期: {社群: 摘要}}
            "提取的訊號": [],  # 從社群提取的訊號（會同步到 external_signal_tracker）
        }
    return json.loads(社群歷史檔.read_text(encoding="utf-8"))


def _存歷史(data: dict):
    社群歷史檔.parent.mkdir(parents=True, exist_ok=True)
    社群歷史檔.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def 記錄社群訊息(社群: str, 內容: str, 日期: Optional[str] = None,
                  AI摘要: bool = True) -> dict:
    """
    記錄一段社群訊息（手動貼上）。
    可選 AI 摘要 + 提取訊號。
    """
    日 = 日期 or datetime.now().strftime("%Y-%m-%d")
    data = _載入歷史()

    if 日 not in data["每日摘要"]:
        data["每日摘要"][日] = {}
    if 社群 not in data["每日摘要"][日]:
        data["每日摘要"][日][社群] = {"原文": "", "摘要": "", "提取訊號": []}

    data["每日摘要"][日][社群]["原文"] += "\n\n" + 內容

    # AI 摘要
    if AI摘要:
        try:
            摘要結果 = _AI摘要與提取(內容, 社群名=社群)
            data["每日摘要"][日][社群]["摘要"] = 摘要結果.get("摘要", "")
            訊號 = 摘要結果.get("訊號", [])
            data["每日摘要"][日][社群]["提取訊號"].extend(訊號)

            # 同步到 external_signal_tracker
            try:
                from . import external_signal_tracker as ext
                for s in 訊號:
                    ext.記錄外部訊號(
                        來源=f"社群_{社群}",
                        symbol=s.get("symbol", ""),
                        類型=s.get("類型", "BUY"),
                        進場價=s.get("進場價", 0),
                        說明=s.get("說明", ""),
                        時間=datetime.now().isoformat(timespec="seconds"),
                    )
            except Exception as e:
                print(f"同步外部訊號失敗：{e}")
        except Exception as e:
            print(f"AI 摘要失敗：{e}")

    _存歷史(data)
    return data["每日摘要"][日][社群]


def _AI摘要與提取(內容: str, 社群名: str = "") -> dict:
    """
    用 Gemini 摘要 + 提取股票訊號。
    回傳：{摘要, 訊號: [{symbol, 類型, 說明}]}
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {"摘要": "未設定 GEMINI_API_KEY", "訊號": []}

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return {"摘要": "請安裝 google-genai", "訊號": []}

    prompt = f"""
你是台股 + 美股投資情報分析師。
以下是 LINE 社群「{社群名}」的訊息內容。

請做兩件事：
1. 摘要重點（150 字內，並標註「內容類型」：訊號 / 心法 / 教學 / 閒聊）
2. 提取「股票買賣訊號」，JSON 格式：
   [{{"symbol": "代號.TW", "類型": "BUY|SELL", "說明": "20字內"}}, ...]

   訊號判定規則（嚴格）：
   - 台股加 .TW（例 2330.TW）、上櫃 .TWO、美股直接代號（例 NVDA）
   - **只提取「明確當下買/賣意圖」**，例如「我今天加碼」「我準備出脫」「剛掛單買進」
   - **不要**把以下內容當訊號：
     a) 教學/心法（如「假設你買在 600」「複利示範」「波段算法」）
     b) 歷史推演（如「過去 600 → 2000 漲 233%」）
     c) 分析範例 / 假設情境
     d) 純粹討論 / 看法 / 閒聊
   - 若整段都是教學/心法，訊號回傳空陣列 `[]`

訊息內容：
{內容[:3000]}

請回傳純 JSON：
{{"摘要": "[類型] 摘要文字...", "訊號": [...]}}
"""

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
    )
    text = response.text or ""
    # 找 JSON
    import re
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {"摘要": text[:200], "訊號": []}


def 跨社群共識(近期天數: int = 7) -> list:
    """
    找出「多個社群都提到」的標的（強訊號）
    """
    from datetime import timedelta
    data = _載入歷史()
    cutoff = (datetime.now() - timedelta(days=近期天數)).strftime("%Y-%m-%d")

    symbol_count = {}  # {symbol: {社群集合}}
    for 日, 各社群 in data["每日摘要"].items():
        if 日 < cutoff:
            continue
        for 社群, 內容 in 各社群.items():
            for 訊號 in 內容.get("提取訊號", []):
                sym = 訊號.get("symbol")
                if sym:
                    symbol_count.setdefault(sym, set()).add(社群)

    結果 = [{"symbol": s, "社群數": len(g), "社群清單": sorted(g)}
            for s, g in symbol_count.items()]
    結果.sort(key=lambda r: -r["社群數"])
    return 結果


def 處理截圖目錄() -> dict:
    """
    處理 D:/LIS股票投資系統/輸入/社群截圖/ 內所有截圖。
    用 Gemini Vision OCR + 提取訊號。
    """
    if not 社群輸入目錄.exists():
        社群輸入目錄.mkdir(parents=True, exist_ok=True)
        return {"處理數": 0, "說明": f"請把社群截圖放到 {社群輸入目錄}"}

    import re
    截圖 = (list(社群輸入目錄.glob("*.png"))
             + list(社群輸入目錄.glob("*.jpg"))
             + list(社群輸入目錄.glob("*.jpeg")))
    if not 截圖:
        return {"處理數": 0, "說明": "目錄空，請放截圖"}

    處理數 = 0
    for img_path in 截圖:
        # 從檔名解析社群與日期（彈性版）
        # 支援：
        #   ark_可可群_2026-05-14.png        → 社群=ark_可可群, 日期=2026-05-14
        #   小護士_2026-05-08_b.jpg          → 社群=小護士,     日期=2026-05-08（_b 為同日序號）
        #   隨便名稱_20260508.png            → 社群=隨便名稱,   日期=2026-05-08
        #   只有檔名.jpg                      → 社群=只有檔名,   日期=今天
        檔名 = img_path.stem
        date_match = re.search(r'(\d{4}[-_]?\d{2}[-_]?\d{2})', 檔名)
        if date_match:
            digits = re.sub(r'[-_]', '', date_match.group(1))
            日期 = f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
            社群 = 檔名[:date_match.start()].rstrip('_-') or "未分類"
        else:
            日期 = datetime.now().strftime("%Y-%m-%d")
            社群 = 檔名 or "未分類"

        try:
            內容 = _Gemini讀圖(img_path)
            if 內容:
                記錄社群訊息(社群, 內容, 日期=日期, AI摘要=True)
                處理數 += 1
                # 移到已處理
                done_dir = 社群輸入目錄 / "已處理"
                done_dir.mkdir(exist_ok=True)
                img_path.rename(done_dir / img_path.name)
        except Exception as e:
            print(f"處理 {img_path.name} 失敗：{e}")

    return {"處理數": 處理數, "說明": f"已處理 {處理數} 張，移到已處理目錄"}


def _Gemini讀圖(image_path: Path) -> str:
    """用 Gemini Vision 讀圖回傳文字"""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return ""
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        # 自動偵測 mime_type（修正：之前寫死 image/png 對 jpg 會出錯）
        ext = image_path.suffix.lower().lstrip('.')
        mime_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                     "png": "image/png", "webp": "image/webp"}.get(ext, "image/png")
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[
                {"inline_data": {"mime_type": mime_type, "data": img_bytes}},
                "請逐字 OCR 這張 LINE 對話截圖，輸出純文字（保留發言者名稱）。",
            ],
        )
        return response.text or ""
    except Exception as e:
        return f"[Gemini 讀圖失敗: {e}]"


# ─────────────────────────────────────────────
# CLI 自測（dry-run，不寫真實資料庫）
# Phase 32.4：之前 CLI 會把 mock 訊息塞進真實 community_intel_history.json，
# 改成只跑 AI 摘要看效果，不 persist。要真實處理請用 處理社群截圖.bat。
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from dotenv import load_dotenv
    load_dotenv(專案根 / "API" / ".env")

    print("=== Phase 29 LINE 社群情報摘要（CLI dry-run）===\n")
    print("⚠️  CLI 模式只跑 AI 不寫資料庫；真實處理請用 處理社群截圖.bat\n")

    模擬訊息 = """
可可：今天 ARK 系統 00910 升溫區噴出，我加碼 200 股
太太：對齊！我也加 100 股 0050
[群組成員 A]：00911 法人連 3 買，跟單
我：聯發科 2454 看起來不錯，但 ARK 沒提示
[群組成員 B]：別追高 2330，等回檔
"""
    # 直接呼叫 _AI摘要與提取 (不經過會寫檔的 記錄社群訊息)
    r = _AI摘要與提取(模擬訊息, 社群名="ark_可可群(dry-run)")
    print(f"📝 摘要：{r.get('摘要','(無)')}")
    print(f"📊 提取訊號：")
    for s in r.get("訊號", []):
        print(f"  {s.get('symbol','?'):<10} {s.get('類型','?'):<6} {s.get('說明','')}")

    print(f"\n📁 截圖輸入目錄：{社群輸入目錄}")
    print("   把社群截圖放這裡（檔名格式：社群名_日期.png），下次跑就會自動處理")
