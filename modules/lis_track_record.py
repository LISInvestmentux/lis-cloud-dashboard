"""
LIS 信任分追蹤系統（Phase 26）

對標 ARK 商業化：每個訊號都要可追蹤、可驗證、可審查。
要敢收費就要敢被審查。

核心功能：
  1. 記錄每個訊號（時間、標的、類型、預測）
  2. N 天後自動追蹤實際結果
  3. 計算 LIS 信任分（歷史準確率）
  4. 月度自我審查報告（推 LINE）

訊號類型：
  BUY_DEEP_VALUE     位階 < 25 進場
  BUY_VALUE_ZONE     位階 25-45 進場
  BUY_MOMENTUM       順勢 >= 70 進場
  SELL_TAKE_PROFIT   達 +15% Strategy A
  SELL_STOP_LOSS     達 -5% Strategy A
  KELLY_HIGH         Kelly TOP10 加碼
  BLACK_SWAN         黑天鵝抄底

驗證目標：30 / 60 / 90 天後
  - 漲幅 (vs entry price)
  - 是否達 +15% (Strategy A)
  - 是否破 -5% (停損)
  - 還在訊號有效期內?

儲存位置：數據/lis_signal_history.json
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
歷史檔 = 專案根 / "數據" / "lis_signal_history.json"


def _載入歷史() -> dict:
    if not 歷史檔.exists():
        return {
            "說明": "LIS 信任分追蹤 — 每個訊號 + N 天驗證",
            "建立日": datetime.now().strftime("%Y-%m-%d"),
            "訊號": [],
            "信任分": {"總訊號數": 0, "已驗證": 0,
                       "命中率_pct": 0, "誤判率_pct": 0},
        }
    return json.loads(歷史檔.read_text(encoding="utf-8"))


def _存歷史(data: dict):
    歷史檔.parent.mkdir(parents=True, exist_ok=True)
    歷史檔.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                      encoding="utf-8")


# ─────────────────────────────────────────────
# 記錄訊號
# ─────────────────────────────────────────────
def 記錄訊號(訊號類型: str, symbol: str, 進場價: float,
              位階: Optional[float] = None,
              順勢分: Optional[float] = None,
              Kelly_pct: Optional[float] = None,
              預期報酬_pct: Optional[float] = None,
              建議金額_twd: Optional[float] = None,
              說明: str = "") -> dict:
    """
    記錄一筆 LIS 訊號。N 天後再用「驗證訊號」回填結果。
    回傳：剛記錄的訊號 record
    """
    data = _載入歷史()
    now = datetime.now()
    記錄 = {
        "id": f"{訊號類型}_{symbol}_{now:%Y%m%d_%H%M}",
        "訊號類型": 訊號類型,
        "symbol": symbol,
        "進場價": round(進場價, 2),
        "進場時間": now.isoformat(timespec="seconds"),
        "位階": 位階,
        "順勢分": 順勢分,
        "Kelly_pct": Kelly_pct,
        "預期報酬_pct": 預期報酬_pct,
        "建議金額_twd": 建議金額_twd,
        "說明": 說明,
        # 驗證欄位（30/60/90 天後填）
        "驗證30d": None,   # {"日期", "現價", "漲幅_pct", "命中"}
        "驗證60d": None,
        "驗證90d": None,
        "已結算": False,
    }
    data["訊號"].append(記錄)
    data["信任分"]["總訊號數"] = len(data["訊號"])
    _存歷史(data)
    return 記錄


# ─────────────────────────────────────────────
# 驗證（N 天後回頭看）
# ─────────────────────────────────────────────
def 驗證所有舊訊號(取得現價, 強制重新驗證: bool = False) -> dict:
    """
    對所有未結算訊號，用即時報價回填驗證結果。
    取得現價(sym) -> float
    """
    data = _載入歷史()
    今天 = datetime.now()
    更新數 = 0

    for r in data["訊號"]:
        進場時 = datetime.fromisoformat(r["進場時間"])
        天數 = (今天 - 進場時).days

        for 標靶_天, key in [(30, "驗證30d"), (60, "驗證60d"), (90, "驗證90d")]:
            if r.get(key) and not 強制重新驗證:
                continue
            if 天數 >= 標靶_天:
                try:
                    現價 = 取得現價(r["symbol"])
                    if 現價 is None:
                        continue
                    漲幅 = (現價 / r["進場價"] - 1) * 100

                    # 判斷命中：
                    # BUY: 漲幅 > 0 = 部分命中 / >= 預期 = 完全命中
                    # SELL: 出場後不漲（沒少賺）= 命中
                    if r["訊號類型"].startswith("BUY"):
                        命中 = "完全" if 漲幅 >= 15 else "部分" if 漲幅 > 0 else "失敗"
                    elif r["訊號類型"].startswith("SELL"):
                        命中 = "守紀律" if 漲幅 <= 5 else "錯失"
                    else:
                        命中 = "完全" if 漲幅 > 0 else "失敗"

                    r[key] = {
                        "日期": 今天.strftime("%Y-%m-%d"),
                        "現價": round(現價, 2),
                        "漲幅_pct": round(漲幅, 2),
                        "命中": 命中,
                    }
                    更新數 += 1
                except Exception:
                    continue

        # 90 天後自動結算
        if 天數 >= 90 and r.get("驗證90d"):
            r["已結算"] = True

    # 重算信任分
    已驗證 = [r for r in data["訊號"] if r.get("驗證30d")]
    if 已驗證:
        命中數 = sum(1 for r in 已驗證
                     if r["驗證30d"]["命中"] in ("完全", "部分", "守紀律"))
        誤判數 = sum(1 for r in 已驗證
                     if r["驗證30d"]["命中"] in ("失敗", "錯失"))
        data["信任分"] = {
            "總訊號數": len(data["訊號"]),
            "已驗證": len(已驗證),
            "命中數": 命中數,
            "誤判數": 誤判數,
            "命中率_pct": round(命中數 / len(已驗證) * 100, 1),
            "誤判率_pct": round(誤判數 / len(已驗證) * 100, 1),
        }
    _存歷史(data)
    return {"更新數": 更新數, "信任分": data["信任分"]}


# ─────────────────────────────────────────────
# 取信任分（給其他模組用）
# ─────────────────────────────────────────────
def 取得信任分() -> dict:
    return _載入歷史().get("信任分", {})


def 取近期訊號(天數: int = 30) -> list:
    data = _載入歷史()
    cutoff = datetime.now() - timedelta(days=天數)
    return [r for r in data["訊號"]
            if datetime.fromisoformat(r["進場時間"]) >= cutoff]


# ─────────────────────────────────────────────
# 月度自我審查
# ─────────────────────────────────────────────
def 月度自審報告() -> dict:
    """
    產生月度自我審查資料（供 Flex 卡用）
    """
    data = _載入歷史()
    今天 = datetime.now()
    一月前 = 今天 - timedelta(days=30)

    本月訊號 = [r for r in data["訊號"]
                if datetime.fromisoformat(r["進場時間"]) >= 一月前]

    # 各訊號類型表現
    分類 = {}
    for r in 本月訊號:
        類 = r["訊號類型"]
        if 類 not in 分類:
            分類[類] = {"總數": 0, "已驗證": 0, "命中": 0, "誤判": 0}
        分類[類]["總數"] += 1
        if r.get("驗證30d"):
            分類[類]["已驗證"] += 1
            if r["驗證30d"]["命中"] in ("完全", "部分", "守紀律"):
                分類[類]["命中"] += 1
            else:
                分類[類]["誤判"] += 1

    # 信任等級
    信 = data.get("信任分", {})
    命中率 = 信.get("命中率_pct", 0)
    if 信.get("已驗證", 0) < 10:
        等級 = "資料不足"
        等級emoji = "❓"
    elif 命中率 >= 70:
        等級 = "高度可信"
        等級emoji = "🟢"
    elif 命中率 >= 55:
        等級 = "可信"
        等級emoji = "✅"
    elif 命中率 >= 45:
        等級 = "勉強可用"
        等級emoji = "🟡"
    else:
        等級 = "需重新校準"
        等級emoji = "🔴"

    return {
        "報告日": 今天.strftime("%Y-%m-%d"),
        "本月訊號數": len(本月訊號),
        "歷史總訊號": len(data["訊號"]),
        "已驗證": 信.get("已驗證", 0),
        "命中率_pct": 命中率,
        "誤判率_pct": 信.get("誤判率_pct", 0),
        "等級": 等級,
        "等級emoji": 等級emoji,
        "分類表現": 分類,
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

    print("=== Phase 26 LIS 信任分追蹤系統 ===\n")

    # 模擬：今天記錄 3 個訊號
    print("[模擬] 記錄今日 3 個訊號...")
    記錄訊號("BUY_VALUE_ZONE", "2890.TW", 30.55,
              位階=24.4, Kelly_pct=8.56,
              預期報酬_pct=25.7, 建議金額_twd=1711,
              說明="深價值區，永豐金加碼")
    記錄訊號("BUY_DEEP_VALUE", "00942B.TWO", 14.29,
              位階=33.8, 預期報酬_pct=11.3,
              建議金額_twd=1715,
              說明="公債避險首次進場")
    記錄訊號("SELL_TAKE_PROFIT", "00876.TW", 86.15,
              位階=80.0, 預期報酬_pct=14.87,
              說明="Strategy D 達 +14.87% 賣 50%")

    報 = 月度自審報告()
    print(f"\n📊 月度自審：")
    print(f"  本月訊號 {報['本月訊號數']} 筆")
    print(f"  歷史總訊號 {報['歷史總訊號']} 筆")
    print(f"  已驗證 {報['已驗證']} 筆")
    print(f"  信任等級：{報['等級emoji']} {報['等級']}")
    print(f"  命中率 {報['命中率_pct']}% / 誤判 {報['誤判率_pct']}%")
    print(f"  資料檔：{歷史檔}")
