"""
真倉部位追蹤（Phase 8.3）
從 portfolio.json 抓你實際持股，搭配 yfinance 即時股價，
算出每檔的 P&L、找達停利停損閾值的個股。

跟模擬盤的差別：
  模擬盤（sim_ledger）= 系統訊號發出的虛擬部位
  真倉（這個模組）= 你 portfolio.json 裡真實持有的股票

回傳結構供 flex_builder 用：
{
  "持股": [{symbol, name, shares, avg_cost, current, pnl_pct, pnl_twd,
            market_value_twd, 警示_類型}, ...],
  "總計": {成本_twd, 市值_twd, 損益_twd, 損益率, 賺檔數, 賠檔數, 總檔數},
  "警示": {達停利: [...], 破停損: [...], 接近停利: [...], 接近停損: [...]},
}
"""
import re
from typing import Optional


停利_PCT = 15.0      # 達 +15% → 建議停利
停損_PCT = -5.0      # 破 -5% → 建議停損（台股）
接近停利_PCT = 12.0  # 達 +12% → 接近停利（提早警示）
接近停損_PCT = -4.0  # 達 -4% → 接近停損（台股）

# Phase 32.6：美股專用 — 波動大，停損更嚴（ARK 戰法）
美股停損_PCT = -3.0       # 破 -3% → 美股停損
美股近停損_PCT = -2.0     # 達 -2% → 美股接近停損


def _規範化代號(原始: str) -> str:
    """台股代號自動補 .TW。"""
    s = (原始 or "").strip().upper()
    if not s:
        return ""
    if s.endswith(".TW") or s.endswith(".TWO"):
        return s
    if s.isalpha():
        return s
    if re.match(r"^\d", s):
        return s + ".TW"
    return s


