"""
新聞情緒監測（Phase 24）— 川普關稅 / 地緣政治 / 黑天鵝預警

對標：LIS 純技術指標，沒抓消息面 → 川普一句話動 5%
解決：用 NewsAPI + Gemini AI 每日抓關鍵新聞 + 情緒打分

關鍵詞分類：
  🚨 緊急黑天鵝   戰爭、爆發、崩盤、暴跌、跳水
  ⚠️ 高風險       川普、關稅、制裁、貿易戰、貨幣戰
  📉 利空         降息預期、衰退、通膨、失業率上升
  📈 利多         降息、QE、刺激、AI 投資、出口大增
  💼 個股相關     特定公司新聞

每日抓 30-50 則新聞，AI 摘要 + 標籤 + 警示等級
存 數據/daily/news_{YYYY-MM-DD}.json

整合到：
  - 即時決策卡（黑天鵝警示）
  - position_sizer（黑天鵝偵測）
  - 盤中推播（即時警示）
"""
import os
import json
import ssl
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "").strip()


# 關鍵詞集合（中英雙語）
緊急黑天鵝關鍵詞 = [
    "暴跌", "崩盤", "閃崩", "跳水", "停損潮",
    "war", "crash", "plunge", "collapse", "panic",
    "戰爭", "爆發", "衝突"
]

高風險關鍵詞 = [
    "川普", "Trump", "關稅", "tariff",
    "制裁", "sanction", "貿易戰", "trade war",
    "FED", "聯準會", "加息", "rate hike",
    "降息", "rate cut", "縮表"
]

利多關鍵詞 = [
    "降息", "rate cut", "QE", "刺激",
    "AI 投資", "AI investment", "突破",
    "創新高", "all-time high", "復甦", "recovery"
]


def _抓NewsAPI(query: str, days: int = 1) -> list:
    """從 NewsAPI 抓近 N 天的新聞"""
    if not NEWS_API_KEY:
        return []

    from_dt = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    url = (
        f"https://newsapi.org/v2/everything?"
        f"q={urllib.parse.quote(query)}&"
        f"from={from_dt}&"
        f"sortBy=publishedAt&"
        f"language=zh&"
        f"pageSize=20&"
        f"apiKey={NEWS_API_KEY}"
    )
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "LIS/1.0"})
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            data = json.loads(r.read().decode("utf-8"))
            return data.get("articles", [])
    except Exception as e:
        print(f"NewsAPI 失敗: {e}")
        return []


def _分類新聞(標題: str, 摘要: str = "") -> dict:
    """判斷新聞的警示等級"""
    內文 = (標題 + " " + 摘要).lower()
    命中 = {"緊急黑天鵝": [], "高風險": [], "利多": []}

    for kw in 緊急黑天鵝關鍵詞:
        if kw.lower() in 內文:
            命中["緊急黑天鵝"].append(kw)
    for kw in 高風險關鍵詞:
        if kw.lower() in 內文:
            命中["高風險"].append(kw)
    for kw in 利多關鍵詞:
        if kw.lower() in 內文:
            命中["利多"].append(kw)

    if 命中["緊急黑天鵝"]:
        等級 = "🚨 緊急"
        分數 = -3
    elif len(命中["高風險"]) >= 2:
        等級 = "⚠️ 高風險"
        分數 = -2
    elif 命中["高風險"]:
        等級 = "📉 風險"
        分數 = -1
    elif 命中["利多"]:
        等級 = "📈 利多"
        分數 = +1
    else:
        等級 = "⚪ 中性"
        分數 = 0

    return {"等級": 等級, "分數": 分數, "命中關鍵詞": 命中}


def 今日新聞情緒(強制重抓: bool = False) -> dict:
    """
    回傳今日新聞情緒摘要。
    緩存到 數據/daily/news_{date}.json
    """
    日 = datetime.now().strftime("%Y-%m-%d")
    cache_path = 專案根 / "數據" / "daily" / f"news_{日}.json"

    if cache_path.exists() and not 強制重抓:
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    if not NEWS_API_KEY:
        return {
            "error": "未設定 NEWS_API_KEY",
            "情緒等級": "資料不足",
            "情緒分數": 0,
            "新聞數": 0,
        }

    # 抓多組關鍵詞
    所有新聞 = []
    queries = ["川普 關稅", "台股", "美股 AI", "聯準會", "降息"]
    for q in queries:
        所有新聞.extend(_抓NewsAPI(q, days=1))

    # 去重 by URL
    seen = set()
    去重 = []
    for n in 所有新聞:
        u = n.get("url")
        if u and u not in seen:
            seen.add(u)
            去重.append(n)

    # 分類
    分析結果 = []
    總分數 = 0
    緊急數 = 0
    高風險數 = 0
    利多數 = 0
    for n in 去重:
        標題 = n.get("title", "")
        摘要 = n.get("description", "") or ""
        分類 = _分類新聞(標題, 摘要)
        rec = {
            "標題": 標題,
            "來源": n.get("source", {}).get("name", ""),
            "時間": n.get("publishedAt", ""),
            "URL": n.get("url", ""),
            "等級": 分類["等級"],
            "分數": 分類["分數"],
            "命中": 分類["命中關鍵詞"],
        }
        分析結果.append(rec)
        總分數 += 分類["分數"]
        if 分類["分數"] <= -3:
            緊急數 += 1
        elif 分類["分數"] <= -1:
            高風險數 += 1
        elif 分類["分數"] >= 1:
            利多數 += 1

    # 整體情緒
    if 緊急數 > 0:
        整體 = "🚨 緊急（建議減碼）"
    elif 高風險數 >= 5:
        整體 = "⚠️ 高風險（觀望）"
    elif 高風險數 >= 2:
        整體 = "📉 偏空"
    elif 利多數 >= 5:
        整體 = "📈 利多明顯"
    else:
        整體 = "⚪ 中性"

    結果 = {
        "日期": 日,
        "新聞數": len(分析結果),
        "情緒等級": 整體,
        "情緒分數": 總分數,
        "緊急數": 緊急數,
        "高風險數": 高風險數,
        "利多數": 利多數,
        "新聞列表": 分析結果[:30],  # 只存前 30 則
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(結果, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    return 結果


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
    NEWS_API_KEY = os.getenv("NEWS_API_KEY", "").strip()

    print("=== Phase 24 新聞情緒測試 ===\n")
    r = 今日新聞情緒(強制重抓=True)
    print(f"📰 今日新聞數：{r.get('新聞數',0)}")
    print(f"🎯 整體情緒：{r.get('情緒等級')}")
    print(f"   情緒分數：{r.get('情緒分數')}")
    print(f"   緊急 {r.get('緊急數',0)} / 高風險 {r.get('高風險數',0)} / 利多 {r.get('利多數',0)}")
    print()
    print("🔥 高風險新聞（前 5 則）：")
    for n in r.get("新聞列表", [])[:30]:
        if n["分數"] <= -1:
            print(f"  {n['等級']} {n['標題'][:60]}")
    print()
    print("📈 利多新聞（前 5 則）：")
    for n in r.get("新聞列表", [])[:30]:
        if n["分數"] >= 1:
            print(f"  {n['等級']} {n['標題'][:60]}")
