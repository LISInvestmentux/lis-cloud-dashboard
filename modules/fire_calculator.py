"""
財務自由 / 離職倒數計算（Phase 6.1）
基於 4% 規則：FIRE 目標金額 = 年支出 × 25 倍

核心算式：
  N 年後資產 = 目前資產 × (1+r)^N
             + 月投入 × 12 × [(1+r)^N - 1] / r
  N = 達到 FIRE 目標的年數（用二分搜尋或對數解）

支援三種情境：
  保守：r=3%（無風險利率 + 通膨）
  中等：r=6%（藍籌股長期報酬，扣稅後）
  積極：r=10%（個人選股、有 LIS 紀律加持）
"""
from datetime import datetime, timedelta
from typing import Optional


# ─────────────────────────────────────────────
# 預設情境
# ─────────────────────────────────────────────
情境_預設 = {
    "保守": {"年化報酬率_pct": 3.0, "說明": "定存 + 高股息（無腦不選股）"},
    "中等": {"年化報酬率_pct": 6.0, "說明": "0050 等大盤 ETF 長期平均"},
    "積極": {"年化報酬率_pct": 10.0, "說明": "LIS 紀律 + 個股選股（含風險）"},
}


# ─────────────────────────────────────────────
# 核心算式
# ─────────────────────────────────────────────
def FIRE目標金額(月支出_twd: float, 倍數: float = 25.0) -> float:
    """4% 規則：FIRE 目標 = 年支出 × 25 倍。"""
    return 月支出_twd * 12 * 倍數


def N年後資產(目前資產: float, 月投入: float, 年化報酬率: float,
                 N: float) -> float:
    """
    複利 + 年金未來值。
    年化報酬率: 例 0.06 表示 6%
    """
    if 年化報酬率 <= 0:
        # 無利息：簡單加總
        return 目前資產 + 月投入 * 12 * N

    複利成長 = 目前資產 * (1 + 年化報酬率) ** N
    # 年金未來值（每年初投入 12 個月，簡化用年度版）
    年投入 = 月投入 * 12
    if 年化報酬率 == 0:
        年金 = 年投入 * N
    else:
        年金 = 年投入 * ((1 + 年化報酬率) ** N - 1) / 年化報酬率
    return 複利成長 + 年金


def 達標年數(目前資產: float, 月投入: float, 年化報酬率: float,
              FIRE目標: float, 最大年數: float = 60.0) -> Optional[float]:
    """
    二分搜尋：多少年達到 FIRE 目標。
    回傳年數（小數），若 60 年內達不到回 None。
    """
    # 邊界：現在就達標
    if 目前資產 >= FIRE目標:
        return 0.0

    # 邊界：60 年也達不到
    if N年後資產(目前資產, 月投入, 年化報酬率, 最大年數) < FIRE目標:
        return None

    低, 高 = 0.0, 最大年數
    while 高 - 低 > 0.01:
        中 = (低 + 高) / 2
        資產 = N年後資產(目前資產, 月投入, 年化報酬率, 中)
        if 資產 < FIRE目標:
            低 = 中
        else:
            高 = 中
    return round((低 + 高) / 2, 2)


