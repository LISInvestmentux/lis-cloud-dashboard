"""
Phase 35.1 — LIS 多因子實驗室

從 sim_ledger 的歷史訊號 + 已實現結果，回測「哪些因子組合對 Ryan 最有效」。

不是抄 ARK 公式，而是用 Ryan 自己的訊號歷史找最佳因子權重。

因子清單（從 sim_ledger 紀錄抓）：
  - 位階分數
  - 順勢分
  - F&G
  - VIX
  - 黑天鵝命中數
  - 基本面分（如有）
  - 情緒分（如有）

回測方式：
  1. 對每筆已平倉訊號，記錄當時的因子組合
  2. 算每個單因子的「勝率」和「平均報酬」
  3. 算組合因子（單因子 × 權重）的綜合表現
  4. 找最佳權重組合（greedy search）

輸出：
  {
    最強單因子: "位階分數",
    最佳組合: {位階: 0.6, F&G: 0.3, 順勢: 0.1},
    回測數: 50,
    建議: "...",
  }

依賴：sim_ledger.統計概覽()
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
LEDGER_DB = 專案根 / "數據" / "sim_ledger.db"
LAB_OUTPUT = 專案根 / "數據" / "cache" / "factor_lab_result.json"


def 載入ledger() -> list:
    """
    讀 sim_ledger.db signals table，回傳訊號清單（dict）。
    把 SQLite 英文欄位映射成中文：
      enjoy_index → F&G（暫用 enjoy 當 proxy）
      realized_pnl_pct → 實際報酬_pct
      signal_type → 訊號類型
      friction_cost_pct → 摩擦成本_pct
    """
    if not LEDGER_DB.exists():
        return []
    try:
        conn = sqlite3.connect(LEDGER_DB)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM signals")
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
    except Exception:
        return []

    # 映射英 → 中
    結果 = []
    for r in rows:
        rec = dict(r)
        rec["訊號類型"] = r.get("signal_type")
        rec["enjoy"] = r.get("enjoy_index")  # 當 F&G proxy
        rec["實際報酬_pct"] = r.get("realized_pnl_pct")
        rec["摩擦_pct"] = r.get("friction_cost_pct")
        rec["已平倉"] = r.get("closed_date") is not None
        rec["未實現_pct"] = r.get("unrealized_pnl_pct")
        # 沒真正的「位階分數」欄位，用 enjoy 當 proxy
        rec["位階分數"] = r.get("enjoy_index")
        rec["順勢分"] = 0  # 之前未存
        rec["F&G"] = r.get("enjoy_index")
        rec["VIX"] = None
        rec["黑天鵝命中數"] = 0
        結果.append(rec)
    return 結果


def 算單因子表現(訊號清單: list, 因子: str,
                  bins: list = None) -> dict:
    """
    對某個因子，分 bins 計算各區間的勝率和平均報酬。

    例：因子="位階分數"，bins=[0, 25, 35, 50, 65, 100]
        → 算每個 bin 內訊號的「平均報酬」和「勝率」
    """
    if bins is None:
        bins = [0, 25, 35, 50, 65, 100]

    結果 = []
    for i in range(len(bins) - 1):
        低 = bins[i]
        高 = bins[i + 1]
        bucket = [s for s in 訊號清單
                  if 低 <= (s.get(因子, -1) or -1) < 高
                  and s.get("已平倉") and s.get("實際報酬_pct") is not None]
        if not bucket:
            結果.append({
                "區間": f"[{低}-{高})", "樣本": 0,
                "勝率": 0, "平均報酬": 0,
            })
            continue
        報酬清單 = [s["實際報酬_pct"] for s in bucket]
        勝 = sum(1 for r in 報酬清單 if r > 0)
        結果.append({
            "區間": f"[{低}-{高})",
            "樣本": len(bucket),
            "勝率": round(勝 / len(bucket) * 100, 1),
            "平均報酬": round(sum(報酬清單) / len(bucket), 2),
            "最佳": round(max(報酬清單), 2),
            "最差": round(min(報酬清單), 2),
        })
    return {
        "因子": 因子,
        "分布": 結果,
        "總樣本": sum(b["樣本"] for b in 結果),
    }


def 算最佳組合(訊號清單: list,
                權重候選: dict = None) -> dict:
    """
    對多因子組合搜尋最佳權重。

    權重候選格式：
      {"位階分數": [0, 0.3, 0.5, 0.7],
       "F&G": [0, 0.3, 0.5],
       "順勢分": [0, 0.2, 0.4]}

    對每組權重組合，算「綜合分數 × 報酬」的相關性。
    """
    if 權重候選 is None:
        權重候選 = {
            "位階分數": [0.3, 0.5, 0.7],
            "順勢分": [0.0, 0.2, 0.4],
            "F&G": [0.0, 0.2, 0.4],
        }

    # 過濾出有完整因子值的訊號
    可用 = [s for s in 訊號清單
            if s.get("已平倉")
            and s.get("實際報酬_pct") is not None
            and all(s.get(f) is not None for f in 權重候選)]

    if len(可用) < 10:
        return {
            "錯誤": f"樣本太少 ({len(可用)} 筆) — 至少需 10 筆已平倉訊號",
            "建議": "再跑系統多收集幾週訊號再回測",
        }

    # Greedy search：枚舉所有權重組合
    from itertools import product
    factors = list(權重候選.keys())
    grids = [權重候選[f] for f in factors]

    最佳 = None
    for combo in product(*grids):
        if sum(combo) == 0:
            continue
        # 正規化權重
        s = sum(combo)
        w = {f: c/s for f, c in zip(factors, combo)}

        # 算每筆訊號的綜合分數
        分數報酬 = []
        for sig in 可用:
            score = sum(w[f] * (sig.get(f, 0) or 0) for f in factors)
            分數報酬.append((score, sig["實際報酬_pct"]))

        # 用「分數 top 30%」的平均報酬當評分
        分數報酬.sort(key=lambda x: -x[0])
        top30 = 分數報酬[:max(1, len(分數報酬) // 3)]
        top30_avg = sum(r for _, r in top30) / len(top30)
        勝率 = sum(1 for _, r in top30 if r > 0) / len(top30) * 100

        if 最佳 is None or top30_avg > 最佳["top30_平均報酬"]:
            最佳 = {
                "權重": w,
                "top30_平均報酬": round(top30_avg, 2),
                "top30_勝率": round(勝率, 1),
                "top30樣本": len(top30),
            }

    return {
        "可用樣本": len(可用),
        "最佳組合": 最佳,
        "factors": factors,
    }


def 跑實驗室(verbose: bool = True) -> dict:
    """主入口：全面回測"""
    訊號 = 載入ledger()
    平倉 = [s for s in 訊號 if s.get("已平倉")]

    if verbose:
        print(f"📊 LIS 多因子實驗室")
        print(f"━━━━━━━━━━━━━━━━━━━━━━")
        print(f"總訊號：{len(訊號)} 筆")
        print(f"已平倉：{len(平倉)} 筆")

    if len(平倉) < 10:
        return {
            "錯誤": f"樣本太少 ({len(平倉)} 筆)",
            "建議": "至少 10 筆已平倉訊號才能跑回測",
            "目前訊號數": len(訊號),
            "已平倉": len(平倉),
        }

    結果 = {"時間": datetime.now().isoformat(timespec="seconds")}

    # 單因子分析
    for 因子 in ["位階分數", "順勢分", "F&G", "VIX", "黑天鵝命中數"]:
        r = 算單因子表現(訊號, 因子)
        if r["總樣本"] >= 5:
            結果[f"單因子_{因子}"] = r
            if verbose:
                print(f"\n📈 因子：{因子}")
                for b in r["分布"]:
                    if b["樣本"] > 0:
                        print(f"  {b['區間']:8s}  "
                              f"n={b['樣本']:3d}  "
                              f"勝率 {b['勝率']:5.1f}%  "
                              f"平均 {b['平均報酬']:+6.2f}%")

    # 多因子組合
    組合 = 算最佳組合(訊號)
    結果["多因子組合"] = 組合
    if verbose and 組合.get("最佳組合"):
        最佳 = 組合["最佳組合"]
        print(f"\n🎯 多因子最佳組合 (樣本 {組合['可用樣本']} 筆)")
        for f, w in 最佳["權重"].items():
            print(f"  {f}: {w:.2f}")
        print(f"  → Top 30% 勝率 {最佳['top30_勝率']:.1f}% / "
              f"平均報酬 {最佳['top30_平均報酬']:+.2f}%")

    # 存結果
    LAB_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    LAB_OUTPUT.write_text(
        json.dumps(結果, ensure_ascii=False, indent=2),
        encoding="utf-8")

    return 結果


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    跑實驗室()
