"""
台股收盤覆盤卡（Phase 33.3）— 13:35 自動推

跟 daily_action_card 同 6 色語意設計：
  🔵 大盤總結    — 加權 / 成交量 / 法人
  🟢 持股表現    — TOP3 / 當日損益
  🟣 今日交易    — 成交記錄 / 累計已實現
  🟡 紀律警示    — 達 +15% / 破 -5%
  🟢 明日預告    — 美股盤前 / 期指夜盤
  💡 一句總結

設計目標：
  13:30 收盤 → 13:35 推卡 → user 5 分鐘內知道今天台股結果
"""
import json
from datetime import datetime, timedelta
from pathlib import Path


專案根 = Path(__file__).resolve().parent.parent.parent


def 算當日漲跌(symbol: str, technical_mod) -> dict:
    """抓某 symbol 今日 close vs 昨日"""
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


def 組今日覆盤() -> dict:
    """主入口：抓所有覆盤資料"""
    try:
        from . import (capital_planner, portfolio_tracker, forex,
                       technical, institutional_tracker)
    except ImportError:
        import capital_planner, portfolio_tracker, forex
        import technical, institutional_tracker

    cfg = capital_planner.載入資金設定()
    USD_TWD = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32))["rate"]
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=USD_TWD)

    # 1. 大盤
    大盤 = {}
    for sym, label in [("^TWII", "加權"), ("^TWO", "OTC")]:
        r = 算當日漲跌(sym, technical)
        if r["當日_pct"] is not None:
            大盤[label] = r

    # 2. 持股當日表現
    台股持股 = [p for p in 真倉["持股"]
                if not p.get("error") and not p.get("is_us")]
    當日表 = []
    當日總損益_twd = 0
    for p in 台股持股:
        r = 算當日漲跌(p["symbol"], technical)
        if r["當日_pct"] is None:
            continue
        當日損益 = r["現價"] * p.get("shares", 0) - r["昨收"] * p.get("shares", 0)
        當日表.append({
            "symbol": p["symbol"],
            "name": p.get("name", "")[:8],
            "shares": p.get("shares", 0),
            "現價": r["現價"],
            "當日_pct": r["當日_pct"],
            "當日損益_twd": round(當日損益, 0),
            "累計_pct": p.get("pnl_pct", 0),
        })
        當日總損益_twd += 當日損益

    當日表.sort(key=lambda r: r["當日_pct"], reverse=True)
    TOP3 = 當日表[:3]
    BOTTOM3 = 當日表[-3:][::-1] if len(當日表) > 3 else []

    # 3. 今日交易記錄（從 capital_inflow_history 抓今日的）
    today_str = datetime.now().strftime("%Y-%m-%d")
    今日交易 = [
        r for r in cfg.get("capital_inflow_history", [])
        if r.get("date") == today_str
        and ("買" in r.get("note", "") or "賣" in r.get("note", ""))
    ]

    # 4. 累計已實現（今年）
    realized = cfg.get("realized_history", [])
    today_d = datetime.now().date()
    本月_start = today_d.replace(day=1)
    本月_TW = sum(r.get("pnl_twd", 0) or 0
                  for r in realized
                  if (r.get("symbol", "").endswith(".TW") or
                      r.get("symbol", "").endswith(".TWO"))
                  and datetime.strptime(r.get("date", "1900-01-01"),
                                         "%Y-%m-%d").date() >= 本月_start)

    # 5. 紀律警示
    達停利 = [r for r in 真倉["警示"].get("達停利", []) if not r.get("is_us")]
    接近停利 = [r for r in 真倉["警示"].get("接近停利", []) if not r.get("is_us")]
    破停損 = [r for r in 真倉["警示"].get("破停損", []) if not r.get("is_us")]
    接近停損 = [r for r in 真倉["警示"].get("接近停損", []) if not r.get("is_us")]

    # 6. 法人三大買賣超
    法人 = None
    try:
        法人 = institutional_tracker.抓今日法人籌碼(
            datetime.now().strftime("%Y%m%d"))
    except Exception:
        pass

    # 7. 美股盤前夜盤（預告）
    美股期指 = {}
    for sym, label in [("ES=F", "S&P 期"), ("NQ=F", "NASDAQ 期"),
                        ("YM=F", "道瓊 期")]:
        r = 算當日漲跌(sym, technical)
        if r["當日_pct"] is not None:
            美股期指[label] = r

    # 8. 待入帳
    待交割 = sum(p.get("net_twd", 0) for p in cfg.get("pending_settlement", []))

    return {
        "大盤": 大盤,
        "持股當日": {
            "TOP3": TOP3,
            "BOTTOM3": BOTTOM3,
            "當日總損益_twd": round(當日總損益_twd, 0),
            "持股檔數": len(當日表),
        },
        "今日交易": 今日交易,
        "累計本月_TW": round(本月_TW, 0),
        "警示": {
            "達停利": 達停利, "接近停利": 接近停利,
            "破停損": 破停損, "接近停損": 接近停損,
        },
        "法人": 法人,
        "美股期指": 美股期指,
        "待交割": 待交割,
        "USD_TWD": USD_TWD,
    }


