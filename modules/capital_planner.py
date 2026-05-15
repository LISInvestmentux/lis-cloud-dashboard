"""
資金規劃模組
依據 portfolio.json 的資金水位 + Enjoy Index 建議，
算出「每檔股票可投多少 / 可買多少股」。

核心邏輯（藍圖第二章）：
1. 永遠留 35% 現金子彈（min_cash_reserve_pct）
2. 單一股票上限 20% 總資金
3. 依 Enjoy Index 決定要動用多少火力：
   - BE HAPPY (≥70): 70% 火力 → 主動加碼
   - WAIT (40-69):  30% 火力 → 中性
   - HOLD  (<40):   10% 火力 → **主動減碼**（Phase 6.0 修正）

Phase 6.0：HOLD 不只「降低買進火力」，還會：
  - 掃使用者 current_positions 找漲幅 +10% 以上的部位
  - 建議減碼比例（單筆 +10~20% 減 1/3、+20% 以上減 1/2）
  - 入袋為安，拉高現金水位等下一波恐慌進場
"""
import json
import re
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────
# Phase 6.0：代號規範化（給 portfolio.json 各種格式相容）
# ─────────────────────────────────────────────
def 規範化代號(原始: str) -> str:
    """
    台股代號自動補 .TW：
      '0050'    → '0050.TW'
      '00631L'  → '00631L.TW'
      '2330'    → '2330.TW'
      '2330.TW' → '2330.TW'（不變）
      'TSLA'    → 'TSLA'（不變，美股）
    """
    s = (原始 or "").strip().upper()
    if not s:
        return ""
    if s.endswith(".TW") or s.endswith(".TWO"):
        return s
    if s.isalpha():
        return s
    if re.match(r"^\d", s):
        return s + ".TW"
    return s


專案根 = Path(__file__).resolve().parent.parent.parent
PORTFOLIO_PATH = 專案根 / "API" / "portfolio.json"


