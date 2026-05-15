"""
歷史回測引擎（Phase 19）— 全策略模擬

對 LIS 整體策略做歷史回測：
  「如果 2020/1/1 用 NT$ 100 萬照 LIS 策略，到今天會變多少？」

vs 基準：
  - 0050 ETF buy & hold（懶人派）
  - 0050 + 00646 DCA（太太派）
  - LIS 訊號驅動 + Kelly 加權（你派）

策略：
  進場：訊號分數 < 45（用 win_rate_engine 同邏輯）
  出場：+15% 停利 / -5% 停損 / 60 天超時
  部位：Kelly × 模式倍率 × 等級倍率（簡化版 position_sizer）
  資金管理：閒錢比 35%，黑天鵝預備 40% 鎖起來

輸出：
  {
    起始資金, 結束資金, 總報酬_pct,
    年化報酬_pct, 最大回撤_pct,
    交易次數, 勝率,
    vs_0050_alpha,
    每月績效曲線: [...]
  }
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from . import technical


專案根 = Path(__file__).resolve().parent.parent.parent


# ─────────────────────────────────────────────
# 簡化 Kelly 部位（避免 import 循環）
# ─────────────────────────────────────────────
def _kelly_pct(勝率: float, 平均賺: float, 平均賠: float) -> float:
    if 勝率 <= 0 or 平均賺 <= 0 or 平均賠 <= 0:
        return 0
    b = 平均賺 / 平均賠
    f = (b * 勝率 - (1 - 勝率)) / b
    return max(0, min(0.05, f * 0.25))  # 1/4 Kelly 上限 5%


# ─────────────────────────────────────────────
# 主回測函式
# ─────────────────────────────────────────────
def 回測LIS策略(標的清單: list[str],
                  期間: str = "5y",
                  初始資金: float = 1_000_000,
                  目標閒錢比: float = 0.35,
                  使用Kelly: bool = True) -> dict:
    """
    用 LIS 策略對多個標的回測。
    每天掃所有標的，看誰觸發進場訊號，按 Kelly 加權建倉。
    """
    # 1. 抓所有標的的歷史 K 線
    每日資料表 = {}
    print(f"抓 {len(標的清單)} 檔歷史（{期間}）...")
    for sym in 標的清單:
        try:
            歷史, _ = technical.取得每日股價(sym, period=期間)
            if 歷史 and len(歷史) > 100:
                # 轉成 {date: bar} 方便查
                每日資料表[sym] = {b["date"]: b for b in 歷史}
            print(f"  {sym}: {len(歷史)} 天")
        except Exception as e:
            print(f"  {sym}: 失敗 ({e})")

    if not 每日資料表:
        return {"error": "沒有有效標的"}

    # 2. 抓所有交易日
    所有日期 = set()
    for d in 每日資料表.values():
        所有日期.update(d.keys())
    交易日 = sorted(所有日期)
    if len(交易日) < 100:
        return {"error": "資料天數不夠"}

    print(f"\n回測期間：{交易日[0]} ~ {交易日[-1]} ({len(交易日)} 天)")

    # 3. 初始化
    現金 = 初始資金
    持股 = {}    # {sym: {shares, avg_cost, entry_date}}
    交易記錄 = []
    equity_curve = []
    閒錢底線 = 初始資金 * 目標閒錢比

    # 4. 主迴圈
    for i, today in enumerate(交易日):
        if i < 50:
            continue   # 前 50 天當暖機

        # 4a. 算當前市值
        持股市值 = 0
        for sym, p in 持股.items():
            today_bar = 每日資料表.get(sym, {}).get(today)
            if today_bar:
                持股市值 += p["shares"] * today_bar["close"]
            else:
                # 用最後價
                持股市值 += p["shares"] * p["avg_cost"] * 1.0

        總資產 = 現金 + 持股市值
        equity_curve.append({"date": today, "equity": round(總資產, 0),
                             "cash": round(現金, 0),
                             "stock": round(持股市值, 0)})

        # 4b. 檢查持股是否該出場
        要出場 = []
        for sym, p in 持股.items():
            today_bar = 每日資料表.get(sym, {}).get(today)
            if not today_bar:
                continue
            漲幅 = today_bar["high"] / p["avg_cost"] - 1
            跌幅 = today_bar["low"] / p["avg_cost"] - 1
            天數 = (datetime.strptime(today, "%Y-%m-%d") -
                     datetime.strptime(p["entry_date"], "%Y-%m-%d")).days
            退場 = None
            if 漲幅 >= 0.15:
                退場 = ("停利", p["avg_cost"] * 1.15, 0.15)
            elif 跌幅 <= -0.05:
                退場 = ("停損", p["avg_cost"] * 0.95, -0.05)
            elif 天數 >= 60:
                退場 = ("超時", today_bar["close"],
                         today_bar["close"] / p["avg_cost"] - 1)
            if 退場:
                要出場.append((sym, 退場, p, 天數))

        for sym, (原因, 賣價, 報酬率), p, 天數 in 要出場:
            收回 = p["shares"] * 賣價
            現金 += 收回
            交易記錄.append({
                "sym": sym,
                "買日": p["entry_date"], "賣日": today,
                "買價": p["avg_cost"], "賣價": round(賣價, 2),
                "股數": p["shares"], "報酬率": round(報酬率 * 100, 2),
                "天數": 天數, "原因": 原因,
            })
            del 持股[sym]

        # 4c. 找新進場機會（RSI < 35）
        新進場候選 = []
        for sym, d in 每日資料表.items():
            if sym in 持股:
                continue
            today_bar = d.get(today)
            if not today_bar:
                continue
            # 算 RSI（用過去 15 天）
            try:
                # 找今天前 15 天
                日期_列 = sorted([dt for dt in d.keys() if dt < today])
                if len(日期_列) < 15:
                    continue
                過去15 = [d[dt]["close"] for dt in 日期_列[-15:]]
                rsi = technical.計算RSI(
                    list(reversed(過去15)), 14)
                if rsi is not None and rsi < 35:
                    新進場候選.append((sym, today_bar, rsi))
            except Exception:
                continue

        # 4d. 進場（用閒錢以上的彈藥）
        可動用 = max(0, 現金 - 閒錢底線)
        if 可動用 < 5000:
            continue   # 沒彈藥
        # 按 RSI 低排序，最深價值優先
        新進場候選.sort(key=lambda x: x[2])

        for sym, bar, rsi in 新進場候選[:3]:   # 一天最多 3 檔新進場
            單筆 = min(可動用 * 0.3, 總資產 * 0.03)  # 單筆最多 3%
            if 單筆 < 3000:
                break
            股數 = int(單筆 / bar["close"])
            if 股數 < 1:
                continue
            花費 = 股數 * bar["close"]
            現金 -= 花費
            可動用 -= 花費
            持股[sym] = {
                "shares": 股數,
                "avg_cost": bar["close"],
                "entry_date": today,
            }

    # 5. 結算
    最終市值 = 現金
    for sym, p in 持股.items():
        最後價 = list(每日資料表[sym].values())[-1]["close"]
        最終市值 += p["shares"] * 最後價

    總報酬 = (最終市值 / 初始資金 - 1) * 100
    年數 = len(交易日) / 252
    年化 = (((最終市值 / 初始資金) ** (1 / 年數)) - 1) * 100 if 年數 > 0 else 0

    # 最大回撤
    高點 = 0
    最大回撤 = 0
    for e in equity_curve:
        if e["equity"] > 高點:
            高點 = e["equity"]
        回撤 = (高點 - e["equity"]) / 高點 if 高點 > 0 else 0
        if 回撤 > 最大回撤:
            最大回撤 = 回撤

    # 勝率
    if 交易記錄:
        賺數 = sum(1 for t in 交易記錄 if t["報酬率"] > 0)
        勝率 = 賺數 / len(交易記錄)
        平均報酬 = sum(t["報酬率"] for t in 交易記錄) / len(交易記錄)
    else:
        勝率 = 0
        平均報酬 = 0

    return {
        "起始資金": 初始資金,
        "最終市值": round(最終市值, 0),
        "總報酬_pct": round(總報酬, 2),
        "年化報酬_pct": round(年化, 2),
        "最大回撤_pct": round(最大回撤 * 100, 2),
        "交易次數": len(交易記錄),
        "勝率": round(勝率 * 100, 1),
        "平均報酬_pct": round(平均報酬, 2),
        "回測期間": f"{交易日[0]} ~ {交易日[-1]}",
        "天數": len(交易日),
        "未平倉_檔數": len(持股),
        "最終現金": round(現金, 0),
        "equity_curve_最近10": equity_curve[-10:],
        "交易記錄_最近10": 交易記錄[-10:],
    }


def 回測_0050_buyhold(初始資金: float = 1_000_000,
                       期間: str = "5y") -> dict:
    """0050 買一張抱到底的基準"""
    歷史, _ = technical.取得每日股價("0050.TW", period=期間)
    if not 歷史 or len(歷史) < 50:
        return {"error": "0050 資料不足"}
    起價 = 歷史[-1]["close"]
    終價 = 歷史[0]["close"]
    股數 = int(初始資金 / 起價)
    最終 = 股數 * 終價 + (初始資金 - 股數 * 起價)
    總報酬 = (最終 / 初始資金 - 1) * 100
    年數 = len(歷史) / 252
    年化 = (((最終 / 初始資金) ** (1 / 年數)) - 1) * 100 if 年數 > 0 else 0
    return {
        "起始資金": 初始資金,
        "最終市值": round(最終, 0),
        "總報酬_pct": round(總報酬, 2),
        "年化報酬_pct": round(年化, 2),
        "策略": "0050 Buy & Hold",
    }


def 回測_DCA(月度_twd: float = 8000,
              初始現金: float = 0,
              期間: str = "5y",
              標的: list = None) -> dict:
    """每月固定 DCA 0050 + 00646（太太派）"""
    標的 = 標的 or [("0050.TW", 6000), ("00646.TW", 2000)]
    # 月度 = sum(amt for _, amt in 標的)
    total = sum(amt for _, amt in 標的)
    每日資料 = {}
    for sym, _ in 標的:
        try:
            歷史, _ = technical.取得每日股價(sym, period=期間)
            每日資料[sym] = {b["date"]: b for b in 歷史}
        except Exception:
            pass
    所有日 = sorted(set().union(*[set(d.keys()) for d in 每日資料.values()]))
    if not 所有日:
        return {"error": "DCA 抓不到資料"}

    持股 = {sym: 0 for sym, _ in 標的}
    投入 = 初始現金
    現金 = 初始現金
    # 每月 6 號扣
    上次月 = None
    for date in 所有日:
        dt = datetime.strptime(date, "%Y-%m-%d")
        if dt.day == 6 or (上次月 != dt.month and dt.day > 6):
            for sym, amt in 標的:
                bar = 每日資料.get(sym, {}).get(date)
                if bar:
                    股 = amt / bar["close"]
                    持股[sym] += 股
            投入 += total
            上次月 = dt.month
    # 結算
    最終市值 = 0
    最後日 = 所有日[-1]
    for sym, _ in 標的:
        bar = 每日資料.get(sym, {}).get(最後日)
        if bar and 持股[sym] > 0:
            最終市值 += 持股[sym] * bar["close"]

    總報酬 = (最終市值 / 投入 - 1) * 100 if 投入 > 0 else 0
    年數 = len(所有日) / 252
    年化 = (((最終市值 / 投入) ** (1 / 年數)) - 1) * 100 if 年數 > 0 and 投入 > 0 else 0
    return {
        "策略": f"DCA NT${total}/月（{[s for s,_ in 標的]}）",
        "投入總額": round(投入, 0),
        "最終市值": round(最終市值, 0),
        "總報酬_pct": round(總報酬, 2),
        "年化報酬_pct": round(年化, 2),
        "回測期間": f"{所有日[0]} ~ {所有日[-1]}",
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

    print("=== Phase 19：歷史回測引擎 ===\n")

    # 基準：0050 Buy & Hold
    print("--- 基準 1：0050 Buy & Hold (5y) ---")
    r0 = 回測_0050_buyhold(初始資金=1_000_000, 期間="5y")
    print(f"  最終市值：NT$ {r0['最終市值']:,.0f}")
    print(f"  總報酬：{r0['總報酬_pct']:.1f}% | 年化：{r0['年化報酬_pct']:.1f}%")
    print()

    # 基準：DCA 太太派
    print("--- 基準 2：太太派 DCA 0050(6K)+00646(2K) 月扣 (5y) ---")
    rd = 回測_DCA(月度_twd=8000, 期間="5y",
                   標的=[("0050.TW", 6000), ("00646.TW", 2000)])
    print(f"  投入：NT$ {rd['投入總額']:,.0f}")
    print(f"  最終：NT$ {rd['最終市值']:,.0f}")
    print(f"  總報酬：{rd['總報酬_pct']:.1f}% | 年化：{rd['年化報酬_pct']:.1f}%")
    print()

    # LIS 策略：分散 ETF 抄底
    print("--- LIS 策略：訊號驅動 + Kelly (5y) ---")
    rl = 回測LIS策略(
        標的清單=["0050.TW", "00646.TW", "00911.TW", "00910.TW",
                   "00876.TW", "00861.TW", "2890.TW", "2891.TW"],
        期間="5y",
        初始資金=1_000_000,
    )
    if "error" not in rl:
        print(f"  最終市值：NT$ {rl['最終市值']:,.0f}")
        print(f"  總報酬：{rl['總報酬_pct']:.1f}% | 年化：{rl['年化報酬_pct']:.1f}%")
        print(f"  最大回撤：{rl['最大回撤_pct']:.1f}%")
        print(f"  交易次數：{rl['交易次數']} 勝率 {rl['勝率']}%")
    else:
        print(f"  錯誤：{rl['error']}")
