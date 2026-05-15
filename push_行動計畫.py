"""推 4 週交易行動計畫 carousel 到 LINE"""
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

from modules import line_push, flex_builder

C = flex_builder.C
文字 = flex_builder.文字
分隔線 = flex_builder.分隔線


def 卡_現況():
    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("📊 你現在的狀況", size="lg",
                 color=C["text_main"], weight="bold"),
            文字("基於 LIS 24+ Phase 分析", size="xxs", color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())
    狀況 = [
        ("總資產", "NT$ 491,111"),
        ("持股市值", "NT$ 322,984 / 25 檔"),
        ("現金", "NT$ 171,500"),
        ("閒錢比", "34.2% / 目標 35%"),
        ("可動用彈藥", "NT$ 0 ⚠️"),
        ("模式", "🟡 接近底線"),
    ]
    for k, v in 狀況:
        內容.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字(k, size="xs", color=C["text_dim"], flex=2),
                文字(v, size="xs", color=C["text_main"],
                     align="end", flex=4),
            ],
        })
    內容.append(分隔線())
    內容.append(文字("💡 核心策略", size="xs",
                     color=C["bull"], weight="bold"))
    內容.append(文字("不加新資金，賣低 Kelly 換高 Kelly",
                     size="xxs", color=C["text_dim"], wrap=True))
    return _bubble(內容)


def 卡_Week1():
    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("📅 Week 1 (5/15-5/21)", size="lg",
                 color=C["text_main"], weight="bold"),
            文字("釋出 NT$ 26K + 重新配置", size="xxs",
                 color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())
    內容.append(文字("🪓 賣（Kelly 0%）", size="sm",
                     color=C["bear"], weight="bold"))
    賣 = [
        "1. 00882 中國 300 股 → +4,878",
        "2. 00920 ESG 200 股 → +5,278",
        "3. 2891 中信金 300 股 → +16,440",
        "4. AMD/GLW/ADBE 各 1 股 → +28K",
    ]
    for s in 賣:
        內容.append(文字(f"  {s}", size="xxs",
                         color=C["text_dim"], wrap=True))
    內容.append(分隔線())
    內容.append(文字("🎯 買（高 Kelly）", size="sm",
                     color=C["bull"], weight="bold"))
    買 = [
        "A. 00910 太空 +200 股 = NT$ 14,700",
        "B. 00942B 公債 +200 股 = NT$ 2,856",
        "C. 1425 福懋 +50 股（觀察試水）",
    ]
    for b in 買:
        內容.append(文字(f"  {b}", size="xxs",
                         color=C["text_dim"], wrap=True))
    return _bubble(內容)


def 卡_Week2():
    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("📅 Week 2 (5/22-5/28)", size="lg",
                 color=C["text_main"], weight="bold"),
            文字("大筆持股調節 NT$ 52K", size="xxs",
                 color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())
    內容.append(文字("🪓 賣（大筆）", size="sm",
                     color=C["bear"], weight="bold"))
    內容.append(文字("• SATL 150 股 → NT$ 38,296",
                     size="xxs", color=C["text_dim"], wrap=True))
    內容.append(文字("• IREN 8 股 → NT$ 13,911",
                     size="xxs", color=C["text_dim"], wrap=True))
    內容.append(分隔線())
    內容.append(文字("🎯 加碼 4 大 Kelly", size="sm",
                     color=C["bull"], weight="bold"))
    內容.append(文字("• 00861 通訊 +150 股 (Kelly 13.09%)",
                     size="xxs", color=C["text_dim"], wrap=True))
    內容.append(文字("• 00911 半導體 +200 股 (Kelly 12.86%)",
                     size="xxs", color=C["text_dim"], wrap=True))
    內容.append(文字("• 00935 新科技 +150 股 (Kelly 12.19%)",
                     size="xxs", color=C["text_dim"], wrap=True))
    內容.append(文字("⚠️ 等過熱回檔再進", size="xxs",
                     color=C["bear"], wrap=True))
    return _bubble(內容)


