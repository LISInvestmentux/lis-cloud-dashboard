"""
技術面掃描模組 — Phase 2
資料源：yfinance；觀察清單從 API/watchlist.json 讀取（不寫死在程式碼）。

對應 Enjoy Index 的「技術面 Shit Indicator」與「轉折訊號」
- Shit Indicator（低點）：RSI(14) < 35 且 收盤 ≤ MA200
- Bull Signal（轉折）：MACD 黃金交叉 且 收盤突破 MA50
"""
import json
import time
from pathlib import Path
from typing import Optional

import yfinance as yf


專案根 = Path(__file__).resolve().parent.parent.parent
WATCHLIST_PATH = 專案根 / "API" / "watchlist.json"


# ─────────────────────────────────────────────
# 設定載入
# ─────────────────────────────────────────────
def 載入觀察清單() -> dict:
    """從 watchlist.json 載入觀察清單設定。"""
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────
# 底層：抓取每日股價（yfinance）
# ─────────────────────────────────────────────
def _抓一次(symbol: str, period: str) -> list[dict]:
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, auto_adjust=False)
    if df.empty:
        raise ValueError(f"yfinance 找不到 {symbol}")

    # 過濾掉 yfinance 偶發回傳 NaN 的日期（特別是 ^TWII / 部分台股 ETF）
    df = df.dropna(subset=["Close"])
    if df.empty:
        raise ValueError(f"{symbol} 全部資料皆為 NaN")

    結果 = []
    for ts, row in df[::-1].iterrows():
        # 雙重保險：個別欄位再檢查一次
        if row["Close"] != row["Close"]:  # NaN check
            continue
        vol = row["Volume"]
        結果.append({
            "date": ts.strftime("%Y-%m-%d"),
            "open": float(row["Open"]) if row["Open"] == row["Open"] else float(row["Close"]),
            "high": float(row["High"]) if row["High"] == row["High"] else float(row["Close"]),
            "low":  float(row["Low"])  if row["Low"]  == row["Low"]  else float(row["Close"]),
            "close": float(row["Close"]),
            "volume": int(vol) if vol == vol else 0,
        })
    return 結果


def 取得每日股價(symbol: str, period: str = "2y",
                  強制更新: bool = False) -> tuple[list[dict], str]:
    """
    回傳 (每日 K 線, 實際使用的 symbol)。
    台股 .TW 抓不到時自動 fallback 到 .TWO（上櫃）。
    Phase 32.7：加入 30 分鐘 cache 層（解決 yfinance 限流）。
    """
    from . import price_cache
    cache_key = f"daily_{symbol}_{period}"

    def _實際抓():
        try:
            return {"data": _抓一次(symbol, period), "used": symbol}
        except Exception:
            if symbol.endswith(".TW") and not symbol.endswith(".TWO"):
                try:
                    替代 = symbol[:-3] + ".TWO"
                    return {"data": _抓一次(替代, period), "used": 替代}
                except Exception:
                    pass
            raise

    try:
        r, source = price_cache.取得或抓(
            cache_key, _實際抓,
            ttl_秒=price_cache.DAILY_TTL,
            強制更新=強制更新,
        )
        return r["data"], r["used"]
    except Exception:
        pass
        raise


# ─────────────────────────────────────────────
# 技術指標計算（純 Python）
# ─────────────────────────────────────────────
def 計算SMA(收盤序列: list[float], 期數: int) -> Optional[float]:
    if len(收盤序列) < 期數:
        return None
    return round(sum(收盤序列[:期數]) / 期數, 2)


def 計算EMA(收盤序列: list[float], 期數: int) -> list[Optional[float]]:
    n = len(收盤序列)
    if n < 期數:
        return [None] * n
    舊到新 = list(reversed(收盤序列))
    ema序列_舊到新: list[Optional[float]] = [None] * (期數 - 1)
    種子 = sum(舊到新[:期數]) / 期數
    ema序列_舊到新.append(種子)
    k = 2 / (期數 + 1)
    for 價 in 舊到新[期數:]:
        前 = ema序列_舊到新[-1]
        ema序列_舊到新.append(價 * k + 前 * (1 - k))
    return list(reversed(ema序列_舊到新))


