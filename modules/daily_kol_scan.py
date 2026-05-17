"""
每日 KOL YouTube 自動掃描（Phase 49 — 5/17）

每天 7:50 跑（8AM 主推前），對配置的 KOL channels：
  1. yt-dlp 抓 channel 最近 N 天的新影片
  2. 對每部新影片跑 terry_chen_aggregator（zh 字幕 + Gemini 摘要）
  3. 跟 user portfolio 比對找直接 cover 持股的觀點
  4. 結果存到 數據/cache/kol_youtube_{date}.json
  5. daily_5cards_detail 卡_完整KOL 自動讀

擴展性：在 KOL_CHANNELS 加更多 channel 即可。
"""
import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
CACHE_FILE = 專案根 / "數據" / "cache" / "kol_youtube_latest.json"

# KOL channel 清單（user 認可的）
KOL_CHANNELS = [
    {
        "name": "Terry Chen 泰瑞",
        "handle": "@hackbearterry",
        "url": "https://www.youtube.com/@hackbearterry/videos",
        "tier": 1.5,
        "focus": "業內 + 第一性原理 + AI/半導體",
    },
    # 之後可加：
    # {"name": "股癌", "handle": "@Gooaye", "url": "...", "tier": 1, "focus": "..."},
]


def 抓channel近期影片(channel_url: str, max_videos: int = 3,
                       days_back: int = 7) -> list:
    """用 yt-dlp 抓 channel 最近的影片 metadata（不下載）"""
    import yt_dlp
    ydl_opts = {
        "extract_flat": True,  # 只拿清單，不深入
        "playlistend": max_videos,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
        entries = info.get("entries", []) or []
        results = []
        cutoff = datetime.now() - timedelta(days=days_back)
        for e in entries[:max_videos]:
            results.append({
                "video_id": e.get("id"),
                "title": e.get("title", ""),
                "url": e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}",
            })
        return results
    except Exception as e:
        print(f"❌ {channel_url}: {e}")
        return []


def 跑單一KOL(kol_config: dict, user_holdings: list) -> dict:
    """掃單一 KOL channel"""
    try:
        from . import terry_chen_aggregator as agg
    except ImportError:
        import terry_chen_aggregator as agg

    name = kol_config["name"]
    channel_url = kol_config["url"]
    print(f"\n📺 [{name}] 掃 {channel_url}")

    videos = 抓channel近期影片(channel_url, max_videos=3)
    if not videos:
        return {"name": name, "videos": [], "error": "抓不到 channel"}

    結果 = []
    for v in videos:
        url = v["url"]
        title = v["title"]
        print(f"  → 處理：{title[:50]}")
        try:
            r = agg.處理影片(url, user_holdings, title)
            結果.append({
                "video_id": v["video_id"],
                "title": title,
                "url": url,
                **r,
            })
        except Exception as e:
            print(f"    ❌ 處理失敗：{e}")

    return {
        "name": name,
        "tier": kol_config.get("tier", 2),
        "focus": kol_config.get("focus", ""),
        "videos": 結果,
    }


def 跑全部() -> dict:
    """每日 KOL 掃描主入口"""
    print(f"=" * 50)
    print(f"📺 每日 KOL YouTube 掃描 [{datetime.now():%H:%M:%S}]")
    print(f"=" * 50)

    # 載 user portfolio
    pf_path = 專案根 / "API" / "portfolio.json"
    pf = json.loads(pf_path.read_text(encoding="utf-8"))
    all_holdings = [p["symbol"] for p in pf.get("current_positions", []) or []]
    us_holdings = [s for s in all_holdings
                   if not s.endswith(".TW") and not s.endswith(".TWO")]
    holdings_for_gemini = us_holdings + ["2330.TW", "TSM", "TSLA"]

    # 跑每個 KOL
    all_results = {
        "scan_at": datetime.now().isoformat(timespec="seconds"),
        "user_holdings": holdings_for_gemini,
        "kols": [],
    }
    for kol in KOL_CHANNELS:
        r = 跑單一KOL(kol, holdings_for_gemini)
        all_results["kols"].append(r)

    # 存 cache
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2),
        encoding="utf-8")

    print(f"\n✅ KOL 掃描完成 → {CACHE_FILE.name}")
    return all_results


# CLI
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from dotenv import load_dotenv
    load_dotenv(專案根 / "API" / ".env")
    跑全部()