def 建構Flex卡(覆盤: dict) -> dict:
    """13:35 覆盤卡 — 跟 daily_action_card 同設計"""
    try:
        from . import flex_builder
    except ImportError:
        import flex_builder

    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    bg = {
        "進行":   "#3B82F61A",
        "預警":   "#FBBF241A",
        "好":     "#22C55E1A",
        "壞":     "#EF44441A",
        "累計":   "#A855F71A",
        "資金":   "#22C55E1A",
    }
    色 = {
        "進行": "#3B82F6",
        "預警": "#FBBF24",
        "好":   "#22C55E",
        "壞":   "#EF4444",
        "累計": "#A855F7",
    }

    body = []

    # Header
    body.append({
        "type": "box", "layout": "vertical",
        "contents": [
            文字("📋 今日台股覆盤", size="xl",
                 color=C["accent"], weight="bold"),
            文字(f"{datetime.now():%m/%d %a %H:%M} · 收盤後 5 分鐘",
                 size="xs", color=C["text_main"]),
        ],
    })
    body.append(分隔線())

    # 1. 大盤（藍 = 資訊）
    大盤 = 覆盤.get("大盤", {})
    if 大盤:
        rows = [文字("📊 大盤", size="md",
                     color=色["進行"], weight="bold")]
        for label, d in 大盤.items():
            色_d = C["bull"] if d["當日_pct"] >= 0 else C["bear"]
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

    # 2. 當日總損益（最重要的 KPI）
    當日 = 覆盤.get("持股當日", {})
    當日損益 = 當日.get("當日總損益_twd", 0)
    if 當日損益:
        色_kpi = C["bull"] if 當日損益 >= 0 else C["bear"]
        bg_kpi = bg["好"] if 當日損益 >= 0 else bg["壞"]
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "12px",
            "backgroundColor": bg_kpi,
            "cornerRadius": "8px",
            "contents": [
                文字(f"💰 今日帳面損益", size="md",
                     color=色_kpi, weight="bold"),
                文字(f"NT$ {當日損益:+,.0f}", size="xxl",
                     color=色_kpi, weight="bold"),
                文字(f"{當日.get('持股檔數', 0)} 檔台股", size="xs",
                     color=C["text_dim"]),
            ],
        })

    # 3. 持股 TOP3 / BOTTOM3
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
                "backgroundColor": "#FFFFFF0A",
                "cornerRadius": "8px",
                "contents": rows,
            })

    # 4. 今日交易
    今日交易 = 覆盤.get("今日交易", [])
    if 今日交易:
        rows = [文字(f"📝 今日成交 ({len(今日交易)} 筆)",
                     size="md", color=色["累計"], weight="bold")]
        for t in 今日交易[:5]:
            amount = t.get("amount_twd", 0)
            色_t = C["bear"] if amount < 0 else C["bull"]
            動作 = "買" if amount < 0 else "賣"
            rows.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"{動作} {t.get('note', '')[:20]}",
                         size="xs", color=C["text_main"], flex=5, wrap=True),
                    文字(f"NT$ {amount:+,.0f}",
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

    # 5. 紀律警示
    警 = 覆盤.get("警示", {})
    達 = 警.get("達停利", [])
    破 = 警.get("破停損", [])
    if 達 or 破:
        rows = []
        if 達:
            rows.append(文字(f"🎯 達 +15% ({len(達)} 檔)",
                              size="md", color=C["accent"], weight="bold"))
            for r in 達[:3]:
                rows.append(文字(
                    f"  {r['symbol']} {r.get('name','')[:8]} {r['pnl_pct']:+.2f}%",
                    size="sm", color=C["text_main"]))
        if 破:
            rows.append(文字(f"💀 破 -5% ({len(破)} 檔)",
                              size="md", color=C["bear"], weight="bold"))
            for r in 破[:3]:
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

    # 6. 法人三大買賣超
    法 = 覆盤.get("法人")
    if 法 and 法.get("三大法人"):
        三大 = 法["三大法人"]
        rows = [文字("🏦 三大法人", size="md",
                     color=色["進行"], weight="bold")]
        for k in ["外資", "投信", "自營"]:
            v = 三大.get(k)
            if v is None:
                continue
            色_l = C["bull"] if v >= 0 else C["bear"]
            rows.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(k, size="sm", color=C["text_main"], flex=2),
                    文字(f"{v:+,.0f} 億", size="sm",
                         color=色_l, weight="bold", align="end", flex=4),
                ],
            })
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["進行"],
            "cornerRadius": "8px",
            "contents": rows,
        })

    # 7. 美股期指（明日預告）
    期指 = 覆盤.get("美股期指", {})
    if 期指:
        rows = [文字("🌙 美股期指（盤前預告）", size="md",
                     color=C["accent"], weight="bold")]
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
            "backgroundColor": "#FFFFFF0A",
            "cornerRadius": "8px",
            "contents": rows,
        })

    # 8. 待交割 + 累計本月
    待 = 覆盤.get("待交割", 0)
    本月 = 覆盤.get("累計本月_TW", 0)
    if 待 > 0 or 本月 != 0:
        rows = []
        if 待 > 0:
            rows.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字("📅 待交割", size="sm", color=C["text_main"], flex=3),
                    文字(f"NT$ {待:+,.0f}", size="sm",
                         color=C["bull"], weight="bold", align="end", flex=4),
                ],
            })
        if 本月 != 0:
            色_m = C["bull"] if 本月 >= 0 else C["bear"]
            rows.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字("📈 本月台股已實現", size="sm",
                         color=C["text_main"], flex=4),
                    文字(f"NT$ {本月:+,.0f}", size="sm",
                         color=色_m, weight="bold", align="end", flex=4),
                ],
            })
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["累計"],
            "cornerRadius": "8px",
            "contents": rows,
        })

    # 一句總結
    body.append(分隔線())
    if 破:
        summary = "👉 紀律：明早 8AM 必做停損"
        sum_color = C["bear"]
    elif 達:
        summary = "👉 紀律：明早 8AM 必做停利"
        sum_color = C["accent"]
    elif 當日損益 > 0:
        summary = "👉 今日勝場，繼續守紀律"
        sum_color = C["bull"]
    elif 當日損益 < -2000:
        summary = "👉 今日小逆風，HOLD 觀察"
        sum_color = C["wait"]
    else:
        summary = "👉 今日盤整，紀律觀察"
        sum_color = C["text_main"]
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
    """推今日台股覆盤卡"""
    try:
        from . import line_push
    except ImportError:
        import line_push
    覆盤 = 組今日覆盤()
    flex = 建構Flex卡(覆盤)
    car = {"type": "carousel", "contents": [flex]}
    alt = f"📋 今日台股覆盤 ({datetime.now():%m/%d %H:%M})"
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
    print(f"=== 台股收盤覆盤 [{datetime.now():%m/%d %H:%M}] ===")
    print(f"\n📊 大盤：")
    for k, v in 覆盤["大盤"].items():
        print(f"  {k}: {v['現價']:,.2f} ({v['當日_pct']:+.2f}%)")
    當日 = 覆盤["持股當日"]
    print(f"\n💰 當日總損益: NT$ {當日['當日總損益_twd']:+,.0f}")
    print(f"   持股 {當日['持股檔數']} 檔")
    print(f"\n🟢 TOP 3:")
    for r in 當日["TOP3"][:3]:
        print(f"  {r['symbol']} {r['name']} {r['當日_pct']:+.2f}%")
    print(f"\n🔴 BOTTOM 3:")
    for r in 當日["BOTTOM3"][:3]:
        print(f"  {r['symbol']} {r['name']} {r['當日_pct']:+.2f}%")

    if len(sys.argv) > 1 and sys.argv[1] == "push":
        print(f"\n推 LINE...")
        if 推Flex卡():
            print("✅ 已推")
