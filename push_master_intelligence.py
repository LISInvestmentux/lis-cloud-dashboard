"""
LIS 主情報中心（Phase 22-26 全整合推送）

每次執行推 carousel 包含：
  1. 即時決策卡（位階+順勢+Kelly+彈藥）
  2. 台美連動卡（昨夜美股 → 台股傳導預測）
  3. 法人籌碼卡（外資+投信共識買賣）
  4. 基本面 TOP 卡（高基本面分數標的）
  5. 新聞情緒卡（黑天鵝預警）
  6. 策略池 carousel（8 策略入選）

執行：
  雙擊 LIS主情報中心.bat
  或 python push_master_intelligence.py
"""
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

from modules import (capital_planner, fugle_market, line_push,
                     flex_builder, institutional_tracker,
                     fundamentals_engine, news_sentiment,
                     tw_us_correlation, strategy_pool)

C = flex_builder.C


# ─────────────────────────────────────────────
# 卡 1：台美連動傳導
# ─────────────────────────────────────────────
def 卡_台美連動():
    r = tw_us_correlation.台股傳導預測()
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線
    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("🌐 台美連動傳導", size="lg", color=C["text_main"], weight="bold"),
            文字(f"美股平均 {r['平均漲幅_pct']:+.2f}% · {r['整體傾向']}",
                 size="xs", color=C["text_dim"], wrap=True),
        ],
    })
    內容.append(分隔線())
    for 美, p in sorted(r["美股表現"].items(),
                        key=lambda x: -x[1]["漲幅_pct"])[:8]:
        色 = (C["bull"] if p["漲幅_pct"] >= 0.5 else
              C["bear"] if p["漲幅_pct"] <= -0.5 else
              C["wait"])
        內容.append({
            "type": "box", "layout": "horizontal", "spacing": "xs",
            "contents": [
                文字(美, size="sm", color=C["text_main"], flex=3),
                文字(p["強度"], size="xxs", color=色, align="center", flex=3),
                文字(f"{p['漲幅_pct']:+.2f}%", size="sm", color=色,
                     align="end", weight="bold", flex=2),
            ],
        })
    內容.append(分隔線())
    內容.append(文字("🔥 預測強勢台股（受 MU/GOOGL/NVDA 帶動）",
                     size="xs", color=C["bull"], weight="bold"))
    最強 = r.get("最強上漲")
    if 最強 and 最強 in r["傳導預測"]:
        for ts in r["傳導預測"][最強]["影響的台股"][:5]:
            內容.append(文字(f"  {ts['symbol']} {ts['name']}",
                             size="xxs", color=C["text_dim"]))

    return {
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "12px",
            "contents": 內容,
        },
    }


# ─────────────────────────────────────────────
# 卡 2：法人籌碼
# ─────────────────────────────────────────────
def 卡_法人籌碼():
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線
    r = institutional_tracker.找今日強訊號()
    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("🏛️ 法人籌碼共識", size="lg", color=C["text_main"], weight="bold"),
            文字(f"{r.get('日期','')} · 外資+投信同向", size="xs",
                 color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())

    內容.append(文字(f"🔥 共識買 {len(r['強共識買'])} 檔",
                     size="md", color=C["bull"], weight="bold"))
    for d in r["強共識買"][:6]:
        內容.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字(f"{d['symbol']} {d['name'][:8]}", size="xs",
                     color=C["text_main"], flex=4),
                文字(f"外{d['外資']/1000:+.0f}k", size="xxs",
                     color=C["bull"], align="end", flex=3),
                文字(f"投{d['投信']/1000:+.0f}k", size="xxs",
                     color=C["accent"], align="end", flex=3),
            ],
        })
    內容.append(分隔線())
    內容.append(文字(f"💀 共識賣 {len(r['強共識賣'])} 檔（警示）",
                     size="md", color=C["bear"], weight="bold"))
    for d in r["強共識賣"][:4]:
        內容.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字(f"{d['symbol']} {d['name'][:8]}", size="xs",
                     color=C["text_main"], flex=4),
                文字(f"外{d['外資']/1000:+.0f}k", size="xxs",
                     color=C["bear"], align="end", flex=3),
                文字(f"投{d['投信']/1000:+.0f}k", size="xxs",
                     color=C["bear"], align="end", flex=3),
            ],
        })

    return {
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "12px",
            "contents": 內容,
        },
    }