def 載入資金設定() -> dict:
    with open(PORTFOLIO_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def 取得部署比例(enjoy_index_score: float, 設定: dict,
                  fire_modifier: Optional[dict] = None) -> dict:
    """
    依 Enjoy Index 算出今天可動用的火力比例 + 主動操作建議。
    Phase 6.0: 主動操作標記。
    Phase 9: fire_modifier 依生命週期階段調整火力比例。
    """
    d = 設定["deployment_by_enjoy_index"]
    fm = fire_modifier or {}

    if enjoy_index_score >= d["be_happy_min_score"]:
        基準 = d["be_happy_deploy_pct"]
        調整 = fm.get("be_happy_modifier", 0)
        return {"建議": "BE HAPPY",
                "火力比例": max(0, min(100, 基準 + 調整)),
                "原始火力": 基準,
                "FIRE調整": 調整,
                "主動操作": "BUY_MORE"}
    if enjoy_index_score >= d["wait_min_score"]:
        基準 = d["wait_deploy_pct"]
        調整 = fm.get("wait_modifier", 0)
        return {"建議": "WAIT",
                "火力比例": max(0, min(100, 基準 + 調整)),
                "原始火力": 基準,
                "FIRE調整": 調整,
                "主動操作": "NEUTRAL"}
    # HOLD：Phase 6.0 修正 — 主動減碼，不是被動暫緩
    基準 = d["hold_deploy_pct"]
    調整 = fm.get("hold_modifier", 0)
    return {"建議": "HOLD",
            "火力比例": max(0, min(100, 基準 + 調整)),
            "原始火力": 基準,
            "FIRE調整": 調整,
            "主動操作": "SELL_TAKE"}


def 計算今日資金規劃(enjoy_index_score: float, 設定: dict = None,
                       fire_modifier: Optional[dict] = None) -> dict:
    """
    回傳今日可動用的子彈與每檔上限。
    Phase 9: fire_modifier 由 fire_calculator.判斷生命週期階段() 提供。
    """
    設定 = 設定 or 載入資金設定()
    # Phase 9：若 fire_modifier 啟用，套用調整
    fm_啟用 = 設定.get("fire_modifier", {}).get("啟用", False)
    部署 = 取得部署比例(enjoy_index_score, 設定,
                        fire_modifier=fire_modifier if fm_啟用 else None)

    股票配置 = 設定["stock_allocation_twd"]
    現金 = 設定["current_cash_twd"]
    最小現金保留 = 設定["total_capital_twd"] * 設定["risk_rules"]["min_cash_reserve_pct"] / 100

    # 今日可動用 = min(火力比例 × 股票配置, 現金 − 最小現金保留)
    火力上限 = 股票配置 * 部署["火力比例"] / 100
    現金上限 = max(0, 現金 - 最小現金保留)
    今日子彈 = min(火力上限, 現金上限)

    # 單檔上限
    單檔上限 = 設定["total_capital_twd"] * 設定["risk_rules"]["max_per_stock_pct"] / 100

    return {
        "建議": 部署["建議"],
        "火力比例": 部署["火力比例"],
        "原始火力": 部署.get("原始火力", 部署["火力比例"]),
        "FIRE調整": 部署.get("FIRE調整", 0),
        "主動操作": 部署["主動操作"],   # Phase 6.0：BUY_MORE / NEUTRAL / SELL_TAKE
        "股票配置": 股票配置,
        "目前現金": 現金,
        "最小現金保留": 最小現金保留,
        "火力上限_twd": round(火力上限, 0),
        "現金上限_twd": round(現金上限, 0),
        "今日可動用子彈_twd": round(今日子彈, 0),
        "單檔上限_twd": round(單檔上限, 0),
        "USD_TWD": 設定["currency_rates"]["USD_TWD"],
    }


# ─────────────────────────────────────────────
# Phase 6.0：HOLD 時的減碼建議
# ─────────────────────────────────────────────
def 計算減碼建議(主動操作: str, 個股分析清單: list[dict],
                  設定: Optional[dict] = None) -> dict:
    """
    當系統建議 SELL_TAKE 時，掃使用者持股找該減碼的標的。

    減碼門檻（含摩擦後仍正報酬才減）：
      +10~20%：減 1/3
      +20~30%：減 1/2
      +30% 以上：減 2/3
      < +10%：不減（成本未抓到、漲幅不夠都不建議減）

    需要 portfolio.json 的 current_positions 有個股明細
    （symbol / shares / avg_cost）才能比對。
    若只有 AGGREGATE 彙總，回傳「無法計算」訊息。

    個股分析清單: technical 掃描結果（用來查當前股價）

    回傳：{
        "可執行": bool,
        "原因": str,
        "減碼建議": [{symbol, name, shares, avg_cost, current_price,
                       pnl_pct, 建議減倉比例, 建議減股數}, ...]
    }
    """
    if 主動操作 != "SELL_TAKE":
        return {"可執行": False, "原因": "Enjoy Index 未觸發減碼條件",
                "減碼建議": []}

    設定 = 設定 or 載入資金設定()
    持股 = 設定.get("current_positions", [])

    # 過濾掉 AGGREGATE 彙總（沒有實際個股明細）
    實際持股 = [p for p in 持股 if p.get("symbol") != "AGGREGATE"]
    if not 實際持股:
        return {"可執行": False,
                "原因": "portfolio.json 只有 AGGREGATE 彙總，請補個股明細（symbol/shares/avg_cost）才能算減碼",
                "減碼建議": []}

    # 建 symbol → 當前股價（兩個版本都建索引，相容純代號 + .TW 後綴）
    分析索引 = {}
    for r in 個股分析清單:
        if "error" in r:
            continue
        sym = r.get("symbol", "")
        if sym:
            分析索引[sym] = r
            # 也建純代號 fallback（去掉 .TW）
            純 = sym.replace(".TW", "").replace(".TWO", "")
            if 純 != sym:
                分析索引.setdefault(純, r)

    建議清單 = []
    for p in 實際持股:
        原sym = p["symbol"]
        sym = 規範化代號(原sym)
        avg_cost = p.get("avg_cost")
        shares = p.get("shares")
        if not avg_cost or not shares:
            continue

        # 先試 normalized 再試原始（相容舊資料）
        分析 = 分析索引.get(sym) or 分析索引.get(原sym)
        if not 分析:
            # Fallback：watchlist 沒有，直接抓 yfinance 補
            try:
                try:
                    from . import technical
                except ImportError:
                    import technical
                每日, _ = technical.取得每日股價(sym, period="5d")
                if 每日:
                    分析 = {
                        "symbol": sym,
                        "name": p.get("name", ""),
                        "close": 每日[0]["close"],
                        "_from_fallback": True,
                    }
            except Exception:
                分析 = None

        if not 分析:
            建議清單.append({
                "symbol": sym,
                "name": p.get("name", ""),
                "shares": shares,
                "avg_cost": avg_cost,
                "建議": "無法評估（抓不到股價）",
                "not_in_watchlist": True,
            })
            continue

        現價 = 分析.get("close")
        if not 現價:
            continue

        漲幅 = (現價 - avg_cost) / avg_cost * 100

        if 漲幅 < 10:
            continue  # 漲幅不夠不建議減

        if 漲幅 < 20:
            減倉比例, 標籤 = 1/3, "減 1/3"
        elif 漲幅 < 30:
            減倉比例, 標籤 = 1/2, "減 1/2"
        else:
            減倉比例, 標籤 = 2/3, "減 2/3"

        減股數 = int(shares * 減倉比例)
        if 減股數 < 1:
            continue

        建議清單.append({
            "symbol": sym,
            "name": p.get("name") or 分析.get("name", ""),
            "shares": shares,
            "avg_cost": avg_cost,
            "current_price": 現價,
            "pnl_pct": round(漲幅, 1),
            "建議減倉比例": round(減倉比例 * 100, 0),
            "建議減股數": 減股數,
            "標籤": 標籤,
            "估入袋_twd": round(減股數 * 現價, 0),
        })

    # 按 pnl_pct 由高到低排（最賺的先減）
    建議清單.sort(key=lambda r: r.get("pnl_pct", 0), reverse=True)

    return {
        "可執行": True,
        "原因": f"Enjoy < 40 + 找到 {len(建議清單)} 檔達減碼門檻",
        "減碼建議": 建議清單,
    }


def 計算建議股數(symbol: str, 股價: float, 預算_twd: float,
                  USD_TWD: float = 32.0) -> dict:
    """
    根據預算（TWD）和股價算出可買股數。
    台股：張(1000) + 零股；美股：整股。
    """
    if 股價 is None or 股價 <= 0:
        return {"可買股數": 0, "實際金額_twd": 0, "註記": "無股價"}

    是台股 = symbol.endswith(".TW") or symbol.endswith(".TWO")

    if 是台股:
        股數 = int(預算_twd / 股價)
        張 = 股數 // 1000
        零股 = 股數 % 1000
        if 張 > 0 and 零股 > 0:
            註記 = f"{張} 張 + {零股} 股"
        elif 張 > 0:
            註記 = f"{張} 張"
        else:
            註記 = f"{零股} 股 (零股)"
        實際金額 = round(股數 * 股價, 0)
    else:
        # 美股股價 USD → 換算 TWD 預算
        股價_twd = 股價 * USD_TWD
        股數 = int(預算_twd / 股價_twd)
        註記 = f"{股數} 股"
        實際金額 = round(股數 * 股價_twd, 0)

    return {
        "可買股數": 股數,
        "實際金額_twd": 實際金額,
        "註記": 註記,
    }


def 取得當前部位金額(設定: dict = None) -> dict:
    """回傳當前持股 by symbol。"""
    設定 = 設定 or 載入資金設定()
    return {p["symbol"]: p for p in 設定.get("current_positions", [])}


# ─────────────────────────────────────────────
# 格式化（給 LINE 訊息用）
# ─────────────────────────────────────────────
def 格式化資金摘要(規劃: dict) -> str:
    return (
        f"💰 今日資金規劃\n"
        f"   建議：{規劃['建議']}（{規劃['火力比例']}% 火力）\n"
        f"   可動用子彈：NT$ {規劃['今日可動用子彈_twd']:,.0f}\n"
        f"   單檔上限：NT$ {規劃['單檔上限_twd']:,.0f}"
    )
