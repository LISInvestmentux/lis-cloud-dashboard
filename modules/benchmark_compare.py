"""
LIS 績效 vs 大盤對比（Phase 32.5）

目的：證明 LIS 系統值不值得用 — 用實際數字打你 vs 0050 同期報酬。

輸入：起算日期（預設 = capital_inflow 首筆日期）
輸出：{
  起算日, 天數,
  LIS_報酬率, LIS_總資產,
  0050_漲幅, 0050_起始, 0050_目前,
  超額報酬,  # LIS - 0050
}
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


def 算LIS_vs_0050(總資產_twd: float,
                    投資內部報酬率_pct: Optional[float] = None,
                    起算日: Optional[str] = None) -> Optional[dict]:
    """
    LIS 報酬 vs 0050 同期報酬比較。

    參數：
      總資產_twd: 目前 LIS 總資產（市值 + 現金）
      投資內部報酬率_pct: 持股市值/成本 報酬率（選股能力更精準）
      起算日: YYYY-MM-DD，None 時用 capital_inflow 首筆

    回傳 None 表示無法計算（沒入金紀錄 / 0050 抓不到）
    """
    try:
        from . import capital_inflow, technical
    except ImportError:
        import capital_inflow
        import technical

    # 起算日 = capital_inflow 首筆，無紀錄就回 None
    if not 起算日:
        歷史 = capital_inflow.載入歷史()
        if not 歷史:
            return None
        起算日 = 歷史[0]["date"]

    try:
        起算dt = datetime.strptime(起算日, "%Y-%m-%d")
    except ValueError:
        return None

    天數 = (datetime.now() - 起算dt).days
    if 天數 <= 0:
        return None

    # 抓 0050 起算日附近股價
    try:
        period = f"{max(70, 天數 + 5)}d"
        歷史K, _ = technical.取得每日股價("0050.TW", period=period)
    except Exception:
        return None
    if not 歷史K:
        return None

    # 歷史K 是「最新 → 最舊」排序，找最接近起算日的
    起始價 = None
    目前價 = 歷史K[0]["close"]
    for d in 歷史K:
        try:
            dt = datetime.strptime(d["date"], "%Y-%m-%d")
        except ValueError:
            continue
        if dt <= 起算dt:
            起始價 = d["close"]
            break
    if 起始價 is None:
        # 起算日比 history 起點還早，取最遠的
        起始價 = 歷史K[-1]["close"]

    if 起始價 <= 0:
        return None

    # LIS 報酬率（用 capital_inflow 算淨報酬）
    淨 = capital_inflow.算淨報酬(總資產_twd)
    if not 淨.get("可計算"):
        return None
    LIS_pct = 淨["淨報酬率_pct"]

    # 0050 漲幅
    fifty_pct = round((目前價 / 起始價 - 1) * 100, 2)

    return {
        "起算日": 起算日,
        "天數": 天數,
        "LIS_淨報酬率_pct": LIS_pct,
        "LIS_投資內部報酬_pct": 投資內部報酬率_pct,  # 可能 None
        "LIS_總資產_twd": 總資產_twd,
        "LIS_累計本金_twd": 淨["累計注入_twd"],
        "0050_起始價": round(起始價, 2),
        "0050_目前價": round(目前價, 2),
        "0050_漲幅_pct": fifty_pct,
        "淨超額報酬_pct": round(LIS_pct - fifty_pct, 2),
        "投資超額報酬_pct": (round(投資內部報酬率_pct - fifty_pct, 2)
                               if 投資內部報酬率_pct is not None else None),
        "贏大盤_用淨報酬": LIS_pct > fifty_pct,
        "贏大盤_用投資內部": (投資內部報酬率_pct > fifty_pct
                                if 投資內部報酬率_pct is not None else None),
    }


# ─────────────────────────────────────────────
# CLI 自測
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from dotenv import load_dotenv
    load_dotenv(專案根 / "API" / ".env")

    # 用一個合理的測試值
    結 = 算LIS_vs_0050(504223)
    if 結:
        print(f"起算日: {結['起算日']} ({結['天數']} 天)")
        print(f"LIS 報酬率: {結['LIS_報酬率_pct']:+.2f}%")
        print(f"0050 漲幅:  {結['0050_漲幅_pct']:+.2f}% "
              f"({結['0050_起始價']} → {結['0050_目前價']})")
        print(f"超額報酬: {結['超額報酬_pct']:+.2f}% "
              f"{'🏆 贏大盤' if 結['贏大盤'] else '👎 輸大盤'}")
    else:
        print("無法計算（缺 capital_inflow 紀錄或 0050 抓不到）")
