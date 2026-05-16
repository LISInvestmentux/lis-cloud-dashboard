"""
Kelly 公式部位大小計算（Phase 42 — 5/16）

Kelly Criterion: 告訴你「該下注多少 %」才最大化長期報酬

公式: f* = (p × b - q) / b
  其中:
    f* = 該投入資金的比例
    p  = 勝率
    q  = 1 - p (敗率)
    b  = 賠率 (平均獲利 / 平均虧損)

LIS 簡化版（給散戶用）:
  - 取「四分之一 Kelly」（保守版）— 防止 Kelly 算出來的部位太極端
  - 結合 conviction 信念分數調整
  - 結合 stop_loss 紀律當下檔風險

範例 (NVDA conviction=5):
  假設勝率 60%, 平均賺 15%, 平均虧 5%
  f* = (0.6 × 3 - 0.4) / 3 = 1.4/3 = 0.467 (47%)
  四分之一 Kelly = 47% × 0.25 = 11.7%

  若總資金 NT$ 473K，可投入 NT$ 55K
  NVDA 現價 $230 × 32 = NT$ 7,360 / 股
  → 建議買 7 股
"""
from typing import Optional


def 算Kelly比例(勝率: float, 平均獲利_pct: float,
                平均虧損_pct: float, 保守係數: float = 0.25) -> float:
    """
    回傳建議投入比例 (0-1)

    Args:
        勝率: 0-1 (例如 0.6 = 60% 勝率)
        平均獲利_pct: 正數 (例如 15 = 賺 15%)
        平均虧損_pct: 正數 (例如 5 = 虧 5%)
        保守係數: 預設 0.25 (四分之一 Kelly)
                  Full Kelly 太激進，散戶建議 1/4 或 1/2

    Returns:
        建議投入比例 (0-1)
        若 EV 為負 → 回傳 0（不該投）
    """
    if 平均虧損_pct <= 0 or 勝率 <= 0 or 勝率 >= 1:
        return 0

    p = 勝率
    q = 1 - p
    b = 平均獲利_pct / 平均虧損_pct  # 賠率

    # Full Kelly
    f_star = (p * b - q) / b

    # 負 EV → 不投
    if f_star <= 0:
        return 0

    # 上限 50%（即使 Full Kelly 算出 80% 也限制）
    f_star = min(f_star, 0.5)

    # 四分之一 Kelly (保守)
    return f_star * 保守係數


def conviction轉勝率(conviction: int) -> dict:
    """
    把 conviction 信念分數 → 預設勝率/賠率假設

    這是「先驗估計」(prior)，user 之後可以從 realized_history 算實際勝率覆蓋

    conviction 對應假設：
      5: 高信念 — AI 核心 / 大盤 ETF
         勝率 60% / 平均賺 15% / 平均虧 9% (因為停損閾值放寬)
      4: 中信念
         勝率 55% / 平均賺 12% / 平均虧 5%
      3: 標準
         勝率 50% / 平均賺 10% / 平均虧 4%
      2: 短線 swing
         勝率 45% / 平均賺 15% / 平均虧 2.4% (停損嚴)
      1: 灰名單
         勝率 30% / 平均賺 8% / 平均虧 1.5%
    """
    table = {
        5: {"勝率": 0.60, "平均獲利": 15, "平均虧損": 9},
        4: {"勝率": 0.55, "平均獲利": 12, "平均虧損": 5},
        3: {"勝率": 0.50, "平均獲利": 10, "平均虧損": 4},
        2: {"勝率": 0.45, "平均獲利": 15, "平均虧損": 2.4},
        1: {"勝率": 0.30, "平均獲利": 8, "平均虧損": 1.5},
    }
    return table.get(conviction, table[3])


