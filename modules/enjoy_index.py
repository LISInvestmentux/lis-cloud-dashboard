"""
Enjoy Index 計算模組 — Phase 2
總分 0-100，由三個面向加總：

情緒面 35 分（多重指標加權）：
  - CNN Fear & Greed         10 分（美股情緒主指標）
  - VIX 恐慌指數              5 分（美股波動率）
  - 加權指數 RSI              10 分（台股情緒主指標）
  - 櫃買指數 RSI              5 分（台股小型股情緒）
  - 費城半導體指數 RSI        5 分（半導體景氣情緒）

技術面 35 分：
  - 每檔 Shit Signal +5（上限 25 分）
  - 任一檔 Bull Signal +10

基本面 30 分：
  - MVP 階段固定 15 分（中性，未來接 AI 基本面分析後動態化）

判讀：
  ≥70 → 🟢 BE HAPPY    40-70 → 🟡 WAIT    <40 → 🔴 HOLD

主動操作邏輯（Phase 6.0 修正）：
  Enjoy < 40 = 市場過熱（F&G 高、VIX 低、RSI 高 = 大家貪婪）
  → HOLD = 「主動減碼，獲利了結拉高現金」（非被動「暫緩進場」）
  → 在使用者持股中找「漲幅 +X% 以上」的部位建議減碼

  Enjoy 40-70 = 平淡    → WAIT = NEUTRAL（不主動操作）
  Enjoy ≥70  = 市場恐慌 → BE HAPPY = BUY_MORE（主動加碼）
"""
from typing import Optional


# ─────────────────────────────────────────────
# 情緒面（多重指標）
# ─────────────────────────────────────────────
def _反比分數(數值: Optional[float], 滿分: float,
              低點: float = 0, 高點: float = 100) -> float:
    """數值越低分數越高（給 F&G、RSI 這類「越恐慌越多分」的指標用）。"""
    if 數值 is None:
        return 滿分 / 2  # 沒抓到資料給中性
    if 數值 <= 低點:
        return 滿分
    if 數值 >= 高點:
        return 0
    return round(滿分 * (高點 - 數值) / (高點 - 低點), 1)


def _VIX分數(vix: Optional[float], 滿分: float = 5.0) -> float:
    """
    VIX 越高（恐慌）→ 分數越高。
    VIX < 15 = 0 分（過度自滿）
    VIX 15-20 = 1-2 分
    VIX 20-30 = 3-4 分
    VIX > 30 = 滿分（極度恐慌，難得進場機會）
    """
    if vix is None:
        return 滿分 / 2
    if vix <= 15:
        return 0.0
    if vix >= 35:
        return 滿分
    return round(滿分 * (vix - 15) / 20, 1)


def 計算情緒分數(fear_greed_score: Optional[float],
                  vix: Optional[float],
                  taiex_rsi: Optional[float],
                  otc_rsi: Optional[float],
                  sox_rsi: Optional[float]) -> dict:
    """回傳 {'total': 35-best, 'breakdown': [...]}"""
    fg分     = _反比分數(fear_greed_score, 10.0)
    vix分    = _VIX分數(vix, 5.0)
    taiex分  = _反比分數(taiex_rsi, 10.0, 低點=30, 高點=80)
    otc分    = _反比分數(otc_rsi, 5.0, 低點=30, 高點=80)
    sox分    = _反比分數(sox_rsi, 5.0, 低點=30, 高點=80)
    總 = round(fg分 + vix分 + taiex分 + otc分 + sox分, 1)
    return {
        "total": min(35.0, 總),
        "breakdown": [
            ("F&G", fg分, fear_greed_score),
            ("VIX", vix分, vix),
            ("加權", taiex分, taiex_rsi),
            ("櫃買", otc分, otc_rsi),
            ("費半", sox分, sox_rsi),
        ],
    }