# ─────────────────────────────────────────────
# 主 API
# ─────────────────────────────────────────────
def 計算財自(月支出_twd: float,
              目前資產_twd: float,
              月投入_twd: float = 0,
              情境: str = "中等",
              fire倍數: float = 25.0) -> dict:
    """
    計算財務自由路徑。

    月支出_twd: 退休後預估的月支出
    目前資產_twd: 你目前的總資產
    月投入_twd: 預計每月可再投入金額（不會就 0）
    情境: 保守 / 中等 / 積極（決定年化報酬率）

    回傳：{
      "FIRE_目標": float,
      "目前資產": float,
      "缺口": float,
      "達標進度_pct": float,
      "達標年數": float | None,
      "達標日期": str | None,
      "剩餘_年": int, "剩餘_月": int, "剩餘_日": int,
      "情境": str,
      "年化報酬率_pct": float,
      "月支出": float,
      "月投入": float,
      "三情境對照": {保守: ..., 中等: ..., 積極: ...},
    }
    """
    if 情境 not in 情境_預設:
        情境 = "中等"

    r_pct = 情境_預設[情境]["年化報酬率_pct"]
    r = r_pct / 100

    fire目標 = FIRE目標金額(月支出_twd, fire倍數)
    缺口 = max(0, fire目標 - 目前資產_twd)
    達標進度 = min(100, 目前資產_twd / fire目標 * 100) if fire目標 > 0 else 0

    年數 = 達標年數(目前資產_twd, 月投入_twd, r, fire目標)

    達標日期 = None
    剩餘年, 剩餘月, 剩餘日 = None, None, None
    if 年數 is not None:
        天數 = int(年數 * 365.25)
        達標 = datetime.now() + timedelta(days=天數)
        達標日期 = 達標.strftime("%Y-%m-%d")
        剩餘年 = int(年數)
        剩餘月 = int((年數 - 剩餘年) * 12)
        剩餘日 = int(((年數 - 剩餘年) * 12 - 剩餘月) * 30)

    # 三情境對照（讓使用者看到差距）
    三情境 = {}
    for 名, cfg in 情境_預設.items():
        年 = 達標年數(目前資產_twd, 月投入_twd, cfg["年化報酬率_pct"] / 100, fire目標)
        三情境[名] = {
            "年化報酬率_pct": cfg["年化報酬率_pct"],
            "達標年數": 年,
            "達標日期": (datetime.now() + timedelta(days=int(年 * 365.25))).strftime("%Y-%m-%d") if 年 is not None else None,
        }

    return {
        "FIRE_目標": round(fire目標, 0),
        "目前資產": 目前資產_twd,
        "缺口": round(缺口, 0),
        "達標進度_pct": round(達標進度, 1),
        "達標年數": 年數,
        "達標日期": 達標日期,
        "剩餘_年": 剩餘年,
        "剩餘_月": 剩餘月,
        "剩餘_日": 剩餘日,
        "情境": 情境,
        "年化報酬率_pct": r_pct,
        "月支出": 月支出_twd,
        "月投入": 月投入_twd,
        "FIRE倍數": fire倍數,
        "三情境對照": 三情境,
    }


# ─────────────────────────────────────────────
# 從 portfolio.json 一鍵呼叫
# ─────────────────────────────────────────────
def 判斷生命週期階段(達標進度_pct: float) -> dict:
    """
    Phase 9：依 FIRE 進度判定生命週期階段。
    回傳階段名 + 火力 modifier（給 capital_planner 用）。
    """
    if 達標進度_pct < 25:
        return {
            "階段": "🚀 衝刺期",
            "說明": "本金少，全力累積階段",
            "be_happy_modifier": +10,   # 70% → 80%
            "wait_modifier": +5,         # 30% → 35%
            "hold_modifier": +5,         # 10% → 15% (恐慌時更積極)
            "建議": "多進場、紀律執行 +15%/-5%",
        }
    if 達標進度_pct < 75:
        return {
            "階段": "⚖️ 平衡期",
            "說明": "穩定累積階段",
            "be_happy_modifier": 0,
            "wait_modifier": 0,
            "hold_modifier": 0,
            "建議": "維持紀律，避免追高殺低",
        }
    if 達標進度_pct < 95:
        return {
            "階段": "🛡 守成期",
            "說明": "離目標不遠，降低風險",
            "be_happy_modifier": -10,   # 70% → 60%
            "wait_modifier": -5,
            "hold_modifier": -5,
            "建議": "提高 ETF 比例，降個股",
        }
    return {
        "階段": "🏆 保本期",
        "說明": "接近 FIRE，保護成果",
        "be_happy_modifier": -20,       # 70% → 50%
        "wait_modifier": -10,
        "hold_modifier": -5,
        "建議": "換高股息/債券，鎖定收益",
    }


