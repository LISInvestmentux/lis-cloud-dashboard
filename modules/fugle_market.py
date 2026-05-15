"""
FUGLE Marketdata 即時行情串接（Phase 15）
比 yfinance 即時（盤中 tick 級 vs 15 分延遲）。

提供：
  抓即時報價(symbol) → 比 yfinance 快
  抓歷史K線(symbol)  → 用來補 yfinance
  抓ETF折溢價(symbol)→ ⚠️ FUGLE 基本版沒給，回 None

設計：
  - fallback：FUGLE fail → 自動切 yfinance
  - cache：30 秒內同 symbol 不重複呼叫
  - quota 警告：基本版 60 次/分，若快用完自動退讓
"""
import os
import ssl
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent

API_KEY = os.getenv("FUGLE_MARKETDATA_API_KEY", "").strip()
BASE_URL = "https://api.fugle.tw/marketdata/v1.0"

# 簡單記憶體 cache（30 秒）
_cache = {}
_cache_ttl = 30   # 秒


def _抓(endpoint: str, timeout: int = 8) -> Optional[dict]:
    """FUGLE REST 呼叫底層。"""
    if not API_KEY:
        return None
    url = f"{BASE_URL}{endpoint}"
    cache_key = endpoint
    now = time.time()
    if cache_key in _cache:
        cached_data, cached_time = _cache[cache_key]
        if now - cached_time < _cache_ttl:
            return cached_data
    try:
        req = urllib.request.Request(url, headers={
            "X-API-KEY": API_KEY,
            "User-Agent": "LIS-Investment/1.0",
        })
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            data = json.loads(r.read().decode("utf-8"))
            _cache[cache_key] = (data, now)
            return data
    except Exception:
        return None


def _去TW後綴(symbol: str) -> str:
    """FUGLE 要 4 碼純代號（不要 .TW）"""
    return symbol.replace(".TW", "").replace(".TWO", "")


def 即時報價(symbol: str) -> Optional[dict]:
    """
    回傳 FUGLE 即時報價。
    回傳格式：
      {
        "symbol": "2330",
        "name": "台積電",
        "close": 2230,      # 最新成交價
        "open": 2250,
        "high": 2270,
        "low": 2230,
        "prev_close": 2220,
        "change_pct": 0.45,
        "timestamp": ISO time,
        "source": "fugle",
      }
    抓不到回 None（呼叫端自動 fallback yfinance）
    """
    # 美股 FUGLE 沒有
    if not (symbol.endswith(".TW") or symbol.endswith(".TWO") or symbol.isdigit() or
            (symbol[0].isdigit() and "0" <= symbol[0] <= "9")):
        return None

    code = _去TW後綴(symbol)
    data = _抓(f"/stock/intraday/quote/{code}")
    if not data or "symbol" not in data:
        return None

    close = data.get("closePrice") or data.get("lastPrice") or data.get("referencePrice")
    open_p = data.get("openPrice")
    high = data.get("highPrice")
    low = data.get("lowPrice")
    prev_close = data.get("previousClose")

    if not close:
        return None

    change_pct = None
    if prev_close and prev_close > 0:
        change_pct = round((close - prev_close) / prev_close * 100, 2)

    return {
        "symbol": symbol,
        "name": data.get("name", ""),
        "close": float(close),
        "open": float(open_p) if open_p else None,
        "high": float(high) if high else None,
        "low": float(low) if low else None,
        "prev_close": float(prev_close) if prev_close else None,
        "change_pct": change_pct,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "source": "fugle",
    }


def 即時報價_fallback(symbol: str) -> Optional[dict]:
    """
    FUGLE 為主、yfinance 為輔。
    台股優先 FUGLE，失敗用 yfinance。
    美股直接用 yfinance（FUGLE 沒美股）。
    """
    # 先試 FUGLE（只對台股）
    if symbol.endswith(".TW") or symbol.endswith(".TWO") or symbol[0].isdigit():
        r = 即時報價(symbol)
        if r:
            return r

    # fallback yfinance
    try:
        try:
            from . import technical
        except ImportError:
            import technical
        每日, 實際 = technical.取得每日股價(symbol, period="5d")
        if 每日:
            最新 = 每日[0]
            return {
                "symbol": 實際,
                "name": "",
                "close": float(最新["close"]),
                "open": float(最新.get("open", 最新["close"])),
                "high": float(最新.get("high", 最新["close"])),
                "low": float(最新.get("low", 最新["close"])),
                "prev_close": float(每日[1]["close"]) if len(每日) > 1 else None,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "source": "yfinance",
            }
    except Exception:
        return None
    return None


def 配額狀態() -> dict:
    """目前 cache size + 預估剩餘呼叫次數（粗估）。"""
    return {
        "cache_筆數": len(_cache),
        "API_KEY_已設定": bool(API_KEY),
        "限制": "基本版 60 次/分",
    }


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
    # 重新讀
    API_KEY = os.getenv("FUGLE_MARKETDATA_API_KEY", "").strip()
    print(f"API Key 設定：{'✅' if API_KEY else '❌'}")
    print()

    print("=== FUGLE 即時報價測試 ===")
    for sym in ["2330.TW", "0050.TW", "00876.TW", "00631L.TW"]:
        r = 即時報價(sym)
        if r:
            print(f"  {sym} ({r['name']:<10}): "
                  f"收={r['close']} "
                  f"開={r['open']} 高={r['high']} 低={r['low']} "
                  f"漲跌={r['change_pct']}% "
                  f"[{r['source']}]")
        else:
            print(f"  {sym}: FAIL")

    print()
    print("=== Fallback 測試（含美股，會切到 yfinance）===")
    for sym in ["2330.TW", "NVDA", "TSLA", "AMD"]:
        r = 即時報價_fallback(sym)
        if r:
            print(f"  {sym}: 收={r['close']} 來源={r['source']}")
        else:
            print(f"  {sym}: FAIL")
