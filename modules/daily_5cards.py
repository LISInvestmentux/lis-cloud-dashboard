"""
LIS 早上 8AM 主卡（Phase 37.1 — 2026-05-16 二次整合）

設計目標：user 抱怨 5 張還是多，再整合成 3 張總卡。

3 張卡：
  1. 🎯 今日行動 — 必做 / 已掛單 / 預警 / 不該追
  2. 📊 市場總覽 — 持股&大盤 + 訊號&機會 + 美股摘要（3 合 1）
  3. 👥 Sylvie & KOL 共識 — KOL 共識 + Sylvie 重押 + 朋友圈訊號

每張卡帶 LIFF 按鈕，點下去開 Streamlit Cloud 對應 section。

歷史：
- Phase 37.0 (16:50): 5 張主卡（持股大盤/訊號機會/美股新聞 各一張）
- Phase 37.1 (17:?): user 看後再整合 → 3 張（持股+訊號+美股 合 1 張）
"""
import os
import sys
from pathlib import Path
from typing import Optional

專案根 = Path(__file__).resolve().parent.parent.parent
LIFF_BASE = os.getenv("LIFF_URL", "https://liff.line.me/2010070081-6wmnysUD")


def _LIFF按鈕(label: str, view: str) -> dict:
    """生成展開按鈕 — Phase 38 改用 postback action

    user 點按鈕 → LINE 送 postback 到 webhook server → 推對應細節卡
    取代 Phase 2b 的 LIFF URL（LIFF redirect 不順）

    LIS_USE_POSTBACK env var：
      "true"（預設）→ 用 postback（需 webhook server 跑著）
      "false"        → fallback 用 LIFF URI（沒 webhook 時暫用）
    """
    use_postback = os.getenv("LIS_USE_POSTBACK", "true").lower() in ("true", "1", "yes")

    if use_postback:
        return {
            "type": "button",
            "style": "primary",
            "height": "sm",
            "margin": "md",
            "color": "#FBBF24",
            "action": {
                "type": "postback",
                "label": label,
                "data": f"view={view}",
                "displayText": f"📖 {label}",  # user 點完 chat 內顯示這行
            },
        }
    else:
        return {
            "type": "button",
            "style": "primary",
            "height": "sm",
            "margin": "md",
            "color": "#FBBF24",
            "action": {
                "type": "uri",
                "label": label,
                "uri": f"{LIFF_BASE}?view={view}",
            },
        }


# ════════════════════════════════════════════
# Phase 37.2 (5/16) — 抽象數字轉小白人話
# 鐵律：feedback_ui_ux_5_core_questions.md
# 小白只要知道「該不該動 / 動什麼」，不要丟 F&G / VIX 數字給他猜
# ════════════════════════════════════════════
def _FG轉人話(score: float) -> str:
    """F&G 恐慌貪婪指數 0-100 → 一句話"""
    if score is None:
        return "—"
    if score < 25:
        return f"😱 大恐慌（{score:.0f}） · 加碼機會"
    if score < 45:
        return f"🟢 偏空（{score:.0f}） · 慢慢買"
    if score < 55:
        return f"⚖️ 中性（{score:.0f}） · 按紀律"
    if score < 75:
        return f"🟡 小貪婪（{score:.0f}） · 可慢慢買"
    return f"🔴 過熱（{score:.0f}） · 少加碼"


def _VIX轉人話(vix: float) -> str:
    """VIX → 一句話"""
    if vix is None:
        return "—"
    if vix > 30:
        return f"😱 市場大慌（{vix:.1f}） · 機會出現"
    if vix > 25:
        return f"🟡 市場慌了（{vix:.1f}） · 準備加碼"
    if vix > 20:
        return f"⚖️ 略緊張（{vix:.1f}）"
    return f"😴 穩定（{vix:.1f}） · 沒大機會"


def _風控分轉人話(score: float) -> str:
    """LIS 風控分 0-100 → 一句話"""
    if score is None:
        return "—"
    if score >= 85:
        return f"🔴 過熱（{score:.0f}） · 多看少做"
    if score >= 70:
        return f"🟡 偏熱（{score:.0f}） · 紀律操作"
    if score >= 50:
        return f"⚖️ 中性（{score:.0f}）"
    if score >= 30:
        return f"🟢 偏冷（{score:.0f}） · 可加碼"
    return f"🟢 大跌機會（{score:.0f}） · 重押"


def _黑天鵝轉人話(命中: int) -> Optional[str]:
    """黑天鵝命中數 0-5 → 一句話（沒命中就回 None 省版面）"""
    if 命中 >= 4:
        return "🚨 ALL IN 級加碼機會出現"
    if 命中 >= 3:
        return "🟢 強加碼訊號 · 等彈藥就位"
    if 命中 >= 2:
        return "🟡 留意機會"
    return None  # 0-1 不顯示


