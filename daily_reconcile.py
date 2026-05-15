"""
模擬盤每日收盤對帳腳本（Phase 8.0 + 8.0b）
每天台股收盤後（13:30 之後）跑一次：

主表（signals）：
1. 抓所有「未平倉」的 BUY 訊號
2. 抓每檔最新收盤價 + 近期 20 日 K 線（給策略 C 用）
3. 算 unrealized_pnl_pct（含摩擦成本）
4. 觸發策略 A 條件 → 主表平倉（+15% / -5% / 30天）

副表（strategy_results）：
5. 對同一檔同時跑 3 套策略，各自判定是否出場：
   - A 固定停利 +15% / -5%
   - B 移動停利 漲到 +20% 後從進場後新高回落 8%
   - C 跌破 20 日線 連 2 天

執行方式：
   .venv\\Scripts\\python.exe daily_reconcile.py
Windows 排程任務：LIS_Sim_Reconcile（13:35 週一-五）
"""
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))

from modules import sim_ledger
from modules import technical


# ─────────────────────────────────────────────
# 停利停損閾值（含摩擦後）— 策略 A
# ─────────────────────────────────────────────
停利_PCT = 15.0    # +15% 觸發停利
停損_PCT = -5.0    # -5% 觸發停損
時間上限_DAYS = 30  # 30 天還沒觸發 → 強制平倉

# 策略 B：移動停利
B_啟動門檻_PCT = 20.0   # 漲到 +20% 才啟動移動停利
B_回落幅度_PCT = 8.0    # 從進場後新高回落 8% 出場

# 策略 C：跌破 20 日線
C_收線下天數 = 2        # 連 2 天收在 20 日線下出場

# 策略 D：分批出場
D_第一階段_PCT = 15.0   # 達 +15% 賣 50%
D_第二階段_PCT = 30.0   # 達 +30% 賣到 75%（再賣 25%）
D_魚尾回落_PCT = 8.0    # 剩 25% 用移動停利（從新高回落 8%）


def _抓最新K線(symbol: str, period: str = "3mo") -> list[dict]:
    """從 yfinance 抓最近 K 線（給策略 C 計算 MA20 用）。"""
    每日, 實際symbol = technical.取得每日股價(symbol, period=period)
    if not 每日:
        raise ValueError(f"{symbol} 沒資料")
    return 每日


def _抓最新收盤(symbol: str) -> tuple[float, str]:
    """
    從 yfinance 抓最新收盤價。回傳 (price, date_str)。
    抓不到時 raise。
    """
    每日 = _抓最新K線(symbol, period="5d")
    最新 = 每日[0]
    return float(最新["close"]), 最新["date"]


# ─────────────────────────────────────────────
# 策略判定函數（每套各一個）
# ─────────────────────────────────────────────
def _策略A_判定(現價: float, 進場價: float, 摩擦: float,
                 持有天數: int) -> Optional[tuple[str, float]]:
    """
    策略 A 固定停利停損。回傳 (exit_reason, pnl_pct) 或 None。
    """
    pnl_pct = ((現價 / 進場價 - 1) - 摩擦) * 100
    if pnl_pct >= 停利_PCT:
        return ("TAKE_PROFIT", pnl_pct)
    if pnl_pct <= 停損_PCT:
        return ("STOP_LOSS", pnl_pct)
    if 持有天數 >= 時間上限_DAYS:
        return ("TIME_LIMIT", pnl_pct)
    return None


def _策略B_判定(現價: float, 進場價: float, 摩擦: float,
                 high_water: float, 持有天數: int) -> Optional[tuple[str, float]]:
    """
    策略 B 移動停利。
    1. 先檢查 -5% 停損
    2. 漲到 +20% 後啟動移動停利
    3. 從進場後新高回落 8% 出
    """
    pnl_pct = ((現價 / 進場價 - 1) - 摩擦) * 100
    if pnl_pct <= 停損_PCT:
        return ("STOP_LOSS", pnl_pct)

    高水位漲幅 = (high_water / 進場價 - 1) * 100
    # 啟動移動停利條件：曾經漲到 +20%
    if 高水位漲幅 >= B_啟動門檻_PCT:
        回落 = (high_water - 現價) / high_water * 100
        if 回落 >= B_回落幅度_PCT:
            return ("TRAILING_STOP", pnl_pct)

    if 持有天數 >= 時間上限_DAYS:
        return ("TIME_LIMIT", pnl_pct)
    return None


