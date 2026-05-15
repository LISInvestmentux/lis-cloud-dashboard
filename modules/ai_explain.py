"""
AI 解釋層（Phase 32.5）

把 LIS 訊號（位階 / Kelly / 順勢 / 等級）翻譯成「人話」。
讓你看 LINE 卡時不只看數字，也看到「為什麼」。

接口：
  批次解釋(訊號清單, 大盤資訊) → {symbol: 解釋字串}
  解釋單一(訊號 dict) → str

設計：
  - 用 Gemini 2.5 Flash Lite（便宜快）
  - 一次呼叫批次解釋多檔（不要 N 個 API 呼叫）
  - 一句話 25 字內，焦點在「為什麼這等級」
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
快取目錄 = 專案根 / "數據" / "ai_explain_cache"


def _載入快取() -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    f = 快取目錄 / f"{today}.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _存快取(data: dict):
    快取目錄.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    f = 快取目錄 / f"{today}.json"
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                  encoding="utf-8")


def 批次解釋(訊號清單: list[dict],
              大盤資訊: Optional[dict] = None,
              強制重跑: bool = False) -> dict:
    """
    一次呼叫 Gemini，產生每檔的「人話解釋」（25 字內）。
    含當日快取，同樣訊號集合不重複叫 API。

    訊號清單格式（最少欄位）：
      [{symbol, name?, score, 等級_標籤, Kelly_pct?, 順勢分?, 理由?}, ...]

    回傳：{symbol: 解釋字串}
    """
    if not 訊號清單:
        return {}

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {r["symbol"]: "" for r in 訊號清單}

    # 快取 key = today + symbol + 等級（同等級不重跑）
    快取 = _載入快取() if not 強制重跑 else {}
    需要叫 = []
    結果 = {}
    for r in 訊號清單:
        sym = r.get("symbol", "")
        等級 = r.get("等級_標籤", "")
        key = f"{sym}_{等級}"
        if key in 快取:
            結果[sym] = 快取[key]
        else:
            需要叫.append(r)

    if not 需要叫:
        return 結果

    # 整理給 Gemini 看的 input
    輸入摘要 = []
    for r in 需要叫:
        sym = r.get("symbol", "?")
        line = (f"{sym} ({r.get('name', '')}): "
                f"等級={r.get('等級_標籤', '?')}, "
                f"位階={r.get('score') or r.get('位階分數'):.1f}, "
                f"倍率={r.get('倍率', 1):.1f}x")
        if r.get("Kelly_pct") or (r.get("Kelly資訊") or {}).get("Kelly_pct"):
            k = r.get("Kelly_pct") or r["Kelly資訊"]["Kelly_pct"]
            line += f", Kelly={k}%"
        if r.get("順勢分"):
            line += f", 順勢={r['順勢分']}"
        理由 = r.get("理由", [])
        if 理由:
            line += f", 理由={'/'.join(理由[:3])}"
        輸入摘要.append(line)

    大盤句 = ""
    if 大盤資訊:
        vix = 大盤資訊.get("VIX")
        fg = 大盤資訊.get("fear_greed_score")
        if vix or fg:
            parts = []
            if vix: parts.append(f"VIX={vix}")
            if fg: parts.append(f"F&G={fg}")
            大盤句 = f"今日大盤：{', '.join(parts)}\n"

    prompt = f"""你是 LIS 投資系統的 AI 助手。把下列訊號用人話解釋給投資新手。

{大盤句}訊號清單：
{chr(10).join(輸入摘要)}

對每檔，產生**25 字內**的人話解釋，焦點在「為什麼這等級」+ 投資新手能理解的關鍵原因。
回傳純 JSON：{{"代號1": "解釋", "代號2": "解釋", ...}}
範例：
{{"2330.TW": "深價值區+高 Kelly，過去類似訊號勝率高", "AMD": "順勢加碼，技術面突破中"}}
"""

    try:
        from google import genai
    except ImportError:
        return 結果

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )
        text = response.text or ""
        import re
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try:
                ai = json.loads(m.group())
                for r in 需要叫:
                    sym = r.get("symbol", "")
                    if sym in ai:
                        結果[sym] = ai[sym]
                        等級 = r.get("等級_標籤", "")
                        快取[f"{sym}_{等級}"] = ai[sym]
                _存快取(快取)
            except Exception:
                pass
    except Exception as e:
        print(f"AI 解釋呼叫失敗: {e}")

    return 結果


def 解釋單一(訊號: dict, 大盤資訊: Optional[dict] = None) -> str:
    """便利函式：解釋單筆訊號"""
    r = 批次解釋([訊號], 大盤資訊)
    return r.get(訊號.get("symbol", ""), "")


# ─────────────────────────────────────────────
# CLI 自測
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from dotenv import load_dotenv
    load_dotenv(專案根 / "API" / ".env")

    test = [
        {"symbol": "2890.TW", "name": "永豐金",
         "等級_標籤": "ALL IN（黑天鵝）", "score": 24.4,
         "倍率": 8.0, "Kelly_pct": 8.6,
         "理由": ["深價值區", "歷史勝率53%", "Kelly 8.6%"]},
        {"symbol": "0050.TW", "name": "元大台50",
         "等級_標籤": "順勢", "score": 65.0,
         "順勢分": 72, "倍率": 1.5,
         "理由": ["DCA 本月定額"]},
    ]
    大盤 = {"VIX": 17.9, "fear_greed_score": 64.4}

    r = 批次解釋(test, 大盤)
    for sym, exp in r.items():
        print(f"  {sym}: {exp}")
