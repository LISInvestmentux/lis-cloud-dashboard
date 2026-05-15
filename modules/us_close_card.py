"""
美股收盤覆盤卡（Phase 36.13）— 04:05 自動推

跟 tw_close_card 對稱設計，但聚焦美股：
  🔵 大盤總結    — S&P / NASDAQ / VIX / 道瓊
  🛡️ 今日抗跌    — 你美股 vs S&P（抗跌設計避免焦慮）
  🟢/🔴 持股 TOP/BOTTOM 3
  📝 今日成交    — 美股交易紀錄
  📈 累計已實現  — 美股月/季/年（USD + TWD 雙幣）
  🚨 紀律警示    — 達 +15% / 破 -3%
  🌅 台股期指    — 預告隔日台股開盤
  💡 一句總結

設計目標：
  04:05 美股盤剛收 → user 早上醒來看到完整覆盤
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


def 算當日漲跌(symbol: str, technical_mod) -> dict:
    try:
        h, _ = technical_mod.取得每日股價(symbol, period="3d")
        if not h or len(h) < 2:
            return {"當日_pct": None, "現價": None}
        現 = h[0]["close"]
        昨 = h[1]["close"]
        return {
            "現價": round(現, 2),
            "當日_pct": round((現 / 昨 - 1) * 100, 2),
            "昨收": round(昨, 2),
        }
    except Exception:
        return {"當日_pct": None, "現價": None}


def 算美股累計已實現(realized_history: list,
                       USD_TWD: float = 31.5) -> dict:
    today = datetime.now().date()
    本月_start = today.replace(day=1)
    本季_q = (today.month - 1) // 3 + 1
    本季_start = today.replace(month=(本季_q - 1) * 3 + 1, day=1)
    今年_start = today.replace(month=1, day=1)

    def 是美股(r):
        sym = r.get("symbol", "")
        return not (sym.endswith(".TW") or sym.endswith(".TWO"))

    def 區間累計(start):
        筆 = 0
        usd = 0
        for r in realized_history:
            if not 是美股(r):
                continue
            try:
                d = datetime.strptime(r.get("date", ""), "%Y-%m-%d").date()
            except Exception:
                continue
            if d < start:
                continue
            筆 += 1
            pnl_usd = r.get("pnl_usd") or 0
            usd += pnl_usd
        return {
            "筆數": 筆,
            "獲利_usd": round(usd, 2),
            "獲利_twd": round(usd * USD_TWD, 0),
        }

    return {
        "本月": 區間累計(本月_start),
        "本季": 區間累計(本季_start),
        "今年": 區間累計(今年_start),
        "本月_label": f"{today.month} 月",
        "本季_label": f"Q{本季_q}",
        "今年_label": f"{today.year}",
    }


def 組今日覆盤() -> dict:
    """主入口：抓美股覆盤所有資料"""
    try:
        from . import (capital_planner, portfolio_tracker, forex,
                       technical)
    except ImportError:
        import capital_planner, portfolio_tracker, forex
        import technical

    cfg = capital_planner.載入資金設定()
    USD_TWD = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32))["rate"]
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=USD_TWD)

    # 1. 美股大盤
    大盤 = {}
    for sym, label in [("^GSPC", "S&P"), ("^IXIC", "NASDAQ"),
                        ("^DJI", "道瓊"), ("^VIX", "VIX")]:
        r = 算當日漲跌(sym, technical)
        if r["當日_pct"] is not None:
            大盤[label] = r

    # 2. 你美股持股當日表現
    美股持股 = [p for p in 真倉["持股"]
                if not p.get("error") and p.get("is_us")]
    當日表 = []
    當日總損益_usd = 0
    for p in 美股持股:
        r = 算當日漲跌(p["symbol"], technical)
        if r["當日_pct"] is None:
            continue
        當日損益 = r["現價"] * p.get("shares", 0) - r["昨收"] * p.get("shares", 0)
        當日表.append({
            "symbol": p["symbol"],
            "name": p.get("name", "")[:10],
            "shares": p.get("shares", 0),
            "現價": r["現價"],
            "當日_pct": r["當日_pct"],
            "當日損益_usd": round(當日損益, 2),
            "累計_pct": p.get("pnl_pct", 0),
        })
        當日總損益_usd += 當日損益

    當日表.sort(key=lambda r: r["當日_pct"], reverse=True)
    TOP3 = 當日表[:3]
    BOTTOM3 = 當日表[-3:][::-1] if len(當日表) > 3 else []

    # 3. 今日美股交易紀錄
    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    今日交易 = []
    for r in cfg.get("capital_inflow_history", []):
        if r.get("date") in (today_str, yesterday_str):
            note = r.get("note", "")
            # 只列美股相關
            is_us_trade = any(s in note for s in
                              ["美股", "USD", "NVDA", "AMD", "MU", "LRCX",
                               "AMAT", "GEV", "SATL", "ADBE", "IREN"])
            if is_us_trade or "美股" in note:
                今日交易.append(r)

    # 4. 累計已實現
    realized = cfg.get("realized_history", [])
    累計 = 算美股累計已實現(realized, USD_TWD)

    # 5. 紀律警示（美股）
    達 = [r for r in 真倉["警示"].get("達停利", []) if r.get("is_us")]
    破 = [r for r in 真倉["警示"].get("破停損", []) if r.get("is_us")]

    # 6. 台股期指（預告隔日台股）
    期指 = {}
    for sym, label in [("^TWII", "台股加權"),
                        ("EWT", "台股 ADR")]:
        r = 算當日漲跌(sym, technical)
        if r["當日_pct"] is not None:
            期指[label] = r

    # 7. 美股小計
    美股小計 = 真倉.get("美股小計", {})

    # 8. 待交割
    待 = sum(p.get("net_twd", 0) for p in cfg.get("pending_settlement", []))

    return {
        "大盤": 大盤,
        "持股當日": {
            "TOP3": TOP3,
            "BOTTOM3": BOTTOM3,
            "當日總損益_usd": round(當日總損益_usd, 2),
            "當日總損益_twd": round(當日總損益_usd * USD_TWD, 0),
            "持股檔數": len(當日表),
        },
        "今日交易": 今日交易,
        "累計已實現": 累計,
        "警示": {"達停利": 達, "破停損": 破},
        "台股期指": 期指,
        "美股小計": 美股小計,
        "待交割": 待,
        "USD_TWD": USD_TWD,
    }


def 建構Flex卡(覆盤: dict) -> dict:
    """美股覆盤卡 — 跟 tw_close_card 同設計（抗跌指標）"""
    try:
        from . import flex_builder
    except ImportError:
        import flex_builder

    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    bg = {
        "進行": "#3B82F61A", "預警": "#FBBF241A",
        "好": "#22C55E1A", "壞": "#EF44441A",
        "累計": "#A855F71A", "中性": "#FFFFFF0A",
    }
    色 = {
        "進行": "#3B82F6", "預警": "#FBBF24",
        "好": "#22C55E", "壞": "#EF4444", "累計": "#A855F7",
    }

    body = []

    # Header
    body.append({
        "type": "box", "layout": "vertical",
        "contents": [
            文字("🌙 美股收盤覆盤", size="xl",
                 color=C["accent"], weight="bold"),
            文字(f"{datetime.now():%m/%d %a %H:%M} · 美股盤後 5 分鐘",
                 size="xs", color=C["text_main"]),
        ],
    })
    body.append(分隔線())

    # 1. 大盤
    大盤 = 覆盤.get("大盤", {})
    if 大盤:
        rows = [文字("📊 美股大盤", size="md",
                     color=色["進行"], weight="bold")]
        for label, d in 大盤.items():
            色_d = C["bull"] if d["當日_pct"] >= 0 else C["bear"]
            if label == "VIX":
                色_d = C["bear"] if d["現價"] > 25 else (
                    C["wait"] if d["現價"] > 18 else C["bull"])
            rows.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(label, size="sm", color=C["text_main"], flex=2),
                    文字(f"{d['現價']:,.2f}", size="sm",
                         color=C["text_main"], align="center", flex=3),
                    文字(f"{d['當日_pct']:+.2f}%", size="sm",
                         color=色_d, weight="bold", align="end", flex=2),
                ],
            })
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["進行"],
            "cornerRadius": "8px",
            "contents": rows,
        })

    # 2. 抗跌指標（反焦慮設計）
    當日 = 覆盤.get("持股當日", {})
    當日損益_usd = 當日.get("當日總損益_usd", 0)
    持股檔數 = 當日.get("持股檔數", 0)
    大盤_sp = 覆盤.get("大盤", {}).get("S&P", {}).get("當日_pct", 0)

    所有當日 = (當日.get("TOP3", []) + 當日.get("BOTTOM3", []))
    if 所有當日 and 持股檔數 > 0:
        市值權 = sum(r.get("現價", 0) * r.get("shares", 0) for r in 所有當日)
        if 市值權 > 0:
            你的當日_pct = sum(
                r.get("當日_pct", 0) * r.get("現價", 0) * r.get("shares", 0)
                for r in 所有當日) / 市值權
        else:
            你的當日_pct = 0
    else:
        你的當日_pct = 0

    抗跌 = 你的當日_pct - 大盤_sp

    if 抗跌 > 0.5:
        標題 = "🛡️ 今日抗跌"; 色_k = C["bull"]; bg_k = bg["好"]
        評語 = "比 S&P 強 ✨"
    elif 抗跌 > 0:
        標題 = "🛡️ 抗跌略勝"; 色_k = C["bull"]; bg_k = bg["好"]
        評語 = "比 S&P 好一些"
    elif 抗跌 > -0.5:
        標題 = "📊 跟跌"; 色_k = C["text_main"]; bg_k = bg["中性"]
        評語 = "與 S&P 同步"
    else:
        標題 = "⚠️ 弱於 S&P"; 色_k = C["wait"]; bg_k = bg["預警"]
        評語 = "明日觀察"

    body.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "margin": "md", "paddingAll": "12px",
        "backgroundColor": bg_k, "cornerRadius": "8px",
        "contents": [
            文字(標題, size="md", color=色_k, weight="bold"),
            文字(f"{抗跌:+.2f}%", size="xxl",
                 color=色_k, weight="bold"),
            文字(f"你 {你的當日_pct:+.2f}% / S&P {大盤_sp:+.2f}%",
                 size="xs", color=C["text_dim"]),
            文字(f"{評語} · {持股檔數} 檔美股",
                 size="xxs", color=C["text_subtle"]),
        ],
    })

    # 3. TOP/BOTTOM 3
    TOP3 = 當日.get("TOP3", [])
    BOTTOM3 = 當日.get("BOTTOM3", [])
    if TOP3 or BOTTOM3:
        rows = []
        if TOP3:
            rows.append(文字("🟢 漲幅 TOP 3", size="sm",
                              color=C["bull"], weight="bold"))
            for r in TOP3:
                if r["當日_pct"] <= 0:
                    continue
                rows.append({
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"{r['symbol']} {r['name']}",
                             size="sm", color=C["text_main"], flex=5),
                        文字(f"{r['當日_pct']:+.2f}%", size="sm",
                             color=C["bull"], weight="bold",
                             align="end", flex=3),
                    ],
                })
        if BOTTOM3 and any(r["當日_pct"] < 0 for r in BOTTOM3):
            if rows:
                rows.append(分隔線())
            rows.append(文字("🔴 跌幅 TOP 3", size="sm",
                              color=C["bear"], weight="bold"))
            for r in BOTTOM3:
                if r["當日_pct"] >= 0:
                    continue
                rows.append({
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"{r['symbol']} {r['name']}",
                             size="sm", color=C["text_main"], flex=5),
                        文字(f"{r['當日_pct']:+.2f}%", size="sm",
                             color=C["bear"], weight="bold",
                             align="end", flex=3),
                    ],
                })
        if rows:
            body.append({
                "type": "box", "layout": "vertical", "spacing": "xs",
                "margin": "md", "paddingAll": "10px",
                "backgroundColor": bg["中性"],
                "cornerRadius": "8px",
                "contents": rows,
            })

    # 4. 今日交易
    今日交易 = 覆盤.get("今日交易", [])
    if 今日交易:
        rows = [文字(f"📝 美股成交 ({len(今日交易)} 筆)",
                     size="md", color=色["累計"], weight="bold")]
        for t in 今日交易[:5]:
            amt = t.get("amount_twd", 0)
            色_t = C["bear"] if amt < 0 else C["bull"]
            動作 = "買" if amt < 0 else "賣"
            rows.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"{動作} {t.get('note', '')[:22]}",
                         size="xs", color=C["text_main"],
                         flex=5, wrap=True),
                    文字(f"NT$ {amt:+,.0f}",
                         size="xs", color=色_t,
                         weight="bold", align="end", flex=3),
                ],
            })
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["累計"],
            "cornerRadius": "8px",
            "contents": rows,
        })

    # 5. 累計已實現
    累 = 覆盤.get("累計已實現", {})
    有累計 = (累["本月"]["筆數"] + 累["本季"]["筆數"] + 累["今年"]["筆數"]) > 0
    if 有累計:
        累_rows = [文字("📈 美股累計已實現", size="md",
                       color=色["累計"], weight="bold")]
        for 期, label_key in [("本月", "本月_label"),
                              ("本季", "本季_label"),
                              ("今年", "今年_label")]:
            r = 累[期]
            usd = r["獲利_usd"]
            twd = r["獲利_twd"]
            金色 = C["bull"] if usd >= 0 else C["bear"]
            累_rows.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"{期} {累[label_key]}", size="sm",
                         color=C["text_main"], flex=3),
                    文字(f"${usd:+,.2f}", size="sm",
                         color=金色, weight="bold", align="end", flex=3),
                ],
            })
            累_rows.append(文字(f"   ≈ NT$ {twd:+,.0f} ({r['筆數']} 筆)",
                                size="xxs", color=C["text_dim"]))
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["累計"],
            "cornerRadius": "8px",
            "contents": 累_rows,
        })

    # 6. 紀律警示
    警 = 覆盤.get("警示", {})
    達 = 警.get("達停利", [])
    破 = 警.get("破停損", [])
    if 達 or 破:
        rows = []
        if 達:
            rows.append(文字(f"🎯 達 +15% ({len(達)} 檔)",
                              size="md", color=C["accent"], weight="bold"))
            for r in 達[:2]:
                rows.append(文字(
                    f"  {r['symbol']} {r.get('name','')[:8]} {r['pnl_pct']:+.2f}%",
                    size="sm", color=C["text_main"]))
        if 破:
            rows.append(文字(f"💀 破 -3% ({len(破)} 檔)",
                              size="md", color=C["bear"], weight="bold"))
            for r in 破[:2]:
                rows.append(文字(
                    f"  {r['symbol']} {r.get('name','')[:8]} {r['pnl_pct']:+.2f}%",
                    size="sm", color=C["text_main"]))
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["預警"],
            "cornerRadius": "8px",
            "contents": rows,
        })

    # 7. 台股期指預告
    期指 = 覆盤.get("台股期指", {})
    if 期指:
        rows = [文字("🌅 台股預告（隔日）", size="md",
                     color=色["進行"], weight="bold")]
        for label, d in 期指.items():
            色_p = C["bull"] if d["當日_pct"] >= 0 else C["bear"]
            rows.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(label, size="sm", color=C["text_main"], flex=3),
                    文字(f"{d['當日_pct']:+.2f}%", size="sm",
                         color=色_p, weight="bold", align="end", flex=3),
                ],
            })
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["中性"],
            "cornerRadius": "8px",
            "contents": rows,
        })

    # 8. 一句總結
    body.append(分隔線())
    if 破:
        summary = "👉 明早 8AM 必做停損"
        sum_color = C["bear"]
    elif 達:
        summary = "👉 明早 8AM 必做停利"
        sum_color = C["accent"]
    elif 抗跌 > 0:
        summary = "👉 今夜抗跌，紀律 OK"
        sum_color = C["bull"]
    else:
        summary = "👉 今夜跟跌，明早 8AM 重新評估"
        sum_color = C["wait"]
    body.append(文字(summary, size="sm",
                     color=sum_color, weight="bold", align="center"))

    return {
        "type": "bubble", "size": "mega",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": body,
        },
    }


def 推Flex卡() -> bool:
    """推美股收盤覆盤卡"""
    try:
        from . import line_push
    except ImportError:
        import line_push
    覆盤 = 組今日覆盤()
    flex = 建構Flex卡(覆盤)
    car = {"type": "carousel", "contents": [flex]}
    alt = f"🌙 美股收盤覆盤 ({datetime.now():%m/%d %H:%M})"
    try:
        line_push.推播Flex訊息(替代文字=alt, flex內容=car)
        return True
    except Exception as e:
        print(f"推播失敗: {e}")
        return False


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from dotenv import load_dotenv
    load_dotenv(專案根 / "API" / ".env")

    覆盤 = 組今日覆盤()
    print(f"=== 美股收盤覆盤 [{datetime.now():%m/%d %H:%M}] ===")
    print(f"\n📊 大盤:")
    for k, v in 覆盤["大盤"].items():
        print(f"  {k}: {v['現價']:,.2f} ({v['當日_pct']:+.2f}%)")
    當 = 覆盤["持股當日"]
    print(f"\n💰 美股 {當['持股檔數']} 檔當日總損益: "
          f"${當['當日總損益_usd']:+,.2f} = NT$ {當['當日總損益_twd']:+,.0f}")
    print(f"\n🟢 TOP 3:")
    for r in 當["TOP3"][:3]:
        print(f"  {r['symbol']} {r['當日_pct']:+.2f}%")
    print(f"\n📈 累計本月: ${覆盤['累計已實現']['本月']['獲利_usd']:+.2f}")

    if len(sys.argv) > 1 and sys.argv[1] == "push":
        print(f"\n推 LINE...")
        if 推Flex卡():
            print("✅ 已推")
