"""
ARK 知識庫（Phase 32.5）

用途：管理 ARK 系統的「教材/方法論」素材（不是即時訊號），例如：
  - 大俠的 ARK 核心數據能力 infographic
  - 6 大調節法 SOP
  - 可可的台積電波段方法論等
與 community_intel 區別：
  - community_intel = 抓即時 BUY/SELL 訊號
  - ark_knowledge   = 累積長期心法/教學內容，供推播卡與 AI 解釋層引用

存放位置：
  圖片：D:/LIS股票投資系統/數據/ark_knowledge/*.jpg, *.png
  索引：D:/LIS股票投資系統/數據/ark_knowledge/index.json

流程：
  1. 把教材圖丟到 ark_knowledge/
  2. 雙擊 處理ARK知識.bat
  3. 對新圖跑 Gemini Vision OCR + AI 摘要 + 提取「概念標籤」
  4. 結果存進 index.json（已處理的不會重跑）
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
知識庫目錄 = 專案根 / "數據" / "ark_knowledge"
索引檔 = 知識庫目錄 / "index.json"


def _載入索引() -> dict:
    if not 索引檔.exists():
        return {
            "說明": "ARK 知識庫索引（教材/方法論長期素材）",
            "建立日": datetime.now().strftime("%Y-%m-%d"),
            "圖片": {},
        }
    return json.loads(索引檔.read_text(encoding="utf-8"))


def _存索引(data: dict):
    索引檔.parent.mkdir(parents=True, exist_ok=True)
    索引檔.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _AI讀圖_摘要與標籤(image_path: Path) -> dict:
    """
    Phase 32.5 改良：2 階段呼叫 Gemini，避開多模態+結構化 JSON 同時做的不穩問題。
      Pass 1: Vision → 純 OCR 文字（不要求 JSON）
      Pass 2: Text → 用 OCR 文字產生 摘要 + 概念 (JSON)
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {"錯誤": "未設定 GEMINI_API_KEY"}
    try:
        from google import genai
    except ImportError:
        return {"錯誤": "請安裝 google-genai"}

    ext = image_path.suffix.lower().lstrip(".")
    mime_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                 "png": "image/png", "webp": "image/webp"}.get(ext, "image/png")

    try:
        client = genai.Client(api_key=api_key)
        with open(image_path, "rb") as f:
            img_bytes = f.read()

        # ── Pass 1: Vision OCR (純文字) ──
        ocr_resp = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[
                {"inline_data": {"mime_type": mime_type, "data": img_bytes}},
                "請逐字 OCR 這張 ARK 投資教材圖中所有文字，"
                "保留段落結構（換行）但不要加任何說明、標點美化、Markdown 或前後說明文字，"
                "直接輸出純文字。",
            ],
        )
        ocr = (ocr_resp.text or "").strip()
        if not ocr:
            return {"錯誤": "OCR 階段沒回傳文字"}

        # ── Pass 2: 用 OCR 文字產生 摘要 + 概念（純文字 prompt → JSON）──
        summary_prompt = f"""以下是一張 ARK 投資系統教材圖的 OCR 純文字內容。
請做 2 件事，回傳純 JSON（不要 markdown wrapper）：

1. 摘要: 用 120 字以內說明這份內容的核心觀念
2. 概念: 3-6 個短標籤，每個 8 字內，描述涉及的投資概念
   （例如「資金流向」「位階排序」「停利紀律」「逆勢操作」）

格式（嚴格 JSON）：
{{"摘要": "...", "概念": ["...", "..."]}}

OCR 內容：
{ocr[:6000]}
"""
        sum_resp = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=summary_prompt,
        )
        sum_text = (sum_resp.text or "").strip()

        # 解析 Pass 2 的 JSON（容錯）
        import re
        摘要, 概念 = "", []
        for pattern in [
            r'```(?:json)?\s*(\{.*?\})\s*```',  # markdown wrapper
            r'(\{.*\})',                         # raw JSON
        ]:
            m = re.search(pattern, sum_text, re.DOTALL)
            if m:
                try:
                    obj = json.loads(m.group(1))
                    摘要 = obj.get("摘要", "")
                    概念 = obj.get("概念", []) or []
                    break
                except Exception:
                    pass
        # 最終 fallback：用 regex 從 sum_text 撈
        if not 摘要:
            ms = re.search(r'"摘要"\s*:\s*"([^"]+)"', sum_text)
            if ms:
                摘要 = ms.group(1)
            else:
                摘要 = sum_text[:120].replace("\n", " ").strip()
        if not 概念:
            mc = re.search(r'"概念"\s*:\s*\[([^\]]*)\]', sum_text)
            if mc:
                概念 = re.findall(r'"([^"]+)"', mc.group(1))

        return {"ocr": ocr, "摘要": 摘要, "概念": 概念}
    except Exception as e:
        return {"錯誤": f"Gemini 呼叫失敗: {e}"}


