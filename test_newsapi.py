"""快速測試 NewsAPI"""
import os
import sys
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "API" / ".env")
sys.stdout.reconfigure(encoding="utf-8")

resp = requests.get(
    "https://newsapi.org/v2/everything",
    params={
        "q": "NVIDIA OR Tesla OR Microsoft OR Fed",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 5,
        "apiKey": os.getenv("NEWS_API_KEY"),
    },
    timeout=15,
)
data = resp.json()
print(f"狀態：{data.get('status')}")
print(f"總筆數：{data.get('totalResults')}")
print()
for i, art in enumerate(data.get("articles", [])[:5], 1):
    print(f"[{i}] {art['title']}")
    print(f"    來源：{art['source']['name']}　時間：{art['publishedAt']}")
    desc = art.get("description") or "(無描述)"
    print(f"    {desc[:120]}")
    print()
