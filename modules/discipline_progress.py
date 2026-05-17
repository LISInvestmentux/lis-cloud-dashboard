"""
紀律進度 / 成就追蹤（Phase 47 — Octalysis 核心 2 應用）

算「連續紀律天數」+「累計已實現」+「給兒子的禮物」給 footer 顯示。
讓 user 在主卡底部看到自己的長期累積 → 觸發成就感（核心 2）。

連續紀律天數計算規則:
  - 看 數據/daily/ 下的 YYYY-MM-DD.json 連續存在天數
  - 從今天往回算，遇到缺檔就停
  - 每天 daily snapshot 存在 = LIS 系統有跑 = user「執行了紀律」

累計已實現:
  - 從 portfolio.json `realized_history` sum(pnl)
  - 分台股（TWD）+ 美股（USD * USD_TWD）

兒子的禮物（傳承計算）:
  - 假設未來給兒子的「家族投資池」= 累計已實現的某 % (預設 20%)
  - 顯示「已累積給兒子的儲蓄」
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


def 算連續紀律天數(最大檢查天數: int = 365) -> int:
    """從今天往回看 daily snapshot 連續存在的天數"""
    daily_dir = 專案根 / "數據" / "daily"
    if not daily_dir.exists():
        return 0

    today = datetime.now().date()
    連續 = 0
    for d in range(最大檢查天數):
        check_date = today - timedelta(days=d)
        snapshot = daily_dir / f"{check_date:%Y-%m-%d}.json"
        if snapshot.exists():
            連續 += 1
        else:
            # 允許今天還沒生成（早上 8AM 之前）
            if d == 0:
                continue
            break
    return 連續


def 算累計已實現(realized_history: list, USD_TWD: float = 32.0) -> dict:
    """從 realized_history 算累計獲利（分台股 + 美股）"""
    if not realized_history:
        return {"總計_twd": 0, "台股_twd": 0, "美股_usd": 0, "美股_twd": 0,
                "筆數": 0, "成功筆數": 0}

    台股_twd = 0
    美股_usd = 0
    筆數 = len(realized_history)
    成功 = 0

    for r in realized_history:
        sym = r.get("symbol", "")
        is_tw = sym.endswith(".TW") or sym.endswith(".TWO")
        if is_tw:
            pnl = r.get("pnl_twd") or 0
            台股_twd += pnl
        else:
            pnl = r.get("pnl_usd") or 0
            美股_usd += pnl

        if (r.get("pnl_usd") or 0) > 0 or (r.get("pnl_twd") or 0) > 0:
            成功 += 1

    美股_twd = 美股_usd * USD_TWD
    return {
        "總計_twd": round(台股_twd + 美股_twd, 0),
        "台股_twd": round(台股_twd, 0),
        "美股_usd": round(美股_usd, 2),
        "美股_twd": round(美股_twd, 0),
        "筆數": 筆數,
        "成功筆數": 成功,
        "勝率_pct": round(成功 / 筆數 * 100, 1) if 筆數 else 0,
    }


def 算給兒子的禮物(累計_twd: float, 傳承比例_pct: float = 20.0) -> int:
    """累計已實現的 20% = 「給兒子的家族池」"""
    return round(累計_twd * 傳承比例_pct / 100, 0)


def 取得footer資料(cfg: dict, USD_TWD: float = 32.0) -> dict:
    """主入口 — 給 daily_5cards 用"""
    天數 = 算連續紀律天數()
    realized = cfg.get("realized_history", []) or []
    累計 = 算累計已實現(realized, USD_TWD)
    兒子 = 算給兒子的禮物(累計["總計_twd"])

    return {
        "連續紀律天數": 天數,
        "累計已實現_twd": 累計["總計_twd"],
        "累計筆數": 累計["筆數"],
        "勝率_pct": 累計["勝率_pct"],
        "兒子家族池_twd": 兒子,
    }


# CLI 測試
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    cfg = json.loads((專案根 / "API" / "portfolio.json").read_text(encoding="utf-8"))
    data = 取得footer資料(cfg)
    print("=" * 50)
    print("LIS 紀律進度（Footer 顯示用）")
    print("=" * 50)
    print(f"📊 連續紀律天數: {data['連續紀律天數']} 天")
    print(f"💎 累計已實現: NT$ {data['累計已實現_twd']:,.0f}")
    print(f"📈 累計交易: {data['累計筆數']} 筆 (勝率 {data['勝率_pct']:.1f}%)")
    print(f"🌱 給兒子家族池 (20%): NT$ {data['兒子家族池_twd']:,.0f}")
