"""
圖片上傳模組（Phase 2.6 + 防呆）
- 兩個圖床 fallback：catbox.moe + 0x0.st
- timeout 5 秒（防止圖床掛掉時卡死整個流程）
- Fail-fast：一旦在同一次執行內偵測到兩家都掛，後續呼叫直接 return None
  讓 main.py 走 Flex 文字版 fallback，整個流程仍能完成。
"""
import sys
from typing import Optional

import requests


HEADERS = {
    "User-Agent": "LIS-Investment-Bot/1.0",
}

# 上傳超時改成 5 秒（30 秒太長，會拖死整個排程）
TIMEOUT = 5

# 同一次執行內，如偵測到兩家圖床都掛，這個 flag 設 True，後續直接跳過
_全部掛了 = False


def 上傳到_catbox(png_bytes: bytes,
                   檔名: str = "lis_chart.png") -> Optional[str]:
    try:
        resp = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (檔名, png_bytes, "image/png")},
            timeout=TIMEOUT,
        )
        if resp.status_code == 200 and resp.text.strip().startswith("http"):
            return resp.text.strip()
        print(f"[uploader] catbox HTTP {resp.status_code}", file=sys.stderr)
    except Exception as e:
        print(f"[uploader] catbox 失敗：{type(e).__name__}", file=sys.stderr)
    return None


def 上傳到_0x0(png_bytes: bytes,
                檔名: str = "lis_chart.png") -> Optional[str]:
    try:
        resp = requests.post(
            "https://0x0.st",
            headers=HEADERS,
            files={"file": (檔名, png_bytes, "image/png")},
            timeout=TIMEOUT,
        )
        if resp.status_code == 200 and resp.text.strip().startswith("http"):
            return resp.text.strip()
        print(f"[uploader] 0x0.st HTTP {resp.status_code}", file=sys.stderr)
    except Exception as e:
        print(f"[uploader] 0x0.st 失敗：{type(e).__name__}", file=sys.stderr)
    return None


def 上傳圖片(png_bytes: bytes, 檔名: str = "lis_chart.png") -> Optional[str]:
    """
    先試 catbox，再試 0x0.st。
    一旦同一次執行偵測到兩家都掛，後續呼叫直接 return None（節省時間）。
    """
    global _全部掛了
    if _全部掛了:
        print("[uploader] 跳過上傳（本次執行先前已偵測到圖床全掛）",
              file=sys.stderr)
        return None

    url = 上傳到_catbox(png_bytes, 檔名)
    if url:
        return url

    url = 上傳到_0x0(png_bytes, 檔名)
    if url:
        return url

    # 兩家都掛
    _全部掛了 = True
    print("[uploader] ⚠️ 所有圖床都失敗，本次執行後續會走 Flex 文字版 fallback",
          file=sys.stderr)
    return None


def 重置失敗旗標() -> None:
    """主程式開頭可呼叫，重置 fail-fast 旗標。"""
    global _全部掛了
    _全部掛了 = False


if __name__ == "__main__":
    from . import chart_generator
    png = chart_generator.生成Enjoy圓環(31.3, "HOLD")
    print(f"PNG 大小：{len(png):,} bytes")
    print(f"上傳結果：{上傳圖片(png, 'test.png')}")