def _卡_今日行動() -> dict:
    """卡 1: 今天該做什麼（Phase 37.2 小白導向 — 該買/該賣/該抱/不該追）"""
    try:
        from . import (daily_action_card, capital_planner, portfolio_tracker,
                       forex, flex_builder)
    except ImportError:
        import daily_action_card, capital_planner, portfolio_tracker
        import forex, flex_builder

    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    # 取資料
    今日 = daily_action_card.組今日行動()
    cfg = capital_planner.載入資金設定()
    USD_TWD = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32))["rate"]
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=USD_TWD)

    現金 = cfg.get("current_cash_twd", 0)
    持股數 = len(真倉["持股"])
    必做 = 今日.get("必做", [])
    待觸發 = 今日.get("待觸發", [])
    不該做 = 今日.get("不該做", [])
    重佈局 = 今日.get("重佈局") or {}
    左側買回 = 今日.get("左側買回") or {}

    body = []

    # ─── Header ───
    body.append(文字("🎯 今天該做什麼", size="xl",
                     color=C["accent"], weight="bold"))
    from datetime import datetime as _dt
    body.append(文字(f"{_dt.now():%m/%d %a · %H:%M}",
                     size="xs", color=C["text_dim"]))
    body.append(分隔線())

    # ─── 🟢 該買 ───
    買選項 = []
    # 左側買回（SATL 跌回機會）
    左側標的 = 左側買回.get("符合的標的", []) if 左側買回 else []
    for s in 左側標的[:2]:
        買選項.append({
            "symbol": s.get("symbol", "?"),
            "name": s.get("name", "")[:8],
            "動作": s.get("建議動作", "買進"),
            "理由": "跌回價值區",
        })
    # 重佈局可用資金
    重佈局可動 = 重佈局.get("立即可動_twd", 0) if 重佈局 else 0
    # 已掛買單（pending BUY）
    買掛單 = [o for o in 待觸發 if o.get("action") == "BUY"]
    for o in 買掛單[:2]:
        買選項.append({
            "symbol": o.get("symbol", "?"),
            "name": "",
            "動作": f"{o.get('shares', 0)} 股 @ ${o.get('price', 0):.2f}",
            "理由": "已掛限價單",
        })

    body.append(文字("🟢 該買", size="md", color=C["bull"], weight="bold"))
    if 買選項:
        for b in 買選項:
            body.append({
                "type": "box", "layout": "vertical", "margin": "xs",
                "contents": [
                    文字(f"• {b['symbol']} {b['name']} — {b['動作']}",
                         size="sm", color=C["text_main"], weight="bold"),
                    文字(f"  理由：{b['理由']}",
                         size="xs", color=C["text_dim"]),
                ],
            })
    else:
        body.append(文字("  今天沒有強訊號 · 紀律觀察",
                        size="xs", color=C["text_dim"]))
    body.append(分隔線())

    # ─── 🔴 該賣 (Phase 40: 套用 conviction 過濾，方舟「算給看不強制」哲學) ───
    body.append(文字("🔴 該賣", size="md", color=C["bear"], weight="bold"))
    警示 = 真倉.get("警示", {})
    達停利 = 警示.get("達停利", [])
    破停損 = 警示.get("破停損", [])

    # 套用信念分數 + 部位大小過濾
    try:
        from . import conviction
    except ImportError:
        import conviction
    真該停損, 停損觀察中 = conviction.過濾停損警示(破停損, cfg, USD_TWD)

    該賣項目 = []
    for r in 達停利:
        is_us = r.get("is_us", False)
        賣股數 = max(1, r["shares"] // 2)
        price = r["current_price"]
        usd = 賣股數 * price if is_us else 0
        twd = 賣股數 * price * (USD_TWD if is_us else 1)
        該賣項目.append({
            "symbol": r["symbol"], "name": r.get("name", "")[:6],
            "is_us": is_us, "shares": 賣股數, "price": price,
            "usd": usd, "twd": twd, "理由": "🎯 達 +15% 停利（賣一半）",
        })
    for r in 真該停損:
        is_us = r.get("is_us", False)
        shares = r["shares"]
        price = r["current_price"]
        usd = shares * price if is_us else 0
        twd = shares * price * (USD_TWD if is_us else 1)
        該賣項目.append({
            "symbol": r["symbol"], "name": r.get("name", "")[:6],
            "is_us": is_us, "shares": shares, "price": price,
            "usd": usd, "twd": twd,
            "理由": f"💀 破停損 {r.get('_閾值', -3):.1f}% (信念 {r.get('_conviction', 3)}/5)",
        })

    if 該賣項目:
        for x in 該賣項目:
            符 = "$" if x["is_us"] else "NT$"
            行 = f"• {x['symbol']} {x['name']} — 賣 {x['shares']} 股 @ {符}{x['price']:.2f}"
            if x["is_us"]:
                金額 = f"  ≈ ${x['usd']:,.0f} (NT$ {x['twd']:,.0f})"
            else:
                金額 = f"  ≈ NT$ {x['twd']:,.0f}"
            body.append(文字(行, size="sm",
                             color=C["text_main"], weight="bold", wrap=True))
            body.append(文字(金額, size="xs", color=C["bull"], wrap=True))
            body.append(文字(f"  {x['理由']}",
                             size="xxs", color=C["text_dim"], wrap=True))
    else:
        body.append(文字("  今天沒有達停利／真該停損",
                        size="xs", color=C["text_dim"]))
    body.append(分隔線())

    # ─── 📉 觀察中（方舟風格：算給看不強制）───
    if 停損觀察中:
        body.append(文字("📉 觀察中（紀律觸發但不強制）",
                        size="md", color=C["wait"], weight="bold"))
        for r in 停損觀察中[:5]:
            sym = r.get("symbol", "?")
            pnl_pct = r.get("pnl_pct", 0)
            conv = r.get("_conviction", 3)
            threshold = r.get("_閾值", -3)
            body.append(文字(
                f"• {sym} {pnl_pct:+.2f}% (信念 {conv}/5, 閾值 {threshold:.1f}%)",
                size="sm", color=C["text_main"], wrap=True))
            body.append(文字(f"  {r.get('_過濾原因', '')}",
                            size="xxs", color=C["text_dim"], wrap=True))
        body.append(分隔線())

    # ─── ⏸️ 該抱（列 Top 3 最賺名字，user 看了更安心）───
    該抱數 = 持股數 - len(必做)
    body.append(文字("⏸️ 該抱（紀律內，繼續抱）", size="md",
                     color=C["text_main"], weight="bold"))
    if 該抱數 > 0:
        # 列出最賺的 3 檔（不是該賣的）
        該賣symbols = set()
        for r in 真倉.get("警示", {}).get("達停利", []):
            該賣symbols.add(r.get("symbol"))
        for r in 真倉.get("警示", {}).get("破停損", []):
            該賣symbols.add(r.get("symbol"))
        該抱持股 = [p for p in 真倉["持股"]
                    if not p.get("error") and p["symbol"] not in 該賣symbols]
        該抱最賺 = sorted(該抱持股, key=lambda p: -p.get("pnl_pct", 0))[:3]
        body.append(文字(f"  共 {該抱數} 檔 — Top 3 表現：",
                        size="xs", color=C["text_dim"]))
        for p in 該抱最賺:
            色 = C["bull"] if p.get("pnl_pct", 0) >= 0 else C["bear"]
            body.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"    {p['symbol']}", size="xs",
                         color=C["text_main"], flex=4),
                    文字(f"{p.get('pnl_pct', 0):+.2f}%", size="xs",
                         color=色, align="end", weight="bold", flex=3),
                ],
            })
    body.append(分隔線())

    # ─── ❌ 不該追 ───
    body.append(文字("❌ 不該追", size="md",
                     color=C["wait"], weight="bold"))
    if 不該做:
        names = " · ".join(x.get("symbol", "?") for x in 不該做[:5])
        body.append(文字(f"  {names}", size="xs",
                        color=C["text_main"], wrap=True))
        body.append(文字("  過熱別追加 · 等回調再說",
                        size="xxs", color=C["text_dim"]))
    else:
        body.append(文字("  今天沒過熱標的",
                        size="xs", color=C["text_dim"]))

    # ─── 💰 可動用 ───
    body.append(分隔線())
    body.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("💰 還可動用", size="sm", color=C["text_dim"], flex=3),
            文字(f"NT$ {現金:,.0f}", size="md",
                 color=C["accent"], weight="bold", align="end", flex=4),
        ],
    })

    # ─── LIFF Button ───
    body.append(分隔線())
    body.append(_LIFF按鈕("📖 看為什麼這樣建議", "action_full"))

    return {
        "type": "bubble", "size": "mega",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": body,
        },
    }