def 卡_Strategy_A_監測():
    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("🎯 Strategy A 監測點", size="lg",
                 color=C["text_main"], weight="bold"),
            文字("達 +15% 落袋 50%", size="xxs", color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())
    監測 = [
        ("00910 太空", "78.5", "你均 68.29"),
        ("00911 半導體", "59.9", "你均 52.12"),
        ("00935 新科技", "63.8", "你均 55.44"),
        ("2890 永豐金", "35.9", "你均 31.25"),
        ("00861 通訊", "87.8", "你均 76.38"),
    ]
    for sym, target, base in 監測:
        內容.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "paddingTop": "xs",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(sym, size="sm",
                             color=C["text_main"], weight="bold", flex=4),
                        文字(f"→ {target}", size="sm",
                             color=C["bull"], align="end", flex=3),
                    ],
                },
                文字(base, size="xxs",
                     color=C["text_subtle"]),
            ],
        })
    return _bubble(內容)


def 卡_預期績效():
    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("📊 預期績效（誠實版）", size="lg",
                 color=C["text_main"], weight="bold"),
            文字("達標 +35% 的 3 個情境", size="xxs",
                 color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())

    內容.append(文字("🟢 樂觀情境", size="sm",
                     color=C["bull"], weight="bold"))
    內容.append(文字("Strategy A 3 次命中 + 黑天鵝重押",
                     size="xxs", color=C["text_dim"], wrap=True))
    內容.append(文字("→ +30-35% ✅ 達標",
                     size="sm", color=C["bull"], weight="bold"))
    內容.append(分隔線())

    內容.append(文字("⚪ 基準情境（最可能）", size="sm",
                     color=C["text_main"], weight="bold"))
    內容.append(文字("DCA + 2 次 Strategy A",
                     size="xxs", color=C["text_dim"], wrap=True))
    內容.append(文字("→ +22-25%",
                     size="sm", color=C["text_main"], weight="bold"))
    內容.append(分隔線())

    內容.append(文字("🔴 保守情境", size="sm",
                     color=C["bear"], weight="bold"))
    內容.append(文字("大盤回檔 -10%",
                     size="xxs", color=C["text_dim"], wrap=True))
    內容.append(文字("→ +10-15%（仍贏定存）",
                     size="xxs", color=C["text_dim"], wrap=True))
    return _bubble(內容)


def 卡_明天行動():
    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("🌅 明天（5/15）就做這 2 件事", size="lg",
                 color=C["bull"], weight="bold"),
            文字("簡單照做不思考", size="xxs", color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())

    內容.append(文字("1️⃣ 開盤後", size="sm",
                     color=C["accent"], weight="bold"))
    內容.append(文字("  掛賣 00882 300 股（盤後 -0.05）",
                     size="xs", color=C["text_main"], wrap=True))
    內容.append(文字("  掛賣 00920 200 股（盤後 -0.05）",
                     size="xs", color=C["text_main"], wrap=True))
    內容.append(分隔線())

    內容.append(文字("2️⃣ 14:30 盤後零股", size="sm",
                     color=C["accent"], weight="bold"))
    內容.append(文字("  確認上述成交，釋出 ~NT$ 10K",
                     size="xs", color=C["text_main"], wrap=True))
    內容.append(分隔線())

    內容.append(文字("⚠️ 不要做的事", size="xs",
                     color=C["bear"], weight="bold"))
    內容.append(文字("• 不買任何新股（彈藥已用）",
                     size="xxs", color=C["text_dim"], wrap=True))
    內容.append(文字("• 不追過熱（00911/00935/00830）",
                     size="xxs", color=C["text_dim"], wrap=True))
    內容.append(文字("• 不違反 35% 閒錢底線",
                     size="xxs", color=C["text_dim"], wrap=True))
    return _bubble(內容)


def _bubble(內容):
    return {
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "12px",
            "contents": 內容,
        },
    }


if __name__ == "__main__":
    cards = [
        卡_現況(),
        卡_明天行動(),
        卡_Week1(),
        卡_Week2(),
        卡_Strategy_A_監測(),
        卡_預期績效(),
    ]
    car = {"type": "carousel", "contents": cards}
    alt = "🎯 Ryan 4 週行動計畫 — 達 +35% 目標"
    line_push.推播Flex訊息(替代文字=alt, flex內容=car)
    print(f"✅ 已推 LINE：{alt}")
