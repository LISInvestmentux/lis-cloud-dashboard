"""
位階分數監測（Phase 12 — ARK 思路移植 / Phase 16 ETF 順勢升級）
給 watchlist 每檔 0-100 分位階分數：

分數越低 = 越接近「價值區」（建議買）
分數越高 = 越接近「超漲區」（建議賣）

5 維加權算分：
  RSI            30 分（RSI 0=0分 / RSI 100=30分）
  MA50 距離      25 分（收盤超 MA50 越多越熱）
  20 日漲幅      20 分（漲多越熱）
  震盪位置       15 分（在區間上半=熱）
  量能           10 分（量爆=熱）

判讀（個股）：
  < 25  深價值區 🟢 強烈買進
  25-45 進入價值區 🟢 建議買
  45-65 中性 ⚪
  65-85 離開價值區 🟡 建議賣
  > 85  超漲區 🔴 強烈賣

▶ Phase 16 ETF 順勢升級：
  ETF 多頭趨勢中 LIS 太保守導致漏訊號。
  新增「順勢分數」（0-100），ETF 套不同判讀：
    - 抄底買 (位階 <45)         → 跟原邏輯
    - 順勢加碼 (順勢分 >=60)   → 新增訊號（多頭中可加）
    - 中性                      → 觀望
    - 真過熱 (位階 >85 或 RSI>80) → PASS

狀態追蹤：對比昨天（讀寫 數據/positional_state.json）：
  昨 > 50 → 今 < 50：今日「進入價值區」（新買進訊號）
  昨 < 50 → 今 > 50：今日「離開價值區」（賣出訊號）
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
狀態檔 = 專案根 / "數據" / "positional_state.json"


# ─────────────────────────────────────────────
# 位階分數計算
# ─────────────────────────────────────────────
def 計算位階分數(個股: dict) -> Optional[float]:
    """
    對單筆個股 record 算 0-100 位階分數。
    需要欄位：rsi14, close, ma50, 漲幅_20日_pct, shakeout_position, 量爆倍數
    缺資料的維度跳過（剩餘維度按比例放大）
    """
    維度 = []   # (分數, 權重)

    # 1. RSI 30 分
    rsi = 個股.get("rsi14")
    if rsi is not None:
        rsi_分 = min(30, max(0, rsi / 100 * 30))
        維度.append((rsi_分, 30))

    # 2. MA50 距離 25 分
    close = 個股.get("close")
    ma50 = 個股.get("ma50")
    if close and ma50 and ma50 > 0:
        距離_pct = (close - ma50) / ma50 * 100   # 例：close 比 MA50 高 15% → +15
        # +30% 以上 = 25 分（過熱）；-20% 以下 = 0 分（深價值區）
        ma_分 = max(0, min(25, (距離_pct + 20) / 50 * 25))
        維度.append((ma_分, 25))

    # 3. 20 日漲幅 20 分
    漲20 = 個股.get("漲幅_20日_pct")
    if 漲20 is not None:
        # +20% 以上 = 20 分；-15% 以下 = 0 分
        漲_分 = max(0, min(20, (漲20 + 15) / 35 * 20))
        維度.append((漲_分, 20))

    # 4. 震盪位置 15 分
    位置 = 個股.get("shakeout_position")   # 0-1
    if 位置 is not None:
        位置_分 = 位置 * 15
        維度.append((位置_分, 15))

    # 5. 量能 10 分
    量爆 = 個股.get("量爆倍數")
    if 量爆 is not None:
        # 量爆 1x = 5 分（中性）；3x+ = 10 分；0.5x = 0 分
        量_分 = max(0, min(10, (量爆 - 0.5) / 2.5 * 10))
        維度.append((量_分, 10))

    if not 維度:
        return None

    # 按比例放大（缺欄位的時候）
    總分 = sum(分 for 分, _ in 維度)
    總權重 = sum(權 for _, 權 in 維度)
    if 總權重 == 0:
        return None
    # normalize 回 100 分制
    return round(總分 / 總權重 * 100, 1)


def 判讀(分數: Optional[float]) -> dict:
    """位階分數 → 文字判讀 + emoji + 顏色 + 動作建議（個股用）"""
    if 分數 is None:
        return {"區": "資料不足", "emoji": "❓", "色": "subtle",
                "動作": "n/a"}
    if 分數 < 25:
        return {"區": "深價值區", "emoji": "🟢", "色": "bull",
                "動作": "強烈買進"}
    if 分數 < 45:
        return {"區": "進入價值區", "emoji": "🟢", "色": "bull",
                "動作": "建議買進"}
    if 分數 < 65:
        return {"區": "中性", "emoji": "⚪", "色": "main",
                "動作": "觀望"}
    if 分數 < 85:
        return {"區": "離開價值區", "emoji": "🟡", "色": "wait",
                "動作": "建議賣出"}
    return {"區": "超漲區", "emoji": "🔴", "色": "bear",
            "動作": "強烈賣出"}


# ─────────────────────────────────────────────
# Phase 16: ETF 順勢加碼模式
# ─────────────────────────────────────────────
def 是否為ETF(symbol: str) -> bool:
    """偵測台股 ETF（00xxx 開頭）+ 美股常見 ETF。"""
    s = (symbol or "").upper().strip()
    # 台股 ETF: 0050, 00xxx
    if s.startswith("00") or s == "0050.TW":
        return True
    if s.startswith("00") and (s.endswith(".TW") or s.endswith(".TWO")):
        return True
    # 美股大盤/類股 ETF（白名單）
    if s in {"VOO", "QQQ", "QQQX", "SPY", "VTI", "DIA", "IWM",
             "ARKK", "ARKW", "ARKG", "ARKF", "ARKQ", "ARKX",
             "SMH", "SOXX", "XLK", "XLF", "XLE", "XLV"}:
        return True
    return False


def 計算順勢分數(個股: dict) -> Optional[float]:
    """
    Phase 16 新增：ETF 順勢強度 0-100。
    高 = 趨勢健康、可順勢加碼
    低 = 趨勢未啟動或已破壞

    維度：
      MA20 站上 + 多頭排列 30 分
      20 日漲幅 0-25% 健康區間 20 分
      RSI 50-75 強勢但未過熱 20 分
      量能正常（0.7-1.5x） 10 分
      未在 60 日高點最後 3% 20 分（避免追頂）
    """
    維度 = []   # (分數, 權重)

    # 1. MA 多頭排列 30 分
    close = 個股.get("close")
    ma20 = 個股.get("ma20")
    ma60 = 個股.get("ma60") or 個股.get("ma50")
    if close and ma20:
        分 = 0
        if close > ma20:
            分 += 15
        if ma60 and ma20 > ma60:
            分 += 15
        elif ma60 and ma20 >= ma60 * 0.99:  # 接近交叉
            分 += 10
        維度.append((分, 30))

    # 2. 20 日漲幅 0-25% 健康 20 分
    漲20 = 個股.get("漲幅_20日_pct")
    if 漲20 is not None:
        if 漲20 < -5:
            分 = 5      # 跌深 → 非順勢
        elif 漲20 < 0:
            分 = 8
        elif 漲20 <= 10:
            分 = 20     # 健康上漲
        elif 漲20 <= 25:
            分 = 16     # 略強
        elif 漲20 <= 40:
            分 = 8      # 過熱
        else:
            分 = 0      # 超漲
        維度.append((分, 20))

    # 3. RSI 50-75 健康強勢 20 分
    rsi = 個股.get("rsi14")
    if rsi is not None:
        if 30 <= rsi < 50:
            分 = 8
        elif 50 <= rsi <= 75:
            分 = 20
        elif 75 < rsi <= 80:
            分 = 12
        elif rsi > 80:
            分 = 0     # 真過熱
        else:
            分 = 5
        維度.append((分, 20))

    # 4. 量能正常 10 分
    量爆 = 個股.get("量爆倍數")
    if 量爆 is not None:
        if 0.7 <= 量爆 <= 2.0:
            分 = 10
        elif 量爆 > 3.0:
            分 = 3    # 爆量 → 警訊
        elif 量爆 < 0.5:
            分 = 4    # 量縮 → 沒人氣
        else:
            分 = 7
        維度.append((分, 10))

    # 5. 不在最高點最後 3% 20 分
    位置 = 個股.get("shakeout_position")  # 0-1
    if 位置 is not None:
        if 位置 < 0.85:
            分 = 20
        elif 位置 < 0.95:
            分 = 12
        else:
            分 = 0   # 在最高點附近 → 追頂
        維度.append((分, 20))

    if not 維度:
        return None
    總分 = sum(分 for 分, _ in 維度)
    總權重 = sum(權 for _, 權 in 維度)
    if 總權重 == 0:
        return None
    return round(總分 / 總權重 * 100, 1)


def 判讀_ETF(位階分數: Optional[float],
              順勢分數: Optional[float],
              rsi: Optional[float] = None) -> dict:
    """
    Phase 16：ETF 專用判讀（區分 抄底 / 順勢 / 中性 / 過熱）。

    優先順序：
      1. 真過熱（RSI > 80 或位階 > 85） → 強烈賣出
      2. 深抄底（位階 < 25）            → 強烈買進
      3. 抄底買（位階 < 45）            → 建議買進
      4. 順勢加碼（順勢分 >= 60）      → ✨ 新訊號
      5. 中性                          → 觀望
    """
    if 位階分數 is None:
        return {"區": "資料不足", "emoji": "❓", "色": "subtle",
                "動作": "n/a", "型態": "未知"}

    # 真過熱
    if (rsi is not None and rsi > 80) or 位階分數 > 85:
        return {"區": "超漲區", "emoji": "🔴", "色": "bear",
                "動作": "強烈賣出", "型態": "過熱_別追"}

    # 深抄底
    if 位階分數 < 25:
        return {"區": "深價值區", "emoji": "🟢", "色": "bull",
                "動作": "強烈買進", "型態": "抄底"}

    # 抄底買
    if 位階分數 < 45:
        return {"區": "進入價值區", "emoji": "🟢", "色": "bull",
                "動作": "建議買進", "型態": "抄底"}

    # 順勢加碼（Phase 16 新增 — 解決多頭時 LIS 太保守）
    if 順勢分數 is not None and 順勢分數 >= 60:
        return {"區": "順勢加碼區", "emoji": "🚀", "色": "bull",
                "動作": "順勢加碼", "型態": "順勢"}

    # 中性
    if 位階分數 < 65:
        return {"區": "中性", "emoji": "⚪", "色": "main",
                "動作": "觀望", "型態": "中性"}

    # 脫離但未過熱 — 不下重判
    return {"區": "脫離價值區", "emoji": "🟡", "色": "wait",
            "動作": "順勢轉弱 觀望", "型態": "轉弱"}


# ─────────────────────────────────────────────
# 狀態追蹤
# ─────────────────────────────────────────────
def _載入昨日狀態() -> dict:
    if not 狀態檔.exists():
        return {}
    try:
        with open(狀態檔, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _儲存今日狀態(分數表: dict, 詳細表: Optional[dict] = None) -> None:
    狀態檔.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "scores": 分數表,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if 詳細表:
        # Phase 16: 也存順勢分 + 型態，給 instant_decision 用
        payload["details"] = 詳細表
    with open(狀態檔, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _跨越50(昨: Optional[float], 今: float) -> Optional[str]:
    """偵測 50 分線跨越（進入/離開價值區的關鍵閾值）。"""
    if 昨 is None:
        return None
    if 昨 >= 50 > 今:
        return "進入"   # 從中性以上掉到價值區
    if 昨 < 50 <= 今:
        return "離開"
    return None


# ─────────────────────────────────────────────
# 主整合
# ─────────────────────────────────────────────
def 掃描位階(全部個股: list[dict],
              寫入狀態檔: bool = True) -> dict:
    """
    全部個股: main.py 的 _合併個股() 結果
    回傳：{
      "今日_進入價值區": [{symbol, name, 昨分, 今分, ...}],
      "今日_離開價值區": [...],
      "深價值區": [...],   # 持續 < 25
      "超漲區": [...],     # 持續 > 85
      "所有": [{symbol, name, 分數, 區, ...}],
      "統計": {深價值: x, 進入價值: y, 中性: z, 離開價值: a, 超漲: b},
    }
    """
    昨日狀態 = _載入昨日狀態()
    昨日分數 = 昨日狀態.get("scores", {})

    今日分數表 = {}
    今日進入 = []
    今日離開 = []
    深價值區 = []
    超漲區 = []
    順勢_ETF = []   # Phase 16: ETF 順勢加碼候選
    所有 = []
    統計 = {"深價值區": 0, "進入價值區": 0, "中性": 0,
              "離開價值區": 0, "超漲區": 0, "資料不足": 0,
              "順勢加碼區": 0, "脫離價值區": 0}

    for r in 全部個股:
        if "error" in r:
            continue
        sym = r.get("symbol")
        if not sym:
            continue
        分 = 計算位階分數(r)

        # Phase 16: ETF 套新判讀
        是ETF = 是否為ETF(sym)
        if 是ETF:
            順勢分 = 計算順勢分數(r)
            判 = 判讀_ETF(分, 順勢分, r.get("rsi14"))
        else:
            順勢分 = None
            判 = 判讀(分)

        統計[判["區"]] = 統計.get(判["區"], 0) + 1
        if 分 is None:
            continue

        今日分數表[sym] = 分

        昨分 = 昨日分數.get(sym)
        跨越 = _跨越50(昨分, 分)

        rec = {
            "symbol": sym,
            "name": r.get("name", ""),
            "close": r.get("close"),
            "分數": 分,
            "區": 判["區"],
            "emoji": 判["emoji"],
            "動作": 判["動作"],
            "昨分": 昨分,
            "變化": (round(分 - 昨分, 1) if 昨分 is not None else None),
            "跨越": 跨越,
            "是ETF": 是ETF,
            "順勢分": 順勢分,
            "型態": 判.get("型態", "中性"),
        }
        所有.append(rec)

        if 跨越 == "進入":
            今日進入.append(rec)
        elif 跨越 == "離開":
            今日離開.append(rec)

        if 分 < 25:
            深價值區.append(rec)
        elif 分 > 85:
            超漲區.append(rec)

        # Phase 16: 順勢 ETF 候選（多頭中可加碼）
        if 是ETF and 判.get("型態") == "順勢":
            順勢_ETF.append(rec)

    # 排序
    今日進入.sort(key=lambda r: r["分數"])   # 最低分（最深價值）在前
    今日離開.sort(key=lambda r: -r["分數"])  # 最高分（最超漲）在前
    深價值區.sort(key=lambda r: r["分數"])
    超漲區.sort(key=lambda r: -r["分數"])
    順勢_ETF.sort(key=lambda r: -(r.get("順勢分") or 0))  # 順勢最強在前
    所有.sort(key=lambda r: r["分數"])      # 整體由低到高（價值排前）

    if 寫入狀態檔:
        # Phase 16: 額外存順勢分 + 型態 + 是否ETF，給 instant_decision 用
        詳細 = {}
        for rec in 所有:
            sym = rec["symbol"]
            詳細[sym] = {
                "順勢分": rec.get("順勢分"),
                "型態": rec.get("型態"),
                "是ETF": rec.get("是ETF", False),
                "動作": rec.get("動作"),
            }
        _儲存今日狀態(今日分數表, 詳細表=詳細)

    return {
        "今日_進入價值區": 今日進入,
        "今日_離開價值區": 今日離開,
        "深價值區": 深價值區,
        "超漲區": 超漲區,
        "順勢加碼_ETF": 順勢_ETF,
        "所有": 所有,
        "統計": 統計,
        "總檔數": sum(統計.values()),
        "有昨日數據": bool(昨日分數),
    }