def 處理新圖(強制重跑: bool = False) -> dict:
    """
    掃 ark_knowledge/ 內所有圖；只處理還沒進 index.json 的（或 強制重跑=True）。
    回傳：{新增數, 跳過數, 失敗數, 明細}
    """
    if not 知識庫目錄.exists():
        知識庫目錄.mkdir(parents=True, exist_ok=True)
        return {"新增數": 0, "說明": f"目錄空，請放教材圖到 {知識庫目錄}"}

    圖片 = (list(知識庫目錄.glob("*.png"))
             + list(知識庫目錄.glob("*.jpg"))
             + list(知識庫目錄.glob("*.jpeg")))
    if not 圖片:
        return {"新增數": 0, "說明": "目錄空"}

    索引 = _載入索引()
    新增 = 0
    跳過 = 0
    失敗 = 0
    明細 = []

    for p in 圖片:
        key = p.name
        if not 強制重跑 and key in 索引["圖片"]:
            跳過 += 1
            continue
        print(f"  ↳ 處理 {key} ...")
        r = _AI讀圖_摘要與標籤(p)
        if "錯誤" in r:
            失敗 += 1
            明細.append({"檔名": key, "狀態": "失敗", "原因": r["錯誤"]})
            continue
        索引["圖片"][key] = {
            "標題": p.stem,
            "摘要": r.get("摘要", ""),
            "概念": r.get("概念", []),
            "ocr": r.get("ocr", ""),
            "處理日": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        新增 += 1
        明細.append({
            "檔名": key, "狀態": "新增",
            "摘要": r.get("摘要", "")[:80],
            "概念": r.get("概念", []),
        })

    _存索引(索引)
    return {"新增數": 新增, "跳過數": 跳過, "失敗數": 失敗, "明細": 明細}


def 根據底部命中對應提示(命中數: int) -> dict:
    """
    Phase 32.5：底部 SOP 命中數 → 對應 ARK 知識庫提示。
    讓 LINE 卡上自動帶上「該怎麼做」的方法論連結。

    回傳 {標題, 概念[], 訊息, 相關圖片[]}
    """
    索引 = _載入索引()
    所有概念 = set()
    for entry in 索引.get("圖片", {}).values():
        for c in entry.get("概念", []):
            所有概念.add(c)

    if 命中數 >= 4:
        # 確認底部 → 該重押 + 風控
        提示 = {
            "標題": "🚨 確認底部 — 該重押",
            "建議概念": ["風控", "修剪枯枝", "位階排序"],
            "訊息": "ARK 6 大調節法：⑤風控解鎖預備金 / ⑥修剪枯枝出脫表現差的",
        }
    elif 命中數 >= 2:
        # 警戒區 → 準備分批 + 觀察位階
        提示 = {
            "標題": "⚠️ 警戒區 — 準備彈藥",
            "建議概念": ["位階排序", "升溫區", "逆勢操作"],
            "訊息": "ARK 6 大調節法：①位階排序看誰最深、②升溫區看誰要分批",
        }
    else:
        # 正常市場 → 維持紀律
        提示 = {
            "標題": "⚪ 正常市場 — 維持紀律",
            "建議概念": ["資金流向", "資產調篩", "DCA"],
            "訊息": "ARK 核心：跟著資金流向、做好資產調節、DCA 不停手",
        }

    # 找出哪些概念真的在知識庫裡（有對應圖）
    可用概念 = [c for c in 提示["建議概念"] if c in 所有概念]
    提示["可用概念"] = 可用概念

    # 找出對應的圖片
    相關圖片 = []
    for fname, entry in 索引.get("圖片", {}).items():
        if any(c in entry.get("概念", []) for c in 提示["建議概念"]):
            相關圖片.append({
                "檔名": fname,
                "標題": entry.get("標題"),
                "摘要": entry.get("摘要", "")[:60],
            })
    提示["相關圖片"] = 相關圖片[:2]
    return 提示


def 查詢(關鍵字: str) -> list:
    """
    用關鍵字搜尋知識庫（在 標題 / 摘要 / 概念 / ocr 內搜）。
    回傳：[{檔名, 摘要, 概念, 命中欄位}]
    """
    索引 = _載入索引()
    k = 關鍵字.lower()
    結果 = []
    for fname, entry in 索引.get("圖片", {}).items():
        命中 = []
        for field in ["標題", "摘要", "ocr"]:
            if k in str(entry.get(field, "")).lower():
                命中.append(field)
        if any(k in c.lower() for c in entry.get("概念", [])):
            命中.append("概念")
        if 命中:
            結果.append({
                "檔名": fname,
                "標題": entry.get("標題"),
                "摘要": entry.get("摘要"),
                "概念": entry.get("概念"),
                "命中欄位": 命中,
            })
    return 結果


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from dotenv import load_dotenv
    load_dotenv(專案根 / "API" / ".env")

    print("=== Phase 32.5 ARK 知識庫處理 ===\n")
    print(f"📁 知識庫目錄：{知識庫目錄}\n")
    r = 處理新圖(強制重跑=False)
    print(f"✅ 新增 {r.get('新增數', 0)} 張，"
          f"跳過 {r.get('跳過數', 0)} 張（已處理），"
          f"失敗 {r.get('失敗數', 0)} 張\n")
    for m in r.get("明細", []):
        if m.get("狀態") == "新增":
            print(f"  📄 {m['檔名']}")
            print(f"      摘要: {m['摘要']}")
            print(f"      概念: {' / '.join(m['概念'])}")
        else:
            print(f"  ❌ {m['檔名']}: {m['原因']}")