def _策略D_判定(現價: float, 進場價: float, 摩擦: float,
                 high_water: float, 已賣階段: int,
                 持有天數: int) -> Optional[tuple[str, float, int]]:
    """
    策略 D 分批出場。回傳 (action, pnl_pct, 新階段) 或 None。
    action: SCALED_50 / SCALED_75 / TRAILING_STOP / STOP_LOSS / TIME_LIMIT
    新階段: 0 / 50 / 75 / 100
    """
    pnl_pct = ((現價 / 進場價 - 1) - 摩擦) * 100

    # 停損保護（任何階段都檢查）
    if pnl_pct <= 停損_PCT:
        return ("STOP_LOSS", pnl_pct, 100)   # 一次出清

    # 第一階段：達 +15% 賣 50%
    if 已賣階段 < 50 and pnl_pct >= D_第一階段_PCT:
        return ("SCALED_50", pnl_pct, 50)

    # 第二階段：達 +30% 賣到 75%
    if 已賣階段 < 75 and pnl_pct >= D_第二階段_PCT:
        return ("SCALED_75", pnl_pct, 75)

    # 第三階段：剩 25% 用移動停利（漲到 +30% 後啟動）
    if 已賣階段 >= 75:
        高水位漲幅 = (high_water / 進場價 - 1) * 100
        if 高水位漲幅 >= D_第二階段_PCT:
            回落 = (high_water - 現價) / high_water * 100
            if 回落 >= D_魚尾回落_PCT:
                return ("TRAILING_STOP", pnl_pct, 100)

    # 時間上限
    if 持有天數 >= 時間上限_DAYS:
        return ("TIME_LIMIT", pnl_pct, 100)

    return None


def _策略C_判定(現價: float, 進場價: float, 摩擦: float,
                 K線: list[dict], 持有天數: int,
                 signal_date_str: str) -> Optional[tuple[str, float]]:
    """
    策略 C 跌破 20 日線連 2 天（**只看進場後**）。
    signal_date_str: 訊號發出當日 YYYY-MM-DD
    """
    pnl_pct = ((現價 / 進場價 - 1) - 摩擦) * 100
    if pnl_pct <= 停損_PCT:
        return ("STOP_LOSS", pnl_pct)

    收盤 = [d["close"] for d in K線]
    if len(收盤) < 21:
        if 持有天數 >= 時間上限_DAYS:
            return ("TIME_LIMIT", pnl_pct)
        return None

    # 只挑進場日之後（含當日）的 K 線
    進場後indices = [i for i, d in enumerate(K線) if d["date"] >= signal_date_str]
    if len(進場後indices) < C_收線下天數:
        # 進場後天數不夠，先持有
        if 持有天數 >= 時間上限_DAYS:
            return ("TIME_LIMIT", pnl_pct)
        return None

    # 從最新（idx=0）開始檢查連續性
    連續收線下 = 0
    for k_idx in 進場後indices:
        if k_idx + 20 > len(收盤):
            break
        當天MA20 = sum(收盤[k_idx:k_idx+20]) / 20
        if 收盤[k_idx] < 當天MA20:
            連續收線下 += 1
            if 連續收線下 >= C_收線下天數:
                return ("MA_BREAK", pnl_pct)
        else:
            break

    if 持有天數 >= 時間上限_DAYS:
        return ("TIME_LIMIT", pnl_pct)
    return None


