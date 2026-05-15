"""推美股焦點卡（Phase 32.7）— 晚上美股時段用"""
import sys
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

from modules import us_focus, line_push, flex_builder


C = flex_builder.C
文字 = flex_builder.文字
分隔線 = flex_builder.分隔線


def 建構美股焦點卡(r: dict) -> dict:
    s = r["統計"]
    彈 = r["彈藥資訊"]

    contents = []
    # Header
    contents.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("🇺🇸 美股焦點", size="xl",
                 color=C["text_main"], weight="bold"),
            文字(f"持股 {s['持股數']} / 市值 NT$ {s['美股市值_twd']:,.0f}"
                 f" · {datetime.now():%H:%M}",
                 size="xxs", color=C["text_dim"]),
        ],
    })
    contents.append(分隔線())

    # 大盤 + 彈藥
    contents.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字(f"VIX {r['大盤'].get('VIX') or '—'} · F&G "
                 f"{r['大盤'].get('fear_greed') or '—'} · "
                 f"黑天鵝 {r['黑天鵝命中']}/5",
                 size="xxs", color=C["text_subtle"], wrap=True),
            文字(f"💰 可動用 NT$ {彈['可動用彈藥_twd']:,.0f}"
                 f" · {彈['模式emoji']}{彈['模式']}"
                 f" · ARK {r['us_mode']}",
                 size="xxs", color=C["text_dim"], wrap=True),
        ],
    })
    contents.append(分隔線())

    # 持股結果 — 按優先排序
    contents.append(文字(f"📋 已持有 ({s['持股數']} 檔)",
                       size="md", color=C["text_main"], weight="bold"))
    for p in r["持股結果"]:
        # 顏色依動作
        動作 = p["動作"]
        if 動作.startswith("🎯") or 動作.startswith("💀"):
            色 = C["bear"]
        elif 動作.startswith("🔄") or 動作.startswith("📈") or 動作.startswith("📉"):
            色 = C["wait"]
        elif 動作.startswith("🆕"):
            色 = C["bull"]
        else:
            色 = C["text_main"]
        contents.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "sm", "paddingAll": "8px",
            "backgroundColor": C["bg_card_alt"], "cornerRadius": "6px",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"{動作} {p['symbol']}", size="sm",
                             color=色, weight="bold", flex=5),
                        文字(f"{p['pnl_pct']:+.2f}%", size="sm",
                             color=色, align="end", flex=2),
                    ],
                },
                文字((
                        f"位 未掃 · {p['shares']} 股 @ ${p['avg_cost']:.2f}"
                        if p['score'] == 0 else
                        f"位 {p['score']:.0f} · {p['shares']} 股 @ ${p['avg_cost']:.2f}"
                     ),
                     size="xxs", color=C["text_dim"]),
                文字(f"→ {p['理由']}", size="xxs",
                     color=C["text_subtle"], wrap=True),
            ],
        })

    # 新進場候選
    if r["新進場結果"]:
        contents.append(分隔線())
        contents.append(文字(f"🆕 價值區候選 ({len(r['新進場結果'])} 檔)",
                           size="md", color=C["bull"], weight="bold"))
        for c in r["新進場結果"]:
            色 = C["bull"] if c["動作"].startswith("🆕") else C["wait"]
            contents.append({
                "type": "box", "layout": "vertical", "spacing": "xs",
                "margin": "sm",
                "contents": [
                    {
                        "type": "box", "layout": "horizontal",
                        "contents": [
                            文字(f"{c['動作']} {c['symbol']}", size="xs",
                                 color=色, weight="bold", flex=5),
                            文字(f"位 {c['score']:.0f}", size="xxs",
                                 color=C["text_dim"], align="end", flex=2),
                        ],
                    },
                    文字(f"→ {c['理由']}", size="xxs",
                         color=C["text_subtle"], wrap=True),
                ],
            })

    contents.append(分隔線())
    contents.append(文字("💡 ARK 派參考；LIS A +15/-5 仍是主紀律",
                       size="xxs", color=C["text_subtle"], wrap=True))

    return {
        "type": "carousel",
        "contents": [{
            "type": "bubble", "size": "mega",
            "body": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "backgroundColor": C["bg_dark"],
                "paddingAll": "14px",
                "contents": contents,
            },
        }],
    }


if __name__ == "__main__":
    print("跑美股焦點分析...")
    r = us_focus.美股焦點分析()
    car = 建構美股焦點卡(r)
    alt = (f"🇺🇸 美股焦點 — {r['統計']['持股數']} 檔 · "
           f"{datetime.now():%H:%M}")
    line_push.推播Flex訊息(替代文字=alt, flex內容=car)
    print(f"✅ 已推 LINE：{alt}")
