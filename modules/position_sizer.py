"""
智能部位演算（Phase 17）— Kelly 簡化版 + 多因子加權

對標 ARK 大俠的「動態建議部位」算法：
  1. 訊號強度（位階分 / 順勢分）
  2. 大盤系統性（VIX / Fear-Greed / 黑天鵝）
  3. 個股歷史勝率（Phase 18 接入）
  4. 集中度限制（單檔不超過 20%）
  5. 已持有部位調節

回傳：
  {
    建議金額_twd, 建議_pct, 倍率, 等級,
    理由: [...],
    Kelly_理論_pct, Kelly_實務_pct,
    解釋: "...",
  }

設計準則：
  ✅ 每個倍率都可解釋（不黑盒）
  ✅ 上限保護（單檔單日 ≤5%，總資金）
  ✅ 黑天鵝才會觸發「重押」等級
  ✅ 跟 ARK 大俠中信金一戰成名同邏輯：高勝率 × 深價值 × 大盤恐慌
"""
from typing import Optional


# ─────────────────────────────────────────────
# 設定常數（可在 portfolio.json 覆寫）
# ─────────────────────────────────────────────
基礎_pct_預設 = 0.5         # 平時起跳每檔 0.5% 總資金
單檔單日上限_pct = 5.0      # 任何狀況下單檔單日不超過 5%
單檔總部位上限_pct = 20.0   # 單檔總部位（含已持有）不超過 20%
黑天鵝重押_倍率 = 3.0       # 黑天鵝命中 4+ 觸發 ×3
全市場恐慌_倍率 = 1.5       # VIX > 25 或 Fear-Greed < 25


# 等級分類（給 LINE 卡顏色 & emoji 用）
def _等級(倍率: float) -> dict:
    if 倍率 >= 6.0:
        return {"等級": "ALL_IN", "emoji": "🚨",
                "標籤": "ALL IN（黑天鵝）",
                "解釋": "歷史級買點，跟大俠當年中信金同等"}
    if 倍率 >= 3.0:
        return {"等級": "重押", "emoji": "🔥",
                "標籤": "重押訊號",
                "解釋": "多訊號加乘，敢買就賺"}
    if 倍率 >= 2.0:
        return {"等級": "加碼", "emoji": "⚡",
                "標籤": "加碼訊號",
                "解釋": "訊號強烈，比平時多放"}
    if 倍率 >= 1.3:
        return {"等級": "順勢", "emoji": "📈",
                "標籤": "順勢買進",
                "解釋": "趨勢確認，分批跟進"}
    if 倍率 >= 0.8:
        return {"等級": "紀律", "emoji": "📌",
                "標籤": "紀律分批",
                "解釋": "平時水位，小量分批"}
    return {"等級": "PASS", "emoji": "🟡",
            "標籤": "降權觀望",
            "解釋": "訊號偏弱，少量或暫停"}