def 對帳一筆(訊號: dict) -> dict:
    """
    處理一筆未平倉訊號：
    1. 抓最近 K 線
    2. 回填主表收盤 + 用策略 A 判定主表平倉
    3. 對 3 套策略各自判定（含 B 移動停利的高水位更新）

    回傳：{"action": ..., "strategy_actions": {...}, ...}
    """
    signal_id = 訊號["id"]
    symbol = 訊號["symbol"]
    買入價 = 訊號["assumed_exec_price"]
    摩擦 = 訊號["friction_cost_pct"]
    signal_time_str = 訊號["signal_time"][:10]
    signal_date = datetime.strptime(signal_time_str, "%Y-%m-%d").date()

    try:
        K線 = _抓最新K線(symbol, period="3mo")
    except Exception as e:
        return {"action": "SKIPPED", "symbol": symbol,
                "reason": str(e), "strategy_actions": {}}

    最新 = K線[0]
    close_price = float(最新["close"])
    close_date = 最新["date"]
    今日date = datetime.strptime(close_date, "%Y-%m-%d").date()
    持有天數 = (今日date - signal_date).days

    # 回填主表收盤
    sim_ledger.回填收盤(signal_id, close_price, close_date)

    # ── 主表（策略 A）平倉判定 ──
    主表action = "HELD"
    A_result = _策略A_判定(close_price, 買入價, 摩擦, 持有天數)
    if A_result:
        reason, _ = A_result
        平倉 = sim_ledger.模擬平倉(signal_id, close_price, reason, close_date)
        主表action = reason

    # ── 副表三套策略判定 ──
    strategy_actions = {}

    # 抓進場後到今天的最高價（給策略 B 用）
    # K線 是最新在 [0]，往後是更舊
    # 找到 signal_date 那一天的 index
    進場後最高 = 買入價
    for d in K線:
        d_date = datetime.strptime(d["date"], "%Y-%m-%d").date()
        if d_date >= signal_date:
            進場後最高 = max(進場後最高, d.get("high", d["close"]))

    # 更新所有 OPEN 策略行的高水位
    sim_ledger.更新策略高水位(signal_id, "B_trailing", 進場後最高)

    # 對每套策略判定
    open策略 = sim_ledger.查詢策略未平倉()
    for sr in open策略:
        if sr["signal_id"] != signal_id:
            continue
        strategy = sr["strategy"]
        result = None
        if strategy == "A_fixed":
            result = _策略A_判定(close_price, 買入價, 摩擦, 持有天數)
        elif strategy == "B_trailing":
            high_water = sr.get("high_water_mark") or 買入價
            high_water = max(high_water, 進場後最高)
            result = _策略B_判定(close_price, 買入價, 摩擦, high_water, 持有天數)
        elif strategy == "C_ma20":
            result = _策略C_判定(close_price, 買入價, 摩擦, K線,
                                   持有天數, signal_time_str)
        elif strategy == "D_scaled":
            # 策略 D：拿目前階段
            已賣階段 = sr.get("partial_pct") or 0
            high_water = max(sr.get("high_water_mark") or 買入價, 進場後最高)
            d_result = _策略D_判定(close_price, 買入價, 摩擦,
                                    high_water, 已賣階段, 持有天數)
            if d_result:
                action_, pnl_, 新階段 = d_result
                # 分批 vs 收尾
                if 新階段 < 100:
                    # 部分平倉
                    sim_ledger.更新策略高水位(signal_id, "D_scaled", high_water)
                    r = sim_ledger.部分平倉(
                        signal_id=signal_id, strategy="D_scaled",
                        新階段_pct=新階段, exit_price=close_price,
                        exit_date=close_date, 摩擦比例=摩擦, 進場價=買入價,
                    )
                    strategy_actions[strategy] = {
                        "action": action_,
                        "pnl_pct": r["累計_pnl_pct"],
                        "partial_pct": 新階段,
                    }
                    continue
                else:
                    # 收尾平倉
                    r = sim_ledger.收尾平倉(
                        signal_id=signal_id, strategy="D_scaled",
                        exit_price=close_price, exit_reason=action_,
                        exit_date=close_date, 摩擦比例=摩擦,
                        進場價=買入價, 持有天數=持有天數,
                    )
                    strategy_actions[strategy] = {
                        "action": action_,
                        "pnl_pct": r["pnl_pct"],
                    }
                    continue
            else:
                pnl_pct = ((close_price / 買入價 - 1) - 摩擦) * 100
                strategy_actions[strategy] = {
                    "action": f"HELD({已賣階段}%)",
                    "pnl_pct": round(pnl_pct, 2),
                }
                continue

        if result:
            exit_reason, _ = result
            r = sim_ledger.平倉策略(
                signal_id=signal_id, strategy=strategy,
                exit_price=close_price, exit_reason=exit_reason,
                exit_date=close_date, 摩擦比例=摩擦,
                進場價=買入價, 持有天數=持有天數,
            )
            strategy_actions[strategy] = {
                "action": exit_reason,
                "pnl_pct": r["pnl_pct"],
            }
        else:
            pnl_pct = ((close_price / 買入價 - 1) - 摩擦) * 100
            strategy_actions[strategy] = {"action": "HELD",
                                            "pnl_pct": round(pnl_pct, 2)}

    return {
        "action": 主表action,
        "symbol": symbol,
        "close_price": close_price,
        "held_days": 持有天數,
        "high_water": round(進場後最高, 2),
        "strategy_actions": strategy_actions,
    }


