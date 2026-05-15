"""測試 ETF 即時淨值 + 五檔報價資料源"""
import sys
import json
import requests
import urllib3
from pathlib import Path
urllib3.disable_warnings()  # 關掉 SSL 警告

sys.stdout.reconfigure(encoding="utf-8")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9",
}

print("=" * 70)
print("測試 1：證交所 MIS 即時市價 + 五檔報價（含 0050 / 0050 / 00830）")
print("=" * 70)
url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
params = {
    "ex_ch": "tse_0050.tw|tse_00646.tw|tse_00830.tw|tse_00878.tw",
    "json": "1",
    "delay": "0",
}
try:
    r = requests.get(url, params=params, headers=HEADERS, timeout=10, verify=False)
    print(f"狀態碼：{r.status_code}")
    print(f"Content-Type：{r.headers.get('content-type')}")
    data = r.json()
    print(f"回傳鍵：{list(data.keys())}")
    if "msgArray" in data:
        print(f"股票數：{len(data['msgArray'])}")
        for s in data["msgArray"][:2]:
            print(f"\n  {s.get('n', '')} ({s.get('c', '')})")
            print(f"    市價(z)：{s.get('z', '-')}")
            print(f"    開(o)：{s.get('o', '-')}　高(h)：{s.get('h', '-')}　低(l)：{s.get('l', '-')}")
            print(f"    委買價(b)：{s.get('b', '-')}")
            print(f"    委賣價(a)：{s.get('a', '-')}")
            print(f"    成交量(s)：{s.get('s', '-')}")
            print(f"    時間(tlong)：{s.get('tlong', '-')}")
except Exception as e:
    print(f"  失敗：{e}")
print()

print("=" * 70)
print("測試 2：抓元大投信 ETF 淨值（0050 元大台灣50）")
print("=" * 70)
# 元大投信淨值資訊 API
url2 = "https://www.yuantaetfs.com/api/RetrieveQuote"
try:
    r = requests.post(url2, json={"FundID": "1066"}, headers=HEADERS, timeout=10, verify=False)
    print(f"狀態碼：{r.status_code}")
    print(f"前 300 字：{r.text[:300]}")
except Exception as e:
    print(f"  失敗：{e}")
print()

print("=" * 70)
print("測試 3：嘗試 TWSE OpenAPI ETF 揭露")
print("=" * 70)
url3 = "https://openapi.twse.com.tw/v1/ETFReport/ETFRanking"
try:
    r = requests.get(url3, headers=HEADERS, timeout=10)
    print(f"狀態碼：{r.status_code}")
    print(f"Content-Type：{r.headers.get('content-type')}")
    print(f"前 500 字：{r.text[:500]}")
except Exception as e:
    print(f"  失敗：{e}")
print()

print("=" * 70)
print("測試 4：抓鉅亨網 ETF 淨值頁面（00830 國泰費城半導體）")
print("=" * 70)
url4 = "https://www.cnyes.com/twstock/etf/00830"
try:
    r = requests.get(url4, headers=HEADERS, timeout=10)
    print(f"狀態碼：{r.status_code}")
    print(f"內容大小：{len(r.text)}")
    # 找關鍵字
    for keyword in ["淨值", "NAV", "iopv", "IOPV"]:
        if keyword in r.text:
            idx = r.text.find(keyword)
            print(f"  找到「{keyword}」：{r.text[max(0,idx-50):idx+100]}")
            break
except Exception as e:
    print(f"  失敗：{e}")
