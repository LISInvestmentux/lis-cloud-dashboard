"""推「跨來源共識」carousel 到 LINE"""
import sys, json
from collections import defaultdict
from pathlib import Path
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))
from dotenv import load_dotenv
load_dotenv(專案根.parent / "API" / ".env")

from modules import line_push, flex_builder, fugle_market

C = flex_builder.C
文字 = flex_builder.文字
分隔線 = flex_builder.分隔線


def 跨來源共識排行(min_sources: int = 2) -> list:
    data = json.loads((專案根.parent / "數據" /
                       "external_signal_history.json").read_text(encoding="utf-8"))
    sym_info = defaultdict(lambda: {"sources": set(), "說明": [],
                                     "BUY_count": 0, "SELL_count": 0})
    for s in data.get("訊號", []):
        sym = s.get("symbol", "")
        if not sym or sym in ("NONE", ""):
            continue
        sym_info[sym]["sources"].add(s.get("來源", ""))
        if s.get("類型") == "BUY":
            sym_info[sym]["BUY_count"] += 1
        elif s.get("類型") == "SELL":
            sym_info[sym]["SELL_count"] += 1
        if s.get("說明"):
            sym_info[sym]["說明"].append(s["說明"][:30])

    結果 = []
    for sym, info in sym_info.items():
        if len(info["sources"]) >= min_sources:
            結果.append({
                "symbol": sym,
                "來源數": len(info["sources"]),
                "來源清單": sorted(info["sources"]),
                "BUY": info["BUY_count"],
                "SELL": info["SELL_count"],
                "代表說明": info["說明"][0] if info["說明"] else "",
            })
    結果.sort(key=lambda r: -r["來源數"])
    return 結果


def 建構共識卡(共識: list) -> dict:
    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("🏆 跨來源共識排行", size="xl",
                 color=C["text_main"], weight="bold"),
            文字(f"305 訊號 / 7 來源 / {datetime.now():%H:%M}",
                 size="xxs", color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())

    for r in 共識[:15]:
        # 抓現價
        try:
            q = fugle_market.即時報價_fallback(r["symbol"])
            現價 = q.get("close") if q else None
        except Exception:
            現價 = None

        色 = (C["bear"] if r["來源數"] >= 4 else
              C["bull"] if r["來源數"] >= 3 else
              C["wait"])

        內容.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "paddingTop": "xs",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"⭐ {r['symbol']}", size="sm",
                             color=色, weight="bold", flex=4),
                        文字(f"{r['來源數']} 來源", size="xs",
                             color=色, align="center", flex=3),
                        文字(f"{現價:.2f}" if 現價 else "-",
                             size="xs", color=C["text_main"],
                             align="end", weight="bold", flex=2),
                    ],
                },
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"買{r['BUY']}/賣{r['SELL']}",
                             size="xxs", color=C["text_dim"], flex=3),
                        文字(", ".join(s[:5] for s in r["來源清單"][:3]),
                             size="xxs", color=C["text_subtle"],
                             align="end", flex=8),
                    ],
                },
            ],
        })

    內容.append(分隔線())
    內容.append(文字("⚠️ 反 CC 提醒", size="xs",
                     color=C["bear"], weight="bold"))
    內容.append(文字("• 共識 = 不一定對，可能是從眾偏差",
                     size="xxs", color=C["text_subtle"], wrap=True))
    內容.append(文字("• 群組 weight 0.1，當參考不當決策",
                     size="xxs", color=C["text_subtle"], wrap=True))
    內容.append(文字("• 配 Kelly + 順勢 + 法人 多訊號交叉",
                     size="xxs", color=C["text_subtle"], wrap=True))

    return {
        "type": "bubble", "size": "giga",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": 內容,
        },
    }


if __name__ == "__main__":
    共識 = 跨來源共識排行(min_sources=2)
    print(f"🏆 跨來源共識 {len(共識)} 檔（>=2 來源）\n")
    for r in 共識[:20]:
        print(f"  {r['symbol']:<14} {r['來源數']} 來源 "
              f"買 {r['BUY']}/賣 {r['SELL']} "
              f"— {', '.join(r['來源清單'][:3])}")

    卡 = 建構共識卡(共識)
    alt = f"🏆 LIS 跨來源共識 — {len(共識)} 檔 / 305 訊號"
    line_push.推播Flex訊息(替代文字=alt, flex內容=卡)
    print(f"\n✅ 已推 LINE：{alt}")
