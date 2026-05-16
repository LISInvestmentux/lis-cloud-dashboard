"""預覽 3 張主卡的文字內容（不真推 LINE）"""
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

os.environ["LIS_TEST_MODE"] = "true"
專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))
from dotenv import load_dotenv
load_dotenv(專案根.parent / "API" / ".env")

from modules import daily_5cards


def extract_text(node, indent=0):
    """遞迴提取 flex 內所有 text + button labels"""
    out = []
    if isinstance(node, dict):
        if node.get("type") == "text":
            t = node.get("text", "")
            if t.strip():
                out.append("  " * indent + t)
        elif node.get("type") == "button":
            action = node.get("action", {})
            out.append("  " * indent + "[ " + action.get("label", "") + " ]")
        elif node.get("type") == "separator":
            out.append("  " * indent + "─" * 30)
        else:
            for c in node.get("contents", []):
                out.extend(extract_text(c, indent))
    return out


print("\n" + "=" * 60)
print("📐 LIS 3 張主卡 — 內容 PREVIEW（沒推 LINE）")
print("=" * 60)

cards = daily_5cards.組5張主卡()
for i, c in enumerate(cards, 1):
    print("\n" + "┌" + "─" * 58 + "┐")
    print(f"│ 卡 {i}".ljust(59) + "│")
    print("├" + "─" * 58 + "┤")
    body = c.get("body", {})
    for line in extract_text(body):
        print("│ " + line[:56].ljust(56) + " │")
    print("└" + "─" * 58 + "┘")
