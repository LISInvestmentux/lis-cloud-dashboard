"""
LIS 覆盤系統（Phase 26.2）

每日 / 每月 / 每年三層級的覆盤檢視。
讓 LIS 不只給訊號，更給「我們做得怎樣」的客觀回顧。

對標 ARK：他們有透明的回測 + 用戶績效追蹤。
LIS 要敢收費，必須敢公開「自己預測 vs 實際差距」。

三層級設計：
  📅 每日覆盤（13:30 收盤後）— 今日訊號實際成交 / 警示是否準確
  📆 每月覆盤（每月 1 號）— 上月勝率、Strategy A 命中率、PnL vs 大盤
  📊 每年覆盤（每年 1/1）— 全年策略表現、是否該調整框架

每個覆盤的核心問題：
  - LIS 預測的 vs 實際的 = 落差多少？
  - 哪些訊號類型表現好？哪些差？
  - 我的執行紀律 vs 系統建議 = 差多少？
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from . import lis_track_record


專案根 = Path(__file__).resolve().parent.parent.parent


# ─────────────────────────────────────────────
# 每日覆盤
# ─────────────────────────────────────────────
def 每日覆盤(取得現價, 日期: Optional[str] = None) -> dict:
    """
    13:30 收盤後檢查：
      1. 今天 LIS 推的訊號 → 你執行了幾個？
      2. 警示是否準確？
      3. 整體部位變化
    """
    日期 = 日期 or datetime.now().strftime("%Y-%m-%d")

    今日訊號 = []
    history = lis_track_record._載入歷史()
    for r in history.get("訊號", []):
        if r["進場時間"].startswith(日期):
            今日訊號.append(r)

    return {
        "日期": 日期,
        "今日訊號數": len(今日訊號),
        "訊號清單": 今日訊號,
        "提醒": (
            "✅ LIS 今日表現如預期" if 今日訊號
            else "📌 今日無新訊號，DCA 照表執行"
        ),
        "明日提醒": [
            "1. 檢查 LIS 8AM 推播",
            "2. 對比實際成交 vs LIS 建議",
            "3. 寫日記錄『執行了幾個』『遵守紀律否』",
        ],
    }


# ─────────────────────────────────────────────
# 每月覆盤
# ─────────────────────────────────────────────
def 每月覆盤(取得現價, 月份: Optional[str] = None) -> dict:
    """
    每月 1 號跑：
      1. 上月所有訊號的 30 天驗證結果
      2. Strategy A 命中數 / 失敗數
      3. 整體 PnL vs 0050 / 大盤
      4. LIS 信任分變化
    """
    今天 = datetime.now()
    if 月份 is None:
        # 預設上個月
        last_month_end = 今天.replace(day=1) - timedelta(days=1)
        月份 = last_month_end.strftime("%Y-%m")

    history = lis_track_record._載入歷史()
    本月訊號 = [r for r in history.get("訊號", [])
                if r["進場時間"][:7] == 月份]

    # 分類統計
    分類 = {}
    for r in 本月訊號:
        類 = r["訊號類型"]
        if 類 not in 分類:
            分類[類] = {"總數": 0, "命中": 0, "失敗": 0, "未驗證": 0,
                        "平均報酬_pct": 0}
        分類[類]["總數"] += 1
        v = r.get("驗證30d")
        if v:
            if v["命中"] in ("完全", "部分", "守紀律"):
                分類[類]["命中"] += 1
            else:
                分類[類]["失敗"] += 1
            分類[類]["平均報酬_pct"] += v["漲幅_pct"]
        else:
            分類[類]["未驗證"] += 1

    for 類, s in 分類.items():
        驗證 = s["命中"] + s["失敗"]
        s["命中率_pct"] = round(s["命中"] / 驗證 * 100, 1) if 驗證 > 0 else None
        s["平均報酬_pct"] = round(s["平均報酬_pct"] / 驗證, 2) if 驗證 > 0 else 0

    # 信任分
    信 = history.get("信任分", {})

    # 三大覆盤問題
    覆盤問題 = []
    if 信.get("已驗證", 0) >= 10:
        if 信.get("命中率_pct", 0) >= 60:
            覆盤問題.append("✅ LIS 命中率達標，繼續執行")
        elif 信.get("命中率_pct", 0) >= 45:
            覆盤問題.append("🟡 LIS 命中率邊緣，看哪類訊號最差")
        else:
            覆盤問題.append("🔴 LIS 命中率偏低，需檢討進場條件")

    # 跟大盤對比
    覆盤問題.append("📊 對比 0050：你的真倉 +X% vs 0050 +Y%")
    覆盤問題.append("🎯 執行紀律：LIS 給 N 個訊號，你執行了 M 個")

    return {
        "月份": 月份,
        "本月訊號數": len(本月訊號),
        "分類表現": 分類,
        "信任分": 信,
        "覆盤問題": 覆盤問題,
        "下月計畫": [
            "1. 觀察 LIS 信任分變化",
            "2. 對最差的訊號類型暫停執行",
            "3. 對最好的訊號類型加碼跟進",
            "4. 檢查 watchlist 有沒有遺漏的熱門 ETF",
        ],
    }


# ─────────────────────────────────────────────
# 每年覆盤
# ─────────────────────────────────────────────
def 每年覆盤(取得現價, 年份: Optional[int] = None) -> dict:
    """
    每年 1 月 1 號跑：
      1. 全年 PnL vs 0050 / S&P 500 / 太太
      2. 全年策略表現排行
      3. 是否該升級 LIS 演算法
      4. 商業化準備度評估
    """
    年份 = 年份 or datetime.now().year - 1

    history = lis_track_record._載入歷史()
    全年訊號 = [r for r in history.get("訊號", [])
                if r["進場時間"][:4] == str(年份)]

    信 = history.get("信任分", {})
    命中率 = 信.get("命中率_pct", 0)

    # 商業化準備度評估
    if len(全年訊號) >= 100 and 命中率 >= 60:
        商業化等級 = "🟢 已準備好上線收費"
    elif len(全年訊號) >= 50 and 命中率 >= 55:
        商業化等級 = "✅ 可開放 beta（朋友圈）"
    elif len(全年訊號) >= 20:
        商業化等級 = "🟡 樣本仍不足，再觀察 6 月"
    else:
        商業化等級 = "🔴 訊號太少，無法評估"

    return {
        "年份": 年份,
        "全年訊號數": len(全年訊號),
        "信任分": 信,
        "命中率_pct": 命中率,
        "商業化等級": 商業化等級,
        "年度問題": [
            f"📊 {年份} 全年總報酬：(算 PnL)",
            f"🎯 vs 0050 全年：(算 alpha)",
            f"🎯 vs 太太可可：(她大概 +27%)",
            "🛠️ 哪些 Phase 沒做完？",
            "📈 商業化準備度：" + 商業化等級,
            "🚀 明年要不要加新功能？",
        ],
        "升級建議": [
            "1. 看 walk-forward 落差 — 是否 overfit?",
            "2. 補基本面（PE/ROE/EPS）",
            "3. 補法人籌碼",
            "4. 補新聞情緒",
            "5. 加 web/app 介面（前置商業化）",
        ],
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

    print("=== Phase 26.2 覆盤系統測試 ===\n")

    def mock取現價(s):
        return None

    print("📅 今日覆盤：")
    r = 每日覆盤(mock取現價)
    print(f"  今日訊號 {r['今日訊號數']} 筆")
    print(f"  {r['提醒']}")
    print()

    print("📆 上月覆盤：")
    r = 每月覆盤(mock取現價)
    print(f"  本月訊號 {r['本月訊號數']} 筆")
    for 類, s in r["分類表現"].items():
        print(f"    {類}: 總 {s['總數']} / 命中 {s['命中']} / 失敗 {s['失敗']}")
    for q in r["覆盤問題"]:
        print(f"  {q}")
    print()

    print("📊 上年覆盤：")
    r = 每年覆盤(mock取現價)
    print(f"  全年訊號 {r['全年訊號數']} 筆")
    print(f"  信任分：{r['信任分']}")
    print(f"  商業化等級：{r['商業化等級']}")
