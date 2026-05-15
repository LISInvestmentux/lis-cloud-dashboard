"""逐步測試 NewsAPI 各種條件"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "API" / ".env")
sys.stdout.reconfigure(encoding="utf-8")

KEY = os.getenv("NEWS_API_KEY")

測試集 = [
    {
        "說明": "1. 純關鍵字（無時間、無來源）",
        "params": {"q": "NVIDIA stock", "language": "en", "pageSize": 3, "apiKey": KEY},
    },
    {
        "說明": "2. 純關鍵字 + 最近 24h",
        "params": {
            "q": "NVIDIA stock", "language": "en", "pageSize": 3, "apiKey": KEY,
            "from": (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S"),
        },
    },
    {
        "說明": "3. 純關鍵字 + 最近 72h（怕假日）",
        "params": {
            "q": "NVIDIA stock", "language": "en", "pageSize": 3, "apiKey": KEY,
            "from": (datetime.now(timezone.utc) - timedelta(hours=72)).strftime("%Y-%m-%dT%H:%M:%S"),
        },
    },
    {
        "說明": "4. 加 domains: bloomberg+cnbc+reuters",
        "params": {
            "q": "NVIDIA stock", "language": "en", "pageSize": 3, "apiKey": KEY,
            "from": (datetime.now(timezone.utc) - timedelta(hours=72)).strftime("%Y-%m-%dT%H:%M:%S"),
            "domains": "bloomberg.com,reuters.com,cnbc.com",
        },
    },
]

for 測 in 測試集:
    print(f"--- {測['說明']} ---")
    resp = requests.get("https://newsapi.org/v2/everything", params=測["params"], timeout=15)
    data = resp.json()
    print(f"  status={data.get('status')}  totalResults={data.get('totalResults')}")
    if data.get("status") != "ok":
        print(f"  錯誤訊息：{data.get('message')}")
    for a in (data.get("articles") or [])[:2]:
        print(f"  • {a['title'][:80]}  ({a['source']['name']})")
    print()
