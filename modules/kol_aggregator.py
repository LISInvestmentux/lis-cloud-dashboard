"""
KOL 觀點匯整模組（Phase 2.8）
用 Gemini 2.5 Flash + Google Search Grounding 自動抓取 KOL 最近觀點。

流程：
1. 從 API/kol_sources.json 讀 KOL 清單
2. 對每位 KOL 呼叫 Gemini，叫他用 Google 搜尋找最近 48h 投資觀點
3. 整合所有 KOL 摘要
4. 比對 watchlist：標出被多位 KOL 提到的標的（共識）
5. 快取結果到 數據/daily/kol_{date}.json（同日重跑不再呼叫 API）
"""
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types


專案根 = Path(__file__).resolve().parent.parent.parent
load_dotenv(專案根 / "API" / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
KOL_SOURCES_PATH = 專案根 / "API" / "kol_sources.json"
WATCHLIST_PATH = 專案根 / "API" / "watchlist.json"
CACHE_DIR = 專案根 / "數據" / "daily"


# ─────────────────────────────────────────────
# 讀設定
# ─────────────────────────────────────────────
def 載入KOL清單() -> list[dict]:
    with open(KOL_SOURCES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [k for k in data["kols"] if k.get("enabled", True)]


def 載入watchlist股票代號() -> set[str]:
    """回傳所有 watchlist 標的的代號（不含 .TW 後綴），方便比對。"""
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    符號集 = set()
    for region in data["regions"]:
        for s in region["stocks"]:
            sym = s["symbol"]
            符號集.add(sym)
            base = sym.split(".")[0]
            if base != sym:
                符號集.add(base)
            if s.get("name"):
                符號集.add(s["name"])
    return 符號集


def 載入watchlist對應表() -> dict[str, str]:
    """回傳 {代號|中文名: 規範化顯示名稱} 方便合併重複。
    例如 '2330' → '台積電 (2330)'、'台積電' → '台積電 (2330)'。"""
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    對應 = {}
    for region in data["regions"]:
        for s in region["stocks"]:
            sym = s["symbol"]
            base = sym.split(".")[0]
            name = s.get("name", "")
            顯示 = f"{name} ({base})" if name else sym
            對應[sym] = 顯示
            對應[base] = 顯示
            if name:
                對應[name] = 顯示
    return 對應


# ─────────────────────────────────────────────
# 單一 KOL 抓取
# ─────────────────────────────────────────────
def 抓單一KOL(kol: dict, client: genai.Client,
              時間範圍小時: int = 48,
              模型: str = "gemini-2.5-flash") -> dict:
    今日 = datetime.now().strftime("%Y-%m-%d")
    昨日 = (datetime.now().day - 2)  # 簡單算

    身分 = f"「{kol['name']}」"
    if kol.get("handle"):
        身分 += f"（帳號 {kol['handle']}）"
    平台 = kol.get("platform", "")
    if 平台:
        身分 += f"（{平台} 平台）"
    主題 = kol.get("topic_hint", "投資觀點")

    提示詞 = f"""請用 Google 搜尋找出 {身分}（台灣股市投資 KOL）
最近 {時間範圍小時} 小時的{主題}重點。

要求：
- 繁體中文輸出
- 整理 2-4 點重點（每點 30-80 字）
- 每點開頭用 emoji 標主題（📈/⚠️/💰/🏭/🇺🇸/🇹🇼）
- 提到的個股要列出代號（例如 2330.TW、NVDA、群創 3481）
- 找不到就明說「過去 {時間範圍小時}h 無公開觀點可摘要」
- 不要加客套話、不要重複 KOL 介紹"""

    # 重試 3 次，每次失敗等 5/10 秒（Gemini grounding 偶發 ClientError）
    摘要 = None
    最後錯誤 = None
    for 嘗試 in range(3):
        try:
            response = client.models.generate_content(
                model=模型,
                contents=提示詞,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.3,
                    max_output_tokens=4000,  # grounding 會吃很多 tokens
                ),
            )
            摘要 = response.text.strip() if response.text else "（無回應）"
            break
        except Exception as e:
            最後錯誤 = f"{type(e).__name__}: {str(e)[:80]}"
            if 嘗試 < 2:
                時間 = 5 * (嘗試 + 1)  # 5s, 10s
                print(f"      (重試 {嘗試 + 1}/2，等 {時間}s)", flush=True)
                time.sleep(時間)
    if 摘要 is None:
        摘要 = f"⚠️ 抓取失敗（重試 3 次）：{最後錯誤}"

    # 從摘要文字裡找股票代號 + 中文名比對
    提及股票 = set()
    # 台股 4-5 位數（含開頭可能是 0 的 ETF 代號）
    for m in re.finditer(r"\b(\d{4})\b", 摘要):
        code = m.group(1)
        if 1000 <= int(code) <= 9999:
            提及股票.add(code)
    # 5 位數 ETF（如 00919）
    for m in re.finditer(r"\b(0\d{4}[A-Z]?)\b", 摘要):
        提及股票.add(m.group(1))
    # 美股大寫代號（2-5 字母）
    排除 = {"AI", "ETF", "RSI", "MACD", "FOMC", "USD", "TWD", "KOL",
            "GDP", "CPI", "EPS", "IPO", "ROE", "EP", "PE", "EV",
            "TW", "TWO", "ADR", "AM", "PM", "ET", "PT", "BT",
            "DM", "OK", "FB", "IG", "URL", "API"}
    for m in re.finditer(r"\b([A-Z]{2,5})\b", 摘要):
        if m.group(1) not in 排除:
            提及股票.add(m.group(1))
    # 中文名比對（從 watchlist 抓所有中文名，看摘要裡有沒有出現）
    watchlist集 = 載入watchlist股票代號()
    for w in watchlist集:
        # 中文名通常 2-6 字
        if 2 <= len(w) <= 8 and not w.isascii() and w in 摘要:
            提及股票.add(w)

    return {
        "name": kol["name"],
        "handle": kol.get("handle", ""),
        "platform": kol.get("platform", ""),
        "summary": 摘要,
        "mentioned_symbols": sorted(提及股票),
    }


# ─────────────────────────────────────────────
# 整合：對所有 KOL 跑一輪 + 算共識
# ─────────────────────────────────────────────
def 取得今日KOL觀點(強制重抓: bool = False) -> dict:
    """
    回傳：
        {
            "date": "2026-05-13",
            "kols": [{name, summary, mentioned_symbols}, ...],
            "watchlist_hits": {"2330.TW 台積電": 3, "NVDA": 2, ...},  # 命中次數
        }
    """
    今日字串 = datetime.now().strftime("%Y-%m-%d")
    cache_path = CACHE_DIR / f"kol_{今日字串}.json"

    # 快取：同日重跑直接讀
    if cache_path.exists() and not 強制重抓:
        print(f"[KOL] 讀今日快取：{cache_path}")
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY 未設定")

    client = genai.Client(api_key=GEMINI_API_KEY)
    kols = 載入KOL清單()
    print(f"[KOL] 對 {len(kols)} 位 KOL 跑 Gemini grounding...")

    結果清單 = []
    所有提及 = []
    for i, kol in enumerate(kols, 1):
        if i > 1:
            # KOL 之間隔 3 秒，避開 Gemini 速率限制
            time.sleep(3)
        print(f"  ({i}/{len(kols)}) {kol['name']}...", end=" ", flush=True)
        r = 抓單一KOL(kol, client)
        結果清單.append(r)
        所有提及.extend(r["mentioned_symbols"])
        if "抓取失敗" in r["summary"]:
            print(f"❌ 失敗")
        else:
            print(f"提及 {len(r['mentioned_symbols'])} 個標的")

    # 比對 watchlist：用對應表 dedup 相同股票
    對應表 = 載入watchlist對應表()
    # 每位 KOL 對某個規範化標的算 1 次（避免一位 KOL 同時用代號+名稱算 2 次）
    每位KOL命中 = []
    for kol_result in 結果清單:
        kol的規範化命中 = set()
        for sym in kol_result["mentioned_symbols"]:
            if sym in 對應表:
                kol的規範化命中.add(對應表[sym])
        每位KOL命中.append(kol的規範化命中)

    命中 = {}
    for s in 每位KOL命中:
        for 規範名 in s:
            命中[規範名] = 命中.get(規範名, 0) + 1

    結果 = {
        "date": 今日字串,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "kols": 結果清單,
        "watchlist_hits": dict(sorted(命中.items(), key=lambda x: -x[1])),
    }

    # 存快取
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(結果, f, ensure_ascii=False, indent=2)
    print(f"[KOL] 結果已存：{cache_path}")

    return 結果


# ─────────────────────────────────────────────
# 文字格式化（debug 用）
# ─────────────────────────────────────────────
def 格式化為訊息(結果: dict) -> str:
    行 = [f"📱 KOL 觀點匯整（{結果['date']}）"]
    for r in 結果["kols"]:
        行.append(f"\n▼ {r['name']} ({r.get('platform','')})")
        行.append(r["summary"])
    if 結果["watchlist_hits"]:
        行.append("\n🎯 命中 watchlist：")
        for s, n in 結果["watchlist_hits"].items():
            行.append(f"   • {s}（{n} 位提到）")
    return "\n".join(行)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    結果 = 取得今日KOL觀點(強制重抓=True)
    print()
    print(格式化為訊息(結果))