def _卡_持股大盤() -> dict:
    """卡 2: 持股 & 大盤（ARK 風控 + Enjoy + 部位簡述 + 產業熱）"""
    try:
        from . import (capital_planner, portfolio_tracker, forex,
                       ark_dashboard, fear_greed, technical, flex_builder)
    except ImportError:
        import capital_planner, portfolio_tracker, forex
        import ark_dashboard, fear_greed, technical, flex_builder

    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    cfg = capital_planner.載入資金設定()
    USD_TWD = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32))["rate"]
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=USD_TWD)
    現金 = cfg.get("current_cash_twd", 0)
    總市值 = 真倉["總計"].get("市值_twd", 0)
    總損益 = 真倉["總計"].get("損益_twd", 0)
    總損益率 = 真倉["總計"].get("損益率_pct", 0)
    總資產 = 總市值 + 現金

    # F&G
    try:
        fg = fear_greed.取得恐慌貪婪指數()
        fg_score = fg.get("score") if fg else None
    except Exception:
        fg_score = None

    # ARK 風控分
    try:
        ark = ark_dashboard.整體儀表()
        ark_score = ark.get("總分") if ark else None
    except Exception:
        ark_score = None

    body = []
    # Header
    body.append({
        "type": "box", "layout": "vertical",
        "contents": [
            文字("📊 持股 & 大盤", size="xl",
                 color=C["accent"], weight="bold"),
            文字(f"{len(真倉['持股'])} 檔 · 總資產 NT$ {總資產:,.0f}",
                 size="xs", color=C["text_dim"]),
        ],
    })
    body.append(分隔線())

    # 部位摘要
    色 = C["bull"] if 總損益 >= 0 else C["bear"]
    body.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("總損益", size="sm", color=C["text_dim"], flex=2),
            文字(f"{總損益:+,.0f} ({總損益率:+.2f}%)",
                 size="md", color=色, weight="bold", align="end", flex=4),
        ],
    })
    body.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("現金水位", size="sm", color=C["text_dim"], flex=2),
            cash_pct := 文字(
                f"NT$ {現金:,.0f} ({現金/總資產*100:.1f}%)" if 總資產 else f"NT$ {現金:,.0f}",
                size="sm", color=C["text_main"], align="end", flex=4),
        ],
    })

    # F&G + ARK 風控
    if fg_score is not None or ark_score is not None:
        body.append(分隔線())
        if fg_score is not None:
            fg_色 = (C["bear"] if fg_score > 75 else
                    C["bull"] if fg_score < 25 else C["text_main"])
            body.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字("F&G 恐慌貪婪", size="sm", color=C["text_dim"], flex=3),
                    文字(f"{fg_score:.0f}", size="lg",
                         color=fg_色, weight="bold", align="end", flex=2),
                ],
            })
        if ark_score is not None:
            ark_色 = (C["bear"] if ark_score >= 80 else
                     C["wait"] if ark_score >= 60 else C["bull"])
            body.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字("LIS 風控分", size="sm", color=C["text_dim"], flex=3),
                    文字(f"{ark_score:.1f}", size="lg",
                         color=ark_色, weight="bold", align="end", flex=2),
                ],
            })

    body.append(分隔線())
    body.append(_LIFF按鈕("📈 看每檔詳細位階", "portfolio_detail"))

    return {
        "type": "bubble", "size": "mega",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": body,
        },
    }


