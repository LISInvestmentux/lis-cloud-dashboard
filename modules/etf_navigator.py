"""
ETF 即時布局建議模組（Phase 5 — 方舟級）

資料源：證交所 MIS API（mis.twse.com.tw）
- 即時市價、五檔買賣價/量
- 內外盤比
- 暫用「中價」當 fair value（之後可接 issuer NAV API 升級）

輸出：
- 每檔 ETF 建議掛單價（左 1-5 委買）
- 建議掛單股數（依資金規劃）
- 內外盤比（積極度判讀）
"""
import json
import sys
import urllib3
from pathlib import Path
from typing import Optional

import requests

# 支援兩種執行方式：(1) python main.py 跑（package 內）(2) 直接 python etf_navigator.py
try:
    from . import capital_planner
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from modules import capital_planner

urllib3.disable_warnings()  # 證交所站證書配置不規範


專案根 = Path(__file__).resolve().parent.parent.parent
WATCHLIST_PATH = 專案根 / "API" / "watchlist.json"

MIS_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://mis.twse.com.tw/",
}


# ─────────────────────────────────────────────
# 載入觀察清單裡的台股 ETF
# ─────────────────────────────────────────────
def 載入ETF清單() -> list[dict]:
    """從 watchlist.json 抓出 tw_etfs 區塊。"""
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    for region in data["regions"]:
        if region["id"] == "tw_etfs":
            return region["stocks"]
    return []


# ─────────────────────────────────────────────
# 即時行情抓取
# ─────────────────────────────────────────────
def _建立查詢字串(symbols: list[str]) -> str:
    """把 symbols 轉成 mis API 需要的 ex_ch 格式：tse_XXXX.tw|tse_YYYY.tw"""
    parts = []
    for s in symbols:
        # 去掉 .TW / .TWO 後綴
        code = s.split(".")[0]
        # tse_ 是上市，otc_ 是上櫃
        parts.append(f"tse_{code}.tw")
    return "|".join(parts)


def 抓即時行情(symbols: list[str]) -> dict:
    """
    一次抓多檔股票/ETF 即時行情。
    回傳 {symbol: {price, bid_prices, ask_prices, bid_volumes, ask_volumes, ...}}
    """
    ex_ch = _建立查詢字串(symbols)
    params = {"ex_ch": ex_ch, "json": "1", "delay": "0"}

    try:
        resp = requests.get(MIS_URL, params=params, headers=HEADERS,
                            timeout=15, verify=False)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[etf] mis API 失敗：{e}", file=sys.stderr)
        return {}

    結果 = {}
    for s in data.get("msgArray", []):
        code = s.get("c", "")
        if not code:
            continue
        # 五檔價量（mis 用底線分隔，最後一個是空字串）
        買價 = [float(p) for p in s.get("b", "").split("_") if p]
        賣價 = [float(p) for p in s.get("a", "").split("_") if p]
        買量 = [int(v) for v in s.get("g", "").split("_") if v]
        賣量 = [int(v) for v in s.get("f", "").split("_") if v]

        # 安全轉數值
        def _safe(v):
            try:
                return float(v) if v and v != "-" else None
            except (ValueError, TypeError):
                return None

        結果[code] = {
            "symbol": code,
            "name": s.get("n", ""),
            "last_price": _safe(s.get("z")),
            "open": _safe(s.get("o")),
            "high": _safe(s.get("h")),
            "low": _safe(s.get("l")),
            "prev_close": _safe(s.get("y")),
            "volume": _safe(s.get("v")),
            "bid_prices": 買價,        # 委買 5 檔（高→低）
            "ask_prices": 賣價,        # 委賣 5 檔（低→高）
            "bid_volumes": 買量,
            "ask_volumes": 賣量,
            "timestamp": s.get("tlong", ""),
        }
    return 結果


# ─────────────────────────────────────────────
# 衍生指標計算
# ─────────────────────────────────────────────
def 計算內外盤比(行情: dict) -> dict:
    """
    內盤 vs 外盤：
    - 內盤量 = 委買量總和（賣方主動成交於委買價）
    - 外盤量 = 委賣量總和（買方主動成交於委賣價）
    - 內盤比 > 50% 表示賣方積極，可能跌
    - 外盤比 > 50% 表示買方積極，可能漲

    這裡用「五檔掛單量」當作積極度近似。
    """
    買量 = sum(行情.get("bid_volumes", []))
    賣量 = sum(行情.get("ask_volumes", []))
    總量 = 買量 + 賣量
    if 總量 == 0:
        return {"內盤比": None, "外盤比": None,
                "內盤量": 0, "外盤量": 0, "判讀": "無掛單"}
    內 = round(買量 / 總量 * 100, 1)
    外 = round(賣量 / 總量 * 100, 1)
    if 外 >= 55:
        判讀 = "🟢 買方積極"
    elif 內 >= 55:
        判讀 = "🔴 賣方積極"
    else:
        判讀 = "🟡 中性"
    return {"內盤比": 內, "外盤比": 外,
            "內盤量": 買量, "外盤量": 賣量, "判讀": 判讀}


def 計算中價(行情: dict) -> Optional[float]:
    """中價（fair value 近似）= 最佳委買 / 最佳委賣 中位數。"""
    買 = 行情.get("bid_prices", [])
    賣 = 行情.get("ask_prices", [])
    if not 買 or not 賣:
        return None
    return round((買[0] + 賣[0]) / 2, 4)


