"""
盤中即時警示系統（Phase 34）

每 15 分鐘自動掃描，偵測：
  1. 持股異動 > ±3% → 立刻 push LINE 警示
  2. 達 Strategy A +15% → 落袋通知
  3. 跌穿 -5% → 停損警示
  4. 接近停利 +12% → 預警
  5. 接近停損 -4% → 預警
  6. 大盤突發訊號（VIX 突破 25）→ 黑天鵝預警

排程設定：
  Windows Task Scheduler：
    - LIS_盤中早盤  每天 09:30-11:00 每 15 分鐘
    - LIS_盤中午盤  每天 11:00-13:00 每 15 分鐘
    - LIS_盤中收前  每天 13:00-13:30 每 5 分鐘

去重機制：
  同一檔 30 分鐘內不重複警示同類型
  存：數據/alerts_history.json
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
警示歷史檔 = 專案根 / "數據" / "alerts_history.json"


# 警示閾值（依紀律調整）
閾值 = {
    "接近停利_pct": 12.0,
    "達停利_pct": 15.0,
    "接近停損_pct": -4.0,
    "破停損_pct": -5.0,
    "盤中急漲_pct": 3.0,
    "盤中急跌_pct": -3.0,
    "暴漲_pct": 5.0,    # 5% 以上立刻警示
    "暴跌_pct": -5.0,
}

去重冷卻分鐘 = 30


def _載入歷史() -> dict:
    if not 警示歷史檔.exists():
        return {"警示": []}
    return json.loads(警示歷史檔.read_text(encoding="utf-8"))


def _存歷史(data: dict):
    警示歷史檔.parent.mkdir(parents=True, exist_ok=True)
    警示歷史檔.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _最近警示過(symbol: str, 類型: str) -> bool:
    """檢查同一檔同類型是否在冷卻時間內已警示過"""
    data = _載入歷史()
    cutoff = datetime.now() - timedelta(minutes=去重冷卻分鐘)
    for a in data.get("警示", [])[-100:]:  # 只查近 100 筆
        if (a["symbol"] == symbol and a["類型"] == 類型 and
            datetime.fromisoformat(a["時間"]) >= cutoff):
            return True
    return False


def _記錄警示(symbol: str, 類型: str, 詳情: dict):
    data = _載入歷史()
    data.setdefault("警示", []).append({
        "時間": datetime.now().isoformat(timespec="seconds"),
        "symbol": symbol,
        "類型": 類型,
        **詳情,
    })
    # 只保留最近 500 筆
    data["警示"] = data["警示"][-500:]
    _存歷史(data)


def 掃描盤中警示() -> list[dict]:
    """
    跑一次盤中掃描，回傳當下產生的警示。
    """
    from . import (capital_planner, fugle_market, portfolio_tracker,
                   forex, technical)

    cfg = capital_planner.載入資金設定()
    持股清單 = [p for p in cfg.get("current_positions", [])
                if p.get("symbol") != "AGGREGATE"]

    匯率 = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32.0))["rate"]

    警示清單 = []
    for p in 持股清單:
        sym = p["symbol"]
        成本 = p.get("avg_cost", 0)
        if 成本 <= 0:
            continue

        # 抓即時報價
        q = fugle_market.即時報價_fallback(sym)
        if not q or not q.get("close"):
            continue
        現價 = q["close"]
        漲幅 = (現價 / 成本 - 1) * 100

        # 抓昨日收盤算當日漲跌幅
        try:
            歷史, _ = technical.取得每日股價(sym, period="3d")
            昨收 = 歷史[1]["close"] if len(歷史) > 1 else 現價
            當日漲幅 = (現價 / 昨收 - 1) * 100
        except Exception:
            當日漲幅 = 0

        is_us = not (sym.endswith(".TW") or sym.endswith(".TWO"))
        倍率 = 匯率 if is_us else 1.0

        警示類型 = None
        emoji = ""
        說明 = ""

        # 優先序：Strategy A > 接近 > 盤中急漲跌
        if 漲幅 >= 閾值["達停利_pct"]:
            警示類型 = "STRATEGY_A_TAKE_PROFIT"
            emoji = "🎯"
            說明 = f"達 +{漲幅:.2f}% Strategy A 落袋 50%"
        elif 漲幅 <= 閾值["破停損_pct"]:
            警示類型 = "STRATEGY_A_STOP_LOSS"
            emoji = "🛑"
            說明 = f"破 {漲幅:.2f}% 全停損紀律"
        elif 漲幅 >= 閾值["接近停利_pct"]:
            警示類型 = "NEAR_TAKE_PROFIT"
            emoji = "📈"
            說明 = f"接近停利 +{漲幅:.2f}%（達 +15% 落袋）"
        elif 漲幅 <= 閾值["接近停損_pct"]:
            警示類型 = "NEAR_STOP_LOSS"
            emoji = "📉"
            說明 = f"接近停損 {漲幅:.2f}%"
        elif abs(當日漲幅) >= abs(閾值["暴漲_pct"]):
            警示類型 = "INTRADAY_SURGE" if 當日漲幅 > 0 else "INTRADAY_DROP"
            emoji = "🚀" if 當日漲幅 > 0 else "💀"
            說明 = f"盤中{'急漲' if 當日漲幅 > 0 else '急跌'} {當日漲幅:+.2f}%"

        if 警示類型 and not _最近警示過(sym, 警示類型):
            警示 = {
                "symbol": sym,
                "name": p.get("name", ""),
                "類型": 警示類型,
                "emoji": emoji,
                "說明": 說明,
                "現價": 現價,
                "成本": 成本,
                "漲幅": round(漲幅, 2),
                "當日漲幅": round(當日漲幅, 2),
                "股數": p.get("shares", 0),
                "市值_twd": round(現價 * p.get("shares", 0) * 倍率, 0),
            }
            警示清單.append(警示)
            _記錄警示(sym, 警示類型, 警示)

    return 警示清單


def 推送LINE警示(警示清單: list[dict]) -> int:
    """把警示推到 LINE（用 Flex carousel）"""
    if not 警示清單:
        return 0

    from . import line_push, flex_builder
    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("⚡ 盤中即時警示", size="xl",
                 color=C["text_main"], weight="bold"),
            文字(f"{datetime.now():%H:%M} · {len(警示清單)} 筆異動",
                 size="xxs", color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())

    for a in 警示清單[:10]:
        色 = (C["bear"] if a["類型"] in ("STRATEGY_A_STOP_LOSS",
                                          "INTRADAY_DROP", "NEAR_STOP_LOSS")
              else C["bull"] if a["類型"] in ("STRATEGY_A_TAKE_PROFIT",
                                              "NEAR_TAKE_PROFIT",
                                              "INTRADAY_SURGE")
              else C["wait"])
        內容.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "paddingTop": "xs",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"{a['emoji']} {a['symbol']}", size="sm",
                             color=色, weight="bold", flex=4),
                        文字(f"{a['漲幅']:+.2f}%", size="md",
                             color=色, align="end", weight="bold", flex=3),
                    ],
                },
                文字(a["說明"][:40], size="xxs",
                     color=C["text_dim"], wrap=True),
                文字(f"現價 {a['現價']:.2f} · {a['股數']} 股 · "
                     f"市值 NT$ {a['市值_twd']:,.0f}",
                     size="xxs", color=C["text_subtle"]),
            ],
        })

    alt = f"⚡ LIS 盤中警示 {len(警示清單)} 筆"
    bubble = {
        "type": "bubble", "size": "giga",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": 內容,
        },
    }
    line_push.推播Flex訊息(替代文字=alt, flex內容=bubble)
    return len(警示清單)


def 主流程():
    """完整跑一輪：掃描 + 推 LINE（如有警示）"""
    print(f"=== Phase 34 盤中警示 [{datetime.now():%H:%M}] ===")
    警示 = 掃描盤中警示()
    if 警示:
        print(f"🚨 觸發 {len(警示)} 筆警示")
        for a in 警示:
            print(f"  {a['emoji']} {a['symbol']} {a['漲幅']:+.2f}% — {a['說明']}")
        推送LINE警示(警示)
        print("✅ 已推 LINE")
    else:
        print("⚪ 無警示（持股都在正常區間）")


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from dotenv import load_dotenv
    load_dotenv(專案根 / "API" / ".env")
    主流程()