def _卡_訊號機會() -> dict:
    """卡 3: 訊號 & 機會（訊號狀態 + 黑天鵝 + 全市場）"""
    try:
        from . import flex_builder, bottom_detector, signal_tracker
    except ImportError:
        import flex_builder, bottom_detector, signal_tracker

    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    body = []
    body.append({
        "type": "box", "layout": "vertical",
        "contents": [
            文字("🌐 訊號 & 機會", size="xl",
                 color=C["accent"], weight="bold"),
            文字("掃黑天鵝 + 新訊號 + 全市場機會", size="xs",
                 color=C["text_dim"]),
        ],
    })
    body.append(分隔線())

    # 黑天鵝命中
    try:
        sop = bottom_detector.即時底部判定()
        命中 = sop.get("命中數", 0)
        body.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字("黑天鵝命中", size="sm", color=C["text_dim"], flex=3),
                文字(f"{命中}/5", size="md",
                     color=C["bull"] if 命中 >= 3 else C["text_main"],
                     weight="bold", align="end", flex=2),
            ],
        })
        if 命中 >= 3:
            body.append(文字("🚨 加碼訊號出現 — 等彈藥就位",
                            size="xs", color=C["bear"], weight="bold", wrap=True))
    except Exception:
        pass

    # 訊號狀態
    try:
        sig = signal_tracker.取得訊號狀態()
        新增 = sig.get("新增", []) if sig else []
        if 新增:
            body.append(分隔線())
            body.append(文字(f"🆕 今日新訊號 {len(新增)} 檔",
                            size="sm", color=C["bull"], weight="bold"))
            for s in 新增[:3]:
                body.append(文字(f"  {s.get('symbol','?')} {s.get('name','')[:6]}",
                                size="xs", color=C["text_main"]))
    except Exception:
        pass

    body.append(分隔線())
    body.append(_LIFF按鈕("🔍 看完整新進場清單", "opportunities"))

    return {
        "type": "bubble", "size": "mega",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": body,
        },
    }