def 階段性目標進度(目前資產: float, 設定: dict) -> dict:
    """
    Phase 9：計算短中長期目標的達成進度。
    回傳：{
      "短期": {目標, 進度_pct, 差距, 目標名},
      "中期": {...},
      "長期FIRE": {...},
    }
    """
    targets = 設定.get("goal_targets", {}) or {}
    fire_cfg = 設定.get("fire_settings", {}) or {}

    短期_目標 = targets.get("短期_1年_twd")
    中期_目標 = targets.get("中期_3年_twd")
    fire_目標 = (fire_cfg.get("monthly_expense_twd", 40000) * 12 *
                 fire_cfg.get("fire_multiplier", 25))

    def _算進度(目標):
        if not 目標 or 目標 <= 0:
            return None
        return {
            "目標_twd": 目標,
            "進度_pct": round(min(100, 目前資產 / 目標 * 100), 1),
            "差距_twd": max(0, 目標 - 目前資產),
            "已達標": 目前資產 >= 目標,
        }

    return {
        "短期": {
            **(_算進度(短期_目標) or {}),
            "目標名": targets.get("短期_目標名", "短期目標"),
        } if 短期_目標 else None,
        "中期": {
            **(_算進度(中期_目標) or {}),
            "目標名": targets.get("中期_目標名", "中期目標"),
        } if 中期_目標 else None,
        "長期FIRE": {
            **(_算進度(fire_目標) or {}),
            "目標名": f"FIRE 財務自由（月支出 {fire_cfg.get('monthly_expense_twd', 0):,} × "
                       f"{fire_cfg.get('fire_multiplier', 25)} 倍）",
        },
    }


def 從portfolio計算(設定: Optional[dict] = None) -> Optional[dict]:
    """
    portfolio.json 需有 fire_settings 區塊：
      {
        "monthly_expense_twd": 40000,
        "monthly_contribution_twd": 10000,
        "scenario": "中等",
        "fire_multiplier": 25
      }
    沒設定就回 None。
    """
    if 設定 is None:
        try:
            from . import capital_planner
        except ImportError:
            import capital_planner
        設定 = capital_planner.載入資金設定()

    fire_cfg = 設定.get("fire_settings")
    if not fire_cfg:
        return None

    月支出 = fire_cfg.get("monthly_expense_twd")
    if not 月支出:
        return None

    結果 = 計算財自(
        月支出_twd=月支出,
        目前資產_twd=設定.get("total_capital_twd", 0),
        月投入_twd=fire_cfg.get("monthly_contribution_twd", 0),
        情境=fire_cfg.get("scenario", "中等"),
        fire倍數=fire_cfg.get("fire_multiplier", 25.0),
    )
    # Phase 9：加生命週期階段 + 階段性目標進度
    結果["生命週期"] = 判斷生命週期階段(結果["達標進度_pct"])
    結果["階段目標"] = 階段性目標進度(設定.get("total_capital_twd", 0), 設定)
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

    print("=" * 60)
    print("Ryan 的離職倒數試算")
    print("=" * 60)

    # 假設：月支出 4 萬、目前 40 萬、月投入 1 萬
    r = 計算財自(
        月支出_twd=40000,
        目前資產_twd=400000,
        月投入_twd=10000,
        情境="中等",
    )

    print(f"\n月支出：NT$ {r['月支出']:,}")
    print(f"目前資產：NT$ {r['目前資產']:,}")
    print(f"月投入：NT$ {r['月投入']:,}")
    print()
    print(f"FIRE 目標：NT$ {r['FIRE_目標']:,.0f}（月支出 × 12 × {r['FIRE倍數']}）")
    print(f"目前進度：{r['達標進度_pct']}%")
    print(f"還缺：NT$ {r['缺口']:,.0f}")
    print()
    print(f"=== 主情境（{r['情境']} / {r['年化報酬率_pct']}%）===")
    if r["達標年數"] is not None:
        print(f"  達標年數：{r['達標年數']} 年")
        print(f"  達標日期：{r['達標日期']}")
        print(f"  剩餘：{r['剩餘_年']} 年 {r['剩餘_月']} 月 {r['剩餘_日']} 日")
    else:
        print("  ⚠️ 60 年內達不到目標，請提高月投入或月支出")

    print()
    print(f"=== 三情境對照 ===")
    for 名, d in r["三情境對照"].items():
        年 = d["達標年數"]
        if 年 is None:
            print(f"  {名:>4} ({d['年化報酬率_pct']}%): 60 年內達不到")
        else:
            print(f"  {名:>4} ({d['年化報酬率_pct']}%): {年:5.2f} 年 → {d['達標日期']}")

    print()
    print("=== 提高月投入到 3 萬看看（中等情境）===")
    r2 = 計算財自(40000, 400000, 30000, "中等")
    print(f"  達標年數：{r2['達標年數']} 年（vs 月投入 1 萬時 {r['達標年數']} 年）")
    print(f"  早 {r['達標年數'] - r2['達標年數']:.2f} 年達標")