def 追蹤真倉(設定: dict,
              個股分析清單: Optional[list[dict]] = None,
              USD_TWD: Optional[float] = None,
              強制即時: bool = True) -> dict:
    """
    主入口。從 portfolio.json 設定計算真倉狀態。

    設定: capital_planner.載入資金設定() 的結果
    個股分析清單: 不再使用（保留參數兼容舊呼叫）
    USD_TWD: 美股換 TWD 用（None = 動態抓 yfinance 即時匯率）
    強制即時: True（預設）= 永遠抓最新 yfinance 確保警示準確

    回傳結構見模組 docstring。
    """
    try:
        from . import technical, forex, fugle_market
    except ImportError:
        import technical
        import forex
        import fugle_market

    # 動態匯率（USD_TWD = None 時抓即時）
    if USD_TWD is None:
        固定 = 設定.get("currency_rates", {}).get("USD_TWD", 32.0)
        USD_TWD = forex.取得匯率_純數字(fallback=固定)

    持股原 = [p for p in 設定.get("current_positions", [])
              if p.get("symbol") != "AGGREGATE"]

    # 真倉警示需要即時：永遠抓最新 yfinance
    分析索引 = {}

    持股列 = []
    成本總 = 0.0
    市值總 = 0.0
    賺 = 0
    賠 = 0

    # 分台股 / 美股小計
    台股成本_twd = 0.0
    台股市值_twd = 0.0
    台股檔數 = 0
    美股成本_usd = 0.0
    美股市值_usd = 0.0
    美股檔數 = 0

    達停利 = []
    破停損 = []
    接近停利 = []
    接近停損 = []

    for p in 持股原:
        原sym = p.get("symbol", "")
        sym = _規範化代號(原sym)
        股數 = p.get("shares", 0)
        成本 = p.get("avg_cost", 0)
        if not sym or 股數 <= 0 or 成本 <= 0:
            continue

        # Phase 15：FUGLE 即時優先 → fallback yfinance
        現價 = None
        報價來源 = None
        報價 = fugle_market.即時報價_fallback(sym)
        if 報價:
            現價 = 報價.get("close")
            報價來源 = 報價.get("source")

        if not 現價:
            # 抓不到，存記錄但 mark 失敗
            持股列.append({
                "symbol": sym,
                "name": p.get("name", ""),
                "shares": 股數,
                "avg_cost": 成本,
                "current_price": None,
                "error": "抓不到股價",
            })
            continue

        is_us = not (sym.endswith(".TW") or sym.endswith(".TWO"))
        倍率 = USD_TWD if is_us else 1.0
        成本_twd = 成本 * 股數 * 倍率
        市值_twd = 現價 * 股數 * 倍率
        損益_twd = 市值_twd - 成本_twd
        漲幅 = (現價 / 成本 - 1) * 100

        rec = {
            "symbol": sym,
            "name": p.get("name", "") or (分析.get("name", "") if 分析 else ""),
            "shares": 股數,
            "avg_cost": 成本,
            "current_price": round(現價, 2),
            "pnl_pct": round(漲幅, 2),
            "pnl_twd": round(損益_twd, 0),
            "market_value_twd": round(市值_twd, 0),
            "is_us": is_us,
        }

        # Phase 32.6：依台/美股套用不同停損 threshold
        本檔停損 = 美股停損_PCT if is_us else 停損_PCT
        本檔近停損 = 美股近停損_PCT if is_us else 接近停損_PCT
        停損鐵律字 = (f"守 {本檔停損}% 鐵律"
                       + ("（美股波動大，較嚴）" if is_us else ""))

        # 警示分類 + Phase 11 雙策略建議
        if 漲幅 >= 停利_PCT:
            rec["警示_類型"] = "TAKE_PROFIT"
            # 策略 A: 全賣 / 策略 D: 賣 50%
            rec["策略A建議"] = {"動作": "全賣", "股數": 股數,
                                  "落袋_twd": round(現價 * 股數 * 倍率, 0)}
            D股數 = int(股數 * 0.5)
            rec["策略D建議"] = {"動作": "賣 50% 分批",
                                  "股數": D股數,
                                  "落袋_twd": round(現價 * D股數 * 倍率, 0),
                                  "剩餘": 股數 - D股數,
                                  "下一階段": f"剩 {股數 - D股數} 股等 +30% 再賣 25%"}
            達停利.append(rec)
        elif 漲幅 <= 本檔停損:
            rec["警示_類型"] = "STOP_LOSS"
            rec["策略A建議"] = {"動作": "全停損", "股數": 股數,
                                  "落袋_twd": round(現價 * 股數 * 倍率, 0)}
            rec["策略D建議"] = {"動作": "全停損（守紀律）",
                                  "股數": 股數,
                                  "落袋_twd": round(現價 * 股數 * 倍率, 0),
                                  "下一階段": 停損鐵律字 + "，不分批"}
            破停損.append(rec)
        elif 漲幅 >= 接近停利_PCT:
            rec["警示_類型"] = "NEAR_TP"
            達停利_股數 = 股數
            D股數 = int(股數 * 0.5)
            rec["策略A建議"] = {"動作": "準備全賣（達 +15% 時）",
                                  "股數": 達停利_股數}
            rec["策略D建議"] = {"動作": "準備賣 50%（達 +15% 時）",
                                  "股數": D股數}
            接近停利.append(rec)
        elif 漲幅 <= 本檔近停損:
            rec["警示_類型"] = "NEAR_SL"
            接近停損.append(rec)

        持股列.append(rec)
        成本總 += 成本_twd
        市值總 += 市值_twd
        if 損益_twd >= 0:
            賺 += 1
        else:
            賠 += 1

        # 分類小計
        if is_us:
            美股成本_usd += 成本 * 股數
            美股市值_usd += 現價 * 股數
            美股檔數 += 1
        else:
            台股成本_twd += 成本 * 股數
            台股市值_twd += 現價 * 股數
            台股檔數 += 1

    # 排序（按漲幅由高到低）
    持股列.sort(key=lambda r: r.get("pnl_pct", -999) if r.get("pnl_pct") is not None else -999,
                 reverse=True)

    損益總 = 市值總 - 成本總
    損益率 = (損益總 / 成本總 * 100) if 成本總 > 0 else 0

    return {
        "持股": 持股列,
        "總計": {
            "成本_twd": round(成本總, 0),
            "市值_twd": round(市值總, 0),
            "損益_twd": round(損益總, 0),
            "損益率_pct": round(損益率, 2),
            "賺檔數": 賺,
            "賠檔數": 賠,
            "總檔數": 賺 + 賠,
        },
        "台股小計": {
            "檔數": 台股檔數,
            "成本_twd": round(台股成本_twd, 0),
            "市值_twd": round(台股市值_twd, 0),
            "損益_twd": round(台股市值_twd - 台股成本_twd, 0),
            "損益率_pct": round((台股市值_twd / 台股成本_twd - 1) * 100, 2)
                              if 台股成本_twd > 0 else 0,
        },
        "美股小計": {
            "檔數": 美股檔數,
            "成本_usd": round(美股成本_usd, 2),
            "市值_usd": round(美股市值_usd, 2),
            "損益_usd": round(美股市值_usd - 美股成本_usd, 2),
            "損益率_pct": round((美股市值_usd / 美股成本_usd - 1) * 100, 2)
                              if 美股成本_usd > 0 else 0,
            "成本_twd": round(美股成本_usd * USD_TWD, 0),
            "市值_twd": round(美股市值_usd * USD_TWD, 0),
            "USD_TWD": USD_TWD,
        },
        "警示": {
            "達停利": 達停利,
            "破停損": 破停損,
            "接近停利": 接近停利,
            "接近停損": 接近停損,
        },
        "有警示": bool(達停利 or 破停損 or 接近停利 or 接近停損),
    }
