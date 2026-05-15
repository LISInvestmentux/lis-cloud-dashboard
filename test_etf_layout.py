"""測試 ETF 布局建議 — 推到 LINE 看效果"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules import etf_navigator, capital_planner, flex_builder, line_push

print("[1] 算今日可動用子彈（用 portfolio.json 的 Enjoy Index 估）...")
資金 = capital_planner.載入資金設定()
# 用昨日的 Enjoy Index 算
import json
from pathlib import Path
snapshot = Path(r"D:\LIS股票投資系統\數據\daily\2026-05-13.json")
if snapshot.exists():
    with open(snapshot, "r", encoding="utf-8") as f:
        snap = json.load(f)
    enjoy分 = snap["enjoy_index"]["總分"]
else:
    enjoy分 = 30  # 預設 HOLD

規劃 = capital_planner.計算今日資金規劃(enjoy分, 資金)
每檔預算 = min(規劃["單檔上限_twd"], 規劃["今日可動用子彈_twd"] / 5)
print(f"     Enjoy={enjoy分}  子彈={規劃['今日可動用子彈_twd']:,.0f}  每檔約={每檔預算:,.0f}")

print()
print("[2] 抓 ETF 即時行情 + 算建議...")
結果 = etf_navigator.取得今日ETF布局建議(每檔預算_twd=每檔預算, 策略="中性")

print()
print("[3] 組 Flex Carousel...")
預算文字 = f"今日子彈 NT$ {規劃['今日可動用子彈_twd']:,.0f}　每檔預算 NT$ {每檔預算:,.0f}（中性策略）"
carousel = flex_builder.建構ETF布局Carousel(結果, 預算文字=預算文字)
print(f"     {len(carousel['contents'])} 張卡")

print()
print("[4] 推播到 LINE...")
line_push.推播Flex訊息(
    替代文字=f"💎 ETF 布局建議 — {len(結果)} 檔即時五檔報價",
    flex內容=carousel,
)
print("✅ 推播完成！請開 LINE 看")