def _卡_Sylvie_KOL() -> dict:
    """卡 3 (Phase 37.2): 我的老師們今天說什麼（小白導向）"""
    try:
        from . import flex_builder
    except ImportError:
        import flex_builder
    try:
        from . import community_consensus
    except Exception:
        try:
            import community_consensus
        except Exception:
            community_consensus = None

    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    body = []

    # ─── Header ───
    body.append(文字("👥 老師們今日重點", size="xl",
                     color=C["accent"], weight="bold"))
    body.append(文字("Enjoy + 香港朋友 + Sylvie + 6 大 KOL",
                     size="xs", color=C["text_dim"]))
    body.append(分隔線())

    # ─── 🚀 Enjoy 朋友（神人 14 年，10 萬→千萬，LIS 命名由來）───
    body.append(文字("🚀 Enjoy 朋友（14 年｜10 萬→千萬）",
                     size="sm", color=C["accent"], weight="bold"))
    body.append(文字("  3 方法給新手:",
                    size="xs", color=C["text_main"]))
    body.append(文字("  ① 無腦投資大盤 ETF",
                    size="xxs", color=C["text_main"]))
    body.append(文字("  ② 一半存股 + 一半短線",
                    size="xxs", color=C["text_main"]))
    body.append(文字("  ③ 重壓一檔最看好",
                    size="xxs", color=C["text_main"]))
    body.append(文字("  「人人都知道，但人人做不到」",
                    size="xxs", color=C["text_dim"], wrap=True))
    body.append(分隔線())

    # ─── 🇭🇰 香港朋友（hard-coded 心法，從記憶來）───
    body.append(文字("🇭🇰 香港朋友（15 年）", size="sm",
                     color=C["accent"], weight="bold"))
    body.append(文字("  • 押 AI + 一點生技",
                    size="xs", color=C["text_main"]))
    body.append(文字("  • 欣興 / 台積電 分批買",
                    size="xs", color=C["text_main"]))
    body.append(文字("  • 動能派 — 追高但 user 該穩定派",
                    size="xxs", color=C["text_dim"]))
    body.append(分隔線())

    # ─── 💎 Sylvie 太太（具體最近動作）───
    body.append(文字("💎 太太 Sylvie", size="sm",
                     color=C["accent"], weight="bold"))
    try:
        sylvie_path = 專案根 / "數據" / "sylvie_portfolio.json"
        if sylvie_path.exists():
            import json as _j
            sy = _j.loads(sylvie_path.read_text(encoding="utf-8"))
            最新加碼日 = sy.get("_最新加碼日", "")
            最新說明 = sy.get("_最新加碼說明", "")
            總報酬率 = sy.get("總報酬率_pct")
            dca = sy.get("DCA帳戶高報酬", {})

            if 最新說明:
                body.append(文字(f"  • {最新加碼日}",
                                size="xxs", color=C["text_dim"]))
                body.append(文字(f"  → {最新說明}",
                                size="xs", color=C["text_main"], wrap=True))
            if 總報酬率 is not None:
                色 = C["bull"] if 總報酬率 >= 0 else C["bear"]
                body.append(文字(f"  • 主帳戶總報酬率 {總報酬率:+.2f}%",
                                size="xs", color=色))
            # DCA 子帳戶最賺 3 檔
            if dca and isinstance(dca, dict):
                dca_items = [(k, v) for k, v in dca.items()
                             if k != "說明" and isinstance(v, dict)
                             and "報酬率_pct" in v]
                dca_items.sort(key=lambda x: -x[1].get("報酬率_pct", 0))
                if dca_items:
                    body.append(文字("  • DCA 子帳戶高報酬:",
                                    size="xs", color=C["text_dim"]))
                    for sym, info in dca_items[:3]:
                        rate = info.get("報酬率_pct", 0)
                        body.append(文字(f"    {sym} +{rate:.1f}%",
                                        size="xxs", color=C["bull"]))
        else:
            body.append(文字("  • 走價值區買進 · DCA + 重押勇氣",
                            size="xs", color=C["text_main"]))
    except Exception:
        body.append(文字("  • 走價值區買進策略",
                        size="xs", color=C["text_main"]))
    body.append(分隔線())

    # ─── 🎤 6 大 KOL 共識（從 KOL cache 讀 watchlist_hits）───
    body.append(文字("🎤 6 大 KOL 今日共識", size="sm",
                     color=C["accent"], weight="bold"))
    try:
        from datetime import datetime as _dt
        kol_path = (專案根 / "數據" / "daily" /
                    f"kol_{_dt.now():%Y-%m-%d}.json")
        if kol_path.exists():
            import json as _j
            kc = _j.loads(kol_path.read_text(encoding="utf-8"))
            hits = kc.get("watchlist_hits", {})
            if hits:
                # 排序 by 次數
                sorted_hits = sorted(hits.items(), key=lambda x: -x[1])[:5]
                for label, count in sorted_hits:
                    body.append(文字(f"  • {label} — {count} 人提到",
                                    size="xs", color=C["text_main"], wrap=True))
            else:
                body.append(文字("  • KOL 今日無明確共識",
                                size="xs", color=C["text_dim"]))
        else:
            body.append(文字("  • 今天還沒抓到 KOL 訊號",
                            size="xs", color=C["text_dim"]))
    except Exception as _e:
        body.append(文字(f"  • KOL 讀取失敗",
                        size="xs", color=C["text_dim"]))

    # ─── LIFF Button ───
    body.append(分隔線())
    body.append(_LIFF按鈕("📋 看完整老師摘要", "kol_consensus"))

    return {
        "type": "bubble", "size": "mega",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": body,
        },
    }


