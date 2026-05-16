"""
LIS 5 主卡的詳細展開版（Phase 38 — 配 webhook 用）

當 user 點主卡按鈕，LINE webhook 收 postback 後呼叫對應 builder
推一張更詳細的卡到 LINE chat。

3 張細節卡（對應 3 張主卡）：
  1. 卡_完整今日行動  — 主卡「該買/該賣/該抱」的完整列表 + 為什麼
  2. 卡_完整持股      — 每檔股票明細（成本/現價/損益）
  3. 卡_完整KOL       — 香港朋友完整心法 + Sylvie 持股 + KOL 完整摘要
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

專案根 = Path(__file__).resolve().parent.parent.parent


# ────────────────────────────────────────
# 輔助：載入大盤暖度人話（從 daily_5cards 重用）
# ────────────────────────────────────────
def _載入卡helper():
    try:
        from . import daily_5cards
    except ImportError:
        import daily_5cards
    return daily_5cards


# ════════════════════════════════════════════
# 卡 1 詳細：完整今日行動
# ════════════════════════════════════════════
def 卡_完整今日行動() -> dict:
    """完整版「今日該做什麼」— 加入詳細理由 + 全部訊號"""
    try:
        from . import (daily_action_card, capital_planner, portfolio_tracker,
                       forex, flex_builder, bottom_detector)
    except ImportError:
        import daily_action_card, capital_planner, portfolio_tracker
        import forex, flex_builder, bottom_detector

    h = _載入卡helper()
    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    今日 = daily_action_card.組今日行動()
    cfg = capital_planner.載入資金設定()
    USD_TWD = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32))["rate"]
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=USD_TWD)

    body = []
    body.append(文字("📖 今日完整行動分析", size="xl",
                     color=C["accent"], weight="bold"))
    body.append(文字(f"{datetime.now():%m/%d %a · %H:%M}",
                     size="xs", color=C["text_dim"]))
    body.append(分隔線())

    # 全部該賣（含理由）
    body.append(文字("🔴 該賣（全部）", size="md",
                     color=C["bear"], weight="bold"))
    達停利 = 真倉.get("警示", {}).get("達停利", [])
    破停損 = 真倉.get("警示", {}).get("破停損", [])

    for r in 達停利:
        is_us = r.get("is_us", False)
        賣股數 = max(1, r["shares"] // 2)
        price = r["current_price"]
        usd = 賣股數 * price if is_us else 0
        twd = 賣股數 * price * (USD_TWD if is_us else 1)
        符 = "$" if is_us else "NT$"
        body.append(文字(
            f"• {r['symbol']} ({r.get('name','')[:8]}) +{r['pnl_pct']:.2f}%",
            size="sm", color=C["text_main"], weight="bold"))
        body.append(文字(
            f"  賣 {賣股數} 股 @ {符}{price:.2f}",
            size="xs", color=C["bull"]))
        if is_us:
            body.append(文字(
                f"  ≈ ${usd:,.0f} (NT$ {twd:,.0f})",
                size="xs", color=C["bull"]))
        else:
            body.append(文字(
                f"  ≈ NT$ {twd:,.0f}",
                size="xs", color=C["bull"]))
        body.append(文字(
            f"  理由：達 +15% Strategy D 第一段（賣一半）",
            size="xxs", color=C["text_dim"]))

    for r in 破停損:
        is_us = r.get("is_us", False)
        shares = r["shares"]
        price = r["current_price"]
        twd = shares * price * (USD_TWD if is_us else 1)
        符 = "$" if is_us else "NT$"
        body.append(文字(
            f"• {r['symbol']} ({r.get('name','')[:8]}) {r['pnl_pct']:.2f}%",
            size="sm", color=C["bear"], weight="bold"))
        body.append(文字(
            f"  全停損 {shares} 股 @ {符}{price:.2f}",
            size="xs", color=C["bear"]))
        body.append(文字(
            f"  理由：破 -3%（美股）/ -5%（台股）停損紀律",
            size="xxs", color=C["text_dim"]))

    if not (達停利 or 破停損):
        body.append(文字("  今天沒有觸發停利/停損",
                        size="xs", color=C["text_dim"]))

    body.append(分隔線())

    # 預警（接近停利/停損）
    預警 = 今日.get("預警", [])
    if 預警:
        body.append(文字("📊 預警（接近觸發）", size="md",
                        color=C["wait"], weight="bold"))
        for w in 預警[:5]:
            body.append(文字(
                f"• {w['symbol']} {w.get('name','')[:6]} "
                f"{w.get('類型','')} {w.get('pnl_pct',0):+.2f}%",
                size="xs", color=C["text_main"], wrap=True))
        body.append(分隔線())

    # 黑天鵝詳細
    try:
        sop = bottom_detector.即時底部判定()
        命中 = sop.get("命中數", 0)
        條件 = sop.get("條件", [])
        body.append(文字(f"🦢 黑天鵝命中 {命中}/5", size="md",
                        color=C["accent"] if 命中 >= 3 else C["text_dim"],
                        weight="bold"))
        for c in 條件[:5]:
            tick = "✓" if c.get("命中") else "○"
            色 = C["bull"] if c.get("命中") else C["text_dim"]
            body.append(文字(
                f"  {tick} {c.get('項目', '?')}",
                size="xxs", color=色))
    except Exception:
        pass

    # 大盤暖度（人話）
    body.append(分隔線())
    body.append(文字("📊 大盤暖度", size="md",
                     color=C["text_main"], weight="bold"))
    fg = 今日.get("大盤", {}).get("F&G")
    vix = 今日.get("大盤", {}).get("VIX")
    body.append(文字(f"  {h._FG轉人話(fg)}",
                     size="xs", color=C["text_main"], wrap=True))
    if vix is not None:
        body.append(文字(f"  {h._VIX轉人話(vix)}",
                        size="xs", color=C["text_main"], wrap=True))

    return _bubble(body, C)


# ════════════════════════════════════════════
# 卡 2 詳細：完整持股
# ════════════════════════════════════════════
def 卡_完整持股() -> dict:
    """完整版「我的部位」— 列出全部持股的成本/現價/損益"""
    try:
        from . import (capital_planner, portfolio_tracker, forex,
                       flex_builder)
    except ImportError:
        import capital_planner, portfolio_tracker, forex, flex_builder

    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    cfg = capital_planner.載入資金設定()
    USD_TWD = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32))["rate"]
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=USD_TWD)

    持股 = [p for p in 真倉["持股"] if not p.get("error")]
    持股.sort(key=lambda p: -p.get("市值_twd", 0))

    body = []
    body.append(文字("📈 完整持股明細", size="xl",
                     color=C["accent"], weight="bold"))
    body.append(文字(f"{len(持股)} 檔 · 按市值排序",
                     size="xs", color=C["text_dim"]))
    body.append(分隔線())

    # 表頭
    body.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("代號", size="xxs", color=C["text_dim"], flex=3),
            文字("股數", size="xxs", color=C["text_dim"], align="end", flex=2),
            文字("成本", size="xxs", color=C["text_dim"], align="end", flex=3),
            文字("現價", size="xxs", color=C["text_dim"], align="end", flex=3),
            文字("損益%", size="xxs", color=C["text_dim"], align="end", flex=3),
        ],
    })
    body.append(分隔線())

    for p in 持股:
        色 = C["bull"] if p.get("pnl_pct", 0) >= 0 else C["bear"]
        貨幣 = "$" if p.get("is_us") else ""
        body.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字(f"{p['symbol'][:8]}", size="xxs",
                     color=C["text_main"], weight="bold", flex=3),
                文字(f"{p.get('shares', 0)}", size="xxs",
                     color=C["text_dim"], align="end", flex=2),
                文字(f"{貨幣}{p.get('avg_cost', 0):.2f}", size="xxs",
                     color=C["text_dim"], align="end", flex=3),
                文字(f"{貨幣}{p.get('current_price', 0):.2f}", size="xxs",
                     color=C["text_main"], align="end", flex=3),
                文字(f"{p.get('pnl_pct', 0):+.2f}%", size="xxs",
                     color=色, align="end", weight="bold", flex=3),
            ],
        })

    body.append(分隔線())
    # 美股小計（修 Phase 39 bug — 用 current_price * shares 自己算市值）
    美股 = [p for p in 持股 if p.get("is_us")]
    if 美股:
        usd = sum((p.get("current_price", 0) or 0) * (p.get("shares", 0) or 0)
                  for p in 美股)
        usd_cost = sum((p.get("avg_cost", 0) or 0) * (p.get("shares", 0) or 0)
                       for p in 美股)
        usd_pnl = usd - usd_cost
        usd_pct = (usd_pnl / usd_cost * 100) if usd_cost > 0 else 0
        色 = C["bull"] if usd_pnl >= 0 else C["bear"]
        body.append(文字(
            f"🇺🇸 美股 {len(美股)} 檔: ${usd:,.0f}",
            size="xs", color=C["text_main"], wrap=True))
        body.append(文字(
            f"  損益 ${usd_pnl:+,.0f} ({usd_pct:+.2f}%)",
            size="xs", color=色, wrap=True))

    return _bubble(body, C)


# ════════════════════════════════════════════
# 卡 3 詳細：完整 KOL
# ════════════════════════════════════════════
def 卡_完整KOL() -> dict:
    """完整版「老師們」— 香港朋友完整心法 + Sylvie 完整持股 + KOL 完整摘要"""
    try:
        from . import flex_builder
    except ImportError:
        import flex_builder

    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    body = []
    body.append(文字("📋 完整老師摘要", size="xl",
                     color=C["accent"], weight="bold"))
    body.append(分隔線())

    # 🚀 Enjoy 朋友（神人 14 年 10 萬→千萬，LIS 命名由來）
    body.append(文字("🚀 Enjoy 朋友", size="md",
                     color=C["accent"], weight="bold"))
    enjoy_lines = [
        "  • 投資 14 年 · 10 萬 → 千萬（100 倍）",
        "  • LIS 系統 \"Enjoy\" 命名由來",
        "  • 派別: 動能積極派 · 有時當沖",
        "",
        "  3 方法給新手（user 親問）:",
        "  ① 無腦投資大盤 ETF",
        "  ② 一半存股 + 一半短線",
        "      短線獲利繼續買存股",
        "  ③ 重壓一檔你看好的股票",
        "",
        "  ✅ LIS strategy_mode 完全對應這 3 種",
        "     (passive_etf / balanced / all_in_one)",
        "",
        "  user 金句:",
        "  「人人都知道，但人人做不到！哈」",
    ]
    for line in enjoy_lines:
        if line:
            body.append(文字(line, size="xxs",
                            color=C["text_main"], wrap=True))
        else:
            body.append(文字(" ", size="xxs"))
    body.append(分隔線())

    # 🇭🇰 香港朋友 — 完整心法
    body.append(文字("🇭🇰 香港朋友 15 年心法", size="md",
                     color=C["accent"], weight="bold"))
    身份 = [
        "  • 動能派 — 追高、可承受腰斬",
        "  • 建議 user 走「穩定派」",
        "",
        "  4 大支柱：",
        "  ① 技術面（線、量、價、大盤櫃買賣）",
        "  ② 基本面（毛利率最重要）",
        "  ③ 持久議題（新聞看方向）",
        "  ④ 心理面（錯殺判斷靠買單）",
        "",
        "  推薦標的：欣興 / 台積電 / 光通訊 AI",
        "  3 段波段：起漲 → 拖長 → 跌深",
        "",
        "  金句：「股價反應未來 1 年後的事」",
        "  金句：「台股也是幫美國人做事」",
    ]
    for line in 身份:
        if line:
            body.append(文字(line, size="xxs",
                            color=C["text_main"], wrap=True))
        else:
            body.append(文字(" ", size="xxs"))
    body.append(分隔線())

    # 💎 Sylvie 完整持股
    body.append(文字("💎 Sylvie 完整持股", size="md",
                     color=C["accent"], weight="bold"))
    try:
        sylvie_path = 專案根 / "數據" / "sylvie_portfolio.json"
        if sylvie_path.exists():
            import json as _j
            sy = _j.loads(sylvie_path.read_text(encoding="utf-8"))
            最新加碼日 = sy.get("_最新加碼日", "")
            最新說明 = sy.get("_最新加碼說明", "")
            總報酬率 = sy.get("總報酬率_pct")
            持股 = sy.get("持股", [])

            if 最新加碼日:
                body.append(文字(f"  最新加碼: {最新加碼日}",
                                size="xs", color=C["text_dim"]))
            if 最新說明:
                body.append(文字(f"  → {最新說明}",
                                size="xs", color=C["text_main"], wrap=True))
            if 總報酬率 is not None:
                色 = C["bull"] if 總報酬率 >= 0 else C["bear"]
                body.append(文字(f"  主帳戶 {總報酬率:+.2f}%",
                                size="xs", color=色))

            if 持股:
                body.append(文字(f"  持股 Top 8（共 {len(持股)} 檔）:",
                                size="xs", color=C["text_dim"]))
                sorted_h = sorted(持股,
                                  key=lambda x: -x.get("報酬率_pct", 0))
                for p in sorted_h[:8]:
                    rate = p.get("報酬率_pct", 0)
                    色 = C["bull"] if rate >= 0 else C["bear"]
                    body.append({
                        "type": "box", "layout": "horizontal",
                        "contents": [
                            文字(f"    {p.get('symbol', '?')}",
                                 size="xxs",
                                 color=C["text_main"], flex=4),
                            文字(p.get("name", "")[:6],
                                 size="xxs",
                                 color=C["text_dim"], flex=3),
                            文字(f"{rate:+.1f}%", size="xxs",
                                 color=色, align="end", flex=3),
                        ],
                    })
    except Exception as e:
        body.append(文字(f"  (Sylvie 讀取失敗)", size="xs",
                        color=C["text_dim"]))
    body.append(分隔線())

    # 🎤 6 大 KOL 完整摘要（從 cache）
    body.append(文字("🎤 6 大 KOL 完整摘要", size="md",
                     color=C["accent"], weight="bold"))
    try:
        kol_path = (專案根 / "數據" / "daily" /
                    f"kol_{datetime.now():%Y-%m-%d}.json")
        if kol_path.exists():
            import json as _j
            kc = _j.loads(kol_path.read_text(encoding="utf-8"))
            kols = kc.get("kols", [])
            for k in kols[:6]:
                name = k.get("name", "?")
                summary = k.get("summary", "")[:80]
                body.append(文字(f"• {name}",
                                size="xs", color=C["text_main"],
                                weight="bold"))
                body.append(文字(f"  {summary}...",
                                size="xxs", color=C["text_dim"], wrap=True))
            # Top hits
            hits = kc.get("watchlist_hits", {})
            if hits:
                body.append(分隔線())
                body.append(文字("🔥 共識排行:",
                                size="xs", color=C["accent"], weight="bold"))
                sorted_hits = sorted(hits.items(), key=lambda x: -x[1])[:5]
                for label, count in sorted_hits:
                    body.append(文字(f"  {label} — {count} 人",
                                    size="xxs",
                                    color=C["text_main"], wrap=True))
        else:
            body.append(文字("  今天還沒抓到 KOL 資料",
                            size="xs", color=C["text_dim"]))
    except Exception:
        body.append(文字("  KOL 讀取失敗",
                        size="xs", color=C["text_dim"]))

    return _bubble(body, C)


def _bubble(body: list, C: dict) -> dict:
    return {
        "type": "bubble", "size": "mega",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "xs",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": body,
        },
    }
