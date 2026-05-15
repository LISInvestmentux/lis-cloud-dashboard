"""
Phase 2.5 第二輪：
- 大盤指標卡（新做）
- 同時用兩個主題（dark / febforest）各推一份 Carousel
讓使用者比較風格
"""
import sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules import fear_greed, technical, enjoy_index, flex_builder, line_push


print("[1] 抓 Fear & Greed...")
情緒 = fear_greed.取得恐慌貪婪指數()

print("[2] 抓 6 大盤指標...")
cfg = technical.載入觀察清單()
指數結果 = technical.掃描清單(cfg["indices"]["items"])

print("[3] 計算 Enjoy Index（個股部分仍留空，只測前兩張卡）...")
指數 = enjoy_index.計算Enjoy指數(情緒, 指數結果, 全部個股分析=[])
日期文字 = datetime.now().strftime("%Y/%m/%d (%a)")

# 對兩個主題各組一份
for 主題 in ["febforest", "dark"]:
    print(f"\n[4-{主題}] 切換到「{主題}」主題並推播...")
    flex_builder.切換主題(主題)

    carousel = {
        "type": "carousel",
        "contents": [
            flex_builder.建構Enjoy主卡(指數, 日期文字),
            flex_builder.建構大盤指標卡(指數結果),
        ],
    }

    替代文字 = f"L.I.S 報表 ({主題} 風格) — Enjoy {指數['總分']}"
    line_push.推播Flex訊息(替代文字=替代文字, flex內容=carousel)
    print(f"    ✅ 已推播 {主題} 版")

print("\n🎨 兩個主題的卡片都已推播，請開 LINE 比較！")
