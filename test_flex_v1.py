"""測試 Phase 2.5 Flex Message — Enjoy 主卡"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

import json
from datetime import datetime
from modules import fear_greed, technical, enjoy_index, flex_builder, line_push

print("[1] 抓 Fear & Greed...")
情緒 = fear_greed.取得恐慌貪婪指數()

print("[2] 掃描觀察清單（只抓指數做測試，省時間）...")
cfg = technical.載入觀察清單()
指數結果 = technical.掃描清單(cfg["indices"]["items"])
print(f"     完成 {len(指數結果)} 個指數")

# 為了測試 Enjoy Index 計算，建立簡化版的 region 個股清單（空的也行）
print("[3] 計算 Enjoy Index（個股部分留空，只測情緒卡）...")
指數 = enjoy_index.計算Enjoy指數(情緒, 指數結果, 全部個股分析=[])
print(f"     總分 {指數['總分']}")

print("[4] 建構 Enjoy 主卡...")
卡 = flex_builder.建構Enjoy主卡(指數, datetime.now().strftime("%Y/%m/%d (%a)"))

# 印出 JSON 看看結構
print(json.dumps(卡, ensure_ascii=False, indent=2)[:1000])
print("...(JSON 已截斷預覽)")

print("\n[5] 推播 Flex 主卡到 LINE...")
line_push.推播Flex訊息(
    替代文字=f"L.I.S 每日報表 Enjoy Index {指數['總分']} {指數['建議']}",
    flex內容=卡,
)
print("✅ 推播成功！請開 LINE 看效果")