def 主流程() -> int:
    開始 = datetime.now()
    print(f"=== 模擬盤收盤對帳 [{開始:%Y-%m-%d %H:%M:%S}] ===")

    未平倉 = sim_ledger.查詢未平倉()
    print(f"未平倉訊號數：{len(未平倉)}")
    if not 未平倉:
        print("無未平倉訊號（主表）。")

    主表統計 = {"HELD": 0, "TAKE_PROFIT": 0, "STOP_LOSS": 0,
                "TIME_LIMIT": 0, "SKIPPED": 0}
    平倉事件 = []

    for 訊號 in 未平倉:
        try:
            結果 = 對帳一筆(訊號)
            action = 結果["action"]
            主表統計[action] = 主表統計.get(action, 0) + 1

            sa = 結果.get("strategy_actions", {})
            策略摘要 = " | ".join(
                f"{s[:4]}={a['action'][:4]}({a['pnl_pct']:+.1f}%)"
                for s, a in sa.items()
            ) if sa else ""

            if action == "HELD":
                print(f"  [持有] {結果['symbol']:>12} "
                      f"收={結果['close_price']:>8.2f} "
                      f"高水位={結果.get('high_water', 0):>8.2f} "
                      f"({結果['held_days']}天)")
                if 策略摘要:
                    print(f"        策略對照: {策略摘要}")
            elif action == "SKIPPED":
                print(f"  [略過] {結果['symbol']:>12} 原因={結果.get('reason')}")
            else:
                emoji = ("🎯" if action == "TAKE_PROFIT"
                          else "💀" if action == "STOP_LOSS"
                          else "⏱")
                print(f"  {emoji} [{action}] {結果['symbol']:>12} "
                      f"收={結果['close_price']:>8.2f} "
                      f"({結果['held_days']}天)")
                if 策略摘要:
                    print(f"        策略對照: {策略摘要}")
                平倉事件.append(結果)
        except Exception as e:
            print(f"  [錯誤] {訊號.get('symbol')}: {e}")
            traceback.print_exc()
            主表統計["SKIPPED"] += 1

    print()
    print(f"=== 主表（策略 A）對帳統計 ===")
    for k, v in 主表統計.items():
        print(f"  {k:>12}: {v}")

    # 副表：3 套策略未平倉狀況
    print()
    print(f"=== 副表 3 套策略未平倉統計 ===")
    for s in sim_ledger.策略清單:
        筆數 = len(sim_ledger.查詢策略未平倉(s))
        print(f"  {sim_ledger.策略中文名[s]:>22}: 未平倉 {筆數}")

    # 副表：3 套策略績效對照
    績效 = sim_ledger.策略績效比對()
    if 績效:
        print()
        print(f"=== 副表 3 套策略已平倉績效對照 ===")
        for d in 績效:
            print(f"  {d['策略名稱']:>22}: "
                  f"平倉 {d['平倉筆數']:>3} "
                  f"勝率 {d.get('勝率_%')}% "
                  f"平均報酬 {d['平均報酬']:+.2f}% "
                  f"最佳 {d['最佳']:+.2f}% / 最差 {d['最差']:+.2f}%")

    概覽 = sim_ledger.統計概覽()
    print()
    print(f"=== Ledger 主表整體概覽 ===")
    for k, v in 概覽.items():
        print(f"  {k:>14}: {v}")

    耗時 = (datetime.now() - 開始).total_seconds()
    print(f"\n=== 完成（耗時 {耗時:.1f} 秒） ===")
    return 0


if __name__ == "__main__":
    sys.exit(主流程())
