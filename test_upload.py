"""測試圖片生成 + 上傳"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules import chart_generator, image_uploader

print("[1] 生成 Enjoy 圓環...")
png1 = chart_generator.生成Enjoy圓環(31.3, "HOLD")
print(f"    PNG: {len(png1):,} bytes")
print("[2] 上傳到圖床...")
url1 = image_uploader.上傳圖片(png1, "enjoy_31.png")
print(f"    URL: {url1}")

print("\n[3] 生成 VIX 半圓...")
png2 = chart_generator.生成VIX半圓(18.92)
print(f"    PNG: {len(png2):,} bytes")
print("[4] 上傳到圖床...")
url2 = image_uploader.上傳圖片(png2, "vix_18.png")
print(f"    URL: {url2}")
