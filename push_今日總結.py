"""推今日 LIS 一日衝刺最終總結到 LINE"""
import sys
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

from modules import line_push, flex_builder

C = flex_builder.C
文字 = flex_builder.文字
分隔線 = flex_builder.分隔線


def 建構總結卡() -> dict:
    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("🚀 LIS 一日衝刺總結", size="xl",
                 color=C["text_main"], weight="bold"),
            文字(f"2026-05-14 · 24 Phase / 305 訊號累積",
                 size="xxs", color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())

    # 完成的關鍵
    內容.append(文字("✅ 今日新增模組（24 個 Phase）",
                     size="sm", color=C["bull"], weight="bold"))
    新模組 = [
        "16 ETF 順勢加碼",
        "17/17.5 智能部位 + 彈藥控管",
        "18 8 年 Kelly DB（49 檔）",
        "19 歷史回測引擎",
        "20 ARK 集中模式",
        "22 法人籌碼 API",
        "22.5 個股順勢突破",
        "23 基本面引擎",
        "24 新聞情緒",
        "25/25.5 策略池 + 台美連動",
        "26 信任分追蹤 + 覆盤",
        "27 外部訊號 + Walk-forward",
        "28 每日調節（ARK 派）",
        "30 LINE TXT 解析（AI + Regex）",
        "31 供需邏輯（億級講師）",
        "32 底部 SOP（Sylvie 派）",
        "33 全息儀表板 + 全套晨報",
    ]
    for m in 新模組:
        內容.append(文字(f"  • {m}", size="xxs",
                         color=C["text_dim"], wrap=True))
    內容.append(分隔線())

    # 資料庫
    內容.append(文字("📊 資料庫", size="sm",
                     color=C["accent"], weight="bold"))
    for db in [
        "Kelly DB: 49 檔（含順勢）",
        "外部訊號: 305 筆",
        "LIS 自家: 7 筆驗證中",
        "法人籌碼: 1316 檔",
        "基本面: 10 檔",
        "新聞情緒: 66 則今日",
    ]:
        內容.append(文字(f"  • {db}", size="xxs",
                         color=C["text_dim"], wrap=True))
    內容.append(分隔線())

    # 跨來源共識
    內容.append(文字("🏆 跨來源共識 TOP 5",
                     size="sm", color=C["bull"], weight="bold"))
    共識 = [
        ("0050.TW", "5 來源", "強買"),
        ("2330", "4 來源", "群內賣多 ⚠️"),
        ("2454 聯發科", "4 來源", "雙向"),
        ("2327 國巨", "3 來源", "被動元件"),
        ("1425 福懋", "2 來源", "新加入 ⭐"),
    ]
    for sym, src, note in 共識:
        內容.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字(f"  {sym}", size="xs", color=C["text_main"], flex=4),
                文字(src, size="xxs", color=C["accent"],
                     align="center", flex=3),
                文字(note, size="xxs", color=C["text_dim"],
                     align="end", flex=3),
            ],
        })
    內容.append(分隔線())

    # 明天起的執行
    內容.append(文字("🌅 明天 8AM 起", size="sm",
                     color=C["bull"], weight="bold"))
    內容.append(文字("Task Scheduler 自動跑：",
                     size="xxs", color=C["text_dim"]))
    for line in [
        "1. main.py（KOL/新聞/Enjoy/ARK 卡）",
        "2. LIS全套晨報.py（5 卡新整合）",
    ]:
        內容.append(文字(f"  {line}", size="xxs",
                         color=C["text_dim"], wrap=True))
    內容.append(分隔線())

    # 累積數字
    內容.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("總工具 .bat", size="xxs", color=C["text_dim"], flex=2),
            文字("12 個", size="sm", color=C["bull"],
                 align="end", weight="bold", flex=2),
        ],
    })
    內容.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("總模組 .py", size="xxs", color=C["text_dim"], flex=2),
            文字("24+ 個", size="sm", color=C["bull"],
                 align="end", weight="bold", flex=2),
        ],
    })
    內容.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("Gemini 月費估", size="xxs", color=C["text_dim"], flex=2),
            文字("NT$ 23-50", size="sm", color=C["bull"],
                 align="end", weight="bold", flex=2),
        ],
    })

    內容.append(分隔線())
    內容.append(文字("💎 心法", size="xs",
                     color=C["bull"], weight="bold"))
    內容.append(文字("「DCA 不停、紀律執行、",
                     size="xxs", color=C["text_main"], wrap=True))
    內容.append(文字("等底部 SOP 5 指標命中 4+ 才重押」",
                     size="xxs", color=C["text_main"], wrap=True))
    內容.append(文字("「強者由系統養出，不主觀預判」",
                     size="xxs", color=C["text_main"], wrap=True))

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
    卡 = 建構總結卡()
    alt = "🚀 LIS 一日衝刺總結 — 24 Phase / 305 訊號"
    line_push.推播Flex訊息(替代文字=alt, flex內容=卡)
    print(f"✅ 已推 LINE：{alt}")
