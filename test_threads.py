"""測試 Threads / IG 抓取可行性"""
import sys
import requests
sys.stdout.reconfigure(encoding="utf-8")

H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0",
    "Accept-Language": "zh-TW,en;q=0.9",
}

測試清單 = [
    ("RSSHub 公共-Threads-oldwangstock", "https://rsshub.app/threads/oldwangstock"),
    ("RSSHub 公共-Threads-oldwangstock(.app)", "https://rsshub.app/threads/user/oldwangstock"),
    ("Threads 原頁-oldwangstock", "https://www.threads.com/@oldwangstock"),
    ("Threads 原頁-via threads.net", "https://www.threads.net/@oldwangstock"),
    ("IG 原頁-uncle_stock", "https://www.instagram.com/uncle_stock/"),
    ("IG-via 第三方 (instagram-api)", "https://www.instagram.com/uncle_stock/?__a=1&__d=dis"),
]

for 名, url in 測試清單:
    print(f"=== {名} ===")
    try:
        r = requests.get(url, headers=H, timeout=15, allow_redirects=True)
        print(f"  狀態：{r.status_code}")
        print(f"  Content-Type：{r.headers.get('content-type', '?')[:80]}")
        print(f"  大小：{len(r.text)} bytes")
        # 嘗試找出貼文片段
        text = r.text
        if r.status_code == 200:
            if 'rss' in text[:200].lower() or 'xml' in text[:200].lower():
                print(f"  → 可能是 RSS")
                print(f"  前 600 字：{text[:600]}")
            elif 'application/ld+json' in text:
                print(f"  → HTML 內有結構化資料")
            else:
                # 看看 HTML 看起來像什麼
                print(f"  前 300 字：{text[:300]}")
        else:
            print(f"  → 非 200 回應")
    except Exception as e:
        print(f"  失敗：{type(e).__name__}: {e}")
    print()
