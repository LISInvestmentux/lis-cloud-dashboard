"""
台灣證交所公告模組（Phase 8.0d / 處置股 L2）
從證交所 OpenAPI 抓「處置股」與「注意股」清單，
給 sim_ledger 寫入訊號時做可成交性檢查用。

處置股：流動性差、撮合間隔變慢、滑價放大
  - 第一階段：20 分鐘撮合一次
  - 第二階段：20 分鐘撮合 + 預收款券

API:
  https://openapi.twse.com.tw/v1/announcement/punish  — 處置標的
  https://openapi.twse.com.tw/v1/announcement/notice  — 注意股

Cache 24 小時（每天主程式跑時更新）。
"""
import json
import ssl
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
快取路徑 = 專案根 / "數據" / "tw_announcements_cache.json"

PUNISH_URL = "https://openapi.twse.com.tw/v1/announcement/punish"
NOTICE_URL = "https://openapi.twse.com.tw/v1/announcement/notice"
QFIIS_SORT_URL = "https://openapi.twse.com.tw/v1/fund/MI_QFIIS_sort_20"
# Phase 6.2 外資持股前 20（買盤集中度指標）

CACHE_TTL_HOURS = 24


# ─────────────────────────────────────────────
# 民國年 ↔ 西元年
# ─────────────────────────────────────────────
def _民國轉西元(民國日期: str) -> Optional[str]:
    """
    "115/05/06" → "2026-05-06"
    "115/05/07～115/05/20" 也支援，取第一段
    """
    if not 民國日期:
        return None
    日期 = 民國日期.split("～")[0].strip().split("~")[0].strip()
    parts = 日期.split("/")
    if len(parts) != 3:
        return None
    try:
        年 = int(parts[0]) + 1911
        月 = int(parts[1])
        日 = int(parts[2])
        return f"{年:04d}-{月:02d}-{日:02d}"
    except ValueError:
        return None


def _解析處置期間(period: str) -> tuple[Optional[str], Optional[str]]:
    """
    "115/05/07～115/05/20" → ("2026-05-07", "2026-05-20")
    """
    if not period:
        return (None, None)
    parts = period.replace("~", "～").split("～")
    if len(parts) < 2:
        return (None, None)
    return (_民國轉西元(parts[0].strip()), _民國轉西元(parts[1].strip()))


# ─────────────────────────────────────────────
# HTTP 抓取
# ─────────────────────────────────────────────
def _抓JSON(url: str, timeout: int = 10) -> list[dict]:
    """簡單 GET，回傳 list[dict]。失敗 raise。
    證交所 OpenAPI 偶有 SSL 證書問題，改用寬鬆 context（公開 API 不影響安全）。"""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "LIS-Investment-System/1.0"}
    )
    # 為證交所 OpenAPI 建立寬鬆 SSL context
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        資料 = json.loads(resp.read().decode("utf-8"))
    if not isinstance(資料, list):
        raise ValueError(f"預期 list 但收到 {type(資料).__name__}")
    return 資料


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
    更新時間_str = 快取.get("updated_at")
    if not 更新時間_str:
        return True
    try:
        更新時間 = datetime.fromisoformat(更新時間_str)
    except ValueError:
        return True
    距今小時 = (datetime.now() - 更新時間).total_seconds() / 3600
    return 距今小時 >= CACHE_TTL_HOURS


# ─────────────────────────────────────────────
# 主 API：取得處置股 + 注意股清單
# ─────────────────────────────────────────────
def 取得公告清單(強制更新: bool = False) -> dict:
    """
    回傳：
      {
        "updated_at": ISO 時間,
        "處置股": [{code, name, start_date, end_date, reason}],
        "注意股": [{code, name, date}],
      }

    自動 cache 24 小時。若 API 失敗則回傳上次快取（即使過期）。
    """
    快取 = _載入快取()
    if not 強制更新 and 快取 and not _快取過期(快取):
        return 快取

    處置股 = []
    注意股 = []
    錯誤訊息 = []

    try:
        for r in _抓JSON(PUNISH_URL):
            start, end = _解析處置期間(r.get("DispositionPeriod", ""))
            處置股.append({
                "code": (r.get("Code") or "").strip(),
                "name": (r.get("Name") or "").strip(),
                "start_date": start,
                "end_date": end,
                "reason": r.get("ReasonsOfDisposition", "").strip(),
                "measure": r.get("DispositionMeasures", "").strip(),
            })
    except Exception as e:
        錯誤訊息.append(f"處置股抓取失敗: {e}")

    try:
        for r in _抓JSON(NOTICE_URL):
            code = (r.get("Code") or "").strip()
            if not code:
                continue
            注意股.append({
                "code": code,
                "name": (r.get("Name") or "").strip(),
                "date": _民國轉西元(r.get("Date", "")),
                "reason": r.get("TradingInfoForAttention", "").strip(),
            })
    except Exception as e:
        錯誤訊息.append(f"注意股抓取失敗: {e}")

    # 外資持股前 20（Phase 6.2）
    外資前20 = []
    try:
        for r in _抓JSON(QFIIS_SORT_URL):
            code = (r.get("Code") or "").strip()
            if not code:
                continue
            try:
                持股比例 = float(r.get("SharesHeldPer", 0))
            except (ValueError, TypeError):
                持股比例 = 0.0
            外資前20.append({
                "rank": int(r.get("Rank", 0) or 0),
                "code": code,
                "name": (r.get("Name") or "").strip(),
                "shares_held_pct": 持股比例,
            })
    except Exception as e:
        錯誤訊息.append(f"外資前20抓取失敗: {e}")

    新快取 = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "處置股": 處置股,
        "注意股": 注意股,
        "外資前20": 外資前20,
        "errors": 錯誤訊息,
    }

    # 若全部都失敗且有舊快取，回傳舊快取
    if 不是合理的更新(新快取) and 快取:
        return 快取

    _儲存快取(新快取)
    return 新快取


