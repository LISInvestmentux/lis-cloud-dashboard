"""即時美股佈局建議卡（Phase 36.11）— 一次性推送"""
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

from datetime import datetime
import yfinance as yf
from modules import line_push, flex_builder, capital_planner, forex


def 抓即時(syms):
    結果 = {}
    for sym in syms:
        try:
            t = yf.Ticker(sym)
            info = t.info
            現 = info.get('currentPrice') or info.get('regularMarketPrice')
            prev = info.get('previousClose')
            if 現 and prev:
                結果[sym] = {
                    "現價": round(現, 2),
                    "昨收": round(prev, 2),
                    "當日_pct": round((現/prev - 1) * 100, 2),
                    "day_high": info.get('dayHigh'),
                    "day_low": info.get('dayLow'),
                }
        except Exception:
            continue
    return 結果


def 建卡():
    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    bg = {"買": "#22C55E1A", "觀": "#FBBF241A", "別": "#F59E0B1A",
          "持": "#3B82F61A"}
    色 = {"買": "#22C55E", "觀": "#FBBF24", "別": "#F59E0B", "持": "#3B82F6"}

    # Sylvie 22:00 買入價
    sylvie = {
        'SATL': 9.18, 'LRCX': 282.68, 'NVDA': 227.12, 'BE': 280.55,
        'MU': 736.94, 'LITE': 937, 'GEV': 1063.23, 'AMAT': 429.02,
        'AMD': 431.03
    }

    # 抓即時
    rt = 抓即時(list(sylvie.keys()))

    cfg = capital_planner.載入資金設定()
    USD_TWD = forex.取得USD_TWD匯率(fallback=32.0)["rate"]
    Ryan持 = {p["symbol"] for p in cfg.get("current_positions", [])
              if not (p["symbol"].endswith(".TW") or p["symbol"].endswith(".TWO"))}

    body = []

    # Header
    body.append({
        "type": "box", "layout": "vertical",
        "contents": [
            文字("🎯 今夜美股佈局建議", size="xl",
                 color=C["accent"], weight="bold"),
            文字(f"{datetime.now():%m/%d %H:%M} · 盤中即時 (Sylvie 已建倉)",
                 size="xs", color=C["text_main"]),
        ],
    })
    body.append(分隔線())

    # 立刻可動資金
    body.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "margin": "md", "paddingAll": "10px",
        "backgroundColor": bg["持"],
        "cornerRadius": "8px",
        "contents": [
            文字("💰 可動用資金", size="md",
                 color=色["持"], weight="bold"),
            文字("立刻可動 NT$ 4,070（已實現獲利）",
                 size="sm", color=C["text_main"]),
            文字("未來 5/18-5/19 入帳 NT$ 29,938",
                 size="sm", color=C["text_main"]),
        ],
    })

    # 分類建議
    買進 = []
    觀察 = []
    別追 = []
    已持 = []

    for sym, syl_p in sylvie.items():
        if sym not in rt:
            continue
        現 = rt[sym]["現價"]
        當日 = rt[sym]["當日_pct"]
        vs_syl = (現/syl_p - 1) * 100

        條目 = {
            "sym": sym,
            "現價": 現,
            "syl_price": syl_p,
            "當日_pct": 當日,
            "vs_syl_pct": vs_syl,
        }

        if sym in Ryan持:
            已持.append(條目)
        elif vs_syl < 0:
            # 比 Sylvie 還便宜！
            買進.append(條目)
        elif vs_syl < 1.5 and 當日 < -2:
            # 接近 Sylvie 買價 + 今日跌深
            買進.append(條目)
        elif vs_syl < 3:
            觀察.append(條目)
        else:
            別追.append(條目)

    # 🟢 買進候選
    if 買進:
        rows = [文字("🟢 可佈局（比 Sylvie 便宜或接近）",
                     size="md", color=色["買"], weight="bold")]
        for c in 買進:
            mark = "⭐ 比她低" if c["vs_syl_pct"] < 0 else "🟡 接近"
            twd = c["現價"] * USD_TWD
            rows.append({
                "type": "box", "layout": "vertical",
                "contents": [
                    {"type": "box", "layout": "horizontal", "contents": [
                        文字(f"{c['sym']} {mark}", size="sm",
                             color=C["text_main"], weight="bold", flex=4),
                        文字(f"${c['現價']:.2f} ({c['當日_pct']:+.1f}%)",
                             size="sm", color=色["買"], align="end", flex=4),
                    ]},
                    文字(f"  Sylvie ${c['syl_price']} / vs 她 {c['vs_syl_pct']:+.2f}% / NT$ {twd:,.0f}",
                         size="xxs", color=C["text_dim"], wrap=True),
                ],
            })
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["買"],
            "cornerRadius": "8px",
            "contents": rows,
        })

    # 🟡 觀察
    if 觀察:
        rows = [文字("🟡 觀察（高 +0.5~3%）",
                     size="md", color=色["觀"], weight="bold")]
        for c in 觀察:
            rows.append(文字(
                f"  {c['sym']}  ${c['現價']:.2f} (Sylvie ${c['syl_price']}, {c['vs_syl_pct']:+.1f}%)",
                size="xs", color=C["text_main"], wrap=True))
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["觀"],
            "cornerRadius": "8px",
            "contents": rows,
        })

    # 🟠 別追
    if 別追:
        rows = [文字("🟠 別追（已高 Sylvie >3%）",
                     size="md", color=色["別"], weight="bold")]
        for c in 別追:
            rows.append(文字(
                f"  {c['sym']}  ${c['現價']:.2f} ({c['vs_syl_pct']:+.1f}%)",
                size="xs", color=C["text_main"]))
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["別"],
            "cornerRadius": "8px",
            "contents": rows,
        })

    # 🔵 你已持
    if 已持:
        rows = [文字("🔵 你已持（不加）",
                     size="md", color=色["持"], weight="bold")]
        for c in 已持:
            rows.append(文字(
                f"  {c['sym']}  ${c['現價']:.2f} ({c['當日_pct']:+.1f}%)",
                size="xs", color=C["text_main"]))
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["持"],
            "cornerRadius": "8px",
            "contents": rows,
        })

    # 一句總結
    body.append(分隔線())
    summary = f"👉 今晚跌深 +Sylvie 同步建倉 = 雙重信號"
    body.append(文字(summary, size="sm",
                     color=C["accent"], weight="bold", align="center"))
    body.append(文字("但你 Enjoy 31.9 HOLD 模式，建議小額試 1 股驗證",
                     size="xxs", color=C["text_dim"],
                     align="center", wrap=True))

    return {
        "type": "bubble", "size": "mega",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": body,
        },
    }


if __name__ == "__main__":
    flex = 建卡()
    car = {"type": "carousel", "contents": [flex]}
    alt = f"🎯 今夜美股佈局建議 ({datetime.now():%H:%M})"
    try:
        line_push.推播Flex訊息(替代文字=alt, flex內容=car)
        print(f"✅ 已推 LINE")
    except Exception as e:
        print(f"❌ 推送失敗: {e}")
