"""
摩擦成本計算（Phase 8.0）
模擬實戰中三大成本：
  1. 滑價 Slippage     — 約 0.15%（買 +0.15%、賣 -0.15%）
  2. 手續費            — 0.1425% × 國泰電子下單 6 折 = 0.0855%（買賣各收一次）
  3. 證交稅            — 0.3%（只有賣的時候收，買不收）
  美股暫不收稅，僅扣手續費 + 滑價（之後可擴充）

預設假設你用「國泰證券電子下單一般戶」。若你拿到更好折扣，
改下面 HANDLING_FEE_RATE 即可。

Phase 8.0a 新增：可成交性檢查（Tradeability）
  - 開盤即跳空漲停 → 不可成交（一般散戶買不到）
  - 開盤即跳空跌停 → 滑價加倍（流動性枯竭）
  - 處置股清單比對 → 待 L2 接證交所 API
"""
from typing import Literal, Optional


# ─────────────────────────────────────────────
# 全域參數（可調）
# ─────────────────────────────────────────────
SLIPPAGE_RATE = 0.0015          # 滑價 0.15%（買進 +、賣出 -）
HANDLING_FEE_BASE = 0.001425    # 手續費基準 0.1425%
HANDLING_FEE_DISCOUNT = 0.60    # 國泰電子下單 6 折
TW_TAX_RATE = 0.003             # 台股證交稅 0.3%（只賣方收）
MIN_HANDLING_FEE_TWD = 20       # 國泰最低手續費 20 元（台股慣例）

# 美股摩擦（國泰複委託網路單實際費率，2026/12/31 前優惠）
US_SLIPPAGE_RATE = 0.0010        # 美股流動性好，滑價 0.1%
US_HANDLING_FEE_RATE = 0.0008    # 國泰網路單 0.08%（個股）
US_MIN_FEE_USD = 0               # 網路單免最低手續費 ⭐
US_ETF_FLAT_FEE_USD = 3.0        # ETF 每筆 $3 USD 固定
US_DCA_FLAT_FEE_USD = 0.1        # 定期定額 $0.1 USD/筆 神級
US_SEC_FEE_RATE = 0.00002        # SEC fee 0.00206%（賣出時收）

# 漲跌停（台股）
TW_LIMIT_UP_RATE = 0.10         # 漲跌停 ±10%
TW_LIMIT_THRESHOLD = 0.095      # 開盤達前收 +9.5% 視同跳空漲停
PENALTY_SLIPPAGE_RATE = 0.005   # 跳空跌停的處罰滑價（一般 0.15% → 0.5%）


# ─────────────────────────────────────────────
# 核心：算實際手續費（不含稅，不含滑價）
# ─────────────────────────────────────────────
def 實際手續費率() -> float:
    """國泰電子下單實際手續費率（一個方向 = 買或賣其中一次）。"""
    return HANDLING_FEE_BASE * HANDLING_FEE_DISCOUNT


# ─────────────────────────────────────────────
# 台股：算買進實際付出
# ─────────────────────────────────────────────
def 台股_買進成本(訊號價: float, 股數: int) -> dict:
    """
    回傳買進相關數字：
      assumed_exec_price: 加滑價後的成交價
      handling_fee:       手續費（元）
      total_paid:         你戶頭實際扣款
    """
    成交價 = 訊號價 * (1 + SLIPPAGE_RATE)
    毛額 = 成交價 * 股數
    手續費 = max(毛額 * 實際手續費率(), MIN_HANDLING_FEE_TWD)
    總付 = 毛額 + 手續費
    return {
        "assumed_exec_price": round(成交價, 2),
        "gross": round(毛額, 0),
        "handling_fee": round(手續費, 0),
        "total_paid": round(總付, 0),
    }


# ─────────────────────────────────────────────
# 台股：算賣出實際收回
# ─────────────────────────────────────────────
def 台股_賣出收回(訊號價: float, 股數: int) -> dict:
    """
    回傳賣出相關數字：
      assumed_exec_price: 減滑價後的成交價
      handling_fee:       手續費（元）
      tax:                證交稅（元）
      total_received:     你戶頭實際入帳
    """
    成交價 = 訊號價 * (1 - SLIPPAGE_RATE)
    毛額 = 成交價 * 股數
    手續費 = max(毛額 * 實際手續費率(), MIN_HANDLING_FEE_TWD)
    稅 = 毛額 * TW_TAX_RATE
    淨收 = 毛額 - 手續費 - 稅
    return {
        "assumed_exec_price": round(成交價, 2),
        "gross": round(毛額, 0),
        "handling_fee": round(手續費, 0),
        "tax": round(稅, 0),
        "total_received": round(淨收, 0),
    }