def _卡_美股新聞() -> dict:
    """卡 5: 美股 & 新聞 + 今日心法"""
    try:
        from . import (flex_builder, capital_planner, portfolio_tracker,
                       forex, technical)
    except ImportError:
        import flex_builder, capital_planner, portfolio_tracker
        import forex, technical

    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    cfg = capital_planner.載入資金設定()
    USD_TWD = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32))["rate"]
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=USD_TWD)
    美股持股 = [p for p in 真倉["持股"]
                if p.get("is_us") and not p.get("error")]
    美股小計 = 真倉.get("美股小計", {})

    body = []
    body.append({
        "type": "box", "layout": "vertical",
        "contents": [
            文字("🇺🇸 美股 & 新聞", size="xl",
                 color=C["accent"], weight="bold"),
            文字(f"{len(美股持股)} 檔美股 · 昨夜收盤", size="xs",
                 color=C["text_dim"]),
        ],
    })
    body.append(分隔線())

    # 美股摘要
    if 美股持股:
        美股市值 = 美股小計.get("市值_usd", 0)
        美股損益 = 美股小計.get("損益_usd", 0)
        美股率 = 美股小計.get("損益率_pct", 0)
        色 = C["bull"] if 美股損益 >= 0 else C["bear"]
        body.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字("美股總損益", size="sm", color=C["text_dim"], flex=3),
                文字(f"{美股損益:+,.2f} ({美股率:+.2f}%)",
                     size="md", color=色, weight="bold", align="end", flex=4),
            ],
        })
        # Top 3 損益
        sorted_持股 = sorted(美股持股, key=lambda p: -abs(p.get("pnl_pct", 0)))[:3]
        for p in sorted_持股:
            p色 = C["bull"] if p.get("pnl_pct", 0) >= 0 else C["bear"]
            body.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"{p['symbol']}", size="xs",
                         color=C["text_main"], weight="bold", flex=2),
                    文字(f"{p.get('pnl_pct', 0):+.2f}%", size="xs",
                         color=p色, align="end", flex=2),
                ],
            })

    # 大盤 VIX / SPY
    body.append(分隔線())
    for sym, label in [("^VIX", "VIX"), ("SPY", "SPY"), ("QQQ", "QQQ")]:
        try:
            歷史, _ = technical.取得每日股價(sym, period="3d")
            if 歷史 and len(歷史) >= 2:
                現 = 歷史[0]["close"]
                昨 = 歷史[1]["close"]
                當日 = (現/昨 - 1) * 100
                色 = (C["bear"] if (sym == "^VIX" and 現 > 25)
                      else C["bull"] if 當日 >= 0 else C["bear"])
                body.append({
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(label, size="xs", color=C["text_dim"], flex=2),
                        文字(f"{現:.2f} ({當日:+.2f}%)", size="xs",
                             color=色, align="end", flex=4),
                    ],
                })
        except Exception:
            continue

    body.append(分隔線())
    body.append(_LIFF按鈕("🌙 看美股完整覆盤", "us_close"))

    return {
        "type": "bubble", "size": "mega",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": body,
        },
    }


def _卡_我的部位() -> dict:
    """卡 2 (Phase 37.2 小白導向): 我現在賺多少 / 虧多少 + 大盤暖度（人話版）"""
    try:
        from . import (capital_planner, portfolio_tracker, forex,
                       ark_dashboard, fear_greed, technical,
                       bottom_detector, flex_builder)
    except ImportError:
        import capital_planner, portfolio_tracker, forex
        import ark_dashboard, fear_greed, technical
        import bottom_detector, flex_builder

    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    cfg = capital_planner.載入資金設定()
    USD_TWD = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32))["rate"]
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=USD_TWD)

    持股數 = len(真倉["持股"])
    總成本 = 真倉["總計"].get("成本_twd", 0)
    總市值 = 真倉["總計"].get("市值_twd", 0)
    總損益 = 真倉["總計"].get("損益_twd", 0)
    總損益率 = 真倉["總計"].get("損益率_pct", 0)

    # 大盤暖度
    try:
        fg = fear_greed.取得恐慌貪婪指數()
        fg_score = fg.get("score") if fg else None
    except Exception:
        fg_score = None
    try:
        ark = ark_dashboard.整體儀表()
        ark_score = ark.get("總分") if ark else None
    except Exception:
        ark_score = None
    try:
        sop = bottom_detector.即時底部判定()
        黑天鵝命中 = sop.get("命中數", 0)
    except Exception:
        黑天鵝命中 = 0

    # Top 賺 / 虧
    持股 = [p for p in 真倉["持股"] if not p.get("error")]
    最賺 = sorted(持股, key=lambda p: -p.get("pnl_pct", 0))[:3]
    最虧 = sorted(持股, key=lambda p: p.get("pnl_pct", 0))[:3]

    body = []

    # ─── Header ───
    body.append(文字("💼 我的部位", size="xl",
                     color=C["accent"], weight="bold"))
    body.append(文字(f"{持股數} 檔 · 總資產 NT$ {(總市值 + cfg.get('current_cash_twd', 0)):,.0f}",
                     size="xs", color=C["text_dim"]))
    body.append(分隔線())

    # ─── 成本 vs 現在 (user 5/16 確認用「成本」)───
    body.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("成本", size="sm", color=C["text_dim"], flex=3),
            文字(f"NT$ {總成本:,.0f}", size="sm",
                 color=C["text_main"], align="end", flex=5),
        ],
    })
    body.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("現在價值", size="sm", color=C["text_dim"], flex=3),
            文字(f"NT$ {總市值:,.0f}", size="sm",
                 color=C["text_main"], align="end", flex=5),
        ],
    })

    色 = C["bull"] if 總損益 >= 0 else C["bear"]
    動詞 = "賺" if 總損益 >= 0 else "虧"
    body.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字(動詞, size="md", color=色, weight="bold", flex=3),
            文字(f"NT$ {總損益:+,.0f} ({總損益率:+.2f}%)",
                 size="md", color=色, weight="bold", align="end", flex=5),
        ],
    })

    # ─── 最賺 / 最虧 ───
    if 最賺:
        body.append(分隔線())
        body.append(文字("🔥 最賺 Top 3", size="sm",
                        color=C["bull"], weight="bold"))
        for p in 最賺:
            if p.get("pnl_pct", 0) <= 0:
                break
            body.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"  {p['symbol']}", size="xs",
                         color=C["text_main"], flex=3),
                    文字(f"{p.get('pnl_pct', 0):+.2f}%", size="xs",
                         color=C["bull"], align="end", weight="bold", flex=2),
                ],
            })

    if 最虧:
        body.append(文字("💧 最虧 Top 3", size="sm",
                        color=C["bear"], weight="bold", margin="md"))
        for p in 最虧:
            if p.get("pnl_pct", 0) >= 0:
                break
            body.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"  {p['symbol']}", size="xs",
                         color=C["text_main"], flex=3),
                    文字(f"{p.get('pnl_pct', 0):+.2f}%", size="xs",
                         color=C["bear"], align="end", weight="bold", flex=2),
                ],
            })

    # ─── 大盤暖度（人話）───
    body.append(分隔線())
    body.append(文字("📊 大盤暖度", size="sm",
                     color=C["text_main"], weight="bold"))
    body.append(文字(f"  {_FG轉人話(fg_score)}",
                     size="xs", color=C["text_main"], wrap=True))
    if ark_score is not None:
        body.append(文字(f"  {_風控分轉人話(ark_score)}",
                        size="xs", color=C["text_main"], wrap=True))
    # 黑天鵝（只在 ≥ 2 才顯示）
    黑天鵝文字 = _黑天鵝轉人話(黑天鵝命中)
    if 黑天鵝文字:
        body.append(文字(f"  {黑天鵝文字}",
                        size="xs", color=C["accent"],
                        weight="bold", wrap=True))

    # ─── LIFF Button ───
    body.append(分隔線())
    body.append(_LIFF按鈕("📈 看每檔詳細", "portfolio_detail"))

    return {
        "type": "bubble", "size": "mega",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": body,
        },
    }


