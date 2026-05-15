"""測試 Gemini Google Search Grounding 抓 KOL 觀點"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / "API" / ".env")

from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

提示詞 = """請用 Google 搜尋找出「老王」（Threads 帳號 @oldwangstock，台灣股市投資 KOL）
最近 48 小時（2026-05-12 ~ 2026-05-13）的投資觀點或貼文重點。

要求：
- 繁體中文輸出
- 整理 2-4 點重點（每點 30-80 字）
- 每點開頭用 emoji 標主題（📈/⚠️/💰/🏭）
- 提到的個股要列出代號（如 2330.TW / NVDA）
- 找不到就明說「過去 48 小時無公開貼文」
"""

print("呼叫 Gemini 2.5 Flash + Google Search Grounding...")
print()
try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=提示詞,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.3,
        ),
    )
    print("=== Gemini 回應 ===")
    print(response.text)
    print()
    # 看 grounding metadata
    if response.candidates and response.candidates[0].grounding_metadata:
        meta = response.candidates[0].grounding_metadata
        print("=== 搜尋來源（grounding sources）===")
        if hasattr(meta, "grounding_chunks") and meta.grounding_chunks:
            for i, chunk in enumerate(meta.grounding_chunks, 1):
                if hasattr(chunk, "web") and chunk.web:
                    print(f"  [{i}] {chunk.web.title}")
                    print(f"      {chunk.web.uri[:100]}")
        else:
            print("  （無詳細 grounding chunks）")
except Exception as e:
    print(f"❌ 失敗：{type(e).__name__}: {e}")
