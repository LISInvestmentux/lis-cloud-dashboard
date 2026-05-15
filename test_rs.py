"""
相對強度單元測試（Phase 7.2）
"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))

from modules import relative_strength as rs

print("=== 相對強度單元測試 ===\n")

# 情境：台股大盤 20 日漲 5%，美股大盤 20 日漲 3%
大盤_台 = 5.0
大盤_美 = 3.0

測試案例 = [
    # (描述, symbol, 個股漲幅, region, 期望標籤)
    ("台股強勢（漲 10% vs 大盤 5%）", "2330.TW", 10.0, "tw_stocks", "強勢"),
    ("台股中性（漲 6% vs 大盤 5%）",  "0050.TW", 6.0,  "tw_etfs",   "中性"),
    ("台股弱勢（漲 1% vs 大盤 5%）",  "2317.TW", 1.0,  "tw_stocks", "弱勢"),
    ("美股強勢（漲 8% vs S&P 3%）",   "TSLA",    8.0,  "us",        "強勢"),
    ("美股弱勢（漲 -2% vs S&P 3%）",  "INTC",    -2.0, "us",        "弱勢"),
    ("資料不足（個股 None）",        "TEST",    None, "tw_stocks", "資料不足"),
    ("台股邊界（+3pp 剛好強勢）",     "AAA.TW", 8.0,  "tw_stocks", "強勢"),
    ("台股邊界（-3pp 剛好弱勢）",     "BBB.TW", 2.0,  "tw_stocks", "弱勢"),
]

過 = 0
敗 = 0
for 描述, sym, 漲幅, region, 期望 in 測試案例:
    結果 = rs.計算單檔RS(漲幅, 大盤_台, 大盤_美, sym, region=region)
    符合 = 結果["rs_label"] == 期望
    狀態 = "✅" if 符合 else "❌"
    if 符合: 過 += 1
    else: 敗 += 1
    print(f"  {狀態} {描述}")
    print(f"     rs_20d={結果.get('rs_20d')}  標籤={結果['rs_label']}  "
          f"vs {結果['market_index']}({結果['market_20d_pct']}%)")

print(f"\n=== 通過 {過} / {過+敗} ===")