def _卡_市場總覽() -> dict:
    """[已棄用 Phase 37.1] 卡 2 三合一 — 5/16 user feedback 後改 _卡_我的部位"""
    try:
        from . import (capital_planner, portfolio_tracker, forex,
                       ark_dashboard, fear_greed, technical,
                       bottom_detector, flex_builder)
    except ImportError:
        import capital_planner, portfolio_tracker, forex
        import ark_dashboard, fear_greed, technical
        import bottom_detector, flex_builder

    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    cfg = capital_planner.載入資金設定()
    USD_TWD = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32))["rate"]
    真倉 = portfolio_tracker.追蹤真倉(cfg, USD_TWD=USD_TWD)
    現金 = cfg.get("current_cash_twd", 0)
    總市值 = 真倉["總計"].get("市值_twd", 0)
    總損益 = 真倉["總計"].get("損益_twd", 0)
    總損益率 = 真倉["總計"].get("損益率_pct", 0)
    總資產 = 總市值 + 現金

    # F&G + ARK 風控
    try:
        fg = fear_greed.取得恐慌貪婪指數()
        fg_score = fg.get("score") if fg else None
    except Exception:
        fg_score = None
    try:
        ark = ark_dashboard.整體儀表()
        ark_score = ark.get("總分") if ark else None
    except Exception:
        ark_score = None

    # 黑天鵝
    try:
        sop = bottom_detector.即時底部判定()
        黑天鵝命中 = sop.get("命中數", 0)
    except Exception:
        黑天鵝命中 = 0

    # 美股摘要
    美股持股 = [p for p in 真倉["持股"]
                if p.get("is_us") and not p.get("error")]
    美股小計 = 真倉.get("美股小計", {})

    body = []

    # ─── Header ───
    body.append({
        "type": "box", "layout": "vertical",
        "contents": [
            文字("📊 市場總覽", size="xl",
                 color=C["accent"], weight="bold"),
            文字(f"{len(真倉['持股'])} 檔 · 總資產 NT$ {總資產:,.0f}",
                 size="xs", color=C["text_dim"]),
        ],
    })
    body.append(分隔線())

    # ─── 區 1：持股摘要 ───
    色 = C["bull"] if 總損益 >= 0 else C["bear"]
    body.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("總損益", size="sm", color=C["text_dim"], flex=3),
            文字(f"{總損益:+,.0f} ({總損益率:+.2f}%)",
                 size="md", color=色, weight="bold", align="end", flex=5),
        ],
    })
    if 總資產 > 0:
        body.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字("現金水位", size="sm", color=C["text_dim"], flex=3),
                文字(f"NT$ {現金:,.0f} ({現金/總資產*100:.1f}%)",
                     size="sm", color=C["text_main"], align="end", flex=5),
            ],
        })

    # ─── 區 2：大盤儀表（F&G + 風控 + 黑天鵝）───
    body.append(分隔線())
    if fg_score is not None:
        fg_色 = (C["bear"] if fg_score > 75 else
                C["bull"] if fg_score < 25 else C["text_main"])
        body.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字("F&G 恐慌貪婪", size="sm", color=C["text_dim"], flex=4),
                文字(f"{fg_score:.0f}", size="md",
                     color=fg_色, weight="bold", align="end", flex=2),
            ],
        })
    if ark_score is not None:
        ark_色 = (C["bear"] if ark_score >= 80 else
                 C["wait"] if ark_score >= 60 else C["bull"])
        body.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字("LIS 風控分", size="sm", color=C["text_dim"], flex=4),
                文字(f"{ark_score:.1f}", size="md",
                     color=ark_色, weight="bold", align="end", flex=2),
            ],
        })
    # 黑天鵝命中
    body.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("黑天鵝命中", size="sm", color=C["text_dim"], flex=4),
            文字(f"{黑天鵝命中}/5", size="md",
                 color=C["bull"] if 黑天鵝命中 >= 3 else C["text_main"],
                 weight="bold", align="end", flex=2),
        ],
    })
    if 黑天鵝命中 >= 3:
        body.append(文字("🚨 加碼訊號出現 — 等彈藥就位",
                        size="xs", color=C["bear"], weight="bold", wrap=True))

    # ─── 區 3：美股摘要 ───
    if 美股持股:
        body.append(分隔線())
        美股損益 = 美股小計.get("損益_usd", 0)
        美股率 = 美股小計.get("損益率_pct", 0)
        美色 = C["bull"] if 美股損益 >= 0 else C["bear"]
        body.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字(f"🇺🇸 美股 {len(美股持股)} 檔", size="sm",
                     color=C["text_dim"], flex=3),
                文字(f"{美股損益:+,.2f} ({美股率:+.2f}%)",
                     size="sm", color=美色, weight="bold", align="end", flex=4),
            ],
        })
        # Top 3 損益絕對值
        sorted_持股 = sorted(美股持股,
                            key=lambda p: -abs(p.get("pnl_pct", 0)))[:3]
        for p in sorted_持股:
            p色 = C["bull"] if p.get("pnl_pct", 0) >= 0 else C["bear"]
            body.append({
                "type": "box", "layout": "horizontal",
                "contents": [
                    文字(f"  {p['symbol']}", size="xs",
                         color=C["text_main"], flex=2),
                    文字(f"{p.get('pnl_pct', 0):+.2f}%", size="xs",
                         color=p色, align="end", flex=2),
                ],
            })

    # 大盤指標
    body.append(分隔線())
    for sym, label in [("^VIX", "VIX"), ("SPY", "SPY"), ("QQQ", "QQQ")]:
        try:
            歷史, _ = technical.取得每日股價(sym, period="3d")
            if 歷史 and len(歷史) >= 2:
                現 = 歷史[0]["close"]
                昨 = 歷史[1]["close"]
                當日 = (現/昨 - 1) * 100
                色 = (C["bear"] if (sym == "^VIX" and 現 > 25)
                      else C["bull"] if 當日 >= 0 else C["bear"])
                body.append({
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(label, size="xs", color=C["text_dim"], flex=2),
                        文字(f"{現:.2f} ({當日:+.2f}%)", size="xs",
                             color=色, align="end", flex=4),
                    ],
                })
        except Exception:
            continue

    # ─── LIFF 按鈕（2 個並列）───
    body.append(分隔線())
    body.append(_LIFF按鈕("📊 看每檔詳細位階", "portfolio_detail"))
    body.append(_LIFF按鈕("🌙 看美股完整覆盤", "us_close"))

    return {
        "type": "bubble", "size": "mega",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": body,
        },
    }


