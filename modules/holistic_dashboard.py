"""
LIS 全息儀表板（Phase 33）— 一張 carousel 看完全部

整合 Phase 22-32 全部模組到單一 carousel：
  1. 部位儀表（現況 + 偏離度）
  2. 底部 SOP（Sylvie 5 指標）
  3. 供需驅動（億級講師事件→受惠股）
  4. 策略池 TOP 5 入選
  5. 法人共識買賣
  6. 信任分 + 紀律提醒

設計準則：
  - 每張卡 < 50KB
  - 整體 carousel < 300KB
  - 一眼看完今日全部關鍵資訊
"""
import sys
from datetime import datetime
from pathlib import Path


專案根 = Path(__file__).resolve().parent.parent.parent


def 建構全息儀表板() -> dict:
    """主入口：跑所有模組，組 carousel"""
    from . import (capital_planner, fugle_market, forex, flex_builder,
                   bottom_detector, supply_demand_engine,
                   strategy_pool, lis_track_record, daily_adjustor,
                   institutional_tracker, money_manager, portfolio_tracker,
                   ark_knowledge, capital_inflow, benchmark_compare, sim_ledger,
                   ark_adjustor, sylvie_lessons, fear_greed)

    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    cards = []

    # ─── 卡 1：部位儀表 ───
    cfg = capital_planner.載入資金設定()
    現金 = cfg.get("current_cash_twd", 0)
    持股清單 = [p for p in cfg.get("current_positions", [])
                if p.get("symbol") != "AGGREGATE"]

    匯率 = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32.0))["rate"]

    # Phase 32.5：用 portfolio_tracker 取得即時市值（修 bug：之前用成本當市值）
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=匯率)
    持股市值總 = 真倉["總計"]["市值_twd"]
    持股成本總 = 真倉["總計"]["成本_twd"]
    投資損益_twd = 真倉["總計"]["損益_twd"]
    投資損益率 = 真倉["總計"]["損益率_pct"]
    總資產 = 持股市值總 + 現金
    彈藥 = money_manager.計算可用彈藥(
        總資金=總資產, 現金=現金,
        持股成本_twd=持股市值總,  # 用市值算水位
        目標閒錢比_pct=35,
    )

    # Phase 32.5：淨投資報酬（總資產 vs 累計本金注入）
    淨報酬 = capital_inflow.算淨報酬(總資產)

    # Phase 32.5：LIS vs 0050 比較
    try:
        對比0050 = benchmark_compare.算LIS_vs_0050(
            總資產, 投資內部報酬率_pct=投資損益率)
    except Exception:
        對比0050 = None

    # Phase 32.5：LIS 訊號自家勝率（sim_ledger 已平倉的統計）
    try:
        lis_stats = sim_ledger.統計概覽()
    except Exception:
        lis_stats = None

    內容1 = []
    內容1.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("💼 部位儀表", size="lg", color=C["text_main"], weight="bold"),
            文字(f"持股 {len(持股清單)} 檔 · {datetime.now():%H:%M}",
                 size="xxs", color=C["text_dim"]),
        ],
    })
    內容1.append(分隔線())
    內容1.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            {
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字("總資產", size="xxs", color=C["text_dim"], flex=2),
                    文字(f"NT$ {總資產:,.0f}", size="sm",
                         color=C["accent"], weight="bold", align="end", flex=4),
                ],
            },
            {
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字("投資損益", size="xxs", color=C["text_dim"], flex=2),
                    文字(f"NT$ {投資損益_twd:+,.0f} ({投資損益率:+.2f}%)",
                         size="xs",
                         color=C["bull"] if 投資損益_twd >= 0 else C["bear"],
                         weight="bold", align="end", flex=4),
                ],
            },
            *([{
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字("淨投資報酬", size="xxs", color=C["text_dim"], flex=2),
                    文字(f"{淨報酬['淨報酬率_pct']:+.2f}% "
                         f"(本金 {淨報酬['累計注入_twd']/1000:,.0f}K)",
                         size="xs",
                         color=C["bull"] if 淨報酬["淨損益_twd"] >= 0 else C["bear"],
                         align="end", flex=4),
                ],
            }] if 淨報酬.get("可計算") else []),
            *([{
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字("vs 0050", size="xxs", color=C["text_dim"], flex=2),
                    文字(f"{對比0050['投資超額報酬_pct']:+.2f}% "
                         f"({對比0050['天數']}天)",
                         size="xs",
                         color=(C["bull"] if 對比0050.get("贏大盤_用投資內部")
                                else C["bear"]),
                         align="end", flex=4),
                ],
            }] if 對比0050 else []),
            *([{
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字("LIS 訊號勝率", size="xxs", color=C["text_dim"], flex=2),
                    文字(f"{lis_stats['勝率_%']:.0f}% "
                         f"(已平倉 {lis_stats['已平倉']}, "
                         f"未平倉 {lis_stats['未平倉']})",
                         size="xxs", color=C["text_main"],
                         align="end", flex=4),
                ],
            }] if lis_stats and lis_stats.get("勝率_%") is not None else []),
            {
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字("現金", size="xxs", color=C["text_dim"], flex=2),
                    文字(f"NT$ {現金:,.0f}", size="xs",
                         color=C["bull"], align="end", flex=4),
                ],
            },
            {
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字("閒錢比", size="xxs", color=C["text_dim"], flex=2),
                    文字(f"{彈藥['水位']['閒錢比_pct']:.1f}% / 目標 35%",
                         size="xxs", color=C["text_main"], align="end", flex=4),
                ],
            },
            {
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字("可動用彈藥", size="xxs", color=C["text_dim"], flex=2),
                    文字(f"NT$ {彈藥['可動用彈藥_twd']:,.0f}", size="xs",
                         color=C["wait"], align="end", flex=4),
                ],
            },
            {
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字("模式", size="xxs", color=C["text_dim"], flex=2),
                    文字(f"{彈藥['模式emoji']} {彈藥['模式']}", size="xs",
                         color=C["text_main"], align="end", flex=4),
                ],
            },
            # Phase 32.7：FOMO 防護機制
            {
                "type": "box", "layout": "vertical", "spacing": "xs",
                "margin": "md", "paddingAll": "8px",
                "backgroundColor": C["bg_card_alt"], "cornerRadius": "6px",
                "contents": [
                    文字("🧠 FOMO 防護", size="xxs",
                         color=C["accent"], weight="bold"),
                    文字((
                        "彈藥 NT$ 0 + 黑天鵝 0/5 → 別追新股，等紀律訊號"
                        if 彈藥['可動用彈藥_twd'] < 1000 else
                        "彈藥剩 < $5000 → 單筆 ≤ $1000 試單"
                        if 彈藥['可動用彈藥_twd'] < 5000 else
                        "彈藥充足 → 照訊號等級執行 ARK 分級限額"
                    ), size="xxs", color=C["text_subtle"], wrap=True),
                    文字("ARK：「市場狂熱追價時，分批賣出時機」",
                         size="xxs", color=C["text_dim"], wrap=True),
                ],
            },
        ],
    })

    cards.append({
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "12px",
            "contents": 內容1,
        },
    })

    # ─── 卡 1.5：持股健診 TOP/BOTTOM 5（Phase 32.5）───
    持股列 = [r for r in 真倉["持股"] if not r.get("error")
              and r.get("pnl_pct") is not None]
    持股列.sort(key=lambda r: r["pnl_pct"], reverse=True)
    達停利數 = sum(1 for r in 持股列 if r["pnl_pct"] >= 15)
    近停利數 = sum(1 for r in 持股列 if 12 <= r["pnl_pct"] < 15)
    破停損數 = sum(1 for r in 持股列 if r["pnl_pct"] <= -5)
    近停損數 = sum(1 for r in 持股列 if -5 < r["pnl_pct"] <= -4)
    TOP5 = 持股列[:5]
    BOTTOM5 = 持股列[-5:][::-1] if len(持股列) > 5 else []

    內容HC = [{
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("📋 持股健診", size="lg",
                 color=C["text_main"], weight="bold"),
            文字(f"{len(持股列)} 檔 · 達+15% {達停利數} / 近+12% {近停利數}"
                 f" / 近-4% {近停損數} / 破-5% {破停損數}",
                 size="xxs", color=C["text_dim"]),
        ],
    }, 分隔線()]

    if TOP5:
        內容HC.append(文字("🟢 漲幅 TOP 5", size="xs",
                          color=C["bull"], weight="bold"))
        for r in TOP5:
            badge = ("🎯" if r["pnl_pct"] >= 15
                     else "📈" if r["pnl_pct"] >= 12
                     else "  ")
            內容HC.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"{badge} {r['symbol']} {r.get('name','')[:6]}",
                         size="xxs", color=C["text_main"], flex=5),
                    文字(f"{r['pnl_pct']:+.2f}%", size="xxs",
                         color=C["bull"] if r["pnl_pct"] >= 0 else C["bear"],
                         flex=2, align="end", weight="bold"),
                ],
            })

    if BOTTOM5:
        內容HC.append(分隔線())
        內容HC.append(文字("🔴 跌幅 TOP 5", size="xs",
                          color=C["bear"], weight="bold"))
        for r in BOTTOM5:
            badge = ("💀" if r["pnl_pct"] <= -5
                     else "📉" if r["pnl_pct"] <= -4
                     else "  ")
            內容HC.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"{badge} {r['symbol']} {r.get('name','')[:6]}",
                         size="xxs", color=C["text_main"], flex=5),
                    文字(f"{r['pnl_pct']:+.2f}%", size="xxs",
                         color=C["bull"] if r["pnl_pct"] >= 0 else C["bear"],
                         flex=2, align="end", weight="bold"),
                ],
            })

    cards.append({
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "12px",
            "contents": 內容HC,
        },
    })

    # ─── 卡 1.6：Sylvie 教學提醒（Phase 32.7）───
    try:
        # 抓黑天鵝命中數
        _sop_for_lessons = sop if 'sop' in locals() else None
        if _sop_for_lessons is None:
            try:
                _sop_for_lessons = bottom_detector.即時底部判定()
            except Exception:
                _sop_for_lessons = {"命中數": 0}
        # 大盤資訊
        _大盤 = {}
        try:
            _fg = fear_greed.取得恐慌貪婪指數()
            _大盤["fear_greed"] = _fg.get("score") if _fg else None
        except Exception:
            pass
        教 = sylvie_lessons.取得全部教學(
            彈藥, _sop_for_lessons.get("命中數", 0), _大盤, 真倉, 匯率)
    except Exception:
        教 = None

    if 教:
        內容SY = [{
            "type": "box", "layout": "vertical", "spacing": "xs",
            "contents": [
                文字("🎓 Sylvie 教學", size="lg",
                     color=C["text_main"], weight="bold"),
                文字("3 紀律：DCA 強度 / 重押勇氣 / 強者繼續抱",
                     size="xxs", color=C["text_dim"]),
            ],
        }, 分隔線()]

        # 1. DCA 今日
        d = 教["DCA今日"]
        內容SY.append(文字("📌 今日 DCA",
                          size="sm", color=C["accent"], weight="bold"))
        內容SY.append(文字(d["提示"], size="xxs",
                          color=C["text_main"], wrap=True))
        if d["建議金額_twd"] > 0:
            內容SY.append(文字(
                f"→ NT$ {d['建議金額_twd']} → {d['推薦標的']['name']} "
                f"({d['推薦標的']['symbol']})",
                size="xxs", color=C["bull"], wrap=True))
        內容SY.append(文字(d["Sylvie格言"], size="xxs",
                          color=C["text_subtle"], wrap=True))

        # 2. 重押訊號
        r = 教["重押訊號"]
        內容SY.append(分隔線())
        內容SY.append(文字("💪 重押訊號",
                          size="sm", color=C["accent"], weight="bold"))
        重押色 = (C["bear"] if r.get("推訊號")
                   else C["text_main"])
        內容SY.append(文字(f"{r['等級']}", size="xs",
                          color=重押色, weight="bold"))
        內容SY.append(文字(r["訊息"], size="xxs",
                          color=C["text_subtle"], wrap=True))
        if r.get("Sylvie範例"):
            內容SY.append(文字(f"📚 {r['Sylvie範例']}", size="xxs",
                              color=C["text_dim"], wrap=True))

        # 3. 強者繼續抱
        強清 = 教["強者繼續抱"]
        if 強清:
            內容SY.append(分隔線())
            內容SY.append(文字(f"🚀 強者繼續抱 ({len(強清)})",
                              size="sm", color=C["accent"], weight="bold"))
            for h in 強清[:3]:
                內容SY.append({
                    "type": "box", "layout": "vertical", "spacing": "xs",
                    "margin": "xs",
                    "contents": [
                        {
                            "type": "box", "layout": "horizontal",
                            "contents": [
                                文字(f"{h['symbol']} {h.get('name','')[:6]}",
                                     size="xxs",
                                     color=C["text_main"], flex=4),
                                文字(f"{h['pnl_pct']:+.2f}%", size="xxs",
                                     color=(C["bull"] if h['pnl_pct'] >= 0
                                            else C["bear"]),
                                     align="end", flex=2),
                            ],
                        },
                        文字(f"→ {h['建議']}", size="xxs",
                             color=C["text_subtle"], wrap=True),
                    ],
                })

        cards.append({
            "type": "bubble", "size": "kilo",
            "body": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "backgroundColor": C["bg_dark"],
                "paddingAll": "12px",
                "contents": 內容SY,
            },
        })

    # ─── 卡 1.7：ARK 6 大調節法觀察（Phase 32.7）───
    try:
        import json as _json
        state_path = 專案根 / "數據" / "positional_state.json"
        _scores = {}
        if state_path.exists():
            _scores = _json.loads(state_path.read_text(encoding="utf-8")).get("scores", {})
        ark_adj = ark_adjustor.算ARK調節建議(真倉, _scores, 總資產)
    except Exception:
        ark_adj = {}

    內容ARK = [{
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("🔧 ARK 調節觀察", size="lg",
                 color=C["text_main"], weight="bold"),
            文字("6 大法則排序（建議參考，非強制）",
                 size="xxs", color=C["text_dim"]),
        ],
    }, 分隔線()]

    法則對映 = [
        ("位階排序",       "① 位階最熱", "score"),
        ("總報酬率排序",   "③ 漲最多",   "pct_only"),
        ("總報酬金額排序", "④ 賺最多 NT$", "twd"),
        ("風控",           "⑤ 過集中",   "ratio"),
        ("修剪枯枝",       "⑥ 接近停損", "near_sl"),
    ]
    有顯示 = False
    for key, label, 顯示型 in 法則對映:
        清單 = ark_adj.get(key, [])
        if not 清單:
            continue
        有顯示 = True
        內容ARK.append(文字(label, size="xs",
                          color=C["accent"], weight="bold", margin="md"))
        for r in 清單[:2]:  # 每類 top 2
            if 顯示型 == "score":
                左 = f"  {r['symbol']} {r['name']}"
                中 = f"位 {r['score']:.0f}"
            elif 顯示型 == "twd":
                左 = f"  {r['symbol']} {r['name']}"
                中 = f"+{r.get('pnl_twd',0)/1000:.0f}K"
            elif 顯示型 == "ratio":
                左 = f"  {r['symbol']} {r['name']}"
                中 = f"占 {r['占比_pct']:.0f}%"
            elif 顯示型 == "near_sl":
                左 = f"  {r['symbol']} {r['name']}"
                中 = f"{r['pnl_pct']:+.1f}%"
            else:  # pct_only
                左 = f"  {r['symbol']} {r['name']}"
                中 = f"{r['pnl_pct']:+.1f}%"
            內容ARK.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(左, size="xxs", color=C["text_main"], flex=4),
                    文字(中, size="xxs", color=C["text_dim"],
                         align="end", flex=2),
                    文字(r["建議"], size="xxs", color=C["wait"],
                         align="end", flex=5),
                ],
            })

    if not 有顯示:
        內容ARK.append(文字("✅ 全部持股紀律內，無需調節",
                          size="sm", color=C["bull"], align="center"))

    內容ARK.append(分隔線())
    內容ARK.append(文字("💡 LIS A 紀律 +15/-5 仍是主軸，這是 ARK 主動派參考",
                      size="xxs", color=C["text_subtle"], wrap=True))

    cards.append({
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "12px",
            "contents": 內容ARK,
        },
    })

    # ─── 卡 2：底部 SOP（Sylvie） ───
    try:
        sop = bottom_detector.即時底部判定()
    except Exception:
        sop = {"命中數": 0, "等級": "❓ 資料不足", "詳情": []}

    內容2 = []
    內容2.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("📉 底部 SOP（Sylvie 5 指標）", size="lg",
                 color=C["text_main"], weight="bold"),
            文字(f"命中 {sop.get('命中數',0)}/5",
                 size="sm",
                 color=(C["bear"] if sop.get("命中數", 0) >= 4
                        else C["wait"] if sop.get("命中數", 0) >= 2
                        else C["bull"]),
                 weight="bold"),
        ],
    })
    內容2.append(分隔線())
    內容2.append(文字(sop.get("等級", "?"), size="md",
                     color=C["text_main"], weight="bold"))
    內容2.append(分隔線())
    for d in sop.get("詳情", []):
        內容2.append(文字(d[:40], size="xxs",
                         color=C["text_dim"], wrap=True))

    # Phase 32.5：ARK 知識庫提示 — 依命中數帶入 6 大調節法相關概念
    try:
        ark提示 = ark_knowledge.根據底部命中對應提示(sop.get("命中數", 0))
        內容2.append(分隔線())
        內容2.append(文字(ark提示["標題"], size="xs",
                         color=C["accent"], weight="bold"))
        內容2.append(文字(ark提示["訊息"], size="xxs",
                         color=C["text_subtle"], wrap=True))
        if ark提示["可用概念"]:
            概念字 = " · ".join(ark提示["可用概念"][:4])
            內容2.append(文字(f"📚 {概念字}", size="xxs",
                             color=C["text_dim"], wrap=True))
    except Exception:
        pass  # 知識庫未建好不影響主卡

    cards.append({
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "12px",
            "contents": 內容2,
        },
    })

    # ─── 卡 3：供需驅動（億級講師派 Phase 31）───
    try:
        sd = supply_demand_engine.今日事件推導()
    except Exception:
        sd = {"今日新聞關鍵詞": [], "受惠": [], "受害": []}

    內容3 = []
    內容3.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("🎯 供需驅動", size="lg", color=C["text_main"], weight="bold"),
            文字("億級講師派：事件→產業→受惠股",
                 size="xxs", color=C["text_dim"], wrap=True),
        ],
    })
    內容3.append(分隔線())
    if sd.get("今日新聞關鍵詞"):
        內容3.append(文字(f"今日關鍵詞：{', '.join(sd['今日新聞關鍵詞'][:4])}",
                         size="xxs", color=C["text_subtle"], wrap=True))
    內容3.append(文字(f"🟢 受惠 {len(sd.get('受惠', []))}",
                     size="sm", color=C["bull"], weight="bold"))
    for s in sd.get("受惠", [])[:5]:
        內容3.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字(f"  {s['symbol']}", size="xxs", color=C["text_main"], flex=3),
                文字(s.get("name", "")[:8], size="xxs",
                     color=C["text_dim"], flex=3),
                文字(f"{s.get('命中事件數',1)}件", size="xxs",
                     color=C["accent"], align="end", flex=2),
            ],
        })
    if sd.get("受害"):
        內容3.append(分隔線())
        內容3.append(文字(f"🔴 受害 {len(sd['受害'])}",
                         size="sm", color=C["bear"], weight="bold"))
        for s in sd["受害"][:3]:
            內容3.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"  {s['symbol']}", size="xxs",
                         color=C["text_main"], flex=3),
                    文字(s.get("name", "")[:8], size="xxs",
                         color=C["text_dim"], flex=5),
                ],
            })

    cards.append({
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "12px",
            "contents": 內容3,
        },
    })

    # ─── 卡 4：策略池 TOP（Phase 25 + 22 + 31）───
    try:
        全部標的 = strategy_pool.組裝標的清單(
            取得現價=lambda s: (fugle_market.即時報價_fallback(s) or {}).get("close"),
            含法人籌碼=True,
        )
        # 把 Phase 31 受惠標的標記到 _供需事件數
        受惠map = {s["symbol"]: s.get("命中事件數", 0)
                   for s in sd.get("受惠", [])}
        for r in 全部標的:
            r["_供需事件數"] = 受惠map.get(r["symbol"], 0)

        DCA清單 = [it["symbol"] for it in
                   cfg.get("long_term_dca", {}).get("items", [])
                   if it.get("symbol")]
        持股集 = {p["symbol"] for p in 持股清單}

        策略結果 = strategy_pool.掃描策略池(
            全部標的, 持股代號集=持股集, DCA清單=DCA清單,
        )
    except Exception as e:
        策略結果 = {}
        print(f"strategy_pool 失敗：{e}")

    內容4 = []
    內容4.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("🎯 策略池 TOP", size="lg", color=C["text_main"], weight="bold"),
            文字("8 策略獨立掃 watchlist", size="xxs", color=C["text_dim"]),
        ],
    })
    內容4.append(分隔線())

    # 篩有入選的 + 排序
    有效 = [(k, v) for k, v in 策略結果.items() if v["總數"] > 0]
    有效.sort(key=lambda x: -x[1]["總數"])

    for 策名, 設 in 有效[:5]:
        內容4.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字(f"{設['emoji']} {策名[:10]}", size="xs",
                     color=C["text_main"], flex=4),
                文字(f"{設['總數']} 檔", size="xs",
                     color=C["accent"], align="end", weight="bold", flex=2),
            ],
        })
        # 列前 2 個入選
        for s in 設["入選"][:2]:
            內容4.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"   {s['symbol']}", size="xxs",
                         color=C["text_dim"], flex=4),
                    文字(s.get("name", "")[:10], size="xxs",
                         color=C["text_subtle"], align="end", flex=4),
                ],
            })

    cards.append({
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "12px",
            "contents": 內容4,
        },
    })

    # ─── 卡 5：信任分 + 紀律 ───
    try:
        信任 = lis_track_record.取得信任分()
    except Exception:
        信任 = {}

    內容5 = []
    內容5.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("📊 LIS 信任分", size="lg", color=C["text_main"], weight="bold"),
            文字("自我審查 + 紀律提醒", size="xxs", color=C["text_dim"]),
        ],
    })
    內容5.append(分隔線())
    內容5.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("總訊號", size="xxs", color=C["text_dim"], flex=2),
            文字(f"{信任.get('總訊號數', 0)} 筆", size="sm",
                 color=C["text_main"], align="end", flex=3),
        ],
    })
    內容5.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("已驗證", size="xxs", color=C["text_dim"], flex=2),
            文字(f"{信任.get('已驗證', 0)} 筆", size="sm",
                 color=C["text_main"], align="end", flex=3),
        ],
    })
    if 信任.get("命中率_pct"):
        內容5.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字("命中率", size="xxs", color=C["text_dim"], flex=2),
                文字(f"{信任['命中率_pct']:.1f}%", size="sm",
                     color=C["accent"], align="end", weight="bold", flex=3),
            ],
        })
    內容5.append(分隔線())
    內容5.append(文字("🧠 今日紀律提醒", size="sm",
                     color=C["bull"], weight="bold"))
    內容5.append(文字("• DCA 0050 + 00646 不停",
                     size="xxs", color=C["text_dim"], wrap=True))
    內容5.append(文字("• 過熱別追，等回檔",
                     size="xxs", color=C["text_dim"], wrap=True))
    內容5.append(文字("• 黑天鵝來時用避險預備金",
                     size="xxs", color=C["text_dim"], wrap=True))
    內容5.append(文字("• 試單→加碼→大部位（億級講師派）",
                     size="xxs", color=C["text_dim"], wrap=True))

    cards.append({
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "12px",
            "contents": 內容5,
        },
    })

    return {"type": "carousel", "contents": cards}


# ─────────────────────────────────────────────
# 推播
# ─────────────────────────────────────────────
def 推送LINE():
    from . import line_push
    car = 建構全息儀表板()
    alt = f"🎯 LIS 全息儀表板 {datetime.now():%H:%M}"
    line_push.推播Flex訊息(替代文字=alt, flex內容=car)
    return alt


# ─────────────────────────────────────────────
# CLI 自測
# ─────────────────────────────────────────────
if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from dotenv import load_dotenv
    load_dotenv(專案根 / "API" / ".env")

    print("=== Phase 33 全息儀表板 ===\n")
    print("組裝 5 張卡 carousel...")
    car = 建構全息儀表板()
    print(f"✅ 完成 {len(car['contents'])} 張卡")

    # 推 LINE
    try:
        from modules import line_push
        alt = f"🎯 LIS 全息儀表板 {datetime.now():%H:%M}"
        line_push.推播Flex訊息(替代文字=alt, flex內容=car)
        print(f"✅ 已推 LINE：{alt}")
    except Exception as e:
        print(f"❌ 推播失敗：{e}")
