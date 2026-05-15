"""驗證各發行公司 ETF NAV API 可行性"""
import sys
import requests
import urllib3
urllib3.disable_warnings()
sys.stdout.reconfigure(encoding="utf-8")

H = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}

測試 = [
    ("元大投信 0050",
     "https://www.yuantaetfs.com/api/Quote/IndexInfo?fundId=1066",
     "GET"),
    ("元大投信 (alternative)",
     "https://www.yuantaetfs.com/api/api/iopv/ETFListwithIopv",
     "GET"),
    ("富邦投信 00662",
     "https://websys.fubon.com/wcontent/etf/ETF_IOPV.aspx",
     "GET"),
    ("國泰投信 00830",
     "https://www.cathayetfs.com/api/etf/iopv?stock_no=00830",
     "GET"),
    ("群益投信 00919",
     "https://www.capitalfund.com.tw/api/etf-iopv",
     "GET"),
    ("TWSE OpenAPI ETF",
     "https://openapi.twse.com.tw/v1/exchangeReport/ETF",
     "GET"),
]

for name, url, method in 測試:
    print(f"\n=== {name} ===")
    print(f"URL: {url}")
    try:
        r = requests.get(url, headers=H, timeout=10, verify=False)
        print(f"狀態：{r.status_code}  Content-Type: {r.headers.get('content-type', '')[:50]}")
        if r.status_code == 200:
            text = r.text[:400]
            print(f"前 400 字：{text}")
    except Exception as e:
        print(f"失敗：{type(e).__name__}: {str(e)[:80]}")