# ─────────────────────────────────────────────
# Kelly Criterion 簡化版
# ─────────────────────────────────────────────
def kelly_部位_pct(勝率: float, 平均賺_pct: float,
                    平均賠_pct: float,
                    分數因子: float = 0.125) -> float:
    """
    Kelly 公式：f* = (b·p - q) / b
    其中：
      p = 勝率 (0-1)
      q = 1 - p
      b = 平均賺/平均賠

    分數因子 0.125 = 1/8 Kelly（Phase 26 修正 — 散戶安全版）
    Kelly 假設事件獨立，但股票漲跌會連動 → 實務再除以 2

    回傳：建議部位佔總資金的 %（0-100）
    """
    if 勝率 <= 0 or 平均賺_pct <= 0 or 平均賠_pct <= 0:
        return 0
    p = max(0, min(1, 勝率))
    q = 1 - p
    b = 平均賺_pct / 平均賠_pct
    f_full = (b * p - q) / b
    if f_full <= 0:
        return 0
    f_practical = f_full * 分數因子
    return round(min(f_practical * 100, 12), 2)  # 上限 12%（原 25%）


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────
def 建議部位金額(symbol: str,
                  訊號: dict,
                  大盤: dict,
                  黑天鵝: Optional[dict],
                  持股: dict,
                  總資金_twd: float,
                  個股勝率: Optional[dict] = None) -> dict:
    """
    回傳該檔今天「應該投多少錢」（含解釋）

    訊號: {位階分數, 順勢分, 型態, 是ETF}
    大盤: {VIX, fear_greed_score, ...}
    黑天鵝: {命中數, ...} or None
    持股: {symbol: {市值_twd, ...}} or {}
    個股勝率: {symbol: {勝率, 平均賺_pct, 平均賠_pct}} or None (Phase 18 接入)
    """
    基礎_pct = 基礎_pct_預設
    倍率 = 1.0
    理由 = []

    # ─── 1. 訊號強度（位階分）───
    位階 = 訊號.get("位階分數") or 訊號.get("分數") or 50
    if 位階 < 25:
        倍率 *= 2.0
        理由.append("🟢 深價值區 ×2.0")
    elif 位階 < 35:
        倍率 *= 1.7
        理由.append("✅ 強進入價值區 ×1.7")
    elif 位階 < 45:
        倍率 *= 1.4
        理由.append("✅ 進入價值區 ×1.4")
    elif 位階 < 65:
        pass  # 中性不調
    else:
        # 已脫離 — 只有「ETF 順勢」可加碼
        型態 = 訊號.get("型態", "")
        順勢分 = 訊號.get("順勢分") or 0
        if 型態 == "順勢" and 順勢分 >= 80:
            倍率 *= 1.3
            理由.append(f"🚀 ETF 順勢強 ×1.3 (順 {順勢分:.0f})")
        elif 型態 == "順勢" and 順勢分 >= 60:
            倍率 *= 1.1
            理由.append(f"🚀 ETF 順勢可加 ×1.1 (順 {順勢分:.0f})")
        else:
            倍率 *= 0.3
            理由.append(f"⚠️ 脫離價值區 ×0.3")

    # ─── 2. 大盤系統性 ───
    vix = 大盤.get("VIX") or 大盤.get("vix")
    if vix is not None:
        if vix > 30:
            倍率 *= 1.7
            理由.append(f"😱 VIX {vix:.1f} 極端恐慌 ×1.7")
        elif vix > 25:
            倍率 *= 1.4
            理由.append(f"😟 VIX {vix:.1f} 偏高 ×1.4")
        elif vix < 12:
            倍率 *= 0.8
            理由.append(f"😎 VIX {vix:.1f} 過低 ×0.8")

    fg = 大盤.get("fear_greed_score") or 大盤.get("FG")
    if fg is not None:
        if fg < 20:
            倍率 *= 1.5
            理由.append(f"💀 Fear-Greed {fg:.0f} 極端恐慌 ×1.5")
        elif fg < 35:
            倍率 *= 1.2
            理由.append(f"😨 Fear-Greed {fg:.0f} 恐慌 ×1.2")
        elif fg > 80:
            倍率 *= 0.7
            理由.append(f"🤑 Fear-Greed {fg:.0f} 極端貪婪 ×0.7")

    # ─── 3. 黑天鵝 ───
    if 黑天鵝:
        命中 = 黑天鵝.get("命中數", 0)
        if 命中 >= 4:
            倍率 *= 黑天鵝重押_倍率
            理由.append(f"🚨 黑天鵝×{命中} ×{黑天鵝重押_倍率}")
        elif 命中 >= 3:
            倍率 *= 2.0
            理由.append(f"⚠️ 黑天鵝×{命中} ×2.0")
        elif 命中 >= 2:
            倍率 *= 1.3
            理由.append(f"📉 黑天鵝×{命中} ×1.3")

    # ─── 4. 個股歷史勝率（Phase 18 接入）───
    if 個股勝率 and symbol in 個股勝率:
        勝 = 個股勝率[symbol]
        勝率 = 勝.get("勝率", 0.5)
        平均賺 = 勝.get("平均賺_pct", 0)
        平均賠 = 勝.get("平均賠_pct", 0)
        交易數 = 勝.get("交易數", 0)
        # 用 DB 內已算好的 Kelly%（已是 1/4 Kelly + 25% 上限）
        kelly_pct = 勝.get("Kelly_pct") or kelly_部位_pct(勝率, 平均賺, 平均賠)
        if kelly_pct > 0:
            # Kelly 部位轉成倍率（基礎 0.5% → Kelly%）
            kelly_倍 = kelly_pct / 基礎_pct
            倍率 *= max(0.5, min(4.0, kelly_倍))  # clip 0.5-4
            理由.append(
                f"📊 歷史勝率 {勝率*100:.0f}% / Kelly {kelly_pct:.1f}% "
                f"(n={交易數})"
            )
        Kelly資訊 = {
            "勝率": 勝率, "平均賺_pct": 平均賺, "平均賠_pct": 平均賠,
            "Kelly_pct": kelly_pct, "交易數": 交易數,
        }
    else:
        Kelly資訊 = None

    # ─── 5. 集中度限制 ───
    已持市值 = 持股.get(symbol, {}).get("市值_twd", 0) or 0
    已持_pct = 已持市值 / 總資金_twd * 100 if 總資金_twd > 0 else 0
    if 已持_pct >= 15:
        倍率 *= 0.3
        理由.append(f"⚠️ 已集中 {已持_pct:.1f}% ×0.3")
    elif 已持_pct >= 10:
        倍率 *= 0.6
        理由.append(f"📊 已配置 {已持_pct:.1f}% ×0.6")

    # ─── 6. 計算最終金額 ───
    建議_pct = 基礎_pct * 倍率
    建議_pct = min(建議_pct, 單檔單日上限_pct)
    # 集中度上限：總部位（已持 + 今天加）不超過 20%
    可加_pct = max(0, 單檔總部位上限_pct - 已持_pct)
    建議_pct = min(建議_pct, 可加_pct)
    建議_pct = max(0, 建議_pct)

    建議金額 = int(總資金_twd * 建議_pct / 100)

    等級資訊 = _等級(倍率)

    # 解釋一句話
    解釋 = (f"{等級資訊['標籤']} — "
            f"基礎 {基礎_pct}% × 倍率 {倍率:.1f}x = {建議_pct:.2f}%")

    return {
        "symbol": symbol,
        "建議金額_twd": 建議金額,
        "建議_pct": round(建議_pct, 2),
        "倍率": round(倍率, 2),
        "等級": 等級資訊["等級"],
        "等級_emoji": 等級資訊["emoji"],
        "等級_標籤": 等級資訊["標籤"],
        "等級_解釋": 等級資訊["解釋"],
        "理由": 理由,
        "Kelly資訊": Kelly資訊,
        "已持_pct": round(已持_pct, 2),
        "解釋": 解釋,
    }


