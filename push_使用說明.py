"""推 LIS 快速上手 carousel 到 LINE"""
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


def 卡_每日流程():
    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("📅 每日標準流程", size="lg",
                 color=C["text_main"], weight="bold"),
            文字("從 8AM 到收盤", size="xxs", color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())
    流程 = [
        ("🌅 08:00", "Task Scheduler 自動跑"),
        ("📱 08:30", "看 LINE 12+ 張卡"),
        ("👀 09:00", "決定今天動作"),
        ("📈 09:00-13:30", "紀律掛單"),
        ("📊 13:30", "雙擊『即時查持股』"),
        ("🎯 收盤後", "雙擊『即時查決策』"),
    ]
    for t, a in 流程:
        內容.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字(t, size="xs", color=C["accent"], flex=3),
                文字(a, size="xs", color=C["text_main"],
                     align="end", flex=5),
            ],
        })
    內容.append(分隔線())
    內容.append(文字("💡 核心觀念", size="xs",
                     color=C["bull"], weight="bold"))
    內容.append(文字("• 看 LIS 推播 不要看別人",
                     size="xxs", color=C["text_dim"], wrap=True))
    內容.append(文字("• DCA 6000 自動扣不要中斷",
                     size="xxs", color=C["text_dim"], wrap=True))
    內容.append(文字("• 紀律 > 直覺",
                     size="xxs", color=C["text_dim"], wrap=True))
    return _bubble(內容)


def 卡_看LINE卡解讀():
    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("📱 LINE 卡片解讀", size="lg",
                 color=C["text_main"], weight="bold"),
            文字("5 種主要卡片", size="xxs", color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())
    卡片 = [
        ("🎯 全息儀表板", "看現況 + 5 SOP + 供需 + 策略池"),
        ("⚡ 即時決策", "Kelly + 彈藥 + 該掛什麼單"),
        ("🌐 主情報", "台美/法人/基本面/新聞 4 維"),
        ("🏆 跨來源共識", "305 訊號分析誰被多群提"),
        ("🎯 策略池", "8 策略入選清單"),
    ]
    for n, d in 卡片:
        內容.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "contents": [
                文字(n, size="sm", color=C["accent"], weight="bold"),
                文字(f"   {d}", size="xxs",
                     color=C["text_dim"], wrap=True),
            ],
        })
    return _bubble(內容)


def 卡_等級判讀():
    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("🎯 等級顏色判讀", size="lg",
                 color=C["text_main"], weight="bold"),
            文字("即時決策卡的標籤", size="xxs", color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())
    等級 = [
        ("🚨 ALL IN", C["bear"], "黑天鵝級 5+ 指標命中"),
        ("🔥 重押", C["bull"], "Kelly + 訊號雙強"),
        ("⚡ 加碼", C["bull"], "中強訊號"),
        ("🚀 順勢", C["bull"], "趨勢確認可加"),
        ("📈 紀律", C["text_main"], "平時分批"),
        ("🟡 PASS", C["wait"], "彈藥不足 / 過熱"),
    ]
    for emoji_name, color, desc in 等級:
        內容.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字(emoji_name, size="sm", color=color,
                     weight="bold", flex=3),
                文字(desc, size="xxs", color=C["text_dim"],
                     align="end", flex=5),
            ],
        })
    return _bubble(內容)


def 卡_BAT_工具():
    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("🛠️ 12 個 .bat 工具", size="lg",
                 color=C["text_main"], weight="bold"),
            文字("D:/LIS股票投資系統/程式碼/", size="xxs",
                 color=C["text_dim"], wrap=True),
        ],
    })
    內容.append(分隔線())
    內容.append(文字("⭐ 每日核心", size="xs",
                     color=C["bull"], weight="bold"))
    日常 = [
        "即時查持股.bat (P&L)",
        "即時查決策.bat (訊號+Kelly)",
        "LIS主情報中心.bat (4 維)",
        "策略池掃描.bat (8 策略)",
    ]
    for b in 日常:
        內容.append(文字(f"  • {b}", size="xxs",
                         color=C["text_dim"], wrap=True))
    內容.append(分隔線())
    內容.append(文字("📅 每週/月", size="xs",
                     color=C["accent"], weight="bold"))
    每週 = [
        "集中模式計畫.bat",
        "處理對話TXT.bat (4 群)",
        "處理社群截圖.bat",
        "LIS全套晨報.bat (一次跑完)",
    ]
    for b in 每週:
        內容.append(文字(f"  • {b}", size="xxs",
                         color=C["text_dim"], wrap=True))
    return _bubble(內容)


def 卡_紀律3條():
    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("🚨 三大紀律", size="lg",
                 color=C["text_main"], weight="bold"),
            文字("絕對不能破", size="xxs", color=C["bear"]),
        ],
    })
    內容.append(分隔線())

    內容.append(文字("1. 35% 閒錢底線", size="sm",
                     color=C["bear"], weight="bold"))
    內容.append(文字("現金 / 總資產 ≥ 35%",
                     size="xxs", color=C["text_dim"], wrap=True))
    內容.append(文字("（黑天鵝命中 4+ 才可動）",
                     size="xxs", color=C["text_subtle"], wrap=True))
    內容.append(分隔線())

    內容.append(文字("2. 單檔 < 20%", size="sm",
                     color=C["bear"], weight="bold"))
    內容.append(文字("單一股票市值 ≤ 總資產 20%",
                     size="xxs", color=C["text_dim"], wrap=True))
    內容.append(分隔線())

    內容.append(文字("3. Strategy A", size="sm",
                     color=C["bear"], weight="bold"))
    內容.append(文字("達 +15% 落袋 50%",
                     size="xxs", color=C["text_dim"], wrap=True))
    內容.append(文字("破 -5% 全停損",
                     size="xxs", color=C["text_dim"], wrap=True))

    return _bubble(內容)


def 卡_3個必做習慣():
    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("💡 3 個必做習慣", size="lg",
                 color=C["text_main"], weight="bold"),
            文字("達標 +35% 的關鍵", size="xxs", color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())

    習慣 = [
        ("1. 每天 8:30", "看 LIS 推播 12+ 張卡",
         "知道今天閒錢比 / 訊號 / 警示"),
        ("2. 每週日", "雙擊『處理對話TXT.bat』",
         "累積外部訊號資料"),
        ("3. 每月 1 號", "對比 LIS 預估 vs 實際",
         "看信任分變化 / 滾動修正"),
    ]
    for t, a, d in 習慣:
        內容.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "paddingTop": "sm",
            "contents": [
                文字(t, size="sm", color=C["accent"], weight="bold"),
                文字(a, size="xs", color=C["text_main"]),
                文字(d, size="xxs",
                     color=C["text_subtle"], wrap=True),
            ],
        })
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
        卡_每日流程(),
        卡_看LINE卡解讀(),
        卡_等級判讀(),
        卡_BAT_工具(),
        卡_紀律3條(),
        卡_3個必做習慣(),
    ]
    car = {"type": "carousel", "contents": cards}
    alt = "📖 LIS 快速上手指南 — 6 張卡"
    line_push.推播Flex訊息(替代文字=alt, flex內容=car)
    print(f"✅ 已推 LINE：{alt}")
