"""
外部訊號追蹤器（Phase 27）

天才想法：**用別人的訊號累積我們的預測勝率資料庫**

LIS 自己訊號累積慢（每天 0-5 筆），但市場上每天有 100+ 來源在出訊號。
追蹤這些外部訊號 + 自動驗證 = 快速累積勝率資料。

最大價值：
  1. 找出「真正準的訊號來源」（哪個 KOL / 哪個系統 / 哪個策略最強）
  2. 自動「跟單」最強來源（不是抄明牌，是學算法）
  3. 建立「來源信任分」資料庫（這檔有多少來源都看好？）

來源類型：
  ARK_可可     太太/可可 ARK 系統截圖訊號（手動 log）
  ARK_系統     ARK 方舟系統公開訊號（如果有 API）
  法人_外資    外資連續買超（公開資料）
  法人_投信    投信連續買超（公開資料）
  KOL_玩股     公開 KOL（已有 kol_aggregator）
  券商_永豐    永豐 / 富邦每日推薦股
  券商_凱基    凱基精選股
  自選_其他    你自己看到的任何來源

資料結構：
  訊號 = {來源, 時間, symbol, 類型(BUY/SELL), 進場價, 目標價, 停損價, 說明}
  驗證 = 30/60/90 天後比對結果

儲存：數據/external_signal_history.json
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
外部歷史檔 = 專案根 / "數據" / "external_signal_history.json"


def _載入() -> dict:
    if not 外部歷史檔.exists():
        return {
            "說明": "外部訊號追蹤 — 累積市場各來源的預測準確度",
            "建立日": datetime.now().strftime("%Y-%m-%d"),
            "訊號": [],
            "來源信任分": {},  # {來源名: {總數, 命中, 命中率}}
        }
    return json.loads(外部歷史檔.read_text(encoding="utf-8"))


def _存(data: dict):
    外部歷史檔.parent.mkdir(parents=True, exist_ok=True)
    外部歷史檔.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                          encoding="utf-8")


# ─────────────────────────────────────────────
# 記錄外部訊號
# ─────────────────────────────────────────────
def 記錄外部訊號(來源: str, symbol: str, 類型: str,
                  進場價: float,
                  目標價: Optional[float] = None,
                  停損價: Optional[float] = None,
                  時間: Optional[str] = None,
                  說明: str = "",
                  metadata: Optional[dict] = None) -> dict:
    """
    記錄一筆外部訊號（任何來源）

    來源範例: "ARK_可可", "ARK_大俠", "法人_外資連10買",
              "KOL_玩股股神", "券商_永豐精選"
    類型: "BUY" / "SELL"
    """
    data = _載入()
    時間 = 時間 or datetime.now().isoformat(timespec="seconds")
    記錄 = {
        "id": f"{來源}_{symbol}_{時間.replace(':','').replace('-','')[:14]}",
        "來源": 來源,
        "symbol": symbol,
        "類型": 類型,
        "進場價": round(進場價, 2),
        "目標價": 目標價,
        "停損價": 停損價,
        "時間": 時間,
        "說明": 說明,
        "metadata": metadata or {},
        # 驗證
        "驗證30d": None,
        "驗證60d": None,
        "驗證90d": None,
        "已結算": False,
    }
    data["訊號"].append(記錄)
    _存(data)
    return 記錄


# ─────────────────────────────────────────────
# 驗證
# ─────────────────────────────────────────────
def 驗證外部訊號(取得現價) -> dict:
    """對所有外部訊號 30/60/90 天後驗證"""
    data = _載入()
    今天 = datetime.now()
    更新數 = 0

    for r in data["訊號"]:
        進場時 = datetime.fromisoformat(r["時間"])
        天數 = (今天 - 進場時).days

        for 標靶, key in [(30, "驗證30d"), (60, "驗證60d"), (90, "驗證90d")]:
            if r.get(key):
                continue
            if 天數 >= 標靶:
                try:
                    現價 = 取得現價(r["symbol"])
                    if 現價 is None:
                        continue
                    漲幅 = (現價 / r["進場價"] - 1) * 100

                    # 命中判定
                    if r["類型"] == "BUY":
                        if r.get("目標價") and 現價 >= r["目標價"]:
                            命中 = "目標達成"
                        elif r.get("停損價") and 現價 <= r["停損價"]:
                            命中 = "停損觸發"
                        elif 漲幅 >= 15:
                            命中 = "完全（+15%）"
                        elif 漲幅 > 0:
                            命中 = "部分（正報酬）"
                        elif 漲幅 > -5:
                            命中 = "持平"
                        else:
                            命中 = "失敗"
                    else:  # SELL
                        if 漲幅 <= 0:
                            命中 = "守紀律（沒漲）"
                        elif 漲幅 < 5:
                            命中 = "勉強（小漲）"
                        else:
                            命中 = "錯失（後續大漲）"

                    r[key] = {
                        "日期": 今天.strftime("%Y-%m-%d"),
                        "現價": round(現價, 2),
                        "漲幅_pct": round(漲幅, 2),
                        "命中": 命中,
                    }
                    更新數 += 1
                except Exception:
                    continue

        if 天數 >= 90 and r.get("驗證90d"):
            r["已結算"] = True

    # 重算每個來源的信任分
    來源統計 = {}
    for r in data["訊號"]:
        來源 = r["來源"]
        if 來源 not in 來源統計:
            來源統計[來源] = {"總數": 0, "已驗證": 0,
                              "命中": 0, "失敗": 0,
                              "平均報酬_pct": 0}
        來源統計[來源]["總數"] += 1
        v = r.get("驗證30d")
        if v:
            來源統計[來源]["已驗證"] += 1
            來源統計[來源]["平均報酬_pct"] += v["漲幅_pct"]
            if "完全" in v["命中"] or "部分" in v["命中"] or \
               "目標" in v["命中"] or "守紀律" in v["命中"]:
                來源統計[來源]["命中"] += 1
            else:
                來源統計[來源]["失敗"] += 1

    for 來源, s in 來源統計.items():
        if s["已驗證"] > 0:
            s["命中率_pct"] = round(s["命中"] / s["已驗證"] * 100, 1)
            s["平均報酬_pct"] = round(s["平均報酬_pct"] / s["已驗證"], 2)
        else:
            s["命中率_pct"] = None

    data["來源信任分"] = 來源統計
    _存(data)
    return {"更新數": 更新數, "來源統計": 來源統計}


# ─────────────────────────────────────────────
# 找出「最準的來源」
# ─────────────────────────────────────────────
def 來源排行(最少樣本: int = 5) -> list:
    """回傳按命中率排序的來源列表"""
    data = _載入()
    來源 = data.get("來源信任分", {})
    有效 = [(k, v) for k, v in 來源.items()
            if v.get("已驗證", 0) >= 最少樣本]
    有效.sort(key=lambda x: -(x[1].get("命中率_pct") or 0))
    return 有效


# ─────────────────────────────────────────────
# 找「多來源都看好」的標的
# ─────────────────────────────────────────────
def 多來源共識(symbol: Optional[str] = None,
                 近期天數: int = 14) -> dict:
    """
    回傳近期被「多少不同來源」買入的標的。
    多來源共識 = 強訊號（不只一個系統說好）
    """
    data = _載入()
    cutoff = datetime.now() - timedelta(days=近期天數)
    近期 = [r for r in data["訊號"]
            if datetime.fromisoformat(r["時間"]) >= cutoff
            and r["類型"] == "BUY"
            and (symbol is None or r["symbol"] == symbol)]

    by_symbol = {}
    for r in 近期:
        s = r["symbol"]
        if s not in by_symbol:
            by_symbol[s] = {"來源清單": set(), "訊號清單": []}
        by_symbol[s]["來源清單"].add(r["來源"])
        by_symbol[s]["訊號清單"].append(r)

    # 結果
    結果 = []
    for s, info in by_symbol.items():
        結果.append({
            "symbol": s,
            "來源數": len(info["來源清單"]),
            "來源清單": sorted(info["來源清單"]),
            "訊號數": len(info["訊號清單"]),
            "最早": min(r["時間"] for r in info["訊號清單"]),
        })
    結果.sort(key=lambda r: -r["來源數"])
    return 結果


# ─────────────────────────────────────────────
# CLI 自測 + 預埋可可訊號
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=== Phase 27 外部訊號追蹤器 ===\n")

    # 預埋：把可可截圖的 7 檔當作外部訊號（推估進場價=現價-累積漲幅）
    可可訊號 = [
        ("00757.TW", 19.47, 125987),   # 統一 FANG+
        ("00911.TW", 45.29, 62939),    # 兆豐洲際半導體
        ("00990A.TW", 63.18, 50187),   # 主動元大 AI 新經濟
        ("00910.TW", 11.33, 164714),   # 第一金太空衛星
        ("00980S.TW", 30.53, 59352),   # 新光美國電力基建
        ("0050.TW", 23.74, 66773),     # 元大台灣50
        ("LITE", 16.19, 32488),        # Lumentum
    ]

    # 假設可可一年前進場（讓 90d 驗證直接命中）
    一年前 = (datetime.now() - timedelta(days=365)).isoformat(timespec="seconds")
    for sym, 漲幅, 市值 in 可可訊號:
        # 進場價 = 現值 / (1+漲幅) / 假設股數
        # 簡化：直接記錄漲幅當 metadata
        記錄外部訊號(
            來源="ARK_可可",
            symbol=sym,
            類型="BUY",
            進場價=100.0,  # 用佔位
            時間=一年前,
            說明=f"可可 1 年累積 +{漲幅}%，市值 NT$ {市值:,}",
            metadata={"累積報酬_pct": 漲幅, "目前市值": 市值},
        )

    print(f"✅ 已記錄可可 7 筆 ARK 訊號（1 年累積）")
    print()

    # 列來源排行
    排行 = 來源排行(最少樣本=1)
    print("📊 來源信任分排行：")
    for 來源, s in 排行:
        print(f"  {來源:<20} 總 {s['總數']} 已驗證 {s['已驗證']} "
              f"命中 {s.get('命中', 0)} "
              f"命中率 {s.get('命中率_pct')} 平均 {s['平均報酬_pct']}%")

    print()
    print("📊 多來源共識（過去 14 天）：")
    共識 = 多來源共識(近期天數=14)
    if 共識:
        for c in 共識[:5]:
            print(f"  {c['symbol']:<12} 來源數 {c['來源數']} "
                  f"訊號數 {c['訊號數']}")
    else:
        print("  （目前沒有多來源共識）")
