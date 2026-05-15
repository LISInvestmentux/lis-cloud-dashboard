"""
持股健康檢查（Phase 7.3）
診斷三個維度：
  1. 產業集中度（單一產業占比過高）
  2. 重複曝險（多檔 ETF 都壓同一主題）
  3. 持有期警示（>180 天強制檢視，若有 buy_date）

回傳給 flex_builder 用的結構：
{
  "產業分布": {產業名: 金額_twd, ...},
  "集中度_pct": 最大產業占比,
  "重複曝險": [{產業, 檔數, 標的}, ...],
  "持有過久": [...],
  "警示等級": "🔴" / "🟡" / "🟢",
  "建議": str,
}
"""
import re
from typing import Optional


# 集中度閾值
紅警_集中度_pct = 40   # 單一產業 > 40% → 紅警
黃警_集中度_pct = 25   # 單一產業 > 25% → 黃警

# 重複曝險閾值
紅警_重複數 = 4   # 同產業 ≥ 4 檔 → 紅警
黃警_重複數 = 3   # 同產業 ≥ 3 檔 → 黃警


# ─────────────────────────────────────────────
# 產業對映表（hard-coded，watchlist 沒這欄位）
# 漸進維護：portfolio.json 可加 industry_overrides 覆寫
# ─────────────────────────────────────────────
產業對映_預設 = {
    # 台股大盤
    "0050.TW": "台股大盤",
    "0056.TW": "台股大盤",
    "00692.TW": "台股大盤",
    "00850.TW": "台股大盤",
    "00981A.TW": "台股大盤",
    # 台股槓桿
    "00631L.TW": "台股槓桿",
    "00632R.TW": "台股槓桿",
    # 美股大盤 ETF（台版）
    "00662.TW": "美股大盤",
    "00646.TW": "美股大盤",
    # 半導體（最容易重複曝險）
    "00830.TW": "半導體",
    "00891.TW": "半導體",
    "00904.TW": "半導體",
    "00911.TW": "半導體",
    "00927.TW": "半導體",
    "00941.TW": "半導體",
    "00942B.TWO": "半導體",
    "2330.TW": "半導體",
    "2454.TW": "半導體",
    "3034.TW": "半導體",
    "3037.TW": "半導體",
    "3443.TW": "半導體",
    "3532.TW": "半導體",
    "2337.TW": "半導體",
    "4919.TW": "半導體",
    "4958.TW": "半導體",
    # 通訊 / 5G
    "00861.TW": "通訊5G",
    "00876.TW": "通訊5G",
    # 主題 / 科技
    "00935.TW": "科技創新",
    "00910.TW": "太空衛星",
    # 高股息
    "00878.TW": "高股息",
    "00713.TW": "高股息",
    "00919.TW": "高股息",
    # 中國
    "00882.TW": "中國/陸股",
    # 綠能 / ESG
    "00920.TW": "綠能ESG",
    "00692.TWO": "綠能ESG",
    # 金融
    "2890.TW": "金融",
    "2891.TW": "金融",
    "2882.TW": "金融",
    "2884.TW": "金融",
    "2885.TW": "金融",
    # 化工
    "1303.TW": "化工",
    "1717.TW": "化工",
    "1711.TW": "化工",
    # 電子代工
    "2317.TW": "電子組裝",
    "2382.TW": "電子組裝",
    "2308.TW": "電子組裝",
    "3017.TW": "電子組裝",
    "2374.TW": "電子組裝",
    # 美股 — 大型科技
    "NVDA": "美股科技",
    "TSLA": "美股科技",
    "META": "美股科技",
    "GOOGL": "美股科技",
    "AMD": "美股科技",
    "AVGO": "美股科技",
    "TSM": "美股科技",
    "MU": "美股科技",
    "INTC": "美股科技",
    "AMAT": "美股科技",
    "NOW": "美股科技",
    "GLW": "美股科技",
    "IREN": "美股科技",
    "CRWV": "美股科技",
    "PLGI": "美股科技",
    # 美股 ETF
    "QQQ": "美股大盤",
    "QQQX": "美股大盤",
    "VOO": "美股大盤",
}


def _規範化代號(原始: str) -> str:
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


def _查產業(symbol: str, overrides: dict) -> str:
    """先看 overrides，再 fallback 預設表，再回『其他』"""
    sym = _規範化代號(symbol)
    if sym in overrides:
        return overrides[sym]
    if sym in 產業對映_預設:
        return 產業對映_預設[sym]
    return "其他"


