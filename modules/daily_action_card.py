"""
今日行動卡（Phase 33.2）

把所有訊號濃縮成「你今天該做什麼」一張卡。
其他資料卡（全息儀表/即時決策/主情報等）變成「補充」。

層級：
  🚨 必做 — 達 +15% / 破 -3% 已觸發
  ⚠️ 待觸發 — pending_orders 已掛單
  ✋ 不該做 — 過熱別追 / 訊號但無彈藥
  📅 資金流 — 待交割 / 即將解鎖
  💡 整體狀況 — F&G / VIX / 黑天鵝

設計目標：
  user 早上 30 秒看完 = 知道今天要動什麼。
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


def 算累計已實現(realized_history: list, USD_TWD: float = 31.5) -> dict:
    """
    從 realized_history 算月/季/年累計已實現獲利（分台股 / 美股）
    """
    from datetime import date as _date
    today = datetime.now().date()
    本月_start = today.replace(day=1)
    本季_q = (today.month - 1) // 3 + 1
    本季_start = today.replace(month=(本季_q - 1) * 3 + 1, day=1)
    今年_start = today.replace(month=1, day=1)

    def 換算twd(r):
        pnl_usd = r.get("pnl_usd")
        pnl_twd = r.get("pnl_twd")
        # 美股看 pnl_usd，台股看 pnl_twd；都沒就推估
        if pnl_usd is not None:
            return pnl_usd * USD_TWD
        if pnl_twd is not None:
            return pnl_twd
        return 0

    def 是美股(r):
        sym = r.get("symbol", "")
        return not (sym.endswith(".TW") or sym.endswith(".TWO"))

    def 區間累計(start):
        US_筆 = 0; US_twd = 0
        TW_筆 = 0; TW_twd = 0
        for r in realized_history:
            try:
                d = datetime.strptime(r.get("date", ""), "%Y-%m-%d").date()
            except Exception:
                continue
            if d < start:
                continue
            twd = 換算twd(r)
            if 是美股(r):
                US_筆 += 1
                US_twd += twd
            else:
                TW_筆 += 1
                TW_twd += twd
        return {
            "US": {"筆數": US_筆, "獲利_twd": round(US_twd, 0)},
            "TW": {"筆數": TW_筆, "獲利_twd": round(TW_twd, 0)},
            "合計_twd": round(US_twd + TW_twd, 0),
            "合計筆數": US_筆 + TW_筆,
        }

    return {
        "本月": 區間累計(本月_start),
        "本季": 區間累計(本季_start),
        "今年": 區間累計(今年_start),
        "本月_label": f"{today.month} 月",
        "本季_label": f"Q{本季_q}",
        "今年_label": f"{today.year}",
    }


def 組今日行動() -> dict:
    """主入口：整合所有訊號 + pending + 大盤狀況"""
    try:
        from . import (capital_planner, portfolio_tracker, forex,
                       money_manager, bottom_detector, fear_greed,
                       order_reminder)
    except ImportError:
        import capital_planner, portfolio_tracker, forex
        import money_manager, bottom_detector, fear_greed
        import order_reminder

    cfg = capital_planner.載入資金設定()
    USD_TWD = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32))["rate"]
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=USD_TWD)
    現金 = cfg.get("current_cash_twd", 0)
    持股市值 = 真倉["總計"]["市值_twd"]
    總資產 = 持股市值 + 現金

    # 待交割
    待交割 = sum(p.get("net_twd", 0) for p in cfg.get("pending_settlement", []))

    # 彈藥
    彈藥 = money_manager.計算可用彈藥(
        總資金=總資產, 現金=現金, 持股成本_twd=持股市值,
        目標閒錢比_pct=35)

    # 1. 必做 — 已觸發停利/停損
    必做 = []
    for r in 真倉["警示"].get("達停利", []):
        賣股數 = max(1, r["shares"] // 2)
        市場 = "美股" if r.get("is_us") else "台股"
        貨幣 = "$" if r.get("is_us") else "NT$"
        # 區分 +15% 達標 vs ATR 鎖利
        警示類型 = r.get("警示_類型", "TAKE_PROFIT")
        類型 = ("🔵 ATR 鎖利（吊燈停損）" if 警示類型 == "ATR_LOCK_PROFIT"
                else "🎯 達 +15% 停利")
        必做.append({
            "類型": 類型,
            "symbol": r["symbol"], "name": r.get("name", "")[:8],
            "pnl_pct": r["pnl_pct"],
            "動作": f"賣 {賣股數} 股 @ {貨幣}{r['current_price']:.2f}",
            "預估落袋": round(賣股數 * r["current_price"] * (USD_TWD if r.get("is_us") else 1), 0),
            "ATR吊燈": r.get("ATR吊燈"),
        })
    for r in 真倉["警示"].get("破停損", []):
        市場 = "美股" if r.get("is_us") else "台股"
        貨幣 = "$" if r.get("is_us") else "NT$"
        必做.append({
            "類型": "💀 破停損",
            "symbol": r["symbol"], "name": r.get("name", "")[:8],
            "pnl_pct": r["pnl_pct"],
            "動作": f"全停損 {r['shares']} 股 @ {貨幣}{r['current_price']:.2f}",
        })

    # 2. 待觸發 — pending_orders
    待觸發 = order_reminder.取得待掛單()

    # 3. 預警 — 接近停利/停損
    預警 = []
    for r in 真倉["警示"].get("接近停利", []):
        預警.append({
            "類型": "📈 接近 +15%",
            "symbol": r["symbol"], "name": r.get("name", "")[:8],
            "pnl_pct": r["pnl_pct"],
            "差距": round(15 - r["pnl_pct"], 2),
        })
    for r in 真倉["警示"].get("接近停損", []):
        是美股 = r.get("is_us", False)
        停損值 = -3 if 是美股 else -5
        預警.append({
            "類型": "📉 接近停損",
            "symbol": r["symbol"], "name": r.get("name", "")[:8],
            "pnl_pct": r["pnl_pct"],
            "差距": round(abs(r["pnl_pct"] - 停損值), 2),
        })

    # 4. 不該做 — 過熱別追
    state_path = 專案根 / "數據" / "positional_state.json"
    scores = {}
    if state_path.exists():
        scores = json.loads(state_path.read_text(encoding="utf-8")).get("scores", {})
    不該做 = []
    for p in 真倉["持股"]:
        if p.get("error"):
            continue
        s = scores.get(p["symbol"], 0) or 0
        if s >= 80 and 0 < p.get("pnl_pct", 0) < 15:
            不該做.append({
                "symbol": p["symbol"], "name": p.get("name", "")[:8],
                "score": s, "pnl_pct": p["pnl_pct"],
                "理由": "過熱別追加",
            })

    # 5. 大盤狀況
    fg = None
    vix = None
    黑天鵝 = 0
    try:
        fg_data = fear_greed.取得恐慌貪婪指數()
        fg = fg_data.get("score") if fg_data else None
    except Exception:
        pass
    try:
        sop = bottom_detector.即時底部判定()
        黑天鵝 = sop.get("命中數", 0)
        vix = (sop.get("原始資料") or {}).get("VIX")
        if vix:
            vix = round(vix, 2)
    except Exception:
        pass

    # 6. 待交割流入時間軸
    流入 = []
    for p in cfg.get("pending_settlement", []):
        流入.append({
            "date": p.get("settlement_date"),
            "symbol": p.get("symbol"),
            "amount": p.get("net_twd"),
        })
    流入.sort(key=lambda r: r.get("date", ""))

    # 7. 累計已實現（月/季/年）
    realized_history = cfg.get("realized_history", [])
    累計 = 算累計已實現(realized_history, USD_TWD)

    # 8. 震盪預警（Phase 33.2 — 連 5+ 天 F&G 極端）
    震盪 = None
    try:
        try:
            from . import volatility_alert
        except ImportError:
            import volatility_alert
        # 每天 8AM 跑一次，會自動把今日 F&G/VIX 寫進歷史
        每日 = volatility_alert.每日記錄()
        震盪 = 每日.get("震盪預警")
    except Exception as e:
        print(f"  ⚠️ 震盪預警失敗：{e}")

    # 8.5 FRED 美國總經（Phase 36.1 — 黑天鵝預警根本指標）
    fred = None
    try:
        try:
            from . import fred_data
        except ImportError:
            import fred_data
        fred = fred_data.全套總經分析()
    except Exception as e:
        print(f"  ⚠️ FRED 抓取失敗（可能未設 FRED_API_KEY）：{e}")

    # 9. 資金量適配（Phase 33.2 — 警告不適合的戰法）
    資金檢查 = None
    try:
        try:
            from . import capital_size_check
        except ImportError:
            import capital_size_check
        資金檢查 = capital_size_check.全面適配檢查(總資產)
    except Exception as e:
        print(f"  ⚠️ 資金量檢查失敗：{e}")

    # 10. Q4 散戶反指（Phase 36.5）
    散戶反指 = None
    try:
        try:
            from . import sentiment_indicator
        except ImportError:
            import sentiment_indicator
        散戶反指 = sentiment_indicator.散戶反指評分()
    except Exception as e:
        pass

    # 11. 左側買回機會（Phase 36.8 — Sylvie 教學）
    買回機會 = []
    try:
        try:
            from . import left_side_rebuy
        except ImportError:
            import left_side_rebuy
        買回機會 = left_side_rebuy.掃描所有買回機會(cfg)
    except Exception as e:
        pass

    # 12. 昨日新聞快取（Phase 36.9 — 自動內化）
    今日新聞 = None
    try:
        from pathlib import Path as _P
        import json as _j
        news_path = 專案根 / "數據" / "cache" / "daily_news" / f"{datetime.now():%Y-%m-%d}.json"
        if not news_path.exists():
            from datetime import timedelta
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            news_path = 專案根 / "數據" / "cache" / "daily_news" / f"{yesterday}.json"
        if news_path.exists():
            今日新聞 = _j.loads(news_path.read_text(encoding="utf-8"))
    except Exception:
        pass

    # 13. 調節後重佈局（Phase 36.10 — Sylvie 教學）⭐ 最重要
    重佈局 = None
    try:
        try:
            from . import rebalance_after_sell
        except ImportError:
            import rebalance_after_sell
        重佈局 = rebalance_after_sell.重佈局建議(cfg, USD_TWD)
    except Exception as e:
        print(f"  ⚠️ 重佈局建議失敗：{e}")

    # 14. 每週位階輪動（Phase 36.12 — LIS 派吸收 Sylvie 美股輪動但降頻）
    週輪動 = None
    try:
        try:
            from . import weekly_rotation
        except ImportError:
            import weekly_rotation
        # 只週一有資料，其他天回 None
        週輪動 = weekly_rotation.週輪動建議(cfg)
    except Exception as e:
        print(f"  ⚠️ 週輪動失敗：{e}")

    return {
        "必做": 必做,
        "待觸發": 待觸發,
        "預警": 預警,
        "不該做": 不該做[:5],
        "大盤": {"F&G": fg, "VIX": vix, "黑天鵝命中": 黑天鵝},
        "彈藥": 彈藥["可動用彈藥_twd"],
        "閒錢比": 彈藥["水位"]["閒錢比_pct"],
        "模式": 彈藥["模式"],
        "待交割": 待交割,
        "資金流入": 流入,
        "總資產": 總資產 + 待交割,
        "累計已實現": 累計,
        "震盪預警": 震盪,
        "資金檢查": 資金檢查,
        "FRED總經": fred,
        "散戶反指": 散戶反指,
        "左側買回": 買回機會,
        "今日新聞": 今日新聞,
        "重佈局": 重佈局,
        "週輪動": 週輪動,
    }


def 推LINE文字版(行動: dict) -> bool:
    """濃縮文字版，每天 8:05 推 LINE（在全套晨報後）"""
    try:
        try:
            from . import line_push
        except ImportError:
            import line_push
    except Exception:
        return False

    片段 = [f"🎯 LIS 今日行動 ({datetime.now():%m/%d})"]
    片段.append(f"━━━━━━━━━━━━━━━━")

    # 必做
    if 行動["必做"]:
        片段.append(f"\n🚨 必做 ({len(行動['必做'])} 件)：")
        for x in 行動["必做"]:
            片段.append(f"  {x['類型']}  {x['symbol']} {x['name']} {x['pnl_pct']:+.2f}%")
            片段.append(f"     → {x['動作']}")
            if x.get("預估落袋"):
                片段.append(f"     落袋 ~NT$ {x['預估落袋']:,.0f}")
    else:
        片段.append(f"\n✅ 無觸發訊號（持股紀律內）")

    # 待觸發
    if 行動["待觸發"]:
        片段.append(f"\n⚠️ 待觸發 ({len(行動['待觸發'])} 筆已掛單)：")
        for o in 行動["待觸發"][:3]:
            unit = "$" if o.get("market") == "US" else "NT$"
            片段.append(f"  ✓ {o.get('symbol')} {o.get('action')} {o.get('shares')} 股"
                          f" @ {unit}{o.get('price'):.2f}")

    # 預警
    if 行動["預警"]:
        片段.append(f"\n📊 預警 ({len(行動['預警'])} 件)：")
        for w in 行動["預警"][:3]:
            片段.append(f"  {w['類型']} {w['symbol']} {w['name']}"
                          f" {w['pnl_pct']:+.2f}% (差 {w['差距']:.1f}%)")

    # 不該做
    if 行動["不該做"]:
        names = ", ".join(f"{x['symbol']}({x['score']:.0f})" for x in 行動["不該做"][:5])
        片段.append(f"\n✋ 不該追 ({len(行動['不該做'])} 檔過熱)：{names}")

    # 資金流入
    if 行動["資金流入"]:
        片段.append(f"\n📅 即將入帳 ({len(行動['資金流入'])} 筆)：")
        for f in 行動["資金流入"]:
            片段.append(f"  {f['date']} {f['symbol']} +NT$ {f['amount']:,.0f}")

    # 整體
    fg = 行動['大盤']['F&G']
    vix = 行動['大盤']['VIX']
    sop = 行動['大盤']['黑天鵝命中']
    片段.append(f"\n💡 整體狀況：")
    片段.append(f"  F&G {fg or '?'} / VIX {vix or '?'} / 黑天鵝 {sop}/5")
    片段.append(f"  彈藥 NT$ {行動['彈藥']:,.0f} / 閒錢比 {行動['閒錢比']:.1f}%")
    片段.append(f"  總資產 NT$ {行動['總資產']:,.0f}（含待交割 NT$ {行動['待交割']:,.0f}）")

    # 一句總結
    if 行動["必做"]:
        片段.append(f"\n👉 今天**先動「必做」**，其他卡當參考")
    elif 行動["待觸發"] or 行動["預警"]:
        片段.append(f"\n👉 今天**守紀律等觸發**，不買新")
    else:
        片段.append(f"\n👉 今天**完全紀律內**，可看價值區候選")

    訊息 = "\n".join(片段)
    try:
        line_push.推播文字訊息(訊息)
        return True
    except Exception as e:
        print(f"推播失敗: {e}")
        return False


def 建構Flex卡(行動: dict) -> dict:
    """漂亮版 Flex 卡 — 放 carousel 第一張"""
    try:
        from . import flex_builder
    except ImportError:
        import flex_builder
    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    # LINE Flex 用 hex 8 位（RRGGBBAA），rgba() 不被支援
    # 顏色語義系統：紅(緊急)/藍(進行)/黃(注意)/橘(警告)/綠(好消息)/紫(成績)
    bg = {
        "必做":   "#EF44441A",  # 🔴 紅 — 緊急（賣/停損）
        "待觸發": "#3B82F61A",  # 🔵 藍 — 進行中（已掛單等成交）
        "預警":   "#FBBF241A",  # 🟡 黃 — 注意（接近觸發）
        "不該追": "#F59E0B1A",  # 🟠 橘 — 警告（別追）
        "資金":   "#22C55E1A",  # 🟢 綠 — 好消息（入帳）
        "累計":   "#A855F71A",  # 🟣 紫 — 成績（累計獲利）
    }
    色 = {
        "必做":   "#EF4444",
        "進行":   "#3B82F6",  # 藍
        "預警":   "#FBBF24",
        "不該追": "#F59E0B",
        "資金":   "#22C55E",
        "累計":   "#A855F7",  # 紫
    }

    body = []

    # Header
    body.append({
        "type": "box", "layout": "vertical",
        "contents": [
            文字(f"🎯 今日行動", size="xl",
                 color=C["accent"], weight="bold"),
            文字(f"{datetime.now():%m/%d %a} · 一張卡看完該做什麼",
                 size="xs", color=C["text_main"]),  # 提亮
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
                文字(f"{x['類型']} {x['symbol']} {x['name']} {x['pnl_pct']:+.2f}%",
                     size="sm", color=C["text_main"], weight="bold"))
            # 動作 = 最重點 → 改黃色加粗放大
            必做_contents.append(
                文字(f"→ {x['動作']}",
                     size="md", color=C["accent"], weight="bold", wrap=True))
            if x.get("預估落袋"):
                必做_contents.append(
                    文字(f"預估落袋 NT$ {x['預估落袋']:,.0f}",
                         size="xs", color=C["bull"], wrap=True))
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
            "backgroundColor": "rgba(34,197,94,0.08)",
            "cornerRadius": "8px",
            "contents": [
                文字("✅ 無觸發訊號", size="md",
                     color=C["bull"], weight="bold"),
                文字("持股全部紀律內 · 守紀律觀察即可",
                     size="xxs", color=C["text_subtle"]),
            ],
        })

    # 2. 待觸發掛單（藍）— 進行中
    待觸發 = 行動.get("待觸發", [])
    if 待觸發:
        rows = []
        rows.append(文字(f"⏰ 已掛單 ({len(待觸發)})",
                          size="md", color=色["進行"], weight="bold"))
        for o in 待觸發[:4]:
            unit = "$" if o.get("market") == "US" else "NT$"
            rows.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"{o.get('symbol')} {o.get('action')}",
                         size="sm", color=C["text_main"],
                         weight="bold", flex=4),
                    文字(f"{o.get('shares')} 股 @ {unit}{o.get('price'):.2f}",
                         size="sm", color=色["進行"],  # 藍亮
                         weight="bold", align="end", flex=5),
                ],
            })
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["待觸發"],
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

    # 4. 不該追（橘 — 警告）
    不該追 = 行動.get("不該做", [])
    if 不該追:
        names = " · ".join(f"{x['symbol']}({x['score']:.0f})" for x in 不該追[:5])
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["不該追"],
            "cornerRadius": "8px",
            "contents": [
                文字(f"✋ 不該追 ({len(不該追)} 檔過熱)", size="md",
                     color=色["不該追"], weight="bold"),
                文字(names, size="sm", color=C["text_main"],
                     weight="bold", wrap=True),
                文字("過熱別追加 · 等價值區再說", size="xs",
                     color=C["text_dim"]),
            ],
        })

    # 5. 資金流入（綠）
    流入 = 行動.get("資金流入", [])
    if 流入:
        rows = [文字("📅 即將入帳", size="md",
                     color=C["bull"], weight="bold")]
        for f in 流入:
            rows.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"{f['date']} {f['symbol']}",
                         size="sm", color=C["text_main"], flex=5),
                    文字(f"+NT$ {f['amount']:,.0f}",
                         size="sm", color=C["bull"],
                         align="end", weight="bold", flex=4),
                ],
            })
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["資金"],
            "cornerRadius": "8px",
            "contents": rows,
        })

    # 6. 累計已實現（月/季/年）— 投資成績追蹤
    累 = 行動.get("累計已實現", {})
    if 累:
        累_rows = [文字("📈 累計已實現", size="md",
                       color=色["累計"], weight="bold")]
        for 期間, 期label in [("本月", 累["本月_label"]),
                              ("本季", 累["本季_label"]),
                              ("今年", 累["今年_label"])]:
            r = 累[期間]
            合計 = r["合計_twd"]
            金額色 = C["bull"] if 合計 >= 0 else C["bear"]
            US_part = (f"US {r['US']['獲利_twd']:+,.0f}" if r['US']['筆數'] > 0 else "")
            TW_part = (f"TW {r['TW']['獲利_twd']:+,.0f}" if r['TW']['筆數'] > 0 else "")
            細節 = " / ".join(x for x in [US_part, TW_part] if x) or "尚無交易"
            累_rows.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"{期間} {期label}", size="sm",
                         color=C["text_main"], flex=3),
                    文字(f"NT$ {合計:+,.0f}", size="sm",
                         color=金額色, weight="bold",
                         align="end", flex=4),
                ],
            })
            累_rows.append(文字(f"   {細節}", size="xxs",
                                color=C["text_dim"], wrap=True))
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["累計"],  # 紫底（成績）
            "cornerRadius": "8px",
            "contents": 累_rows,
        })

    # 6.5 震盪預警（Phase 33.2 — F&G 連續極端值警示）
    震 = 行動.get("震盪預警")
    if 震 and 震.get("有警報"):
        震_rows = [文字(f"⚠️ 震盪預警 — {震['最高等級']}",
                       size="md", color=C["wait"], weight="bold")]
        for a in 震["警報"][:2]:
            震_rows.append(文字(f"{a['類型']}",
                                size="sm", color=C["text_main"],
                                weight="bold"))
            震_rows.append(文字(f"  {a['訊息'][:50]}",
                                size="xxs", color=C["text_dim"], wrap=True))
            震_rows.append(文字(f"  → {a['建議'][:40]}",
                                size="xs", color=C["accent"], wrap=True))
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["預警"],
            "cornerRadius": "8px",
            "contents": 震_rows,
        })

    # 6.6 資金量適配（Phase 33.2 — 警告不適合的戰法）
    # 只在「別碰」項目 > 0 時顯示（避免 spam）
    資 = 行動.get("資金檢查")
    if 資 and 資.get("別碰"):
        別碰 = 資["別碰"]
        資_rows = [文字(f"⚠️ 資金不適合 ({len(別碰)} 戰法)",
                       size="md", color=C["bear"], weight="bold")]
        for x in 別碰[:3]:
            資_rows.append(文字(f"❌ {x['戰法']}", size="sm",
                                color=C["text_main"], weight="bold"))
            資_rows.append(文字(f"   {x['訊息'][:50]}",
                                size="xxs", color=C["text_dim"], wrap=True))
        資_rows.append(文字(f"→ {資['推薦'][:50]}",
                            size="xs", color=C["accent"], wrap=True))
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": bg["不該追"],
            "cornerRadius": "8px",
            "contents": 資_rows,
        })

    # 6.7 美國總經（Phase 36.1 — FRED）
    fred = 行動.get("FRED總經")
    if fred and fred.get("fed_rate"):
        # 事件預警（FOMC 14 天內）優先
        事件 = fred.get("事件預警", [])
        if 事件:
            for e in 事件[:1]:
                色_e = C["bear"] if e["色"] == "bear" else C["wait"]
                body.append({
                    "type": "box", "layout": "vertical", "spacing": "xs",
                    "margin": "md", "paddingAll": "10px",
                    "backgroundColor": bg["預警"],
                    "cornerRadius": "8px",
                    "contents": [
                        文字(f"{e['類型']}", size="md",
                             color=色_e, weight="bold"),
                        文字(f"{e['日期']} (還 {e['天數']} 天)",
                             size="sm", color=C["text_main"]),
                        文字(f"→ {e['建議'][:40]}",
                             size="xs", color=C["accent"], wrap=True),
                    ],
                })

        # 總經 row
        spread = fred.get("10y_2y_spread")
        cpi_yoy = fred.get("cpi_yoy")
        fed_rate = fred.get("fed_rate")
        t10y = fred.get("10y_treasury")
        倒掛 = fred.get("倒掛分析", {})
        色_倒 = (C["bear"] if 倒掛.get("色") == "bear"
                 else C["wait"] if 倒掛.get("色") == "wait"
                 else C["bull"])
        body.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "margin": "md", "paddingAll": "10px",
            "backgroundColor": "#FFFFFF0A",
            "cornerRadius": "8px",
            "contents": [
                文字("🇺🇸 美國總經", size="sm",
                     color=C["text_dim"], weight="bold"),
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"Fed {fed_rate:.2f}%" if fed_rate else "Fed ?",
                             size="xs", color=C["text_main"], flex=2),
                        文字(f"CPI {cpi_yoy:.1f}%" if cpi_yoy else "CPI ?",
                             size="xs", color=C["text_main"], flex=2),
                        文字(f"10Y {t10y:.2f}%" if t10y else "10Y ?",
                             size="xs", color=C["text_main"], flex=2),
                    ],
                },
                文字(f"{倒掛.get('等級', '')} · {倒掛.get('說明', '')[:40]}",
                     size="xxs", color=色_倒, wrap=True),
            ],
        })

    # 7. 整體狀況 footer
    fg = 行動["大盤"].get("F&G")
    vix = 行動["大盤"].get("VIX")
    sop = 行動["大盤"].get("黑天鵝命中", 0)
    body.append(分隔線())
    body.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字(f"F&G {fg or '?'}", size="sm",
                 color=C["text_main"], weight="bold", flex=2),
            文字(f"VIX {vix or '?'}", size="sm",
                 color=C["text_main"], weight="bold", flex=2),
            文字(f"黑天鵝 {sop}/5", size="sm",
                 color=(C["bear"] if sop >= 3 else C["bull"] if sop == 0 else C["wait"]),
                 weight="bold", flex=3),
        ],
    })
    body.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字(f"💰 總資產 NT$ {行動['總資產']:,.0f}",
                 size="md", color=C["accent"],
                 weight="bold", flex=6),
            文字(f"彈藥 {行動['彈藥']:,.0f}",
                 size="sm",
                 color=(C["bull"] if 行動['彈藥'] > 5000 else C["wait"]),
                 weight="bold", align="end", flex=4),
        ],
    })

    # 一句總結
    if 必做:
        summary = "👉 今天先動「必做」"
        sum_color = C["bear"]
    elif 待觸發 or 預警:
        summary = "👉 守紀律等觸發，不買新"
        sum_color = C["wait"]
    else:
        summary = "👉 完全紀律內，可看價值區"
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
    """推漂亮版 Flex 今日行動卡"""
    try:
        try:
            from . import line_push
        except ImportError:
            import line_push
    except Exception:
        return False
    行動 = 組今日行動()
    flex = 建構Flex卡(行動)
    car = {"type": "carousel", "contents": [flex]}
    alt = f"🎯 LIS 今日行動 ({datetime.now():%m/%d})"
    try:
        line_push.推播Flex訊息(替代文字=alt, flex內容=car)
        return True
    except Exception as e:
        print(f"推播失敗: {e}")
        return False


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from dotenv import load_dotenv
    load_dotenv(專案根 / "API" / ".env")

    行動 = 組今日行動()
    print("=" * 60)
    print(f"🎯 LIS 今日行動")
    print("=" * 60)

    print(f"\n🚨 必做 {len(行動['必做'])} 件")
    for x in 行動["必做"]:
        print(f"  {x['類型']} {x['symbol']} {x['name']} {x['pnl_pct']:+.2f}% → {x['動作']}")

    print(f"\n⚠️ 待觸發 {len(行動['待觸發'])} 筆")
    for o in 行動["待觸發"]:
        print(f"  {o.get('symbol')} {o.get('action')} {o.get('shares')} @ {o.get('price')}")

    print(f"\n📊 預警 {len(行動['預警'])} 件")
    for w in 行動["預警"]:
        print(f"  {w['類型']} {w['symbol']} {w['name']} 差 {w['差距']:.1f}%")

    print(f"\n✋ 不該追 {len(行動['不該做'])} 檔")
    for x in 行動["不該做"][:5]:
        print(f"  {x['symbol']} 位階 {x['score']:.0f}")

    print(f"\n💡 整體：F&G {行動['大盤']['F&G']} / VIX {行動['大盤']['VIX']} / 黑天鵝 {行動['大盤']['黑天鵝命中']}/5")
    print(f"   彈藥 NT$ {行動['彈藥']:,.0f} / 閒錢比 {行動['閒錢比']:.1f}%")
    print(f"   總資產 NT$ {行動['總資產']:,.0f}")

    if len(sys.argv) > 1 and sys.argv[1] == "push":
        print(f"\n推 LINE...")
        if 推LINE文字版(行動):
            print("✅ 已推 LINE")