def 計算RSI(收盤序列: list[float], 期數: int = 14) -> Optional[float]:
    if len(收盤序列) < 期數 + 1:
        return None
    舊到新 = list(reversed(收盤序列))
    漲幅, 跌幅 = [], []
    for i in range(1, len(舊到新)):
        差 = 舊到新[i] - 舊到新[i - 1]
        漲幅.append(max(差, 0))
        跌幅.append(max(-差, 0))
    平均漲 = sum(漲幅[:期數]) / 期數
    平均跌 = sum(跌幅[:期數]) / 期數
    for i in range(期數, len(漲幅)):
        平均漲 = (平均漲 * (期數 - 1) + 漲幅[i]) / 期數
        平均跌 = (平均跌 * (期數 - 1) + 跌幅[i]) / 期數
    if 平均跌 == 0:
        return 100.0
    rs = 平均漲 / 平均跌
    return round(100 - (100 / (1 + rs)), 1)


def 計算MACD(收盤序列: list[float]) -> dict:
    if len(收盤序列) < 35:
        return {"macd": None, "signal": None, "hist": None,
                "is_golden_cross": False, "is_death_cross": False}
    ema12 = 計算EMA(收盤序列, 12)
    ema26 = 計算EMA(收盤序列, 26)
    dif = [
        (a - b) if (a is not None and b is not None) else None
        for a, b in zip(ema12, ema26)
    ]
    有效 = [x for x in dif if x is not None]
    if len(有效) < 9:
        return {"macd": None, "signal": None, "hist": None,
                "is_golden_cross": False, "is_death_cross": False}
    dem_有效 = 計算EMA(有效, 9)
    今日DIF = dif[0]
    昨日DIF = dif[1] if len(dif) > 1 else None
    今日DEM = dem_有效[0]
    昨日DEM = dem_有效[1] if len(dem_有效) > 1 else None
    黃金 = bool(昨日DIF is not None and 昨日DEM is not None
              and 昨日DIF <= 昨日DEM and 今日DIF > 今日DEM)
    死亡 = bool(昨日DIF is not None and 昨日DEM is not None
              and 昨日DIF >= 昨日DEM and 今日DIF < 今日DEM)
    return {
        "macd": round(今日DIF, 3) if 今日DIF is not None else None,
        "signal": round(今日DEM, 3) if 今日DEM is not None else None,
        "hist": round(今日DIF - 今日DEM, 3) if (今日DIF is not None and 今日DEM is not None) else None,
        "is_golden_cross": 黃金,
        "is_death_cross": 死亡,
    }


# ─────────────────────────────────────────────
# 震盪低點偵測
# ─────────────────────────────────────────────
def 偵測震盪低點(每日資料: list[dict],
                  rsi14: Optional[float],
                  ma50: Optional[float],
                  ma200: Optional[float]) -> dict:
    """
    震盪低點 = 區間盤整 + 在區間下半部 + 微弱超賣 + 長期趨勢仍向上 + 量縮
    四大條件全部成立 → 可大量佈局

    回傳：
        {
            "is_shakeout_low": bool,
            "score": 0-4 (吻合幾個條件),
            "range_pct": 近 20 日區間幅度 %,
            "position_in_range": 收盤在區間位置 0-1,
            "理由": [...]
        }
    """
    if len(每日資料) < 20:
        return {"is_shakeout_low": False, "score": 0,
                "range_pct": None, "position_in_range": None, "理由": []}

    近20日 = 每日資料[:20]
    近20日最高 = max(d["high"] for d in 近20日)
    近20日最低 = min(d["low"] for d in 近20日)
    今日收盤 = 每日資料[0]["close"]
    中位數 = (近20日最高 + 近20日最低) / 2 or 1
    區間幅度 = (近20日最高 - 近20日最低) / 中位數
    位置 = ((今日收盤 - 近20日最低) / (近20日最高 - 近20日最低)
             if 近20日最高 > 近20日最低 else 0.5)

    # 五大條件
    成立 = []
    區間夠窄 = 區間幅度 < 0.15
    if 區間夠窄:
        成立.append("近20日波動<15%")

    位置偏低 = 位置 < 0.45
    if 位置偏低:
        成立.append("收盤位於區間下半")

    RSI偏弱 = (rsi14 is not None and 35 <= rsi14 <= 50)
    if RSI偏弱:
        成立.append(f"RSI {rsi14} 微弱（非恐慌）")

    趨勢向上 = (ma50 is not None and ma200 is not None and ma50 > ma200)
    if 趨勢向上:
        成立.append("MA50>MA200 長期向上")

    # 量縮確認（如資料足夠）
    量縮 = False
    if len(每日資料) >= 20:
        近5日均量 = sum(d["volume"] for d in 每日資料[:5]) / 5
        近20日均量 = sum(d["volume"] for d in 每日資料[:20]) / 20
        if 近20日均量 > 0 and 近5日均量 < 近20日均量 * 0.85:
            量縮 = True
            成立.append("近5日量縮")

    # 至少 4 條件成立才算震盪低點
    is_shakeout = len(成立) >= 4

    return {
        "is_shakeout_low": is_shakeout,
        "score": len(成立),
        "range_pct": round(區間幅度 * 100, 1),
        "position_in_range": round(位置, 2),
        "理由": 成立,
    }