def 計算折溢價(行情: dict) -> Optional[dict]:
    """
    用中價當 fair value，看市價（最近成交）相對中價是折還溢。
    （之後可接 issuer NAV API 拿真實淨值）
    回傳：
        {"基準": float, "市價": float, "差價": float, "百分比": float, "狀態": "折價"/"溢價"/"持平"}
    """
    中價 = 計算中價(行情)
    市價 = 行情.get("last_price")
    if 中價 is None or 市價 is None:
        return None
    差 = 市價 - 中價
    百分比 = round(差 / 中價 * 100, 3)
    if 差 < -0.005:
        狀態 = "💚 折價（可進場）"
    elif 差 > 0.005:
        狀態 = "🔴 溢價（追高）"
    else:
        狀態 = "🟡 持平"
    return {"基準": 中價, "市價": 市價, "差價": round(差, 4),
            "百分比": 百分比, "狀態": 狀態}


# ─────────────────────────────────────────────
# 建議掛單價邏輯（紀律布局法）
# ─────────────────────────────────────────────
def 算建議掛單(行情: dict, 預算_twd: float,
               策略: str = "中性") -> dict:
    """
    紀律布局法：
    - 積極（左1委買）：掛在當前最高委買價（最容易成交，但稍貴）
    - 中性（左3委買）：掛在中間，平衡成交速度與價格
    - 保守（左5委買）：掛在較低位，便宜但難成交

    回傳：
        {"建議價": float, "策略": str, "可買股數": int, "註記": str}
    """
    買 = 行情.get("bid_prices", [])
    if len(買) < 1 or not 預算_twd:
        return {"建議價": None, "策略": 策略, "可買股數": 0, "註記": "無五檔資料"}

    if 策略 == "積極":
        掛價 = 買[0]
    elif 策略 == "保守":
        掛價 = 買[min(4, len(買) - 1)]
    else:  # 中性
        掛價 = 買[min(2, len(買) - 1)]

    # 用 capital_planner 算股數
    symbol_tw = f"{行情['symbol']}.TW"
    股數計算 = capital_planner.計算建議股數(symbol_tw, 掛價, 預算_twd)

    return {
        "建議價": 掛價,
        "策略": 策略,
        "可買股數": 股數計算["可買股數"],
        "實際金額_twd": 股數計算["實際金額_twd"],
        "註記": 股數計算["註記"],
    }


# ─────────────────────────────────────────────
# 整合：產出今日 ETF 布局建議
# ─────────────────────────────────────────────
def 取得今日ETF布局建議(每檔預算_twd: float = 30000,
                          策略: str = "中性") -> list[dict]:
    """
    對所有 watchlist 內的 ETF：
    - 抓即時行情
    - 算內外盤比
    - 算建議掛單價 + 股數
    - 按折價深度排序（折價最深者最值得布局）
    """
    etfs = 載入ETF清單()
    print(f"[etf] 對 {len(etfs)} 檔 ETF 抓即時行情...")
    symbols = [e["symbol"] for e in etfs]
    行情dict = 抓即時行情(symbols)
    print(f"     成功抓到 {len(行情dict)} 檔")

    結果 = []
    for etf in etfs:
        code = etf["symbol"].split(".")[0]
        行情 = 行情dict.get(code)
        if not 行情:
            continue
        if not 行情.get("bid_prices"):
            continue  # 沒掛單（盤前盤後常見）

        盤比 = 計算內外盤比(行情)
        折溢價 = 計算折溢價(行情)
        建議 = 算建議掛單(行情, 每檔預算_twd, 策略)

        結果.append({
            "symbol": etf["symbol"],
            "name": etf["name"],
            "code": code,
            "last_price": 行情["last_price"],
            "mid_price": 計算中價(行情),
            "bid_top": 行情["bid_prices"][0] if 行情["bid_prices"] else None,
            "ask_top": 行情["ask_prices"][0] if 行情["ask_prices"] else None,
            "bid_prices": 行情["bid_prices"],      # 完整五檔買價
            "ask_prices": 行情["ask_prices"],      # 完整五檔賣價
            "bid_volumes": 行情["bid_volumes"],    # 完整五檔買量
            "ask_volumes": 行情["ask_volumes"],    # 完整五檔賣量
            "盤比": 盤比,
            "折溢價": 折溢價,
            "建議掛單": 建議,
        })

    # 排序：有折價的優先（百分比由負到正）
    結果.sort(key=lambda r: (
        r["折溢價"]["百分比"] if r["折溢價"] else 0
    ))
    return 結果


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    結果 = 取得今日ETF布局建議(每檔預算_twd=30000)
    print()
    for r in 結果[:10]:
        print(f"━━━ {r['name']} ({r['code']}) ━━━")
        print(f"  市價：{r['last_price']}  中價：{r['mid_price']}")
        print(f"  委買1：{r['bid_top']}  委賣1：{r['ask_top']}")
        if r["折溢價"]:
            d = r["折溢價"]
            print(f"  折溢價：{d['百分比']:+.3f}%  {d['狀態']}")
        if r["盤比"]["內盤比"] is not None:
            print(f"  內盤 {r['盤比']['內盤比']}% 外盤 {r['盤比']['外盤比']}%  {r['盤比']['判讀']}")
        b = r["建議掛單"]
        if b["建議價"]:
            print(f"  💎 建議：{b['策略']}掛 ${b['建議價']}，約 {b['註記']}")
        print()
