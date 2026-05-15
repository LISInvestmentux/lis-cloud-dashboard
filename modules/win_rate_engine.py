"""
個股勝率引擎（Phase 18）— 8 年歷史回測 + Kelly Criterion 數據庫

對標 ARK 大俠的勝率資料庫：
  - 對每檔股票跑 8 年歷史「進入價值區買 → +15% 賣 / -5% 停損」模擬
  - 算出每檔的真實 勝率 / 平均賺 / 平均賠 / 平均持倉天數
  - 算 Kelly Criterion 的最佳部位 %
  - 存到 數據/win_rate_db.json，給 position_sizer 用

策略基準：
  進場：RSI(14) < 35（深度價值區訊號）
  停利：+15%
  停損：-5%
  超時：60 天未觸發 → 平倉
  冷卻：訊號觸發後 14 天內不重複進場

使用：
  from modules import win_rate_engine as wre
  wre.跑全部watchlist()             # 對全 watchlist 跑
  wre.載入勝率資料庫()              # 給 position_sizer 用
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import technical

# 確保 console 能印中文 + emoji（修 cp950 問題）
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


專案根 = Path(__file__).resolve().parent.parent.parent
DB_PATH = 專案根 / "數據" / "win_rate_db.json"


# ─────────────────────────────────────────────
# 模擬交易（純邏輯，不依賴外部）
# ─────────────────────────────────────────────
def 模擬交易序列(歷史: list[dict],
                  進場RSI閾值: float = 35.0,
                  停利_pct: float = 0.15,
                  停損_pct: float = -0.05,
                  最長持倉_天: int = 60,
                  冷卻_天: int = 14) -> list[dict]:
    """
    歷史: yfinance 抓的 K 線（由「新到舊」排序，technical 的格式）
    回傳：完整交易記錄列表
    """
    if not 歷史 or len(歷史) < 100:
        return []

    # 反轉成「由舊到新」做時序模擬
    時序 = list(reversed(歷史))
    n = len(時序)

    交易 = []
    in_position = False
    買價 = None
    買日 = None
    買日索引 = None
    上次訊號索引 = -999

    for i in range(20, n):
        當日 = 時序[i]
        # 算 RSI(14)：取過去 15 天收盤（i 包含當天）
        # technical.計算RSI 吃「新到舊」陣列，所以要 reverse
        過去15 = [時序[i - k]["close"] for k in range(14, -1, -1)]
        過去15_新到舊 = list(reversed(過去15))
        rsi = technical.計算RSI(過去15_新到舊, 14)

        if not in_position:
            # 進場判斷
            if rsi is not None and rsi < 進場RSI閾值 \
               and (i - 上次訊號索引) > 冷卻_天:
                in_position = True
                買價 = 當日["close"]
                買日 = 當日["date"]
                買日索引 = i
                上次訊號索引 = i
                進場RSI = rsi
        else:
            # 持倉中
            漲幅 = (當日["close"] / 買價 - 1)
            天數 = i - 買日索引
            退場 = None

            # 用當日 high/low 判斷是否觸發（更貼近實盤）
            高_漲 = (當日["high"] / 買價 - 1)
            低_跌 = (當日["low"] / 買價 - 1)

            if 高_漲 >= 停利_pct:
                # 觸發停利（用停利價結算）
                退場 = "停利"
                結算價 = 買價 * (1 + 停利_pct)
                結算漲 = 停利_pct
            elif 低_跌 <= 停損_pct:
                退場 = "停損"
                結算價 = 買價 * (1 + 停損_pct)
                結算漲 = 停損_pct
            elif 天數 >= 最長持倉_天:
                退場 = "超時"
                結算價 = 當日["close"]
                結算漲 = 漲幅

            if 退場:
                交易.append({
                    "買日": 買日,
                    "賣日": 當日["date"],
                    "買價": round(買價, 2),
                    "賣價": round(結算價, 2),
                    "漲幅_pct": round(結算漲 * 100, 2),
                    "天數": 天數,
                    "退場": 退場,
                    "進場RSI": round(進場RSI, 1),
                })
                in_position = False
                買價 = None

    return 交易


# ─────────────────────────────────────────────
# 統計
# ─────────────────────────────────────────────
def 計算勝率(交易記錄: list[dict]) -> dict:
    """從交易記錄算統計指標"""
    if not 交易記錄:
        return {
            "交易數": 0, "勝率": 0,
            "平均賺_pct": 0, "平均賠_pct": 0,
            "平均持倉天": 0, "勝場": 0, "敗場": 0,
            "Kelly_pct": 0, "夏普近似": 0,
        }

    賺 = [t for t in 交易記錄 if t["漲幅_pct"] > 0]
    賠 = [t for t in 交易記錄 if t["漲幅_pct"] <= 0]

    勝率 = len(賺) / len(交易記錄)
    平均賺 = (sum(t["漲幅_pct"] for t in 賺) / len(賺)) if 賺 else 0
    平均賠 = (abs(sum(t["漲幅_pct"] for t in 賠) / len(賠))) if 賠 else 0
    平均天數 = sum(t["天數"] for t in 交易記錄) / len(交易記錄)

    # Kelly 1/8（Phase 26 修正 — 比 ARK 還保守，避免 Kelly 高估）
    # 數學上 Kelly 假設「事件獨立」，但股票漲跌會連動 → 實務再除以 2
    # 1/4 Kelly = 一般避險基金實務 / 1/8 Kelly = 散戶最安全
    if 平均賠 > 0:
        b = 平均賺 / 平均賠
        f = (b * 勝率 - (1 - 勝率)) / b
        kelly = max(0, f * 0.125 * 100)  # 1/8 Kelly，%（更保守）
        kelly = min(kelly, 12)  # 上限 12%（原 25%）
    else:
        kelly = 0

    # 夏普近似（簡化版）：平均報酬 / 報酬標準差
    所有漲 = [t["漲幅_pct"] for t in 交易記錄]
    if 所有漲:
        平均 = sum(所有漲) / len(所有漲)
        變異 = sum((x - 平均) ** 2 for x in 所有漲) / len(所有漲)
        std = 變異 ** 0.5
        夏普 = round(平均 / std, 2) if std > 0 else 0
    else:
        夏普 = 0

    return {
        "交易數": len(交易記錄),
        "勝率": round(勝率, 3),
        "平均賺_pct": round(平均賺, 2),
        "平均賠_pct": round(平均賠, 2),
        "平均持倉天": round(平均天數, 1),
        "勝場": len(賺),
        "敗場": len(賠),
        "Kelly_pct": round(kelly, 2),
        "夏普近似": 夏普,
    }


# ─────────────────────────────────────────────
# 對單檔跑回測
# ─────────────────────────────────────────────
def 模擬交易序列_順勢(歷史: list[dict],
                       進場條件: str = "ma_breakout",
                       停利_pct: float = 0.20,
                       停損_pct: float = -0.07,
                       最長持倉_天: int = 90,
                       冷卻_天: int = 21) -> list[dict]:
    """
    Phase 22.5 新增：個股「順勢突破」模式
    對 ODM、被動元件等個股不適合 RSI<35 的標的用這套：

    進場：突破 MA20 + MA20>MA60 + RSI 50-70（多頭起漲確認）
    停利：+20%（個股波動大，給更多空間）
    停損：-7%（個股容易續跌）
    冷卻：21 天（個股訊號間隔長）
    """
    if not 歷史 or len(歷史) < 100:
        return []

    時序 = list(reversed(歷史))
    n = len(時序)
    交易 = []
    in_position = False
    買價 = None
    買日索引 = None
    上次訊號索引 = -999

    for i in range(60, n):
        當日 = 時序[i]

        if not in_position and (i - 上次訊號索引) > 冷卻_天:
            # 算 MA20, MA60, RSI
            收20 = [時序[i - k]["close"] for k in range(20)]
            收60 = [時序[i - k]["close"] for k in range(60)]
            收15 = [時序[i - k]["close"] for k in range(15)]
            ma20 = sum(收20) / 20
            ma60 = sum(收60) / 60
            rsi = technical.計算RSI(list(reversed(收15)), 14)
            昨日收 = 時序[i - 1]["close"]
            今日收 = 當日["close"]

            # 進場：突破 MA20 + 多頭排列 + RSI 50-70
            if (昨日收 < ma20 and 今日收 >= ma20 and
                ma20 > ma60 and rsi is not None and 50 <= rsi <= 70):
                in_position = True
                買價 = 今日收
                買日 = 當日["date"]
                買日索引 = i
                上次訊號索引 = i
                進場RSI = rsi

        elif in_position:
            漲幅 = (當日["close"] / 買價 - 1)
            天數 = i - 買日索引
            退場 = None
            高漲 = (當日["high"] / 買價 - 1)
            低跌 = (當日["low"] / 買價 - 1)

            if 高漲 >= 停利_pct:
                退場 = "停利"
                結算 = 買價 * (1 + 停利_pct)
                結算漲 = 停利_pct
            elif 低跌 <= 停損_pct:
                退場 = "停損"
                結算 = 買價 * (1 + 停損_pct)
                結算漲 = 停損_pct
            elif 天數 >= 最長持倉_天:
                退場 = "超時"
                結算 = 當日["close"]
                結算漲 = 漲幅

            if 退場:
                交易.append({
                    "買日": 買日, "賣日": 當日["date"],
                    "買價": round(買價, 2),
                    "賣價": round(結算, 2),
                    "漲幅_pct": round(結算漲 * 100, 2),
                    "天數": 天數, "退場": 退場,
                    "進場RSI": round(進場RSI, 1),
                })
                in_position = False
                買價 = None

    return 交易


def 回測單檔_順勢(symbol: str, period: str = "5y") -> dict:
    """個股順勢模式專用回測"""
    try:
        歷史, 實際sym = technical.取得每日股價(symbol, period=period)
    except Exception as e:
        return {"symbol": symbol, "error": str(e),
                "統計": 計算勝率([])}
    if not 歷史 or len(歷史) < 100:
        return {"symbol": symbol, "error": "資料不足",
                "統計": 計算勝率([])}

    交易 = 模擬交易序列_順勢(歷史)
    統計 = 計算勝率(交易)

    return {
        "symbol": 實際sym,
        "策略": "順勢突破（MA20 + RSI 50-70）+20%/-7%",
        "資料天數": len(歷史),
        "統計": 統計,
        "交易記錄": 交易[-15:],
    }


def 回測單檔(symbol: str, period: str = "8y",
              walk_forward: bool = True,
              **策略參數) -> dict:
    """
    對單檔股票跑歷史回測，回傳完整統計。
    period: yfinance 期間（"5y"/"8y"/"10y"/"max"）
    walk_forward: True = 跑 in-sample + out-of-sample 對比（Phase 26 修正）
      避免「用同樣 5 年數據又 train 又 test」的 overfit 問題。
    """
    try:
        歷史, 實際sym = technical.取得每日股價(symbol, period=period)
    except Exception as e:
        return {
            "symbol": symbol, "error": str(e),
            "統計": 計算勝率([]),
        }

    if not 歷史 or len(歷史) < 100:
        return {
            "symbol": symbol,
            "error": f"資料不足 ({len(歷史) if 歷史 else 0} 筆)",
            "統計": 計算勝率([]),
        }

    # 全期回測
    交易_全 = 模擬交易序列(歷史, **策略參數)
    統計_全 = 計算勝率(交易_全)

    # Walk-forward 分割（前 70% in-sample / 後 30% out-of-sample）
    if walk_forward and len(歷史) >= 300:
        # 歷史是「由新到舊」排序
        split_idx = int(len(歷史) * 0.3)  # 後 30% (新資料) = out-of-sample
        in_sample = 歷史[split_idx:]   # 舊 70%
        out_sample = 歷史[:split_idx]  # 新 30%
        交易_IS = 模擬交易序列(in_sample, **策略參數)
        交易_OOS = 模擬交易序列(out_sample, **策略參數)
        統計_IS = 計算勝率(交易_IS)
        統計_OOS = 計算勝率(交易_OOS)
        WF驗證 = {
            "in_sample": 統計_IS,
            "out_of_sample": 統計_OOS,
            "勝率落差_pct": round(統計_OOS["勝率"] * 100 - 統計_IS["勝率"] * 100, 1),
            "可靠性": (
                "高" if abs(統計_OOS["勝率"] - 統計_IS["勝率"]) < 0.10
                else "中" if abs(統計_OOS["勝率"] - 統計_IS["勝率"]) < 0.20
                else "低（可能 overfit）"
            ),
        }
    else:
        WF驗證 = None

    起 = 歷史[-1]["date"] if 歷史 else None
    迄 = 歷史[0]["date"] if 歷史 else None

    return {
        "symbol": 實際sym,
        "資料期間": f"{起} ~ {迄}",
        "資料天數": len(歷史),
        "策略": {
            "進場RSI閾值": 策略參數.get("進場RSI閾值", 35),
            "停利_pct": 策略參數.get("停利_pct", 0.15),
            "停損_pct": 策略參數.get("停損_pct", -0.05),
            "最長持倉_天": 策略參數.get("最長持倉_天", 60),
        },
        "統計": 統計_全,
        "WalkForward": WF驗證,
        "交易記錄": 交易_全[-20:],
    }


# ─────────────────────────────────────────────
# 跑全部 watchlist + 持股
# ─────────────────────────────────────────────
def 跑全部watchlist(period: str = "8y",
                     限制檔數: Optional[int] = None,
                     僅這些: Optional[list] = None) -> dict:
    """
    跑 watchlist + 用戶持股，存到 win_rate_db.json
    限制檔數: 測試用，只跑前 N 檔
    僅這些: 只跑指定 symbol list（如 ['0050.TW', 'NVDA']）
    """
    from . import capital_planner

    cfg_w = technical.載入觀察清單()
    cfg_p = capital_planner.載入資金設定()

    # 收集要回測的標的
    標的清單 = []
    for r in cfg_w.get("regions", []):
        for s in r.get("stocks", []):
            標的清單.append({"symbol": s["symbol"], "name": s.get("name", "")})

    # 加上 portfolio
    for p in cfg_p.get("current_positions", []):
        if p.get("symbol") == "AGGREGATE":
            continue
        sym = p["symbol"]
        if not any(x["symbol"] == sym for x in 標的清單):
            標的清單.append({"symbol": sym, "name": p.get("name", "")})

    # 篩選
    if 僅這些:
        標的清單 = [x for x in 標的清單 if x["symbol"] in 僅這些]
    if 限制檔數:
        標的清單 = 標的清單[:限制檔數]

    print(f"準備回測 {len(標的清單)} 檔 / 期間 {period}")
    print(f"預估時間：{len(標的清單) * 2} 秒（每檔 ~2 秒）")

    結果 = {}
    成功 = 0
    失敗 = 0
    for i, x in enumerate(標的清單, 1):
        sym = x["symbol"]
        print(f"  [{i}/{len(標的清單)}] {sym} {x['name'][:10]:<10} ...",
              end="", flush=True)
        try:
            r = 回測單檔(sym, period=period)
        except Exception as e:
            r = {"symbol": sym, "error": f"crash:{e}", "統計": 計算勝率([])}
        try:
            if "error" in r:
                print(f" [X] {r['error']}")
                失敗 += 1
            else:
                stats = r["統計"]
                print(f" 交易 {stats['交易數']:>3} 勝 {stats['勝率']*100:>4.1f}% "
                      f"賺 {stats['平均賺_pct']:>5.2f}% 賠 -{stats['平均賠_pct']:>4.2f}% "
                      f"Kelly {stats['Kelly_pct']:>5.2f}%")
                成功 += 1
        except UnicodeEncodeError:
            print(" (encoding skip)")
            if "error" not in r:
                成功 += 1
            else:
                失敗 += 1
        結果[sym] = {**r, "name": x["name"]}
        # 不要請求太快（yfinance 嚴格限流）
        time.sleep(1.0)

    # 存檔
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "策略": "RSI<35 進場 / +15% 停利 / -5% 停損 / 60d 超時",
        "期間": period,
        "成功檔數": 成功,
        "失敗檔數": 失敗,
        "標的": 結果,
    }
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已存到 {DB_PATH}")
    print(f"   成功 {成功} 檔 / 失敗 {失敗} 檔")
    return payload


# ─────────────────────────────────────────────
# 載入給 position_sizer 用
# ─────────────────────────────────────────────
def 載入勝率資料庫() -> dict:
    """
    給 position_sizer 用。
    回傳：{symbol: {勝率, 平均賺_pct, 平均賠_pct, Kelly_pct}, ...}
    """
    if not DB_PATH.exists():
        return {}
    try:
        data = json.loads(DB_PATH.read_text(encoding="utf-8"))
        out = {}
        for sym, r in data.get("標的", {}).items():
            if "error" in r:
                continue
            s = r.get("統計", {})
            if s.get("交易數", 0) < 5:  # 樣本太少不採用
                continue
            out[sym] = {
                "勝率": s["勝率"],
                "平均賺_pct": s["平均賺_pct"],
                "平均賠_pct": s["平均賠_pct"],
                "Kelly_pct": s["Kelly_pct"],
                "交易數": s["交易數"],
                "夏普近似": s["夏普近似"],
            }
        return out
    except Exception as e:
        print(f"載入勝率 DB 失敗：{e}")
        return {}


# ─────────────────────────────────────────────
# CLI 自測
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=== Phase 18：個股勝率引擎自測 ===\n")

    # 先單檔測試
    print("--- 測 0050 8 年 ---")
    r = 回測單檔("0050.TW", period="8y")
    print(json.dumps(r["統計"], ensure_ascii=False, indent=2))
    print()

    print("--- 測 中信金 2891 8 年 ---")
    r = 回測單檔("2891.TW", period="8y")
    print(json.dumps(r["統計"], ensure_ascii=False, indent=2))
    print()

    print("--- 測 NVDA 8 年 ---")
    r = 回測單檔("NVDA", period="8y")
    print(json.dumps(r["統計"], ensure_ascii=False, indent=2))
