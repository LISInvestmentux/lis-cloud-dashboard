"""
驚喜因子 / Earnings Surprise（Phase 44 — 5/16）

「股票買的是未來」漏了**驚喜因子** — 股價反應的不是 good news，
而是「**比預期更好**」(earnings surprise positive)。

NVDA 過去 8 季都「比預期更好」→ 漲不停
一旦只是「跟預期一樣好」→ 立刻跌

LIS 加這個因子：
  1. 抓某股票最近 4 季 EPS surprise %
  2. 算「驚喜趨勢」（連續正 / 連續負 / 混合）
  3. 給推播卡用 — 「該抱」段加註「earnings 趨勢」

資料源: yfinance Ticker.earnings_dates
快取: 數據/cache/earnings_<symbol>.json
"""
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yfinance as yf

專案根 = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = 專案根 / "數據" / "cache"
CACHE_TTL_HOURS = 24  # 財報資料一天抓一次就夠


def _快取路徑(symbol: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = symbol.replace("/", "_").replace("\\", "_")
    return CACHE_DIR / f"earnings_{safe}.json"


def _讀快取(symbol: str) -> Optional[dict]:
    path = _快取路徑(symbol)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # 檢查 TTL
        if "_cached_at" in data:
            cached = datetime.fromisoformat(data["_cached_at"])
            if (datetime.now() - cached) < timedelta(hours=CACHE_TTL_HOURS):
                return data
    except Exception:
        pass
    return None


def _寫快取(symbol: str, data: dict) -> None:
    try:
        data["_cached_at"] = datetime.now().isoformat()
        _快取路徑(symbol).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8")
    except Exception:
        pass


def 取得財報歷史(symbol: str, 季數: int = 4) -> dict:
    """
    抓某股票最近 N 季財報的 EPS 預測 vs 實際

    Returns:
        {
            "symbol": "NVDA",
            "歷史": [
                {"date": "2025-11-20", "預期EPS": 0.85, "實際EPS": 0.95,
                 "surprise_pct": 11.8, "type": "BEAT"},
                ...
            ],
            "驚喜趨勢": "持續超預期 (4/4 季 BEAT)",
            "下次財報日": "2026-02-20" (如果有),
            "平均_surprise_pct": 8.5,
        }
    """
    # 先查快取
    cached = _讀快取(symbol)
    if cached:
        return cached

    result = {
        "symbol": symbol,
        "歷史": [],
        "驚喜趨勢": "資料不足",
        "下次財報日": None,
        "平均_surprise_pct": None,
    }

    try:
        ticker = yf.Ticker(symbol)
        # earnings_dates 包含過去 + 未來財報
        dates = ticker.earnings_dates
        if dates is None or dates.empty:
            _寫快取(symbol, result)
            return result

        # 排序：最新優先
        dates = dates.sort_index(ascending=False)

        # 分過去 / 未來
        now = datetime.now(dates.index.tz) if dates.index.tz else datetime.now()
        過去 = []
        未來 = []
        for idx, row in dates.iterrows():
            日期 = idx.strftime("%Y-%m-%d")
            預期 = row.get("EPS Estimate")
            實際 = row.get("Reported EPS")
            surprise_pct = row.get("Surprise(%)")

            if idx <= now:
                # 過去財報（要有實際 EPS）
                if 實際 is not None and not (isinstance(實際, float) and 實際 != 實際):
                    # 算 surprise%
                    if surprise_pct is None or (isinstance(surprise_pct, float) and surprise_pct != surprise_pct):
                        if 預期 and 預期 != 0:
                            surprise_pct = (實際 - 預期) / abs(預期) * 100
                        else:
                            surprise_pct = 0
                    type_ = "BEAT" if surprise_pct > 0 else ("MISS" if surprise_pct < 0 else "INLINE")
                    過去.append({
                        "date": 日期,
                        "預期EPS": round(float(預期), 2) if 預期 else None,
                        "實際EPS": round(float(實際), 2),
                        "surprise_pct": round(float(surprise_pct), 1),
                        "type": type_,
                    })
            else:
                未來.append(日期)

        # 取最近 N 季
        result["歷史"] = 過去[:季數]
        if 未來:
            result["下次財報日"] = 未來[-1]  # 最近的未來

        # 算驚喜趨勢
        if result["歷史"]:
            beats = sum(1 for r in result["歷史"] if r["type"] == "BEAT")
            misses = sum(1 for r in result["歷史"] if r["type"] == "MISS")
            total = len(result["歷史"])
            avg = sum(r["surprise_pct"] for r in result["歷史"]) / total
            result["平均_surprise_pct"] = round(avg, 1)

            if beats == total:
                result["驚喜趨勢"] = f"🟢 持續超預期 ({beats}/{total} BEAT, 平均 +{avg:.1f}%)"
            elif misses == total:
                result["驚喜趨勢"] = f"🔴 持續失望 ({misses}/{total} MISS, 平均 {avg:.1f}%)"
            elif beats > misses:
                result["驚喜趨勢"] = f"🟡 偏正面 ({beats} BEAT vs {misses} MISS, 平均 {avg:+.1f}%)"
            else:
                result["驚喜趨勢"] = f"🟠 偏負面 ({beats} BEAT vs {misses} MISS, 平均 {avg:+.1f}%)"

    except Exception as e:
        result["error"] = str(e)[:200]

    _寫快取(symbol, result)
    return result


def 批量分析(symbols: list, sleep_sec: float = 0.5) -> dict:
    """
    一次分析多檔股票（限制 sleep 避免 yfinance rate limit）

    Returns:
        {symbol: 財報歷史_dict, ...}
    """
    results = {}
    for sym in symbols:
        try:
            results[sym] = 取得財報歷史(sym)
            time.sleep(sleep_sec)
        except Exception as e:
            results[sym] = {"symbol": sym, "error": str(e)[:100]}
    return results


# ════════════════════════════════════════════
# CLI 測試
# ════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=" * 60)
    print("驚喜因子測試（user 持股美股）")
    print("=" * 60)

    test_symbols = ["NVDA", "AMD", "MU", "LRCX", "ADBE"]
    for sym in test_symbols:
        print(f"\n[{sym}]")
        r = 取得財報歷史(sym, 季數=4)
        if "error" in r:
            print(f"  ❌ {r['error']}")
            continue
        print(f"  驚喜趨勢: {r.get('驚喜趨勢', 'N/A')}")
        if r.get("下次財報日"):
            print(f"  下次財報: {r['下次財報日']}")
        for h in r.get("歷史", [])[:4]:
            print(f"    {h['date']}: 預期 {h['預期EPS']} / 實際 {h['實際EPS']} "
                  f"({h['surprise_pct']:+.1f}% {h['type']})")
        time.sleep(0.5)
