"""
法人籌碼追蹤（Phase 22）— TWSE 三大法人買賣超

對標 ARK 籌碼面：每日抓三大法人（外資/投信/自營商）買賣超。
連續 N 日買超 = 強訊號（外資進場）
連續 N 日賣超 = 警示（外資撤退）

公開資料：
  TWSE 上市：https://www.twse.com.tw/rwd/zh/fund/T86
  TPEX 上櫃：https://www.tpex.org.tw/web/inc_notice/qprice/

策略整合：
  - 「外資連 N 買」獨立策略
  - 跟 Kelly TOP10 交叉 = 超強訊號
  - 對抗 LIS 訊號（外資賣 vs LIS 抄底）= 警示

每日資料快取 在 數據/法人籌碼/{YYYY-MM-DD}.json
"""
import json
import ssl
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent
快取目錄 = 專案根 / "數據" / "法人籌碼"


def _抓TWSE(日期: str) -> Optional[dict]:
    """日期格式 YYYYMMDD"""
    url = (f"https://www.twse.com.tw/rwd/zh/fund/T86"
           f"?date={日期}&selectType=ALLBUT0999&response=json")
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"TWSE 抓取失敗 {日期}: {e}")
        return None


def _抓TPEX(日期: str) -> Optional[dict]:
    """日期格式 民國 YYY/MM/DD 或 YYYYMMDD → 轉換"""
    # TPEX 用民國年
    yyyy_mm_dd = datetime.strptime(日期, "%Y%m%d")
    民國 = f"{yyyy_mm_dd.year - 1911}/{yyyy_mm_dd.month:02d}/{yyyy_mm_dd.day:02d}"
    url = (f"https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php"
           f"?l=zh-tw&se=EW&t=D&d={urllib.parse.quote(民國)}&_=1")
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return None


