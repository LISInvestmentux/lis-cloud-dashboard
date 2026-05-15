"""
新聞抓取 + Gemini AI 中文摘要模組
對應 L.I.S 系統「每日 LINE 報表」的「重點新聞摘要」區塊。

流程：
1. 用 NewsAPI 抓最近 24 小時的英文財經新聞（限定大廠來源）
2. 把標題 + 描述塞給 Gemini 2.5 Flash
3. Gemini 產出繁體中文摘要（3-5 點），聚焦投資人視角
"""
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types


專案根 = Path(__file__).resolve().parent.parent.parent
load_dotenv(專案根 / "API" / ".env")

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

NEWS_API = "https://newsapi.org/v2/everything"

# 投資人關注關鍵字
SEARCH_QUERY = (
    "(NVIDIA OR \"Jensen Huang\" OR TSMC OR \"Taiwan Semiconductor\" "
    "OR Microsoft OR Tesla OR Apple OR \"Federal Reserve\" OR Powell OR FOMC "
    "OR \"interest rate\" OR Trump OR tariff OR \"AI chip\" OR semiconductor) "
    "AND (stock OR market OR economy OR investor OR earnings OR rally OR \"Wall Street\")"
)


# ─────────────────────────────────────────────
# 1. 抓新聞（自動 fallback：先 24h，沒有就放寬到 72h）
# ─────────────────────────────────────────────
def _抓一次(時間範圍小時: int, 最多筆數: int) -> list[dict]:
    起始時間 = (datetime.now(timezone.utc) - timedelta(hours=時間範圍小時))
    resp = requests.get(NEWS_API, params={
        "q": SEARCH_QUERY,
        "language": "en",
        "sortBy": "publishedAt",
        "from": 起始時間.strftime("%Y-%m-%dT%H:%M:%S"),
        "pageSize": 最多筆數,
        "apiKey": NEWS_API_KEY,
    }, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "ok":
        raise RuntimeError(f"NewsAPI 錯誤：{data}")
    return [
        {
            "title": a["title"],
            "description": a.get("description") or "",
            "source": a["source"]["name"],
            "published_at": a["publishedAt"],
            "url": a["url"],
        }
        for a in data.get("articles", [])
        if a.get("title") and "[Removed]" not in a["title"]
    ]


def 抓取重點新聞(最多筆數: int = 20) -> tuple[list[dict], int]:
    """先試 24h，沒有再放寬到 72h。回傳 (新聞清單, 實際時間範圍小時)。"""
    if not NEWS_API_KEY:
        raise ValueError("NEWS_API_KEY 未設定")

    for 範圍 in [24, 48, 72]:
        新聞 = _抓一次(範圍, 最多筆數)
        if 新聞:
            return 新聞, 範圍
    return [], 72


# ─────────────────────────────────────────────
# 2. Gemini 摘要
# ─────────────────────────────────────────────
def AI摘要(新聞清單: list[dict],
            模型清單: list[str] | None = None) -> str:
    """
    把新聞餵給 Gemini，回傳繁體中文摘要。
    模型清單按順序嘗試，遇 503/服務忙就換下一個。
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY 未設定")
    if not 新聞清單:
        return "今日無重點新聞。"

    # 只放免費版有額度的模型（2.0-flash 已從免費版下架）
    模型清單 = 模型清單 or [
        "gemini-2.5-flash-lite",  # 首選：免費版額度最高、最快
        "gemini-2.5-flash",       # 備援：能力較強但較常 503
    ]

    client = genai.Client(api_key=GEMINI_API_KEY)

    新聞段落 = "\n\n".join(
        f"[{i+1}] {n['title']}\n來源：{n['source']}\n內容：{n['description']}"
        for i, n in enumerate(新聞清單)
    )

    提示詞 = f"""你是 L.I.S 投資系統的新聞分析助理，協助一位**中長線（3-12 個月）台美科技股波段投資人**閱讀今日重點新聞。

請從以下 {len(新聞清單)} 則英文新聞中，挑出**對投資人最重要的 3-5 則**，用**繁體中文**摘要成短句：

要求：
- 每點開頭用 emoji 標主題（🤖 AI / 🇺🇸 政策 / 💵 利率 / 🏭 半導體 / ⚡ 個股動態）
- 每點長度 30-60 字，**講清楚「發生什麼 + 對投資人影響」**
- 不要客套話、不要重複新聞標題、不要寫「以下是摘要」
- 直接給結論，按重要性排序
- 略過娛樂、體育、戶外活動等非投資相關新聞

新聞清單：
{新聞段落}

請直接輸出 3-5 點摘要（每點一行，前面加 emoji）："""

    最後錯誤 = None
    for 模型 in 模型清單:
        try:
            response = client.models.generate_content(
                model=模型,
                contents=提示詞,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=800,
                ),
            )
            return response.text.strip()
        except Exception as e:
            最後錯誤 = e
            訊息 = str(e)
            if "503" in 訊息 or "UNAVAILABLE" in 訊息 or "overloaded" in 訊息.lower():
                # 該模型過載，等 2 秒後換下一個
                time.sleep(2)
                continue
            raise
    raise RuntimeError(f"所有 Gemini 模型都暫不可用：{最後錯誤}")


# ─────────────────────────────────────────────
# 3. 對外主函式
# ─────────────────────────────────────────────
def 取得每日新聞摘要() -> dict:
    """組合抓取 + 摘要，回傳 dict 方便上層使用。"""
    新聞, 時間範圍 = 抓取重點新聞()
    摘要 = AI摘要(新聞) if 新聞 else "今日無新聞可摘要。"
    return {
        "新聞筆數": len(新聞),
        "時間範圍小時": 時間範圍,
        "摘要": 摘要,
        "原始新聞": 新聞,
    }


def 格式化為訊息(結果: dict) -> str:
    return (
        f"📰 重點新聞摘要（過去 {結果['時間範圍小時']}h，{結果['新聞筆數']} 則來源）\n"
        f"{結果['摘要']}"
    )


if __name__ == "__main__":
    print("正在抓新聞（自動依範圍 fallback）...")
    新聞, 範圍 = 抓取重點新聞()
    print(f"抓到 {len(新聞)} 則（過去 {範圍} 小時）")
    for i, n in enumerate(新聞[:5], 1):
        print(f"  [{i}] {n['title'][:80]}  ({n['source']})")
    print()
    print("呼叫 Gemini 摘要...")
    摘要 = AI摘要(新聞)
    print()
    print("=== Gemini 摘要結果 ===")
    print(摘要)