# ─────────────────────────────────────────────
# 美股：算買進實際付出（複委託，USD）
# ─────────────────────────────────────────────
def 美股_買進成本(訊號價: float, 股數: int,
                  方案: str = "個股網路單") -> dict:
    """
    美股複委託買進，回傳 USD 金額。
    方案：'個股網路單' (0.08% 無最低) / 'ETF' ($3 固定) / '定期定額' ($0.1 固定)
    """
    成交價 = 訊號價 * (1 + US_SLIPPAGE_RATE)
    毛額 = 成交價 * 股數
    if 方案 == "ETF":
        手續費 = US_ETF_FLAT_FEE_USD
    elif 方案 == "定期定額":
        手續費 = US_DCA_FLAT_FEE_USD
    else:
        手續費 = max(毛額 * US_HANDLING_FEE_RATE, US_MIN_FEE_USD)
    總付 = 毛額 + 手續費
    return {
        "assumed_exec_price": round(成交價, 4),
        "gross": round(毛額, 2),
        "handling_fee": round(手續費, 2),
        "total_paid": round(總付, 2),
        "方案": 方案,
    }


def 美股_賣出收回(訊號價: float, 股數: int,
                   方案: str = "個股網路單") -> dict:
    """美股複委託賣出（含 SEC fee）。"""
    成交價 = 訊號價 * (1 - US_SLIPPAGE_RATE)
    毛額 = 成交價 * 股數
    if 方案 == "ETF":
        手續費 = US_ETF_FLAT_FEE_USD
    elif 方案 == "定期定額":
        手續費 = US_ETF_FLAT_FEE_USD   # 定期定額賣出仍比照 ETF
    else:
        手續費 = max(毛額 * US_HANDLING_FEE_RATE, US_MIN_FEE_USD)
    sec_fee = 毛額 * US_SEC_FEE_RATE
    淨收 = 毛額 - 手續費 - sec_fee
    return {
        "assumed_exec_price": round(成交價, 4),
        "gross": round(毛額, 2),
        "handling_fee": round(手續費, 2),
        "sec_fee": round(sec_fee, 4),
        "total_received": round(淨收, 2),
        "方案": 方案,
    }


# ─────────────────────────────────────────────
# 統一介面：給 ledger 用的「來回摩擦成本比例」
# ─────────────────────────────────────────────
def 來回摩擦比例(market: Literal["TW", "US", "ETF"]) -> float:
    """
    估算一買一賣的總摩擦成本比例（不含滑價）。
    ledger 存這個數字當「保守扣除值」。

    台股：手續費 × 2 + 證交稅 = 0.0855% × 2 + 0.3% = 0.471%
    美股：國泰網路單 0.08% × 2 + SEC fee = 0.162%

    註：ETF 視為台股算（多數使用者買的是台股 ETF）。
    """
    if market in ("TW", "ETF"):
        return 實際手續費率() * 2 + TW_TAX_RATE
    if market == "US":
        return US_HANDLING_FEE_RATE * 2 + US_SEC_FEE_RATE
    return 實際手續費率() * 2 + TW_TAX_RATE  # 默認台股


def 訊號進場價(訊號價: float, market: Literal["TW", "US", "ETF"]) -> float:
    """
    給 ledger 用的「假設成交價」（含滑價）。
    買進方向 +滑價，這是預設用法（系統發訊號通常是想買）。
    """
    rate = US_SLIPPAGE_RATE if market == "US" else SLIPPAGE_RATE
    return round(訊號價 * (1 + rate), 4 if market == "US" else 2)


# ─────────────────────────────────────────────
# 可成交性檢查（Phase 8.0a）
# ─────────────────────────────────────────────
def 檢查可成交性(每日資料: list[dict],
                  market: Literal["TW", "US", "ETF"] = "TW") -> dict:
    """
    判斷今日是否「可成交」+ 是否要加倍滑價。

    每日資料: technical.取得每日股價() 回傳格式（最新在 [0]）
              至少要有 2 筆才能算（今日 + 昨日）

    回傳：
      {
        "is_tradeable":     bool   是否可成交（False = 跳空漲停買不到）
        "slippage_multiplier": float 滑價倍數（正常 1.0，跳空跌停 3-5）
        "warnings":         list[str] 警示字串
      }

    判斷邏輯：
      - 今日 open ≥ 昨收 × 1.095 且 close ≈ open（漲停鎖死）→ 不可成交
      - 今日 open ≤ 昨收 × 0.905 → 跳空跌停，滑價 ×3
      - 美股無漲跌停，永遠可成交
    """
    if market == "US":
        return {"is_tradeable": True, "slippage_multiplier": 1.0, "warnings": []}

    if len(每日資料) < 2:
        # 資料不夠，保守視為可成交
        return {"is_tradeable": True, "slippage_multiplier": 1.0,
                "warnings": ["資料不足無法判斷可成交性"]}

    今日 = 每日資料[0]
    昨日 = 每日資料[1]
    昨收 = 昨日.get("close")
    今開 = 今日.get("open")
    今高 = 今日.get("high")
    今低 = 今日.get("low")
    今收 = 今日.get("close")

    if not 昨收 or not 今開:
        return {"is_tradeable": True, "slippage_multiplier": 1.0,
                "warnings": ["缺價量資料"]}

    開盤漲幅 = (今開 - 昨收) / 昨收
    全日漲幅 = (今收 - 昨收) / 昨收 if 今收 else 0

    warnings = []

    # 跳空漲停：開盤接近 +10%，且全日漲幅 >= 9.5%（接近鎖死）
    if 開盤漲幅 >= TW_LIMIT_THRESHOLD and 全日漲幅 >= TW_LIMIT_THRESHOLD:
        warnings.append(
            f"⚠️ 跳空漲停（開盤 +{開盤漲幅*100:.1f}% / 收盤 +{全日漲幅*100:.1f}%）"
        )
        return {"is_tradeable": False, "slippage_multiplier": 0.0,
                "warnings": warnings}

    # 跳空跌停：開盤接近 -10%
    if 開盤漲幅 <= -TW_LIMIT_THRESHOLD:
        warnings.append(
            f"⚠️ 跳空跌停（開盤 {開盤漲幅*100:.1f}%），滑價加倍"
        )
        return {"is_tradeable": True, "slippage_multiplier": 3.0,
                "warnings": warnings}

    # 振幅過大（單日漲跌 > 7% 但沒鎖停）：滑價 ×1.5
    if 今高 and 今低 and 今低 > 0:
        日內振幅 = (今高 - 今低) / 今低
        if 日內振幅 > 0.07:
            warnings.append(f"⚠️ 日內振幅 {日內振幅*100:.1f}%，滑價加倍")
            return {"is_tradeable": True, "slippage_multiplier": 1.5,
                    "warnings": warnings}

    return {"is_tradeable": True, "slippage_multiplier": 1.0, "warnings": []}


