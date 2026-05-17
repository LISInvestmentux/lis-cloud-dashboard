"""
Terry Chen 泰瑞 影片聚合器（Phase 48 — 5/17）

工作流程:
  1. yt-dlp 抓 Terry 最近 N 集 zh 字幕
  2. 解析 VTT → 純文字
  3. 餵 Gemini 摘要（含「對 user 持股的影響」分析）
  4. 存到 數據/cache/terry_<video_id>.json
  5. daily_5cards 「老師們」卡或專區可呼叫

特色:
  - 比對 user portfolio symbols → 找「直接 cover 持股」的段落
  - 業內視角 second opinion
"""
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = 專案根 / "數據" / "cache" / "terry_transcripts"
SUMMARY_DIR = 專案根 / "數據" / "cache"


def 解析VTT(path: Path) -> str:
    """把 .vtt 字幕轉成純文字（去掉時間軸、WEBVTT header）"""
    if not path.exists():
        return ""
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        # 跳過 header / 空行 / 時間軸
        if not line:
            continue
        if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if re.match(r'^\d{2}:\d{2}', line):  # 時間軸
            continue
        if "-->" in line:
            continue
        # 純文字行
        lines.append(line)
    # 連起來
    return " ".join(lines)


def 抓影片字幕(video_url: str, lang: str = "zh") -> Optional[Path]:
    """用 yt-dlp 抓字幕，回傳 .vtt 檔案 path"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # 從 URL 抓 video_id
    m = re.search(r'(?:v=|/)([0-9A-Za-z_-]{11})', video_url)
    if not m:
        return None
    video_id = m.group(1)

    target = CACHE_DIR / f"{video_id}.{lang}.vtt"
    if target.exists():
        return target

    python_bin = str(專案根 / "程式碼" / ".venv" / "Scripts" / "python.exe")
    cmd = [
        python_bin, "-m", "yt_dlp",
        "--write-sub", "--sub-langs", lang,
        "--skip-download",
        "--sub-format", "vtt/srt/best",
        "-o", str(CACHE_DIR / "%(id)s.%(ext)s"),
        video_url,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=60)
    except Exception as e:
        print(f"yt-dlp 失敗: {e}")
        return None

    return target if target.exists() else None


def Gemini摘要(transcript: str, user_holdings: list,
                video_title: str = "") -> dict:
    """用 Gemini 摘要 + 找對 user 持股的 commentary"""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or not transcript:
        return {"摘要": "", "對持股的commentary": {}, "error": "no api key or transcript"}

    持股清單 = ", ".join(user_holdings) if user_holdings else "（無）"
    prompt = f"""你是投資 KOL 內容摘要助手。下面是 Terry Chen 泰瑞（矽谷工程師，57.3 萬訂閱 YouTuber）的最新影片字幕。

影片標題：{video_title}

用戶持股清單：{持股清單}

請完成 3 件事：
1. **5 個重點摘要**（每點 1 句話 ≤ 40 字，繁中）
2. **對用戶持股的 commentary**：對清單中每個有提到的標的，整理 Terry 的觀點（看多/看空/中性 + 原因 ≤ 50 字）
3. **整體投資觀點**：Terry 的整體立場（≤ 80 字）

請輸出純 JSON，格式：
{{
  "摘要": ["重點1", "重點2", ...],
  "對持股的commentary": {{"MU": {{"立場": "看多/看空/中性", "原因": "..."}}}},
  "整體觀點": "..."
}}

影片字幕：
{transcript[:8000]}
"""

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )
        text = resp.text.strip()
        # 移除 ``` 包裝
        text = re.sub(r'^```json\s*|\s*```$', '', text, flags=re.MULTILINE).strip()
        text = re.sub(r'^```\s*|\s*```$', '', text, flags=re.MULTILINE).strip()
        result = json.loads(text)
        return result
    except Exception as e:
        return {"摘要": [], "對持股的commentary": {},
                "整體觀點": "", "error": str(e)[:200]}


def 處理影片(video_url: str, user_holdings: list,
              video_title: str = "") -> dict:
    """主入口：抓字幕 + 摘要 + 存 cache"""
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    m = re.search(r'(?:v=|/)([0-9A-Za-z_-]{11})', video_url)
    video_id = m.group(1) if m else "unknown"

    # 看快取
    summary_path = SUMMARY_DIR / f"terry_{video_id}.json"
    if summary_path.exists():
        try:
            return json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 抓字幕
    vtt_path = 抓影片字幕(video_url, lang="zh")
    if not vtt_path:
        return {"error": "字幕抓不到", "video_id": video_id}

    # 解析純文字
    transcript = 解析VTT(vtt_path)

    # Gemini 摘要
    summary = Gemini摘要(transcript, user_holdings, video_title)

    result = {
        "video_id": video_id,
        "video_url": video_url,
        "video_title": video_title,
        "transcript_len": len(transcript),
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        **summary,
    }
    summary_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return result


# CLI 測試
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from dotenv import load_dotenv
    load_dotenv(專案根 / "API" / ".env")

    # user 持股 — 美股優先（Terry 主要講美股）
    pf = json.loads((專案根 / "API" / "portfolio.json").read_text(encoding="utf-8"))
    all_holdings = [p["symbol"] for p in pf.get("current_positions", [])]
    us_holdings = [s for s in all_holdings
                    if not s.endswith(".TW") and not s.endswith(".TWO")]
    tw_core = ["2330.TW"]  # 台積電是 Terry 會講的
    holdings = us_holdings + tw_core

    print(f"User 持股清單給 Gemini: {holdings}")
    print()

    url = "https://www.youtube.com/watch?v=gj5gBsjYaF4"
    title = "記憶體類股還可以買嗎？"
    result = 處理影片(url, holdings, title)

    print(f"Video ID: {result.get('video_id')}")
    print(f"字幕長度: {result.get('transcript_len')} 字")
    print()
    if result.get("error"):
        print(f"❌ Error: {result['error']}")
    else:
        print("📝 5 個重點摘要：")
        for i, p in enumerate(result.get("摘要", []), 1):
            print(f"  {i}. {p}")
        print()
        print("💼 對 user 持股的 commentary：")
        for sym, info in result.get("對持股的commentary", {}).items():
            if info is None:
                print(f"  {sym}: (未直接 cover)")
            elif isinstance(info, dict):
                print(f"  {sym}: {info.get('立場','?')} — {info.get('原因','')}")
            else:
                print(f"  {sym}: {info}")
        print()
        print("🎯 整體觀點：")
        print(f"  {result.get('整體觀點','')}")
