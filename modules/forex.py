"""
動態匯率模組（USD/TWD 即時匯率）
從 yfinance 抓 `TWD=X` ticker，10 分鐘 cache。
失敗時 fallback 到 portfolio.json 的固定值。
"""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
快取路徑 = 專案根 / "數據" / "forex_cache.json"

CACHE_TTL_SECONDS = 600   # 10 分鐘

FALLBACK_USD_TWD = 32.0   # yfinance fail 時最後 fallback


# ─────────────────────────────────────────────
# Cache 機制
# ─────────────────────────────────────────────
def _載入快取() -> Optional[dict]:
    if not 快取路徑.exists():
        return None
    try:
        with open(快取路徑, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _儲存快取(資料: dict) -> None:
    快取路徑.parent.mkdir(parents=True, exist_ok=True)
    with open(快取路徑, "w", encoding="utf-8") as f:
        json.dump(資料, f, ensure_ascii=False, indent=2)


def _快取過期(快取: dict) -> bool:
    ts = 快取.get("timestamp")
    if not ts:
        return True
    return (time.time() - ts) >= CACHE_TTL_SECONDS


# ─────────────────────────────────────────────
# 主 API
# ─────────────────────────────────────────────
def 取得USD_TWD匯率(強制更新: bool = False,
                     fallback: Optional[float] = None) -> dict:
    """
    回傳：{
      "rate": float USD/TWD,
      "source": "yfinance" / "cache" / "fallback",
      "updated_at": ISO time,
      "age_seconds": int,
    }
    """
    fallback = fallback or FALLBACK_USD_TWD
    now = time.time()

    # 1. 試 cache
    快取 = _載入快取()
    if not 強制更新 and 快取 and not _快取過期(快取):
        快取["source"] = "cache"
        快取["age_seconds"] = int(now - 快取["timestamp"])
        return 快取

    # 2. 抓 yfinance（USD/TWD = "TWD=X"）
    try:
        import yfinance as yf
        ticker = yf.Ticker("TWD=X")
        # 用 history 抓最近 1 天最可靠
        df = ticker.history(period="2d")
        if not df.empty:
            rate = float(df["Close"].iloc[-1])
            if rate > 0:
                資料 = {
                    "rate": round(rate, 4),
                    "timestamp": now,
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                    "source": "yfinance",
                    "age_seconds": 0,
                }
                _儲存快取(資料)
                return 資料
    except Exception as e:
        print(f"  ⚠️ yfinance 抓匯率失敗：{e}")

    # 3. fallback 到舊 cache（即使過期）
    if 快取:
        快取["source"] = "stale_cache"
        快取["age_seconds"] = int(now - 快取.get("timestamp", now))
        return 快取

    # 4. 最後 fallback 固定值
    return {
        "rate": fallback,
        "source": "fallback",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "age_seconds": 0,
    }


def 取得匯率_純數字(fallback: Optional[float] = None) -> float:
    """簡化版：只回傳數字。給不需要詳情的場景用。"""
    return 取得USD_TWD匯率(fallback=fallback)["rate"]


# ─────────────────────────────────────────────
# CLI 自測
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=== USD/TWD 動態匯率 ===")
    r = 取得USD_TWD匯率(強制更新=True)
    print(f"匯率：{r['rate']} TWD = 1 USD")
    print(f"來源：{r['source']}")
    print(f"更新時間：{r.get('updated_at')}")
    print(f"快取年齡：{r.get('age_seconds')} 秒")

    print()
    print("=== 再抓一次（應該從 cache 來）===")
    r2 = 取得USD_TWD匯率()
    print(f"匯率：{r2['rate']} TWD = 1 USD")
    print(f"來源：{r2['source']}")
    print(f"快取年齡：{r2.get('age_seconds')} 秒")