# ─────────────────────────────────────────────
# 卡 3：基本面 TOP
# ─────────────────────────────────────────────
def 卡_基本面TOP():
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    # 抓重點標的的基本面
    重點 = [
        "2330.TW", "2317.TW", "2382.TW", "2327.TW", "2454.TW",
        "NVDA", "AVGO", "MU", "META", "GOOGL",
    ]
    results = []
    for sym in 重點:
        try:
            r = fundamentals_engine.抓基本面(sym)
            if r:
                s = fundamentals_engine.算基本面分數(r)
                if s["總分"] is not None:
                    results.append({
                        "symbol": sym,
                        "name": r.get("name", "")[:14],
                        "分數": s["總分"],
                        "PE": r.get("trailingPE"),
                        "ROE": (r.get("returnOnEquity") or 0) * 100,
                        "EPS成長": (r.get("earningsGrowth") or 0) * 100,
                    })
        except Exception:
            pass
    results.sort(key=lambda x: -x["分數"])

    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("📊 基本面 TOP", size="lg", color=C["text_main"], weight="bold"),
            文字("ROE + EPS 成長 + PE 估值 加權", size="xs", color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())

    for r in results[:10]:
        色 = (C["bull"] if r["分數"] >= 70 else
              C["text_main"] if r["分數"] >= 50 else
              C["wait"])
        內容.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "paddingTop": "xs",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(r["symbol"], size="sm", color=色, weight="bold", flex=4),
                        文字(f"{r['分數']:.0f} 分", size="sm", color=色,
                             align="end", weight="bold", flex=3),
                    ],
                },
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"PE {r['PE']:.0f}" if r['PE'] else "PE -",
                             size="xxs", color=C["text_dim"], flex=2),
                        文字(f"ROE {r['ROE']:.0f}%", size="xxs",
                             color=C["text_dim"], align="center", flex=2),
                        文字(f"EPS {r['EPS成長']:+.0f}%", size="xxs",
                             color=C["bull"] if r['EPS成長']>=10 else C["text_dim"],
                             align="end", flex=2),
                    ],
                },
            ],
        })

    return {
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "12px",
            "contents": 內容,
        },
    }


# ─────────────────────────────────────────────
# 卡 4：新聞情緒
# ─────────────────────────────────────────────
def 卡_新聞情緒():
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線
    r = news_sentiment.今日新聞情緒()
    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("📰 新聞情緒", size="lg", color=C["text_main"], weight="bold"),
            文字(r.get("情緒等級", "資料不足"),
                 size="md", color=(C["bear"] if r.get("情緒分數", 0) <= -5
                                   else C["bull"] if r.get("情緒分數", 0) >= 5
                                   else C["wait"]), weight="bold"),
        ],
    })
    內容.append(分隔線())
    內容.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字(f"緊急 {r.get('緊急數',0)}", size="xxs", color=C["bear"], flex=1),
            文字(f"高險 {r.get('高風險數',0)}", size="xxs", color=C["wait"], flex=1),
            文字(f"利多 {r.get('利多數',0)}", size="xxs", color=C["bull"], flex=1),
        ],
    })
    內容.append(分隔線())
    內容.append(文字("🚨 高警示新聞", size="xs", color=C["bear"], weight="bold"))
    for n in r.get("新聞列表", [])[:30]:
        if n["分數"] <= -2:
            內容.append(文字(f"• {n['標題'][:34]}",
                             size="xxs", color=C["text_dim"], wrap=True))
            if len([x for x in 內容 if "•" in str(x)]) >= 4:
                break
    內容.append(分隔線())
    內容.append(文字("📈 利多新聞", size="xs", color=C["bull"], weight="bold"))
    count = 0
    for n in r.get("新聞列表", [])[:30]:
        if n["分數"] >= 1:
            內容.append(文字(f"• {n['標題'][:34]}",
                             size="xxs", color=C["text_dim"], wrap=True))
            count += 1
            if count >= 3:
                break

    return {
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "12px",
            "contents": 內容,
        },
    }


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────
def 主流程():
    開始 = datetime.now()
    print(f"=== LIS 主情報中心 {開始:%H:%M:%S} ===\n")

    cards = []

    print("📊 [1/5] 台美連動...")
    try:
        cards.append(卡_台美連動())
    except Exception as e:
        print(f"  失敗: {e}")

    print("🏛️ [2/5] 法人籌碼...")
    try:
        cards.append(卡_法人籌碼())
    except Exception as e:
        print(f"  失敗: {e}")

    print("📈 [3/5] 基本面 TOP...")
    try:
        cards.append(卡_基本面TOP())
    except Exception as e:
        print(f"  失敗: {e}")

    print("📰 [4/5] 新聞情緒...")
    try:
        cards.append(卡_新聞情緒())
    except Exception as e:
        print(f"  失敗: {e}")

    print(f"\n推送 {len(cards)} 張卡到 LINE...")
    carousel = {"type": "carousel", "contents": cards}
    alt = f"🔥 LIS 主情報中心 — {len(cards)} 維分析 {開始:%H:%M}"
    try:
        line_push.推播Flex訊息(替代文字=alt, flex內容=carousel)
        print("✅ 推送成功！打開 LINE 看 📱")
    except Exception as e:
        print(f"❌ 推送失敗: {e}")

    耗時 = (datetime.now() - 開始).total_seconds()
    print(f"\n=== 完成（耗時 {耗時:.0f} 秒）===")


if __name__ == "__main__":
    主流程()