# ─────────────────────────────────────────────
# 單檔分析
# ─────────────────────────────────────────────
def 分析個股(symbol: str, 中文名: str = "") -> dict:
    """對單一股票/ETF/指數回傳完整技術面分析。"""
    每日, 實際symbol = 取得每日股價(symbol, "2y")
    收盤 = [d["close"] for d in 每日]
    今日 = 每日[0]

    rsi = 計算RSI(收盤, 14)
    ma50 = 計算SMA(收盤, 50)
    ma200 = 計算SMA(收盤, 200)
    macd = 計算MACD(收盤)

    shit_signal = bool(rsi is not None and ma200 is not None
                       and rsi < 35 and 今日["close"] <= ma200)
    bull_signal = bool(macd["is_golden_cross"] and ma50 is not None
                       and 今日["close"] > ma50)

    震盪 = 偵測震盪低點(每日, rsi, ma50, ma200)

    昨日 = 每日[1] if len(每日) > 1 else None

    # Phase 7.2：20 日漲幅（給相對強度 vs 大盤用）
    漲幅_20日 = None
    if len(每日) >= 21:
        二十日前收盤 = 每日[20]["close"]
        if 二十日前收盤 > 0:
            漲幅_20日 = round((今日["close"] / 二十日前收盤 - 1) * 100, 2)

    # Phase 6.2：量能爆衝（當日成交量 vs 20 日均量倍數）
    量爆倍數 = None
    量爆訊號 = False
    if len(每日) >= 21 and 今日.get("volume", 0) > 0:
        近20日均量 = sum(d.get("volume", 0) for d in 每日[1:21]) / 20
        if 近20日均量 > 0:
            量爆倍數 = round(今日["volume"] / 近20日均量, 2)
            量爆訊號 = 量爆倍數 >= 2.0   # 2 倍以上視為爆衝

    return {
        "symbol": 實際symbol,
        "original_symbol": symbol,
        "name": 中文名,
        "date": 今日["date"],
        "close": round(今日["close"], 2),
        # Phase 8.0a 新增：給可成交性判斷用
        "open": round(今日.get("open", 今日["close"]), 2),
        "high": round(今日.get("high", 今日["close"]), 2),
        "low": round(今日.get("low", 今日["close"]), 2),
        "volume": 今日.get("volume", 0),
        "prev_close": round(昨日["close"], 2) if 昨日 else None,
        # Phase 7.2 新增：20 日漲幅
        "漲幅_20日_pct": 漲幅_20日,
        # Phase 6.2 新增：量能爆衝
        "量爆倍數": 量爆倍數,
        "量爆訊號": 量爆訊號,
        "rsi14": rsi,
        "ma50": ma50,
        "ma200": ma200,
        "macd": macd["macd"],
        "macd_golden_cross": macd["is_golden_cross"],
        "macd_death_cross": macd["is_death_cross"],
        "shit_signal": shit_signal,
        "bull_signal": bull_signal,
        "shakeout_low": 震盪["is_shakeout_low"],
        "shakeout_score": 震盪["score"],
        "shakeout_range_pct": 震盪["range_pct"],
        "shakeout_position": 震盪["position_in_range"],
        "shakeout_reasons": 震盪["理由"],
        "above_ma50": (ma50 is not None and 今日["close"] > ma50),
        "below_ma200": (ma200 is not None and 今日["close"] < ma200),
    }


