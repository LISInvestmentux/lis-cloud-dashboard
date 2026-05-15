"""
今夜美股行動卡（Phase 33.2）— 美股版的「今日行動」

晚場 21:00-22:00 第一張卡，跟早上「今日行動」結構一致：
  🚨 必做     — 達 +15% / 破 -3%（美股停損嚴 -3%）
  ⏰ 已掛單   — pending_orders 裡 market="US"
  📊 預警     — 接近停利/停損的美股
  ✋ 不該追   — 美股過熱（位階 >= 80）
  📅 入帳     — pending_settlement 裡的美股
  📈 累計     — 美股已實現獲利
  💡 大盤     — VIX / SPY 當日 / SMH 當日 / 黑天鵝
  💵 美股可動用 — house_money_pool 或彈藥 USD 部分

設計理念：
  跟 daily_action_card 一樣的 6 色語意系統
  user 晚上看「該不該掛單、該不該等到隔天」一目了然
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


def 算美股累計已實現(realized_history: list, USD_TWD: float = 31.5) -> dict:
    """只算美股，分本月/本季/今年"""
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
        twd = 0
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
            twd += pnl_usd * USD_TWD
        return {"筆數": 筆, "獲利_usd": round(usd, 2),
                "獲利_twd": round(twd, 0)}

    return {
        "本月": 區間累計(本月_start),
        "本季": 區間累計(本季_start),
        "今年": 區間累計(今年_start),
        "本月_label": f"{today.month} 月",
        "本季_label": f"Q{本季_q}",
        "今年_label": f"{today.year}",
    }


def 組今夜行動() -> dict:
    """主入口：聚焦美股部位 + 美股訊號"""
    try:
        from . import (capital_planner, portfolio_tracker, forex,
                       money_manager, fear_greed, order_reminder)
        from . import technical
    except ImportError:
        import capital_planner, portfolio_tracker, forex
        import money_manager, fear_greed, order_reminder
        import technical

    cfg = capital_planner.載入資金設定()
    USD_TWD = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32))["rate"]

    # 真倉
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=USD_TWD)
    美股持股 = [p for p in 真倉["持股"]
                if not p.get("error") and p.get("is_us")]

    # 1. 必做 — 美股達 +15% / ATR 鎖利 / 破 -3%
    必做 = []
    for r in 真倉["警示"].get("達停利", []):
        if not r.get("is_us"):
            continue
        賣股數 = max(1, r["shares"] // 2)
        # 區分 +15% 達標 vs ATR 鎖利
        警示類型 = r.get("警示_類型", "TAKE_PROFIT")
        if 警示類型 == "ATR_LOCK_PROFIT":
            類型 = "🔵 ATR 鎖利（吊燈停損觸發）"
            atr資訊 = r.get("ATR吊燈", {})
            說明 = f"已破吊燈 ${atr資訊.get('停損價', '?')} / HWM ${atr資訊.get('HWM', '?')}"
        else:
            類型 = "🎯 達 +15% 停利"
            說明 = ""
        必做.append({
            "類型": 類型,
            "symbol": r["symbol"], "name": r.get("name", "")[:10],
            "pnl_pct": r["pnl_pct"],
            "現價_usd": r["current_price"],
            "動作": f"賣 {賣股數} 股 @ ${r['current_price']:.2f}",
            "預估落袋_usd": round(賣股數 * r["current_price"], 2),
            "預估落袋_twd": round(賣股數 * r["current_price"] * USD_TWD, 0),
            "說明": 說明,
        })
    for r in 真倉["警示"].get("破停損", []):
        if not r.get("is_us"):
            continue
        必做.append({
            "類型": "💀 破停損 -3%",
            "symbol": r["symbol"], "name": r.get("name", "")[:10],
            "pnl_pct": r["pnl_pct"],
            "現價_usd": r["current_price"],
            "動作": f"全停損 {r['shares']} 股 @ ${r['current_price']:.2f}",
        })

    # 2. 已掛單 — pending_orders 美股
    全部掛單 = order_reminder.取得待掛單()
    美股掛單 = [o for o in 全部掛單 if o.get("market") == "US"]

    # 3. 預警 — 接近停利/停損（美股）
    預警 = []
    for r in 真倉["警示"].get("接近停利", []):
        if not r.get("is_us"):
            continue
        預警.append({
            "類型": "📈 接近 +15%",
            "symbol": r["symbol"], "name": r.get("name", "")[:10],
            "pnl_pct": r["pnl_pct"],
            "差距": round(15 - r["pnl_pct"], 2),
        })
    for r in 真倉["警示"].get("接近停損", []):
        if not r.get("is_us"):
            continue
        預警.append({
            "類型": "📉 接近 -3% 停損",
            "symbol": r["symbol"], "name": r.get("name", "")[:10],
            "pnl_pct": r["pnl_pct"],
            "差距": round(abs(r["pnl_pct"] - (-3)), 2),
        })

    # 4. 不該追 — 美股過熱
    state_path = 專案根 / "數據" / "positional_state.json"
    scores = {}
    if state_path.exists():
        scores = json.loads(state_path.read_text(encoding="utf-8")).get("scores", {})
    不該追 = []
    for p in 美股持股:
        s = scores.get(p["symbol"], 0) or 0
        if s >= 80 and 0 < p.get("pnl_pct", 0) < 15:
            不該追.append({
                "symbol": p["symbol"], "name": p.get("name", "")[:10],
                "score": s, "pnl_pct": p["pnl_pct"],
            })

    # 5. 即將入帳 — pending_settlement 美股
    流入 = []
    for p in cfg.get("pending_settlement", []):
        sym = p.get("symbol", "")
        if sym.endswith(".TW") or sym.endswith(".TWO"):
            continue  # 跳過台股
        流入.append({
            "date": p.get("settlement_date"),
            "symbol": sym,
            "amount_usd": p.get("net_usd"),
            "amount_twd": p.get("net_twd"),
        })
    流入.sort(key=lambda r: r.get("date", ""))

    # 6. 累計已實現（美股）
    realized_history = cfg.get("realized_history", [])
    累計 = 算美股累計已實現(realized_history, USD_TWD)

    # 7. 大盤 — VIX / SPY / SMH
    大盤 = {}
    for sym, label in [("^VIX", "VIX"), ("SPY", "SPY"), ("SMH", "SMH"),
                        ("QQQ", "QQQ")]:
        try:
            歷史, _ = technical.取得每日股價(sym, period="3d")
            if 歷史 and len(歷史) >= 2:
                現 = 歷史[0]["close"]
                昨 = 歷史[1]["close"]
                大盤[label] = {
                    "現價": round(現, 2),
                    "當日_pct": round((現/昨 - 1) * 100, 2),
                }
        except Exception:
            continue

    # 8. F&G
    try:
        fg_data = fear_greed.取得恐慌貪婪指數()
        fg = fg_data.get("score") if fg_data else None
    except Exception:
        fg = None

    # 9. 震盪預警（如果系統有跑過）
    震盪 = None
    try:
        from . import volatility_alert
        震盪 = volatility_alert.震盪預警判定()
    except Exception:
        try:
            import volatility_alert
            震盪 = volatility_alert.震盪預警判定()
        except Exception:
            pass

    # 10. 美股市值/損益（直接取自 portfolio_tracker 的「美股小計」）
    美股小計 = 真倉.get("美股小計", {})
    美股總市值_usd = 美股小計.get("市值_usd", 0)
    美股損益_usd = 美股小計.get("損益_usd", 0)
    美股損益率 = 美股小計.get("損益率_pct", 0)

    return {
        "必做": 必做,
        "已掛單": 美股掛單,
        "預警": 預警,
        "不該追": 不該追[:5],
        "資金流入": 流入,
        "累計已實現": 累計,
        "大盤": 大盤,
        "F&G": fg,
        "震盪預警": 震盪,
        "美股總市值_usd": round(美股總市值_usd, 2),
        "美股損益_usd": round(美股損益_usd, 2),
        "美股損益率": round(美股損益率, 2),
        "美股檔數": len(美股持股),
        "USD_TWD": USD_TWD,
    }


def 建構Flex卡(行動: dict) -> dict:
    """美股今夜行動卡 — 6 色語意系統（跟 daily_action_card 同風格）"""
    try:
        from . import flex_builder
    except ImportError:
        import flex_builder

    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    # 6 色語意系統
    bg = {
        "必做":   "#EF44441A",
        "進行":   "#3B82F61A",
        "預警":   "#FBBF241A",
        "不該追": "#F59E0B1A",
        "資金":   "#22C55E1A",
        "累計":   "#A855F71A",
        "大盤":   "#6B72801A",
    }
    色 = {
        "必做":   "#EF4444",
        "進行":   "#3B82F6",
        "預警":   "#FBBF24",
        "不該追": "#F59E0B",
        "資金":   "#22C55E",
        "累計":   "#A855F7",
    }

    body = []

    # Header
    body.append({
        "type": "box", "layout": "vertical",
        "contents": [
            文字("🌙 今夜美股行動", size="xl",
                 color=C["accent"], weight="bold"),
            文字(f"{datetime.now():%m/%d %a %H:%M} · "
                 f"{行動['美股檔數']} 檔 / "
                 f"${行動['美股總市值_usd']:,.0f} ({行動['美股損益率']:+.1f}%)",
                 size="xs", color=C["text_main"]),
        ],
    })
    body.append(分隔線())

    # 1. 必做（紅）
    必做 = 行動.get("必做", [])
    if 必做:
        必做_contents = [
            文字(f"🚨 必做 ({len(必做)})", size="md",
                 color=C["bear"], weight="bold"),
        ]
        for x in 必做:
            必做_contents.append(
                文字(f"{x['類型']} {x['symbol']} {x['pnl_pct']:+.2f}%",
                     size="sm", color=C["text_main"], weight="bold"))
            必做_contents.append(
                文字(f"→ {x['動作']}",
                     size="md", color=C["accent"], weight="bold", wrap=True))
            if x.get("預估落袋_twd"):
                必做_contents.append(
                    文字(f"預估落袋 ${x['預估落袋_usd']:,.2f} "
                         f"(NT$ {x['預估落袋_twd']:,.0f})",
                         size="xs", color=C["bull"]))
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "12px",
            "backgroundColor": bg["必做"],
            "cornerRadius": "8px",
            "contents": 必做_contents,
        })
    else:
        body.append({
            "type": "box", "layout": "vertical",
            "margin": "md", "paddingAll": "12px",
            "backgroundColor": bg["資金"],
            "cornerRadius": "8px",
            "contents": [
                文字("✅ 美股無觸發訊號", size="md",
                     color=C["bull"], weight="bold"),
                文字("紀律觀察 · 等開盤後動態",
                     size="xxs", color=C["text_subtle"]),
            ],
        })

    # 2. 已掛單（藍）
    已掛 = 行動.get("已掛單", [])
    if 已掛:
        rows = [文字(f"⏰ 已掛單 ({len(已掛)})", size="md",
                     color=色["進行"], weight="bold")]
        for o in 已掛:
            rows.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"{o.get('symbol')} {o.get('action')}",
                         size="sm", color=C["text_main"],
                         weight="bold", flex=4),
                    文字(f"{o.get('shares')} 股 @ ${o.get('price'):.2f}",
                         size="sm", color=色["進行"],
                         weight="bold", align="end", flex=5),
                ],
            })
            if o.get("note"):
                rows.append(文字(f"  {o.get('note')[:32]}",
                                 size="xxs", color=C["text_dim"], wrap=True))
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["進行"],
            "cornerRadius": "8px",
            "contents": rows,
        })

    # 3. 預警（黃）
    預警 = 行動.get("預警", [])
    if 預警:
        rows = [文字(f"📊 預警 ({len(預警)})", size="md",
                     color=C["wait"], weight="bold")]
        for w in 預警[:3]:
            rows.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"{w['symbol']} {w['name']}",
                         size="sm", color=C["text_main"],
                         weight="bold", flex=5),
                    文字(f"{w['pnl_pct']:+.2f}% 差{w['差距']:.1f}%",
                         size="sm", color=C["wait"],
                         weight="bold", align="end", flex=5),
                ],
            })
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["預警"],
            "cornerRadius": "8px",
            "contents": rows,
        })

    # 4. 不該追（橘）
    不該追 = 行動.get("不該追", [])
    if 不該追:
        names = " · ".join(f"{x['symbol']}({x['score']:.0f})" for x in 不該追)
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["不該追"],
            "cornerRadius": "8px",
            "contents": [
                文字(f"✋ 不該追 ({len(不該追)})", size="md",
                     color=色["不該追"], weight="bold"),
                文字(names, size="sm", color=C["text_main"],
                     weight="bold", wrap=True),
                文字("過熱別追加 · 等回調再說", size="xs",
                     color=C["text_dim"]),
            ],
        })

    # 5. 即將入帳（綠）
    流入 = 行動.get("資金流入", [])
    if 流入:
        rows = [文字("📅 即將入帳（美股）", size="md",
                     color=C["bull"], weight="bold")]
        for f in 流入:
            # 容錯：拆兩筆撥款時可能只有 net_twd 沒 net_usd
            usd = f.get('amount_usd')
            twd = f.get('amount_twd') or 0
            if usd is None or usd == 0:
                # 推估 USD：用匯率 ≈ 31.5 回推
                usd = twd / (行動.get('USD_TWD') or 31.5)
            rows.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"{f['date']} {f['symbol']}",
                         size="sm", color=C["text_main"], flex=5),
                    文字(f"+${usd:,.0f}",
                         size="sm", color=C["bull"],
                         align="end", weight="bold", flex=4),
                ],
            })
            if twd:
                rows.append(文字(f"  ≈ NT$ {twd:,.0f}",
                                 size="xxs", color=C["text_dim"]))
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["資金"],
            "cornerRadius": "8px",
            "contents": rows,
        })

    # 6. 累計已實現（紫）
    累 = 行動.get("累計已實現", {})
    有累計 = 累 and (累["本月"]["筆數"] + 累["本季"]["筆數"] + 累["今年"]["筆數"]) > 0
    if 有累計:
        累_rows = [文字("📈 美股累計已實現", size="md",
                       color=色["累計"], weight="bold")]
        for 期間, 期label in [("本月", 累["本月_label"]),
                              ("本季", 累["本季_label"]),
                              ("今年", 累["今年_label"])]:
            r = 累[期間]
            usd = r["獲利_usd"]
            twd = r["獲利_twd"]
            金色 = C["bull"] if usd >= 0 else C["bear"]
            累_rows.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"{期間} {期label}", size="sm",
                         color=C["text_main"], flex=3),
                    文字(f"${usd:+,.2f}", size="sm",
                         color=金色, weight="bold",
                         align="end", flex=3),
                ],
            })
            累_rows.append(文字(f"   ≈ NT$ {twd:+,.0f} ({r['筆數']} 筆)",
                                size="xxs", color=C["text_dim"], wrap=True))
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["累計"],
            "cornerRadius": "8px",
            "contents": 累_rows,
        })

    # 7. 震盪預警（如果有）
    震 = 行動.get("震盪預警")
    if 震 and 震.get("有警報"):
        rows = [文字(f"⚠️ 震盪預警", size="md",
                     color=C["wait"], weight="bold")]
        for a in 震["警報"][:2]:
            rows.append(文字(f"{a['類型']} — {a['等級']}",
                             size="sm", color=C["text_main"],
                             weight="bold", wrap=True))
            rows.append(文字(f"  {a['訊息'][:50]}", size="xxs",
                             color=C["text_dim"], wrap=True))
            rows.append(文字(f"  → {a['建議'][:40]}", size="xs",
                             color=C["accent"], wrap=True))
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["預警"],
            "cornerRadius": "8px",
            "contents": rows,
        })

    # 8. 大盤 footer
    大盤 = 行動.get("大盤", {})
    fg = 行動.get("F&G")
    body.append(分隔線())
    if 大盤:
        rows = []
        for label in ["VIX", "SPY", "QQQ", "SMH"]:
            d = 大盤.get(label)
            if not d:
                continue
            色2 = (C["bear"] if (label == "VIX" and d["現價"] > 25)
                   else C["bull"] if d["當日_pct"] >= 0 else C["bear"])
            rows.append(
                文字(f"{label} {d['現價']:.1f} ({d['當日_pct']:+.1f}%)",
                     size="xs", color=色2, weight="bold", flex=1))
        if rows:
            body.append({"type": "box", "layout": "horizontal", "contents": rows})

    if fg is not None:
        body.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字(f"F&G {fg:.0f}", size="sm",
                     color=(C["bear"] if fg > 75 else
                            C["bull"] if fg < 25 else
                            C["text_main"]),
                     weight="bold", flex=3),
                文字(f"匯 {行動['USD_TWD']:.2f}", size="sm",
                     color=C["text_main"], weight="bold",
                     align="end", flex=3),
            ],
        })

    # 一句總結
    if 必做:
        summary = "👉 開盤後先動「必做」"
        sum_color = C["bear"]
    elif 已掛單 := 行動.get("已掛單"):
        summary = f"👉 等成交 ({len(已掛單)} 筆已掛)"
        sum_color = 色["進行"]
    elif 預警:
        summary = "👉 守紀律觀察觸發"
        sum_color = C["wait"]
    else:
        summary = "👉 紀律內，可看價值區候選"
        sum_color = C["bull"]
    body.append(分隔線())
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
    """推今夜美股行動卡"""
    try:
        from . import line_push
    except ImportError:
        import line_push
    行動 = 組今夜行動()
    flex = 建構Flex卡(行動)
    car = {"type": "carousel", "contents": [flex]}
    alt = f"🌙 今夜美股行動 ({datetime.now():%m/%d %H:%M})"
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

    行動 = 組今夜行動()
    print("=" * 60)
    print(f"🌙 今夜美股行動")
    print("=" * 60)

    print(f"\n美股 {行動['美股檔數']} 檔 / "
          f"${行動['美股總市值_usd']:,.2f} "
          f"({行動['美股損益率']:+.2f}%)")

    print(f"\n🚨 必做 {len(行動['必做'])} 件")
    for x in 行動["必做"]:
        print(f"  {x['類型']} {x['symbol']} {x['pnl_pct']:+.2f}% → {x['動作']}")
        if x.get("預估落袋_twd"):
            print(f"     預估落袋 ${x['預估落袋_usd']:.2f} = NT$ {x['預估落袋_twd']:,.0f}")

    print(f"\n⏰ 已掛單 {len(行動['已掛單'])} 筆")
    for o in 行動["已掛單"]:
        print(f"  {o.get('symbol')} {o.get('action')} {o.get('shares')} @ ${o.get('price'):.2f}")

    print(f"\n📊 預警 {len(行動['預警'])} 件")
    for w in 行動["預警"]:
        print(f"  {w['類型']} {w['symbol']} 差 {w['差距']:.1f}%")

    print(f"\n✋ 不該追 {len(行動['不該追'])} 檔")
    for x in 行動["不該追"]:
        print(f"  {x['symbol']} 位階 {x['score']:.0f}")

    print(f"\n📈 累計已實現")
    累 = 行動["累計已實現"]
    for 期 in ["本月", "本季", "今年"]:
        r = 累[期]
        print(f"  {期} {累[期+'_label']}: ${r['獲利_usd']:+,.2f} "
              f"≈ NT$ {r['獲利_twd']:+,.0f} ({r['筆數']} 筆)")

    震 = 行動.get("震盪預警")
    if 震 and 震.get("有警報"):
        print(f"\n⚠️ 震盪預警: {震['最高等級']}")
        for a in 震["警報"]:
            print(f"  [{a['等級']}] {a['類型']} — {a['訊息']}")

    if len(sys.argv) > 1 and sys.argv[1] == "push":
        print(f"\n推 LINE...")
        if 推Flex卡():
            print("✅ 已推 LINE")
