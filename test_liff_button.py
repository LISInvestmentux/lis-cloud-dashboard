"""推測試訊息：附 LIFF 開啟按鈕"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

import os
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / "API" / ".env")

from modules import line_push, flex_builder

LIFF_URL = os.getenv("LIFF_URL", "")
print(f"LIFF URL：{LIFF_URL}")

# 建一個漂亮的 Flex 卡，中央大按鈕點開 LIFF
卡 = {
    "type": "bubble",
    "size": "mega",
    "header": flex_builder._卡片Header(
        "📲 L.I.S 持股配置", "從 LINE 直接開啟", "NEW", flex_builder.C["bull"]),
    "body": {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": flex_builder.C["bg_dark"],
        "paddingAll": "24px",
        "spacing": "lg",
        "contents": [
            flex_builder.文字("方舟級體驗已上線！",
                              size="xl", color=flex_builder.C["text_main"],
                              weight="bold", align="center"),
            flex_builder.文字(
                "點下方按鈕，**全螢幕**從 LINE 進入持股配置表單。"
                "填完即時看到建議部位。",
                size="sm", color=flex_builder.C["text_dim"],
                wrap=True, align="center"),
            {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": flex_builder.C["bg_card"],
                "cornerRadius": "12px",
                "paddingAll": "16px",
                "margin": "lg",
                "contents": [
                    flex_builder.文字("✨ 體驗特色", size="xs",
                                       color=flex_builder.C["text_dim"],
                                       weight="bold"),
                    flex_builder.文字("• 全螢幕、不離開 LINE",
                                       size="sm",
                                       color=flex_builder.C["text_main"],
                                       margin="sm"),
                    flex_builder.文字("• 自動帶你的 LINE 身分",
                                       size="sm",
                                       color=flex_builder.C["text_main"]),
                    flex_builder.文字("• 真圓環 + 火力規劃",
                                       size="sm",
                                       color=flex_builder.C["text_main"]),
                ],
            },
            # 主按鈕：開啟 LIFF
            {
                "type": "button",
                "style": "primary",
                "color": flex_builder.C["bull"],
                "height": "md",
                "margin": "lg",
                "action": {
                    "type": "uri",
                    "label": "🚀 開啟 LIS 表單",
                    "uri": LIFF_URL,
                },
            },
        ],
    },
    "styles": {
        "header": {"backgroundColor": flex_builder.C["bg_card"]},
        "body":   {"backgroundColor": flex_builder.C["bg_dark"]},
    },
}

print("推播 LIFF 按鈕卡到 LINE...")
line_push.推播Flex訊息(
    替代文字="🚀 L.I.S 持股配置 — 點擊開啟",
    flex內容=卡,
)
print("✅ 推播完成！請開 LINE 點藍黃按鈕測試")
