"""
即時持股快照（隨時雙擊看 LINE）
跑一次推「💼 持股總覽 + ⚡ 紀律警示」兩張卡到 LINE。

不檢查市場時間、不檢查去重（每次都推）。
適合「我現在就想看」的時刻。

執行：
  雙擊 即時查持股.bat
  或 .venv\\Scripts\\python.exe instant_snapshot.py
"""
import sys
import traceback
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))

from dotenv import load_dotenv
load_dotenv(專案根.parent / "API" / ".env")

from modules import (capital_planner, portfolio_tracker,
                     forex, flex_builder, line_push)


def 主流程() -> int:
    開始 = datetime.now()
    print(f"=== 即時持股快照 [{開始:%Y-%m-%d %H:%M:%S}] ===")

    cfg = capital_planner.載入資金設定()
    固定匯率 = cfg.get("currency_rates", {}).get("USD_TWD", 32.0)
    匯率資訊 = forex.取得USD_TWD匯率(fallback=固定匯率)
    匯率 = 匯率資訊["rate"]
    print(f"💱 USD/TWD = {匯率} ({匯率資訊['source']})")

    print("\n抓即時股價 + 算損益（含 19+ 檔，約 30 秒）...")
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=匯率)

    總 = 真倉["總計"]
    台 = 真倉["台股小計"]
    美 = 真倉["美股小計"]
    print(f"\n總損益：NT$ {總['損益_twd']:+,.0f} ({總['損益率_pct']:+.2f}%)")
    print(f"  🇹🇼 台股 {台['檔數']} 檔: NT$ {台['市值_twd']:,.0f} ({台['損益率_pct']:+.2f}%)")
    print(f"  🇺🇸 美股 {美['檔數']} 檔: $ {美['市值_usd']:,.2f} (≈ NT$ {美['市值_twd']:,.0f}, {美['損益率_pct']:+.2f}%)")

    # 列警示
    警示 = 真倉["警示"]
    for 類, 清單 in [("達停利 🎯", 警示["達停利"]),
                     ("破停損 💀", 警示["破停損"]),
                     ("接近停利 📈", 警示["接近停利"]),
                     ("接近停損 📉", 警示["接近停損"])]:
        if 清單:
            print(f"\n{類}：{len(清單)} 檔")
            for r in 清單:
                print(f"  {r['symbol']} ({r.get('name','')[:10]}) "
                      f"{r['pnl_pct']:+.2f}% / 損益 NT$ {r['pnl_twd']:+,.0f}")

    # 建卡
    持股總覽卡 = flex_builder.建構持股總覽卡(真倉)
    真倉警示卡 = flex_builder.建構真倉警示卡(真倉)

    內容 = []
    if 持股總覽卡:
        內容.append(持股總覽卡)
    if 真倉警示卡:
        內容.append(真倉警示卡)

    if not 內容:
        print("\n⚠️ 沒有持股資料，跳過推播")
        return 0

    carousel = {"type": "carousel", "contents": 內容}
    alt = (f"📸 即時持股快照 — {總['損益率_pct']:+.2f}% "
           f"NT$ {總['市值_twd']:,.0f} {datetime.now():%H:%M}")

    print(f"\n推送 {len(內容)} 卡到 LINE...")
    try:
        line_push.推播Flex訊息(替代文字=alt, flex內容=carousel)
        print("✅ 推播成功！打開 LINE 看 📱")
    except Exception as e:
        print(f"❌ 推播失敗：{e}")
        traceback.print_exc()
        return 1

    耗時 = (datetime.now() - 開始).total_seconds()
    print(f"\n=== 完成（耗時 {耗時:.0f} 秒）===")
    return 0


if __name__ == "__main__":
    sys.exit(主流程())