def 訊號進場價_含可成交性(訊號價: float,
                              market: Literal["TW", "US", "ETF"],
                              slippage_multiplier: float = 1.0) -> Optional[float]:
    """
    含可成交性的進場價計算。
    slippage_multiplier=0 表示不可成交，回傳 None。
    """
    if slippage_multiplier <= 0:
        return None
    rate = (US_SLIPPAGE_RATE if market == "US" else SLIPPAGE_RATE) * slippage_multiplier
    return round(訊號價 * (1 + rate), 4 if market == "US" else 2)


# ─────────────────────────────────────────────
# 模擬完整一買一賣（給情境試算用）
# ─────────────────────────────────────────────
def 模擬完整交易(訊號買價: float, 訊號賣價: float,
                  股數: int,
                  market: Literal["TW", "US", "ETF"] = "TW") -> dict:
    """
    模擬一買一賣的完整 PnL，含全部摩擦。
    用來給使用者試算：
      「我用 580 買、用 667 賣 100 股，國泰實際進帳多少？」
    """
    if market == "US":
        買 = 美股_買進成本(訊號買價, 股數)
        賣 = 美股_賣出收回(訊號賣價, 股數)
        貨幣 = "USD"
    else:
        買 = 台股_買進成本(訊號買價, 股數)
        賣 = 台股_賣出收回(訊號賣價, 股數)
        貨幣 = "TWD"

    淨損益 = 賣["total_received"] - 買["total_paid"]
    報酬率 = 淨損益 / 買["total_paid"] * 100 if 買["total_paid"] > 0 else 0

    # 紙上 vs 實際差距（理論報酬 - 實際報酬）
    理論報酬率 = (訊號賣價 - 訊號買價) / 訊號買價 * 100
    摩擦損耗_pp = round(理論報酬率 - 報酬率, 2)  # percentage points

    return {
        "貨幣": 貨幣,
        "買進": 買,
        "賣出": 賣,
        "淨損益": round(淨損益, 0 if market != "US" else 2),
        "實際報酬率_%": round(報酬率, 2),
        "理論報酬率_%": round(理論報酬率, 2),
        "摩擦損耗_pp": 摩擦損耗_pp,
    }


# ─────────────────────────────────────────────
# CLI 自測
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("國泰證券電子下單摩擦成本試算")
    print("=" * 50)
    print(f"手續費率（單邊）：{實際手續費率()*100:.4f}%")
    print(f"來回摩擦（台股）：{來回摩擦比例('TW')*100:.4f}%")
    print(f"來回摩擦（美股）：{來回摩擦比例('US')*100:.4f}%")
    print()
    print("情境 1：台積電 580 買、580 賣（持平）100 股")
    試算1 = 模擬完整交易(580, 580, 100, "TW")
    for k, v in 試算1.items():
        print(f"  {k}: {v}")
    print()
    print("情境 2：台積電 580 買、667 賣（+15% 停利）100 股")
    試算2 = 模擬完整交易(580, 667, 100, "TW")
    for k, v in 試算2.items():
        print(f"  {k}: {v}")
    print()
    print("情境 3：台積電 580 買、551 賣（-5% 停損）100 股")
    試算3 = 模擬完整交易(580, 551, 100, "TW")
    for k, v in 試算3.items():
        print(f"  {k}: {v}")