# ─────────────────────────────────────────────
# 批次：對訊號清單算建議
# ─────────────────────────────────────────────
def 批次建議(訊號清單: list,
              大盤: dict,
              黑天鵝: Optional[dict],
              持股: dict,
              總資金_twd: float,
              個股勝率: Optional[dict] = None) -> list:
    """
    對訊號清單批量算建議。
    訊號清單格式：[{symbol, 位階分數, 順勢分, 型態, 是ETF, ...}, ...]
    """
    結果 = []
    for s in 訊號清單:
        建議 = 建議部位金額(
            symbol=s["symbol"],
            訊號=s,
            大盤=大盤,
            黑天鵝=黑天鵝,
            持股=持股,
            總資金_twd=總資金_twd,
            個股勝率=個股勝率,
        )
        # 把訊號原資訊也帶出來
        建議.update({
            "name": s.get("name", ""),
            "現價": s.get("close") or s.get("現價"),
            "位階分數": s.get("位階分數") or s.get("分數"),
            "型態": s.get("型態"),
            "順勢分": s.get("順勢分"),
        })
        結果.append(建議)

    # 排序：等級高的在前
    等級排序 = {"ALL_IN": 0, "重押": 1, "加碼": 2, "順勢": 3,
                  "紀律": 4, "PASS": 5}
    結果.sort(key=lambda r: 等級排序.get(r["等級"], 9))
    return 結果


# ─────────────────────────────────────────────
# CLI 自測
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=== 測試 1：平常 0050 ===")
    r = 建議部位金額(
        symbol="0050.TW",
        訊號={"位階分數": 70, "順勢分": 85, "型態": "順勢", "是ETF": True},
        大盤={"VIX": 15, "fear_greed_score": 55},
        黑天鵝=None,
        持股={"0050.TW": {"市值_twd": 14000}},
        總資金_twd=400000,
    )
    print(f"  建議：NT$ {r['建議金額_twd']:,} ({r['建議_pct']:.2f}%)")
    print(f"  等級：{r['等級_emoji']} {r['等級_標籤']}")
    print(f"  理由：{' / '.join(r['理由'])}")

    print()
    print("=== 測試 2：黑天鵝 ALL IN 0050 ===")
    r = 建議部位金額(
        symbol="0050.TW",
        訊號={"位階分數": 20, "型態": "抄底", "是ETF": True},
        大盤={"VIX": 32, "fear_greed_score": 18},
        黑天鵝={"命中數": 4},
        持股={"0050.TW": {"市值_twd": 14000}},
        總資金_twd=400000,
    )
    print(f"  建議：NT$ {r['建議金額_twd']:,} ({r['建議_pct']:.2f}%)")
    print(f"  等級：{r['等級_emoji']} {r['等級_標籤']}")
    print(f"  理由：{' / '.join(r['理由'])}")

    print()
    print("=== 測試 3：Kelly with 中信金 92% 勝率 ===")
    pct = kelly_部位_pct(勝率=0.92, 平均賺_pct=25, 平均賠_pct=8)
    print(f"  中信金 Kelly 1/4：{pct}%")
    print(f"  → 對 800 萬 = NT$ {800_0000 * pct / 100:,.0f}")