# ─────────────────────────────────────────────
# 技術面（從掃描結果聚合）
# ─────────────────────────────────────────────
def 計算技術分數(全部個股分析: list[dict]) -> dict:
    """全部個股（美股+台股+ETF）合併計算。"""
    有效 = [r for r in 全部個股分析 if "error" not in r]
    低點觸發 = [r for r in 有效 if r.get("shit_signal")]
    轉折觸發 = [r for r in 有效 if r.get("bull_signal")]

    分 = 0.0
    說明 = []
    if 低點觸發:
        加 = min(25.0, len(低點觸發) * 5.0)
        分 += 加
        說明.append(f"{len(低點觸發)} 檔錯殺 +{加:.0f}")
    if 轉折觸發:
        分 += 10
        說明.append(f"{len(轉折觸發)} 檔金叉 +10")

    return {
        "total": min(35.0, round(分, 1)),
        "說明": 說明,
        "低點觸發": 低點觸發,
        "轉折觸發": 轉折觸發,
    }


# ─────────────────────────────────────────────
# 基本面（MVP 中性）
# ─────────────────────────────────────────────
def 計算基本分數(_fundamental_signal: Optional[dict] = None) -> dict:
    return {"total": 15.0, "說明": "MVP 中性 +15"}


# ─────────────────────────────────────────────
# 主整合
# ─────────────────────────────────────────────
def 計算Enjoy指數(fear_greed: dict,
                  指數結果: list[dict],
                  全部個股分析: list[dict]) -> dict:
    """
    fear_greed: fear_greed.取得恐慌貪婪指數() 的結果
    指數結果: technical.掃描全部觀察清單()['indices']
    全部個股分析: 所有 region 的 items 合併
    """
    # 從指數結果撈關鍵 RSI
    指數對應 = {r.get("original_symbol") or r["symbol"]: r for r in 指數結果}

    def _取RSI(symbol: str) -> Optional[float]:
        r = 指數對應.get(symbol)
        if r is None or "error" in r:
            return None
        return r.get("rsi14")

    def _取收盤(symbol: str) -> Optional[float]:
        r = 指數對應.get(symbol)
        if r is None or "error" in r:
            return None
        return r.get("close")

    情緒 = 計算情緒分數(
        fear_greed_score=fear_greed.get("score"),
        vix=_取收盤("^VIX"),
        taiex_rsi=_取RSI("^TWII"),
        otc_rsi=_取RSI("^TWOII"),
        sox_rsi=_取RSI("^SOX"),
    )
    技術 = 計算技術分數(全部個股分析)
    基本 = 計算基本分數()

    總分 = round(情緒["total"] + 技術["total"] + 基本["total"], 1)

    if 總分 >= 70:
        建議 = "🟢 BE HAPPY"
        文案 = "偵測到黃金機會，Enjoy it！"
        主動操作 = "BUY_MORE"
    elif 總分 >= 40:
        建議 = "🟡 WAIT"
        文案 = "持續觀察，等待更明確訊號"
        主動操作 = "NEUTRAL"
    else:
        # Phase 6.0 修正：HOLD = 市場過熱 = 主動減碼（非被動暫緩）
        建議 = "🔴 HOLD"
        文案 = "市場過熱 → 主動減碼，獲利了結拉高現金水位"
        主動操作 = "SELL_TAKE"

    return {
        "總分": 總分,
        "情緒": 情緒,
        "技術": 技術,
        "基本": 基本,
        "建議": 建議,
        "建議文案": 文案,
        "主動操作": 主動操作,   # Phase 6.0：BUY_MORE / NEUTRAL / SELL_TAKE
    }


# ─────────────────────────────────────────────
# 格式化
# ─────────────────────────────────────────────
def 格式化為訊息(指數: dict) -> str:
    情緒明細 = " ".join(
        f"{名}{分:.1f}" for 名, 分, _ in 指數["情緒"]["breakdown"]
    )
    技術明細 = ("｜" + "、".join(指數["技術"]["說明"])) if 指數["技術"]["說明"] else ""
    return (
        f"🎯 Enjoy Index：{指數['總分']} / 100\n"
        f"   情緒 {指數['情緒']['total']} + 技術 {指數['技術']['total']} + 基本 {指數['基本']['total']}\n"
        f"   情緒拆解：{情緒明細}{技術明細}\n"
        f"   {指數['建議']}：{指數['建議文案']}"
    )
