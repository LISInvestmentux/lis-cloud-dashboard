"""一次性：推 ARK 集中計畫卡到 LINE"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))

from dotenv import load_dotenv
load_dotenv(專案根.parent / "API" / ".env")

from modules import concentration_planner as cp, line_push


if __name__ == "__main__":
    計畫 = cp.產生集中計畫(目標檔數=8, 目標報酬_pct=35, 時程_月=7)

    print(f"✅ 保留 {len(計畫['保留'])} 檔：")
    for h in 計畫["保留"]:
        k = h["評分"].get("Kelly_pct")
        k_s = f"{k:.1f}%" if k else "n/a"
        print(f"  {h['symbol']:<12} K {k_s:<6} +{h['加碼股數']:>4} 股 "
              f"(NT$ {h['加碼金_twd']:>7,}) 目標 {h['目標佔比_pct']:.1f}%")

    print(f"\n🪓 賣出 {len(計畫['賣出'])} 檔，釋出 NT$ {計畫['釋出資金_twd']:,.0f}")
    for h in 計畫["賣出"]:
        k = h["評分"].get("Kelly_pct")
        k_s = f"{k:.1f}%" if k else "n/a"
        print(f"  {h['symbol']:<12} K {k_s:<6} "
              f"{h['未實現損益_pct']:+5.1f}%  NT$ {h['市值_twd']:>9,.0f}")

    print(f"\n📊 預估 7 月後 {計畫['預估7月後報酬_pct']:+.1f}% "
          f"(NT$ +{計畫['預估7月後報酬_twd']:,.0f})")
    print(f"   達標 +{計畫['目標報酬_pct']:.0f}% 機率：{計畫['達標機率']}")

    # 推到 LINE
    卡 = cp.建構集中計畫卡(計畫)
    alt = (f"🎯 ARK 集中計畫 — 留 {len(計畫['保留'])} 賣 {len(計畫['賣出'])} "
           f"/ 預估 {計畫['預估7月後報酬_pct']:+.1f}%")
    line_push.推播Flex訊息(替代文字=alt, flex內容=卡)
    print("\n✅ 已推到 LINE 📱")
