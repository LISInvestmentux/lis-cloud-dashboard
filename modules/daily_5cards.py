"""
LIS 早上 8AM 5 張總覽主卡（Phase 37 — 2026-05-16）

設計目標：user 抱怨 30+ 張卡太多 → 整合成 5 張，每張帶 LIFF 按鈕展開細節。

5 張卡：
  1. 🎯 今日行動 — 必做 / 已掛單 / 預警 / 不該追
  2. 📊 持股 & 大盤 — 部位 + ARK 風控 + Enjoy + 處置警示 + 產業氣溫
  3. 🌐 訊號 & 機會 — 訊號狀態 + 位階 + 黑天鵝 + 全市場發現
  4. 👥 Sylvie & KOL 共識 — KOL 共識 + Sylvie 重押 + 朋友圈訊號
  5. 🇺🇸 美股 & 新聞 — 美股觀察 + 新聞摘要 + AI 解釋 + 今日心法

每張卡上加 LIFF 按鈕，點下去開 Streamlit Cloud 對應 view（Phase 2b 完成 view 切換）。
"""
import os
import sys
from pathlib import Path
from typing import Optional

專案根 = Path(__file__).resolve().parent.parent.parent
LIFF_BASE = os.getenv("LIFF_URL", "https://liff.line.me/2010070081-6wmnysUD")


def _LIFF按鈕(label: str, view: str) -> dict:
    """生成 LIFF 按鈕（Phase 2b 加 ?view=xxx 切換）"""
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


def _卡_今日行動() -> dict:
    """卡 1: 今日行動（複用 daily_action_card）"""
    try:
        from . import daily_action_card, flex_builder
    except ImportError:
        import daily_action_card, flex_builder

    今日 = daily_action_card.組今日行動()
    flex = daily_action_card.建構Flex卡(今日)

    # 在 body 末尾加 LIFF 按鈕
    if "body" in flex and "contents" in flex["body"]:
        flex["body"]["contents"].append(
            _LIFF按鈕("📖 看完整 watchlist 訊號", "action_full")
        )
    return flex


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
    """卡 4: Sylvie & KOL 共識"""
    try:
        from . import flex_builder, kol_aggregator, community_consensus
    except ImportError:
        import flex_builder
        try:
            import kol_aggregator
        except Exception:
            kol_aggregator = None
        try:
            import community_consensus
        except Exception:
            community_consensus = None

    C = flex_builder.C
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線

    body = []
    body.append({
        "type": "box", "layout": "vertical",
        "contents": [
            文字("👥 Sylvie & KOL 共識", size="xl",
                 color=C["accent"], weight="bold"),
            文字("太太佈局 + 6 大 KOL + 香港朋友", size="xs",
                 color=C["text_dim"]),
        ],
    })
    body.append(分隔線())

    # Sylvie 最新動作（從 sylvie_portfolio.json 或 sylvie_tracker）
    try:
        sylvie_path = 專案根 / "數據" / "sylvie_portfolio.json"
        if sylvie_path.exists():
            import json as _j
            sy = _j.loads(sylvie_path.read_text(encoding="utf-8"))
            最新 = sy.get("recent_actions", [])[:3] if isinstance(sy, dict) else []
            if 最新:
                body.append(文字("💎 Sylvie 最近動作", size="sm",
                                color=C["accent"], weight="bold"))
                for a in 最新:
                    body.append(文字(f"  {a}", size="xxs",
                                    color=C["text_main"], wrap=True))
    except Exception:
        pass

    # KOL 共識
    try:
        if community_consensus:
            cc = community_consensus.產生共識()
            top = cc.get("top_consensus", [])[:3] if cc else []
            if top:
                body.append(分隔線())
                body.append(文字(f"🔥 KOL 共識 Top {len(top)}", size="sm",
                                color=C["bull"], weight="bold"))
                for t in top:
                    sym = t.get("symbol", "?")
                    name = t.get("name", "")[:6]
                    count = t.get("count", 0)
                    body.append(文字(f"  {sym} {name} — {count} 人提到",
                                    size="xxs", color=C["text_main"]))
    except Exception:
        pass

    body.append(分隔線())
    body.append(_LIFF按鈕("📋 看完整 KOL 摘要", "kol_consensus"))

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


def 組5張主卡() -> list[dict]:
    """產生 5 張主卡，回傳 bubble list（每個 element 是 1 個 bubble）"""
    cards = []
    for builder, 名 in [
        (_卡_今日行動, "今日行動"),
        (_卡_持股大盤, "持股大盤"),
        (_卡_訊號機會, "訊號機會"),
        (_卡_Sylvie_KOL, "Sylvie/KOL"),
        (_卡_美股新聞, "美股新聞"),
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
    """組 5 張主卡 + 推 LINE"""
    try:
        from . import line_push
    except ImportError:
        import line_push

    print("組 5 張主卡...")
    cards = 組5張主卡()
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