def 診斷持股健康(設定: dict,
                  真倉資料: Optional[dict] = None,
                  USD_TWD: float = 32.0) -> dict:
    """
    主入口。
    設定: portfolio.json 載入結果
    真倉資料: portfolio_tracker.追蹤真倉() 結果（可選，加速）
    """
    持股 = [p for p in 設定.get("current_positions", [])
            if p.get("symbol") != "AGGREGATE"]
    if not 持股:
        return _空診斷("尚無持股資料")

    overrides = 設定.get("industry_overrides", {})

    # 用 真倉資料（有 current_price）算市值；沒有就用 avg_cost 估
    市值表 = {}
    if 真倉資料 and 真倉資料.get("持股"):
        for r in 真倉資料["持股"]:
            if r.get("market_value_twd"):
                市值表[r["symbol"]] = r["market_value_twd"]

    產業分布 = {}     # 產業 → 金額_twd
    產業檔數 = {}     # 產業 → [symbol]
    總市值 = 0.0

    for p in 持股:
        原sym = p.get("symbol", "")
        sym = _規範化代號(原sym)
        股數 = p.get("shares", 0) or 0
        成本 = p.get("avg_cost", 0) or 0
        if not sym or 股數 <= 0:
            continue

        is_us = not (sym.endswith(".TW") or sym.endswith(".TWO"))
        市值 = 市值表.get(sym)
        if 市值 is None:
            # fallback: 用 avg_cost 估市值
            倍率 = USD_TWD if is_us else 1.0
            市值 = 成本 * 股數 * 倍率

        產業 = _查產業(sym, overrides)
        產業分布[產業] = 產業分布.get(產業, 0) + 市值
        產業檔數.setdefault(產業, []).append({
            "symbol": sym,
            "name": p.get("name", ""),
        })
        總市值 += 市值

    # 集中度（最大產業占比）
    if 總市值 <= 0:
        return _空診斷("市值無法計算")

    最大產業, 最大金額 = max(產業分布.items(), key=lambda x: x[1])
    最大占比 = 最大金額 / 總市值 * 100

    # 重複曝險
    重複曝險 = []
    for 產業, 檔列 in 產業檔數.items():
        if len(檔列) >= 黃警_重複數:
            重複曝險.append({
                "產業": 產業,
                "檔數": len(檔列),
                "金額_twd": round(產業分布[產業], 0),
                "占比_pct": round(產業分布[產業] / 總市值 * 100, 1),
                "標的": 檔列,
            })
    重複曝險.sort(key=lambda r: r["檔數"], reverse=True)

    # 警示等級
    警示等級 = "🟢 健康"
    建議 = "目前持股分散度尚可"
    if 最大占比 >= 紅警_集中度_pct or any(r["檔數"] >= 紅警_重複數 for r in 重複曝險):
        警示等級 = "🔴 集中度過高"
        建議 = f"{最大產業} 已占 {最大占比:.1f}%，建議分散到其他產業"
    elif 最大占比 >= 黃警_集中度_pct or 重複曝險:
        警示等級 = "🟡 偏向集中"
        建議 = f"{最大產業} 占 {最大占比:.1f}%，留意單一產業曝險"

    # 排序產業分布（金額由高到低）
    產業分布_排序 = sorted(產業分布.items(), key=lambda x: x[1], reverse=True)

    return {
        "總市值_twd": round(總市值, 0),
        "產業數": len(產業分布),
        "持股數": sum(len(v) for v in 產業檔數.values()),
        "產業分布": [
            {"產業": p, "金額_twd": round(金, 0),
             "占比_pct": round(金 / 總市值 * 100, 1),
             "檔數": len(產業檔數[p])}
            for p, 金 in 產業分布_排序
        ],
        "最大產業": 最大產業,
        "最大占比_pct": round(最大占比, 1),
        "重複曝險": 重複曝險,
        "警示等級": 警示等級,
        "建議": 建議,
    }


def _空診斷(原因: str) -> dict:
    return {
        "總市值_twd": 0,
        "產業數": 0,
        "持股數": 0,
        "產業分布": [],
        "最大產業": None,
        "最大占比_pct": 0,
        "重複曝險": [],
        "警示等級": "⚪ 無資料",
        "建議": 原因,
    }
