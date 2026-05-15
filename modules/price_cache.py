"""
股價快取層（Phase 32.7）

解決 yfinance 限流問題 — 同檔股 N 分鐘內不重抓，從快取讀。

設計：
  - 雙層快取：記憶體 (process 期間) + 磁碟 (跨 process 共用)
  - 預設 TTL 30 分鐘（足夠 LIS 用，不會卡到 8AM/22:30 排程）
  - 強制 refresh 模式（給排程任務用）

存放：
  D:/LIS股票投資系統/數據/price_cache/{symbol}_{period}.json
  D:/LIS股票投資系統/數據/price_cache/quote_{symbol}.json

用法：
  從 technical.取得每日股價 / fugle_market.即時報價_fallback 內部呼叫。
"""
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Callable


專案根 = Path(__file__).resolve().parent.parent.parent
快取目錄 = 專案根 / "數據" / "price_cache"

# 預設 TTL（秒）
DAILY_TTL = 30 * 60          # 每日 K 線 30 分鐘
QUOTE_TTL = 5 * 60           # 即時報價 5 分鐘

# Process 記憶體快取（避免重複讀磁碟）
_記憶體快取: dict = {}


def _安全檔名(s: str) -> str:
    """把 ^/= 等字元換掉避免檔案系統錯誤"""
    return s.replace("/", "_").replace("\\", "_").replace("^", "IDX_")


def _磁碟快取_讀(key: str, ttl_秒: int) -> Optional[dict]:
    """從磁碟讀，超過 TTL 回 None"""
    f = 快取目錄 / f"{_安全檔名(key)}.json"
    if not f.exists():
        return None
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        當下 = time.time()
        if 當下 - d.get("_快取時間", 0) > ttl_秒:
            return None
        return d.get("data")
    except Exception:
        return None


def _磁碟快取_寫(key: str, data) -> None:
    快取目錄.mkdir(parents=True, exist_ok=True)
    f = 快取目錄 / f"{_安全檔名(key)}.json"
    payload = {"_快取時間": time.time(), "data": data}
    try:
        f.write_text(json.dumps(payload, ensure_ascii=False),
                      encoding="utf-8")
    except Exception:
        pass


def 取得或抓(key: str,
              抓取函式: Callable,
              ttl_秒: int = DAILY_TTL,
              強制更新: bool = False):
    """
    通用快取入口：先查 memory → 查 disk → 都沒就跑抓取函式
    強制更新=True 跳過所有快取直接抓
    """
    # 1. 記憶體快取
    if not 強制更新 and key in _記憶體快取:
        ts, data = _記憶體快取[key]
        if time.time() - ts <= ttl_秒:
            return data, "memory"

    # 2. 磁碟快取
    if not 強制更新:
        data = _磁碟快取_讀(key, ttl_秒)
        if data is not None:
            _記憶體快取[key] = (time.time(), data)
            return data, "disk"

    # 3. 真的抓
    try:
        data = 抓取函式()
        if data is not None:
            _記憶體快取[key] = (time.time(), data)
            _磁碟快取_寫(key, data)
            return data, "live"
    except Exception as e:
        # 抓失敗時 fallback 到過期快取（總比沒有好）
        f = 快取目錄 / f"{_安全檔名(key)}.json"
        if f.exists():
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                return d.get("data"), "stale"
            except Exception:
                pass
        raise e

    return None, "miss"


def 清除過期(超過天數: int = 7) -> int:
    """清掉超過 N 天的快取檔（保健康）"""
    if not 快取目錄.exists():
        return 0
    cutoff = time.time() - 超過天數 * 86400
    清掉 = 0
    for f in 快取目錄.glob("*.json"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                清掉 += 1
        except Exception:
            pass
    return 清掉


def 統計() -> dict:
    """快取狀態"""
    記憶體數 = len(_記憶體快取)
    磁碟數 = 0
    磁碟大小 = 0
    if 快取目錄.exists():
        for f in 快取目錄.glob("*.json"):
            磁碟數 += 1
            try:
                磁碟大小 += f.stat().st_size
            except Exception:
                pass
    return {
        "記憶體_筆數": 記憶體數,
        "磁碟_筆數": 磁碟數,
        "磁碟_KB": round(磁碟大小 / 1024, 1),
        "目錄": str(快取目錄),
    }


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("=== 股價快取狀態 ===")
    s = 統計()
    for k, v in s.items():
        print(f"  {k}: {v}")
    清 = 清除過期(7)
    print(f"\n清掉 {清} 筆超過 7 天的舊快取")