def 組5張主卡() -> list[dict]:
    """產生 3 張主卡（Phase 37.2 小白導向重寫）

    函式名保留為「組5張主卡」避免破壞 push_5cards.py 呼叫，內容已改 3 張且小白化。
    3 張：
      1. 今天該做什麼（該買/該賣/該抱/不該追）
      2. 我的部位（賺多少/虧多少/大盤暖度人話）
      3. 老師們今日重點（香港朋友/Sylvie/KOL）
    """
    cards = []
    for builder, 名 in [
        (_卡_今日行動, "今天該做什麼"),
        (_卡_我的部位, "我的部位（賺多少）"),
        (_卡_Sylvie_KOL, "老師們今日重點"),
    ]:
        try:
            cards.append(builder())
            print(f"  ✓ {名}")
        except Exception as e:
            import traceback
            print(f"  ✗ {名} 失敗：{e}")
            traceback.print_exc()
    return cards


def 推5張主卡() -> bool:
    """組 3 張主卡 + 推 LINE（函式名保留兼容性）"""
    try:
        from . import line_push
    except ImportError:
        import line_push

    print("組主卡...")
    cards = 組5張主卡()  # 內容已改 3 張
    if not cards:
        print("❌ 沒有任何卡可推")
        return False

    print(f"\n推 {len(cards)} 張主卡到 LINE...")
    from datetime import datetime
    carousel = {"type": "carousel", "contents": cards}
    alt = f"🌅 LIS 早晨總覽 — {datetime.now():%m/%d %a} ({len(cards)} 張主卡)"
    try:
        line_push.推播Flex訊息(替代文字=alt, flex內容=carousel)
        print(f"✅ 推播完成 — {len(cards)} 張主卡")
        return True
    except Exception as e:
        print(f"❌ 推播失敗：{e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from dotenv import load_dotenv
    load_dotenv(專案根 / "API" / ".env")
    sys.path.insert(0, str(專案根 / "程式碼"))

    ok = 推5張主卡()
    sys.exit(0 if ok else 1)
