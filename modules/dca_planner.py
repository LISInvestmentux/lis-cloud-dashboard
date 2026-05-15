"""
零股長期持有清單（Phase 11）
推薦給「想定期定額、長期持有」的人。
重點：低摩擦（台版美股 ETF）、可零股、長期向上、明確加碼時機。

組合：
  - 00646 元大 S&P 500（VOO 台版）
  - 00662 富邦 NASDAQ（QQQ 台版）
  - 00858 永豐美國 500（VTI 台版）
  - 0050  元大台灣 50（核心地基）

加碼時機判定：依當前股價 + RSI + VIX。
"""
from typing import Optional


# 零股長期清單
零股推薦 = [
    {
        "symbol": "0050.TW", "name": "元大台灣 50",
        "市場": "🇹🇼 台股大盤", "等價": "—",
        "理由": "台股核心配置，長期 ~10% 年化",
    },
    {
        "symbol": "00646.TW", "name": "元大 S&P 500",
        "市場": "🇺🇸 美股大盤", "等價": "VOO 台版",
        "理由": "S&P 500 大盤，長期 ~10% 年化",
    },
    {
        "symbol": "00662.TW", "name": "富邦 NASDAQ",
        "市場": "🇺🇸 美股科技", "等價": "QQQ 台版",
        "理由": "NASDAQ 100 科技，長期 ~13% 年化（高波動）",
    },
    {
        "symbol": "00858.TW", "name": "永豐美國 500",
        "市場": "🇺🇸 美股全市場", "等價": "VTI 台版",
        "理由": "美股全市場（含中小型），長期 ~10% 年化",
    },
]


def 建立零股清單(月可投_twd: int = 5000) -> dict:
    """
    用 yfinance 抓即時股價，組成「今天該怎麼買」清單。

    月可投_twd: 每月可投入金額（預設 5000）

    回傳：
    {
      "清單": [{symbol, name, 現價, 加碼訊號, 建議買X股, 金額}, ...],
      "月總投入_twd": int,
      "說明": str,
    }
    """
    try:
        from . import technical
    except ImportError:
        import technical

    清單 = []
    每檔金額 = 月可投_twd // len(零股推薦)

    for item in 零股推薦:
        try:
            每日, _ = technical.取得每日股價(item["symbol"], period="3mo")
        except Exception:
            清單.append({
                **item,
                "現價": None,
                "加碼訊號": "n/a",
                "建議買股數": 0,
                "金額_twd": 0,
            })
            continue

        if not 每日:
            continue

        現價 = 每日[0]["close"]
        建議買股數 = max(1, int(每檔金額 / 現價))
        實際金額 = 建議買股數 * 現價

        # 計算 RSI（給加碼判斷）
        收盤 = [d["close"] for d in 每日]
        rsi = technical.計算RSI(收盤, 14)
        ma50 = technical.計算SMA(收盤, 50)

        # 加碼訊號判定
        if rsi is not None and rsi < 35 and ma50 and 現價 < ma50:
            訊號 = "🟢 超賣加碼"
            訊號描述 = "RSI < 35 + 跌破 MA50，加倍買進"
            倍率 = 2.0
        elif rsi is not None and rsi < 50:
            訊號 = "🟢 平淡可進"
            訊號描述 = "RSI 偏低，正常定期定額"
            倍率 = 1.0
        elif rsi is not None and rsi > 75:
            訊號 = "⚠️ 過熱不買"
            訊號描述 = "RSI > 75 過熱，本月跳過"
            倍率 = 0.0
        else:
            訊號 = "🟡 中性買"
            訊號描述 = "RSI 中性，依紀律買"
            倍率 = 1.0

        實際買股數 = int(建議買股數 * 倍率)
        實際金額 = 實際買股數 * 現價

        清單.append({
            **item,
            "現價": round(現價, 2),
            "rsi": rsi,
            "加碼訊號": 訊號,
            "訊號描述": 訊號描述,
            "建議買股數": 實際買股數,
            "金額_twd": round(實際金額, 0),
        })

    月總投入 = sum(r.get("金額_twd", 0) for r in 清單)

    return {
        "清單": 清單,
        "月總投入_twd": round(月總投入, 0),
        "說明": "每月初執行，跌時加碼、漲時跳過、平時定額",
    }
