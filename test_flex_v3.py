"""
Phase 2.5 第三輪：
- 新主題：febforest_dark（暖×深 混血）
- 新卡：VIX 風險指針卡（放 carousel 最前）
- 現有：Enjoy 主卡 + 大盤指標卡（無 VIX）
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

print("[3] 計算 Enjoy Index...")
指數 = enjoy_index.計算Enjoy指數(情緒, 指數結果, 全部個股分析=[])

# 找 VIX
vix項 = next((r for r in 指數結果
              if (r.get("original_symbol") or r.get("symbol")) == "^VIX"
              and "error" not in r), None)
vix值 = vix項["close"] if vix項 else None
print(f"     VIX = {vix值}")

# 預設主題已是 febforest_dark
日期文字 = datetime.now().strftime("%Y/%m/%d (%a)")

print("[4] 建構 Carousel: 風險指針 + Enjoy + 大盤...")
carousel = {
    "type": "carousel",
    "contents": [
        flex_builder.建構風險指針卡(vix值),
        flex_builder.建構Enjoy主卡(指數, 日期文字),
        flex_builder.建構大盤指標卡(指數結果),
    ],
}

print("[5] 推播到 LINE...")
line_push.推播Flex訊息(
    替代文字=f"L.I.S 報表 — VIX {vix值} Enjoy {指數['總分']}",
    flex內容=carousel,
)
print("✅ 已推播 Febforest Dark 版三張卡片！請開 LINE 看效果")