def 抓今日法人籌碼(日期: Optional[str] = None) -> dict:
    """
    抓今日（或指定日期）三大法人買賣超。
    回傳：{
      "日期": "YYYY-MM-DD",
      "資料": {symbol: {外資, 投信, 自營商, 三大法人合計}},
      "資料筆數": N,
    }
    """
    日 = 日期 or datetime.now().strftime("%Y%m%d")

    # 先看快取
    cache_key = f"{日[:4]}-{日[4:6]}-{日[6:]}"
    cache_path = 快取目錄 / f"{cache_key}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    raw = _抓TWSE(日)
    if not raw or not raw.get("data"):
        return {"日期": cache_key, "資料": {}, "資料筆數": 0,
                "錯誤": "API 無資料"}

    # 解析欄位
    # ['證券代號', '證券名稱', '外資買進', '外資賣出', '外資買賣超',
    #  '外資自營買進', '外資自營賣出', '外資自營買賣超',
    #  '投信買進', '投信賣出', '投信買賣超',
    #  '自營商買賣超', '自營商買進(自行)', '自營商賣出(自行)',
    #  '自營商買賣超(自行)', ...]
    fields = raw.get("fields", [])

    def _to_int(s):
        try:
            return int(str(s).replace(",", ""))
        except Exception:
            return 0

    資料 = {}
    for row in raw["data"]:
        if len(row) < 11:
            continue
        sym = row[0].strip()
        name = row[1].strip()
        外資買賣超 = _to_int(row[4])  # 含外資自營
        投信買賣超 = _to_int(row[10])
        自營商 = _to_int(row[11]) if len(row) > 11 else 0
        三大 = 外資買賣超 + 投信買賣超 + 自營商

        資料[sym] = {
            "symbol": sym,
            "name": name,
            "外資": 外資買賣超,
            "投信": 投信買賣超,
            "自營商": 自營商,
            "三大法人合計": 三大,
        }

    結果 = {
        "日期": cache_key,
        "資料": 資料,
        "資料筆數": len(資料),
    }

    # 存快取
    快取目錄.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(結果, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 結果


def 連續買賣超(symbol: str, 天數: int = 5) -> dict:
    """
    回傳近 N 天該檔的外資/投信買賣超狀況。
    """
    今天 = datetime.now()
    記錄 = []
    for i in range(天數 * 2):  # 多抓幾天避開假日
        if len(記錄) >= 天數:
            break
        日 = 今天 - timedelta(days=i)
        if 日.weekday() >= 5:  # 週末跳過
            continue
        try:
            r = 抓今日法人籌碼(日.strftime("%Y%m%d"))
            if symbol in r.get("資料", {}):
                d = r["資料"][symbol]
                記錄.append({"日期": r["日期"], **d})
        except Exception:
            continue

    # 統計連續
    外資連續買 = 0
    外資連續賣 = 0
    投信連續買 = 0
    if 記錄:
        for r in 記錄:
            if r["外資"] > 0:
                if 外資連續賣 > 0:
                    break
                外資連續買 += 1
            elif r["外資"] < 0:
                if 外資連續買 > 0:
                    break
                外資連續賣 += 1
        for r in 記錄:
            if r["投信"] > 0:
                投信連續買 += 1
            else:
                break

    return {
        "symbol": symbol,
        "天數": len(記錄),
        "記錄": 記錄,
        "外資連續買": 外資連續買,
        "外資連續賣": 外資連續賣,
        "投信連續買": 投信連續買,
        "外資累計": sum(r["外資"] for r in 記錄),
        "投信累計": sum(r["投信"] for r in 記錄),
    }


def 找今日強訊號(門檻_外資張: int = 1000,
                  門檻_投信張: int = 500) -> dict:
    """
    回傳今日「外資 + 投信同向買超」的標的。
    這是 ARK 大俠講「籌碼共識」的核心。
    """
    今天 = datetime.now().strftime("%Y%m%d")
    r = 抓今日法人籌碼(今天)
    if not r.get("資料"):
        # 試昨日
        昨 = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        r = 抓今日法人籌碼(昨)

    強共識買 = []
    強共識賣 = []
    外資大買 = []
    投信大買 = []

    for sym, d in r.get("資料", {}).items():
        if d["外資"] >= 門檻_外資張 * 1000 and d["投信"] >= 門檻_投信張 * 1000:
            強共識買.append(d)
        elif d["外資"] <= -門檻_外資張 * 1000 and d["投信"] <= -門檻_投信張 * 1000:
            強共識賣.append(d)
        elif d["外資"] >= 門檻_外資張 * 1000:
            外資大買.append(d)
        elif d["投信"] >= 門檻_投信張 * 1000:
            投信大買.append(d)

    強共識買.sort(key=lambda r: -r["三大法人合計"])
    強共識賣.sort(key=lambda r: r["三大法人合計"])
    外資大買.sort(key=lambda r: -r["外資"])
    投信大買.sort(key=lambda r: -r["投信"])

    return {
        "日期": r.get("日期"),
        "強共識買": 強共識買[:20],
        "強共識賣": 強共識賣[:20],
        "外資大買_only": 外資大買[:15],
        "投信大買_only": 投信大買[:15],
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

    print("=== Phase 22 法人籌碼測試 ===\n")

    r = 找今日強訊號()
    print(f"資料日：{r['日期']}")
    print(f"\n🔥 外資+投信『同向強買』{len(r['強共識買'])} 檔（前 10）")
    for d in r["強共識買"][:10]:
        print(f"  {d['symbol']:<8} {d['name']:<10} "
              f"外資 {d['外資']/1000:>+8.0f} 張 / "
              f"投信 {d['投信']/1000:>+6.0f} 張")

    print(f"\n💀 外資+投信『同向強賣』{len(r['強共識賣'])} 檔")
    for d in r["強共識賣"][:10]:
        print(f"  {d['symbol']:<8} {d['name']:<10} "
              f"外資 {d['外資']/1000:>+8.0f} 張 / "
              f"投信 {d['投信']/1000:>+6.0f} 張")

    print(f"\n📈 外資大買（投信沒同步）TOP 10")
    for d in r["外資大買_only"][:10]:
        print(f"  {d['symbol']:<8} {d['name']:<10} 外資 {d['外資']/1000:>+8.0f} 張")

    # 你關心的標的
    print(f"\n=== 你今天 LIS 推的標的 vs 法人籌碼 ===")
    關心 = ["2890", "00942B", "00910", "00911", "00861", "00935",
            "2330", "2327", "2492", "2408", "2344"]
    for sym in 關心:
        記 = r.get("強共識買", []) + r.get("強共識賣", []) + \
             r.get("外資大買_only", []) + r.get("投信大買_only", [])
        d = next((x for x in 記 if x["symbol"] == sym), None)
        if not d:
            # 抓單檔
            data = 抓今日法人籌碼(datetime.now().strftime("%Y%m%d"))
            d = data.get("資料", {}).get(sym)
        if d:
            外 = d["外資"] / 1000
            投 = d["投信"] / 1000
            標 = (f"🔥 共識買" if 外 > 1000 and 投 > 500
                  else f"💀 共識賣" if 外 < -1000 and 投 < -500
                  else f"📈 外資買" if 外 > 1000
                  else f"📉 外資賣" if 外 < -1000
                  else f"⚪ 平淡")
            print(f"  {sym:<8} 外資 {外:>+8.0f} 張 / 投信 {投:>+6.0f} 張 {標}")
        else:
            print(f"  {sym:<8} 無資料（可能上櫃 TPEX）")