def 不是合理的更新(新快取: dict) -> bool:
    """全部空 + 有錯誤 → 視為失敗（保留舊 cache）。"""
    return (not 新快取["處置股"]
            and not 新快取["注意股"]
            and not 新快取.get("外資前20")
            and bool(新快取["errors"]))


def 查詢外資前20命中(symbols: list[str],
                      清單: Optional[dict] = None) -> list[dict]:
    """
    給定 symbols（e.g. ['2330.TW', '2317.TW']），
    回傳這些 symbol 中**有在外資持股前 20** 的清單。
    """
    清單 = 清單 if 清單 is not None else 取得公告清單()
    前20_code_set = {r["code"] for r in 清單.get("外資前20", [])}
    前20_map = {r["code"]: r for r in 清單.get("外資前20", [])}

    命中 = []
    for sym in symbols:
        code = _symbol轉code(sym)
        if code in 前20_code_set:
            命中.append({**前20_map[code], "symbol": sym})
    命中.sort(key=lambda r: r.get("rank", 99))
    return 命中


# ─────────────────────────────────────────────
# 查詢 API（給 sim_ledger 用）
# ─────────────────────────────────────────────
def _symbol轉code(symbol: str) -> str:
    """2330.TW → 2330  /  0050.TW → 0050"""
    return symbol.replace(".TW", "").replace(".TWO", "").strip()


def 是否處置股(symbol: str, 今日: Optional[str] = None,
                清單: Optional[dict] = None) -> dict:
    """
    判斷某 symbol 是否在處置期間內。
    回傳：{"是否處置": bool, "原因": str, "結束日": str}
    """
    if not (symbol.endswith(".TW") or symbol.endswith(".TWO")):
        return {"是否處置": False, "原因": "", "結束日": ""}

    清單 = 清單 if 清單 is not None else 取得公告清單()
    code = _symbol轉code(symbol)
    今日 = 今日 or datetime.now().strftime("%Y-%m-%d")

    for r in 清單.get("處置股", []):
        if r["code"] != code:
            continue
        start = r.get("start_date")
        end = r.get("end_date")
        if start and end and start <= 今日 <= end:
            return {
                "是否處置": True,
                "原因": f"{r.get('measure', '處置')}：{r.get('reason', '')}".strip(": "),
                "結束日": end,
            }
    return {"是否處置": False, "原因": "", "結束日": ""}


def 是否注意股(symbol: str, 清單: Optional[dict] = None) -> bool:
    """是否在注意股清單中（today 公告日，無期間）。"""
    if not (symbol.endswith(".TW") or symbol.endswith(".TWO")):
        return False
    清單 = 清單 if 清單 is not None else 取得公告清單()
    code = _symbol轉code(symbol)
    return any(r["code"] == code for r in 清單.get("注意股", []))


# ─────────────────────────────────────────────
# CLI 自測
# ─────────────────────────────────────────────
if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=== 抓證交所公告清單 ===")
    清單 = 取得公告清單(強制更新=True)
    print(f"更新時間：{清單['updated_at']}")
    print(f"處置股：{len(清單['處置股'])} 筆")
    print(f"注意股：{len(清單['注意股'])} 筆")
    print(f"外資前20：{len(清單.get('外資前20', []))} 筆")
    if 清單["errors"]:
        print(f"⚠️ 錯誤：{清單['errors']}")

    print()
    print("=== 外資前 20（前 5）===")
    for r in 清單.get("外資前20", [])[:5]:
        print(f"  #{r['rank']:>2} {r['code']:>5} {r['name']:<10} "
              f"持股 {r['shares_held_pct']}%")

    print()
    print("=== 處置股清單（前 5）===")
    for r in 清單["處置股"][:5]:
        print(f"  {r['code']:>5} {r['name']:<10} "
              f"{r['start_date']} ~ {r['end_date']} "
              f"{r['measure']} / {r['reason']}")

    print()
    print("=== 查詢測試 ===")
    for sym in ["2330.TW", "1597.TW", "1809.TW"]:
        r = 是否處置股(sym, 清單=清單)
        print(f"  {sym}: 處置={r['是否處置']} 原因={r['原因']} 結束日={r['結束日']}")
