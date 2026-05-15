"""
盤中即時警示推播（Phase 8.4）
每 30 分鐘檢查一次真倉，達 +15%/-5% 立刻推 LINE。

執行方式：
  .venv\\Scripts\\python.exe intraday_real_alert.py

Windows 排程任務：
  - LIS_Intraday_TW: 週一-五 09:30/10:00/10:30/11:00/11:30/12:00/12:30/13:00
  - LIS_Intraday_US: 週一-五（夜）23:00/23:30/00:00/00:30/01:00/.../03:30

去重機制：
  - 已推送的訊號記錄在 數據/intraday_alerts.json
  - 同檔同訊號 24 小時內不重推
"""
import json
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))

from dotenv import load_dotenv
load_dotenv(專案根.parent / "API" / ".env")

from modules import (capital_planner, portfolio_tracker,
                     flex_builder, line_push, forex)


數據根 = 專案根.parent / "數據"
警示紀錄路徑 = 數據根 / "intraday_alerts.json"

去重TTL_HOURS = 24   # 同檔同訊號 24h 內不重推


# ─────────────────────────────────────────────
# 去重紀錄
# ─────────────────────────────────────────────
def _載入警示紀錄() -> dict:
    if not 警示紀錄路徑.exists():
        return {"alerts": []}
    try:
        with open(警示紀錄路徑, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"alerts": []}


def _儲存警示紀錄(資料: dict) -> None:
    警示紀錄路徑.parent.mkdir(parents=True, exist_ok=True)
    with open(警示紀錄路徑, "w", encoding="utf-8") as f:
        json.dump(資料, f, ensure_ascii=False, indent=2)


def _清理過期(紀錄: dict) -> dict:
    """刪 24 小時前的紀錄。"""
    cutoff = datetime.now() - timedelta(hours=去重TTL_HOURS)
    cutoff_iso = cutoff.isoformat()
    紀錄["alerts"] = [a for a in 紀錄.get("alerts", [])
                       if a.get("time", "") > cutoff_iso]
    return 紀錄


def _已推過(紀錄: dict, symbol: str, 類型: str) -> bool:
    """檢查 24h 內是否推過這個 symbol+類型。"""
    for a in 紀錄.get("alerts", []):
        if a.get("symbol") == symbol and a.get("type") == 類型:
            return True
    return False


def _記錄推送(紀錄: dict, symbol: str, 類型: str, pnl_pct: float) -> None:
    紀錄.setdefault("alerts", []).append({
        "symbol": symbol,
        "type": 類型,
        "pnl_pct": pnl_pct,
        "time": datetime.now().isoformat(timespec="seconds"),
    })


# ─────────────────────────────────────────────
# 市場時間判斷
# ─────────────────────────────────────────────
def _目前市場() -> str:
    """回傳 'TW' / 'US' / 'CLOSED'"""
    now = datetime.now()
    h, m = now.hour, now.minute
    weekday = now.weekday()  # 0=Mon
    # 週末跳過
    if weekday >= 5:
        return "CLOSED"

    當前分 = h * 60 + m
    # 台股 09:00-13:30
    if 9 * 60 <= 當前分 <= 13 * 60 + 30:
        return "TW"
    # 美股 22:30-04:00（夏令）或 21:30-04:00（粗略）
    if 當前分 >= 21 * 60 + 30 or 當前分 <= 4 * 60:
        return "US"
    return "CLOSED"


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────
def 主流程() -> int:
    開始 = datetime.now()
    市場 = _目前市場()
    print(f"=== 盤中即時警示 [{開始:%Y-%m-%d %H:%M:%S}] 市場={市場} ===")

    if 市場 == "CLOSED":
        print("市場休市，跳過")
        return 0

    # 載入持股 + 即時匯率
    cfg = capital_planner.載入資金設定()
    固定匯率 = cfg.get("currency_rates", {}).get("USD_TWD", 32.0)
    匯率 = forex.取得匯率_純數字(fallback=固定匯率)

    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=匯率)
    警示 = 真倉.get("警示", {})
    達停利 = 警示.get("達停利", [])
    破停損 = 警示.get("破停損", [])

    if not (達停利 or 破停損):
        print(f"無 +15%/-5% 觸發訊號（持股 {真倉['總計']['總檔數']} 檔）")
        return 0

    # 依市場過濾（台股盤中只警示台股，美股盤中只警示美股）
    def _過濾(清單):
        if 市場 == "TW":
            return [r for r in 清單 if not r.get("is_us")]
        if 市場 == "US":
            return [r for r in 清單 if r.get("is_us")]
        return 清單

    達停利 = _過濾(達停利)
    破停損 = _過濾(破停損)

    # 去重檢查
    紀錄 = _清理過期(_載入警示紀錄())
    新推送 = []

    for r in 達停利:
        if not _已推過(紀錄, r["symbol"], "TAKE_PROFIT"):
            新推送.append((r, "TAKE_PROFIT"))
    for r in 破停損:
        if not _已推過(紀錄, r["symbol"], "STOP_LOSS"):
            新推送.append((r, "STOP_LOSS"))

    if not 新推送:
        print(f"觸發 {len(達停利) + len(破停損)} 檔但 24h 內已推過，跳過")
        return 0

    print(f"觸發新警示：{len(新推送)} 筆")

    # 建立精簡 Flex 卡（只放這幾筆新觸發）
    新真倉 = {
        "持股": 真倉["持股"],
        "總計": 真倉["總計"],
        "警示": {
            "達停利": [r for r, t in 新推送 if t == "TAKE_PROFIT"],
            "破停損": [r for r, t in 新推送 if t == "STOP_LOSS"],
            "接近停利": [],
            "接近停損": [],
        },
        "有警示": True,
    }
    卡 = flex_builder.建構真倉警示卡(新真倉)
    if not 卡:
        print("無有效警示卡")
        return 0

    carousel = {"type": "carousel", "contents": [卡]}
    時段標 = "台股盤中" if 市場 == "TW" else "美股盤中"
    alt = f"⚡ LIS 盤中警示（{時段標}）— {len(新推送)} 筆觸發 {datetime.now():%H:%M}"

    try:
        line_push.推播Flex訊息(替代文字=alt, flex內容=carousel)
        print(f"✅ 推播成功！")
        # 記錄已推
        for r, t in 新推送:
            _記錄推送(紀錄, r["symbol"], t, r.get("pnl_pct", 0))
            print(f"   {t} {r['symbol']} ({r.get('name','')}) "
                  f"{r.get('pnl_pct'):.2f}%")
        _儲存警示紀錄(紀錄)
    except Exception as e:
        print(f"❌ 推播失敗：{e}")
        traceback.print_exc()
        return 1

    耗時 = (datetime.now() - 開始).total_seconds()
    print(f"完成（耗時 {耗時:.1f} 秒）")
    return 0


if __name__ == "__main__":
    sys.exit(主流程())
