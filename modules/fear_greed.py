"""
CNN Fear & Greed Index 抓取模組
對應 Enjoy Index 的「情緒面 Chaos Indicator」
"""
import requests
from datetime import datetime


CNN_API = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Origin": "https://edition.cnn.com",
    "Referer": "https://edition.cnn.com/",
}


def 取得恐慌貪婪指數() -> dict:
    """
    回傳目前 CNN Fear & Greed Index 的數值與等級。
    回傳結構：
        {
            "score": 32.5,                          # 0-100 分
            "rating": "Fear",                       # Extreme Fear / Fear / Neutral / Greed / Extreme Greed
            "label_zh": "恐慌",                     # 中文對應
            "previous_close": 35.0,                 # 昨日收盤
            "one_week_ago": 28.0,                   # 一週前
            "one_month_ago": 45.0,                  # 一個月前
            "timestamp": "2026-05-12T08:00:00",
        }
    """
    resp = requests.get(CNN_API, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    現在 = data["fear_and_greed"]
    分數 = round(現在["score"], 1)
    等級英 = 現在["rating"]

    return {
        "score": 分數,
        "rating": 等級英,
        "label_zh": _翻譯等級(等級英),
        "previous_close": round(現在.get("previous_close", 0), 1),
        "one_week_ago": round(現在.get("previous_1_week", 0), 1),
        "one_month_ago": round(現在.get("previous_1_month", 0), 1),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


def _翻譯等級(英文等級: str) -> str:
    對照 = {
        "extreme fear": "極度恐慌 🔴",
        "fear": "恐慌 🟠",
        "neutral": "中性 🟡",
        "greed": "貪婪 🟢",
        "extreme greed": "極度貪婪 🔵",
    }
    return 對照.get(英文等級.lower(), 英文等級)


def 格式化為訊息(資料: dict) -> str:
    """將指數資料格式化成 LINE 推播用的字串。"""
    return (
        f"📊 大盤情緒（CNN F&G）\n"
        f"   今日：{資料['score']}　{資料['label_zh']}\n"
        f"   昨日：{資料['previous_close']}　"
        f"上週：{資料['one_week_ago']}　"
        f"上月：{資料['one_month_ago']}"
    )


if __name__ == "__main__":
    print("正在抓取 CNN Fear & Greed Index...")
    結果 = 取得恐慌貪婪指數()
    print()
    print(格式化為訊息(結果))
    print()
    print(f"原始資料：{結果}")