# ─────────────────────────────────────────────
# 批次掃描（清單可來自任何來源）
# ─────────────────────────────────────────────
def 掃描清單(項目清單: list[dict], 延遲秒: float = 0.5) -> list[dict]:
    """
    輸入 [{"symbol": "...", "name": "..."}, ...]
    回傳 [{...完整分析...}] 或 {"symbol", "name", "error"}
    """
    結果 = []
    for i, 項 in enumerate(項目清單):
        if i > 0:
            time.sleep(延遲秒)
        try:
            結果.append(分析個股(項["symbol"], 項.get("name", "")))
        except Exception as e:
            結果.append({
                "symbol": 項["symbol"],
                "name": 項.get("name", ""),
                "error": str(e)[:80],
            })
    return 結果


def 掃描全部觀察清單() -> dict:
    """讀 watchlist.json 並掃描所有區域 + 指數。回傳：
    {
        "indices": [...],
        "regions": {
            "us":        {"label": ..., "items": [...]},
            "tw_stocks": {"label": ..., "items": [...]},
            "tw_etfs":   {"label": ..., "items": [...]},
        }
    }
    """
    cfg = 載入觀察清單()

    print(f"  掃描大盤指標 ({len(cfg['indices']['items'])} 檔)...")
    indices = 掃描清單(cfg["indices"]["items"])

    regions = {}
    for region in cfg["regions"]:
        print(f"  掃描 {region['label']} ({len(region['stocks'])} 檔)...")
        regions[region["id"]] = {
            "label": region["label"],
            "items": 掃描清單(region["stocks"]),
        }

    return {
        "indices_label": cfg["indices"]["label"],
        "indices": indices,
        "regions": regions,
    }


# ─────────────────────────────────────────────
# 格式化（給 LINE 訊息用）
# ─────────────────────────────────────────────
def _ROC數字(數值: Optional[float], 寬度: int = 5) -> str:
    """簡單把數字對齊寬度。"""
    if 數值 is None:
        return "—"
    return f"{數值}"


def _單檔一行(r: dict, 價格前綴: str = "$") -> str:
    """產出單行：• 中文名(代號) 價格 RSIxx 旗標"""
    if "error" in r:
        return f"   • {r['name']}({r['symbol']}) ⚠️ {r['error']}"
    旗標 = []
    if r.get("shit_signal"):
        旗標.append("🔴錯殺")
    if r.get("bull_signal"):
        旗標.append("🟢金叉")
    if r.get("below_ma200"):
        旗標.append("跌破200")
    if r.get("above_ma50"):
        旗標.append(">50")
    旗文 = "｜" + " ".join(旗標) if 旗標 else ""
    名 = r["name"] or r["symbol"]
    return f"   • {名}({r['symbol']}) {價格前綴}{r['close']} RSI{r['rsi14']}{旗文}"


def 格式化指數區(掃描結果: dict) -> str:
    行 = [掃描結果["indices_label"]]
    for r in 掃描結果["indices"]:
        前綴 = "" if r["symbol"].startswith("^") else "$"
        行.append(_單檔一行(r, 前綴))
    return "\n".join(行)


def 格式化單一區域(區域: dict, 含明細: bool = True) -> str:
    """格式化美股 / 台股 / ETF 任一區域。"""
    items = 區域["items"]
    有效 = [r for r in items if "error" not in r]
    錯誤 = [r for r in items if "error" in r]
    低點 = [r for r in 有效 if r.get("shit_signal")]
    轉折 = [r for r in 有效 if r.get("bull_signal")]

    行 = [區域["label"]]
    行.append(f"   📊 {len(有效)} 檔可分析" +
              (f"，⚠️ {len(錯誤)} 檔無資料" if 錯誤 else ""))

    if 低點:
        行.append("   🔴 錯殺低點:")
        for r in 低點:
            行.append(_單檔一行(r))
    if 轉折:
        行.append("   🟢 MACD 金叉轉折:")
        for r in 轉折:
            行.append(_單檔一行(r))
    if not 低點 and not 轉折:
        行.append("   （目前無觸發訊號）")

    if 含明細:
        行.append("   ── 全清單明細 ──")
        for r in items:
            行.append(_單檔一行(r))

    return "\n".join(行)


if __name__ == "__main__":
    print("正在跑全部觀察清單掃描（測試模式）...")
    結果 = 掃描全部觀察清單()
    print()
    print(格式化指數區(結果))
    print()
    for 區id, 區 in 結果["regions"].items():
        print(格式化單一區域(區, 含明細=False))
        print()