def 建議部位金額(總可動用_twd: float, conviction: int,
                  最大單一倉位_pct: float = 20.0) -> dict:
    """
    給定 conviction，回傳建議投入金額 (TWD)

    Args:
        總可動用_twd: 可用彈藥 (NT$)
        conviction: 1-5 信念分數
        最大單一倉位_pct: 單一標的最大上限 (預設 20%)

    Returns:
        {
            "kelly_pct": 0.117,  # Kelly 算出的比例
            "建議金額_twd": 55000,
            "限制原因": "受 20% 單一上限" 或 "Kelly 結果",
            "詳細": {勝率/賠率假設},
        }
    """
    假設 = conviction轉勝率(conviction)
    kelly_pct = 算Kelly比例(
        勝率=假設["勝率"],
        平均獲利_pct=假設["平均獲利"],
        平均虧損_pct=假設["平均虧損"],
        保守係數=0.25,
    )

    # 受 20% 單一上限拘束
    max_pct = 最大單一倉位_pct / 100
    effective_pct = min(kelly_pct, max_pct)
    限制 = "受 20% 單一上限" if kelly_pct > max_pct else "Kelly 算出"

    建議金額 = 總可動用_twd * effective_pct

    return {
        "kelly_pct": round(kelly_pct * 100, 1),
        "effective_pct": round(effective_pct * 100, 1),
        "建議金額_twd": round(建議金額, 0),
        "限制原因": 限制,
        "詳細": 假設,
    }


def 建議股數(總可動用_twd: float, conviction: int,
              現價: float, is_us: bool, USD_TWD: float,
              最小股數: int = 1) -> dict:
    """
    給定 conviction + 現價，回傳建議買幾股

    Args:
        總可動用_twd: 可用彈藥 NT$
        conviction: 1-5
        現價: 股票現價 (美股=USD, 台股=TWD)
        is_us: 是否美股
        USD_TWD: 匯率
        最小股數: 至少幾股（預設 1）

    Returns:
        {
            "建議股數": 7,
            "建議金額_twd": 55000,
            "建議金額_usd": 1719,  (美股才有)
            "說明": "Kelly 算出 11.7%，conviction=5",
        }
    """
    result = 建議部位金額(總可動用_twd, conviction)
    twd = result["建議金額_twd"]

    # 算單股 TWD 價
    if is_us:
        單股twd = 現價 * USD_TWD
    else:
        單股twd = 現價

    # 算股數
    股數 = max(最小股數, int(twd // 單股twd))

    # 實際投入金額
    實際twd = 股數 * 單股twd
    實際usd = 股數 * 現價 if is_us else None

    return {
        "建議股數": 股數,
        "建議金額_twd": round(實際twd, 0),
        "建議金額_usd": round(實際usd, 2) if 實際usd else None,
        "kelly_pct": result["kelly_pct"],
        "說明": (
            f"Kelly {result['kelly_pct']}% × 保守 1/4 = "
            f"{result['effective_pct']}% (信念 {conviction}/5)"
        ),
        "詳細": result["詳細"],
    }


# ════════════════════════════════════════════
# CLI 測試
# ════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("Kelly 公式測試（依 conviction 分級）")
    print("=" * 60)
    print(f"{'信念':<4} {'勝率':<6} {'賺':<5} {'虧':<5} {'Kelly%':<8} {'1/4 Kelly%':<10}")
    print("-" * 60)
    for conv in [5, 4, 3, 2, 1]:
        假設 = conviction轉勝率(conv)
        full = 算Kelly比例(
            假設["勝率"], 假設["平均獲利"], 假設["平均虧損"],
            保守係數=1.0)
        quarter = full * 0.25
        print(f"{conv:<4} {假設['勝率']*100:.0f}%   "
              f"+{假設['平均獲利']}%  -{假設['平均虧損']}%  "
              f"{full*100:>6.1f}%  {quarter*100:>6.1f}%")

    print()
    print("=" * 60)
    print("實際場景：總可動用 NT$ 51,653 / NVDA $230.26 / 信念 5")
    print("=" * 60)
    r = 建議股數(
        總可動用_twd=51653,
        conviction=5,
        現價=230.26,
        is_us=True,
        USD_TWD=32.0,
    )
    print(f"建議股數: {r['建議股數']} 股")
    print(f"建議金額: NT$ {r['建議金額_twd']:,.0f} (${r['建議金額_usd']:,.0f})")
    print(f"說明: {r['說明']}")
