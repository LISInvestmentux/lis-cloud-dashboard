"""
ARK 集中模式行動規劃（Phase 20）

對標 ARK 大俠的 6-9 檔集中部位：
  讀 portfolio + Kelly DB + 即時報價，輸出具體賣什麼 / 留什麼 / 加碼什麼。

輸出：
  {
    保留: [{symbol, 現股, 目標股, 加碼股, 加碼金, ...}],
    賣出: [{symbol, 現股, 估值_twd, 賣理由, ...}],
    釋出資金_twd,
    建議部署_twd,
    預估7月後報酬_pct,
  }

策略：
  保留分數 = Kelly_pct ×3 + (是否ETF ×5) + (順勢分/10) - 集中懲罰
  Top N (預設 8) → 保留 + 按 Kelly 加權加碼
  其他 → 列入「賣出候選」
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import fugle_market, win_rate_engine, forex, capital_planner


專案根 = Path(__file__).resolve().parent.parent.parent


def 算保留分數(sym: str, p: dict, kelly_info: Optional[dict],
                positional_state: dict, 現價: Optional[float],
                持股市值_twd: float, 總資產_twd: float) -> dict:
    """
    對一檔持股算「保留分數」+ 解釋。
    """
    分 = 0
    理由 = []

    # 1. Kelly% 主因子 ×3
    if kelly_info:
        kelly = kelly_info.get("Kelly_pct", 0)
        分 += kelly * 3
        if kelly >= 10:
            理由.append(f"Kelly {kelly:.1f}% 極高 +{kelly*3:.0f}")
        elif kelly >= 5:
            理由.append(f"Kelly {kelly:.1f}% +{kelly*3:.0f}")
        elif kelly > 0:
            理由.append(f"Kelly {kelly:.1f}% 偏低 +{kelly*3:.0f}")
        else:
            理由.append(f"Kelly 0% ⚠️")
    else:
        # 無 Kelly 資料 = 樣本不足或新股
        理由.append("無 Kelly 數據（樣本不足）")

    # 2. 是否 ETF +5（分散風險 + 易回測）
    is_etf = sym.startswith("00") or sym == "0050.TW"
    if is_etf:
        分 += 5
        理由.append("ETF +5")

    # 2b. 避險工具 +15（公債/抗風險 ETF）
    if sym.startswith("00942") or sym in ("00679B.TW", "00937B.TW"):
        分 += 15
        理由.append("避險工具 +15")

    # 2c. 龍頭股 +10（台股雙巨頭、必要 base）
    if sym in ("0050.TW", "2330.TW", "00646.TW", "VOO", "QQQ"):
        分 += 10
        理由.append("市場龍頭 +10")

    # 3. 順勢分 ÷10
    d = positional_state.get("details", {}).get(sym, {})
    順勢分 = d.get("順勢分")
    if 順勢分:
        分 += 順勢分 / 10
        理由.append(f"順勢 {順勢分:.0f} +{順勢分/10:.1f}")

    # 4. 集中度懲罰
    集中度 = (持股市值_twd / 總資產_twd * 100) if 總資產_twd > 0 else 0
    if 集中度 >= 15:
        分 -= 10
        理由.append(f"已過度集中 {集中度:.0f}% -10")
    elif 集中度 >= 10:
        分 -= 5
        理由.append(f"集中度 {集中度:.0f}% -5")

    # 5. 美股零碎股 (1 股) → 強烈降權
    is_us = not (sym.endswith(".TW") or sym.endswith(".TWO"))
    shares = p.get("shares", 0)
    if is_us and shares <= 1:
        分 -= 20
        理由.append("美股零碎股 -20")

    # 6. 個股 vs ETF 偏好（小資金優先 ETF，但高 Kelly 個股保留）
    if not is_etf and not is_us:
        if kelly_info and kelly_info.get("Kelly_pct", 0) >= 6:
            分 += 5  # 高 Kelly 個股值得保留
            理由.append("高Kelly 個股 +5")
        else:
            分 -= 3
            理由.append("台股個股 -3")

    return {
        "分數": round(分, 1),
        "理由": 理由,
        "Kelly_pct": kelly_info.get("Kelly_pct", 0) if kelly_info else None,
        "集中度_pct": round(集中度, 2),
        "是ETF": is_etf,
        "是美股": is_us,
    }


def 產生集中計畫(目標檔數: int = 8,
                  總資產_twd: Optional[float] = None,
                  目標報酬_pct: float = 35.0,
                  時程_月: int = 7,
                  強制保留: Optional[list] = None) -> dict:
    """
    主入口：產生 ARK 集中模式行動計畫。
    強制保留: 不論評分都納入保留的標的清單（避險、DCA 主力）
    """
    cfg = capital_planner.載入資金設定()
    現金 = cfg.get("current_cash_twd", 0)
    持股清單 = [p for p in cfg.get("current_positions", [])
                if p.get("symbol") != "AGGREGATE"]

    # 抓匯率
    匯率資訊 = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32.0))
    USD_TWD = 匯率資訊["rate"]

    # 載入 Kelly DB
    勝率DB = win_rate_engine.載入勝率資料庫()

    # 載入 positional state
    state_path = 專案根 / "數據" / "positional_state.json"
    positional_state = {}
    if state_path.exists():
        positional_state = json.loads(state_path.read_text(encoding="utf-8"))

    # 抓所有持股現價 + 算市值
    持股詳細 = []
    持股市值總 = 0
    for p in 持股清單:
        sym = p["symbol"]
        股數 = p.get("shares", 0)
        成本 = p.get("avg_cost", 0)

        q = fugle_market.即時報價_fallback(sym)
        現價 = q.get("close") if q else None
        if 現價 is None:
            現價 = 成本

        is_us = not (sym.endswith(".TW") or sym.endswith(".TWO"))
        倍率 = USD_TWD if is_us else 1.0
        市值_twd = 現價 * 股數 * 倍率
        成本_twd = 成本 * 股數 * 倍率
        持股市值總 += 市值_twd

        持股詳細.append({
            "symbol": sym, "name": p.get("name", ""),
            "shares": 股數, "avg_cost": 成本,
            "現價": 現價, "市值_twd": 市值_twd, "成本_twd": 成本_twd,
            "is_us": is_us, "倍率": 倍率,
            "未實現損益": 市值_twd - 成本_twd,
            "未實現損益_pct": ((現價 / 成本 - 1) * 100) if 成本 > 0 else 0,
        })

    總資產 = 總資產_twd or (持股市值總 + 現金)

    # 對每檔算保留分數
    for h in 持股詳細:
        h["評分"] = 算保留分數(
            h["symbol"], h, 勝率DB.get(h["symbol"]),
            positional_state, h["現價"],
            h["市值_twd"], 總資產
        )

    # 排序：分數高在前
    持股詳細.sort(key=lambda h: -h["評分"]["分數"])

    # 強制保留清單（避險 + DCA 主力 + 台股龍頭）
    強制保留 = 強制保留 or []
    # DCA 主力
    dca_items = cfg.get("long_term_dca", {}).get("items", [])
    for it in dca_items:
        if it.get("symbol") and it["symbol"] not in 強制保留:
            強制保留.append(it["symbol"])
    # 台股龍頭（必保留）
    for sym in ("2330.TW",):
        if sym not in 強制保留:
            強制保留.append(sym)
    # 自動加避險 ETF
    for h in 持股詳細:
        if (h["symbol"].startswith("00942") and
            h["symbol"] not in 強制保留):
            強制保留.append(h["symbol"])

    # 切分：先 Top N，再把強制保留檔加進來（如果還沒在內）
    保留 = list(持股詳細[:目標檔數])
    保留_代號 = {h["symbol"] for h in 保留}
    for h in 持股詳細:
        if h["symbol"] in 強制保留 and h["symbol"] not in 保留_代號:
            保留.append(h)
            保留_代號.add(h["symbol"])

    賣出 = [h for h in 持股詳細 if h["symbol"] not in 保留_代號]

    # 算釋出資金 + 加碼計畫
    釋出資金 = sum(h["市值_twd"] for h in 賣出)
    可加碼 = 釋出資金 + max(0, 現金 - 總資產 * 0.35)  # 加上閒錢過量部分

    # 對保留檔按 Kelly% 加權，計算加碼比例
    Kelly權重 = []
    for h in 保留:
        kelly = h["評分"].get("Kelly_pct") or 0
        # 沒 Kelly 的給最低權重
        權重 = max(2.0, kelly) if kelly else 2.0
        Kelly權重.append(權重)
    Kelly總 = sum(Kelly權重) or 1

    for h, w in zip(保留, Kelly權重):
        加碼金 = 可加碼 * (w / Kelly總)
        加碼金 = max(0, 加碼金)
        h["加碼金_twd"] = int(加碼金)
        加碼股 = int(加碼金 / (h["現價"] * h["倍率"])) if h["現價"] > 0 else 0
        h["加碼股數"] = max(0, 加碼股)
        h["目標股數"] = h["shares"] + 加碼股
        h["目標市值_twd"] = h["目標股數"] * h["現價"] * h["倍率"]
        h["目標佔比_pct"] = h["目標市值_twd"] / 總資產 * 100

    # 估算 7 月後報酬
    預估報酬_twd = 0
    for h in 保留:
        kelly = h["評分"].get("Kelly_pct") or 3.0
        # 7 月期望報酬 ≈ kelly% × 5 + 順勢加成
        順勢 = positional_state.get("details", {}).get(
            h["symbol"], {}).get("順勢分") or 50
        期望_pct = kelly * 3 + (順勢 - 50) / 5
        期望_pct = max(-10, min(50, 期望_pct))
        h["預估7月報酬_pct"] = round(期望_pct, 1)
        預估報酬_twd += h["目標市值_twd"] * 期望_pct / 100

    預估報酬率 = 預估報酬_twd / 總資產 * 100 if 總資產 > 0 else 0

    return {
        "目標檔數": 目標檔數,
        "目標報酬_pct": 目標報酬_pct,
        "時程_月": 時程_月,
        "現狀": {
            "總資產_twd": round(總資產, 0),
            "現金_twd": round(現金, 0),
            "持股市值_twd": round(持股市值總, 0),
            "持股檔數": len(持股清單),
            "USD_TWD": USD_TWD,
        },
        "保留": 保留,
        "賣出": 賣出,
        "釋出資金_twd": round(釋出資金, 0),
        "可加碼總額_twd": round(可加碼, 0),
        "預估7月後報酬_twd": round(預估報酬_twd, 0),
        "預估7月後報酬_pct": round(預估報酬率, 2),
        "達標機率": ("高" if 預估報酬率 >= 目標報酬_pct
                      else "中" if 預估報酬率 >= 目標報酬_pct * 0.7
                      else "低"),
    }


# ─────────────────────────────────────────────
# Flex 卡建構
# ─────────────────────────────────────────────
def 建構集中計畫卡(計畫: dict) -> dict:
    from . import flex_builder
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線
    C = flex_builder.C

    現 = 計畫["現狀"]
    內容 = []

    # Header
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字(f"🎯 ARK 集中模式（{計畫['目標檔數']} 檔）",
                 size="xl", color=C["text_main"], weight="bold"),
            文字(f"7 月內目標 +{計畫['目標報酬_pct']:.0f}% · "
                 f"預估 +{計畫['預估7月後報酬_pct']:.1f}%",
                 size="xs", color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())

    # 現狀
    內容.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("📐 總資產", size="xs", color=C["text_dim"], flex=2),
            文字(f"NT$ {現['總資產_twd']:,.0f}", size="xs",
                 color=C["text_main"], align="end", flex=3),
        ],
    })
    內容.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字(f"當前持股 {現['持股檔數']} 檔", size="xs",
                 color=C["text_dim"], flex=2),
            文字(f"→ 目標 {計畫['目標檔數']} 檔", size="xs",
                 color=C["accent"], align="end", flex=3),
        ],
    })
    內容.append(分隔線())

    # 保留清單
    內容.append(文字(f"✅ 保留並加碼 ({len(計畫['保留'])} 檔)",
                     size="md", color=C["bull"], weight="bold"))
    for h in 計畫["保留"]:
        # 第一行：標的 + Kelly + 目標佔比
        kelly = h["評分"].get("Kelly_pct")
        kelly_str = f"K {kelly:.1f}%" if kelly else "K n/a"
        內容.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "paddingTop": "sm",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"⭐ {h['symbol']}", size="sm",
                             color=C["text_main"], weight="bold", flex=4),
                        文字(kelly_str, size="xxs",
                             color=C["accent"], align="end", flex=2),
                        文字(f"目標 {h['目標佔比_pct']:.0f}%",
                             size="xxs", color=C["bull"],
                             align="end", flex=3),
                    ],
                },
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"現 {h['shares']} 股", size="xxs",
                             color=C["text_dim"], flex=3),
                        文字(f"+ {h['加碼股數']} 股", size="xxs",
                             color=C["bull"], align="center", flex=2),
                        文字(f"NT$ {h['加碼金_twd']:,}",
                             size="xs", color=C["accent"],
                             align="end", flex=4),
                    ],
                },
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        文字(f"預估 7 月 +{h['預估7月報酬_pct']:.1f}%",
                             size="xxs", color=C["text_subtle"], flex=1),
                    ],
                },
            ],
        })

    內容.append(分隔線())

    # 賣出清單
    內容.append(文字(f"🪓 建議賣出 ({len(計畫['賣出'])} 檔)",
                     size="md", color=C["bear"], weight="bold"))
    內容.append(文字(f"釋出資金 NT$ {計畫['釋出資金_twd']:,.0f}",
                     size="xs", color=C["accent"]))

    for h in 計畫["賣出"][:8]:
        kelly = h["評分"].get("Kelly_pct")
        kelly_str = f"K {kelly:.1f}%" if kelly else "K n/a"
        # 估值用市值
        內容.append({
            "type": "box", "layout": "horizontal", "spacing": "xs",
            "paddingTop": "xs",
            "contents": [
                文字(f"❌ {h['symbol']}", size="sm",
                     color=C["text_dim"], flex=3),
                文字(kelly_str, size="xxs",
                     color=C["bear"], align="center", flex=2),
                文字(f"{h['未實現損益_pct']:+.1f}%", size="xxs",
                     color=(C["bull"] if h["未實現損益_pct"] >= 0
                            else C["bear"]),
                     align="center", flex=2),
                文字(f"NT$ {h['市值_twd']:,.0f}",
                     size="xs", color=C["text_main"],
                     align="end", flex=3),
            ],
        })

    if len(計畫["賣出"]) > 8:
        內容.append(文字(f"... 還有 {len(計畫['賣出']) - 8} 檔",
                         size="xxs", color=C["text_subtle"]))

    內容.append(分隔線())

    # 結語
    達標 = 計畫["達標機率"]
    達標色 = (C["bull"] if 達標 == "高"
              else C["wait"] if 達標 == "中"
              else C["bear"])
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "paddingTop": "sm",
        "contents": [
            文字(f"📊 達 +{計畫['目標報酬_pct']:.0f}% 機率：{達標}",
                 size="sm", color=達標色, weight="bold",
                 align="center"),
            文字(f"預估 7 月後資產 NT$ "
                 f"{現['總資產_twd'] + 計畫['預估7月後報酬_twd']:,.0f}",
                 size="xxs", color=C["text_subtle"],
                 align="center"),
            文字("• 賣出按優先順序，每週分批進行",
                 size="xxs", color=C["text_subtle"], wrap=True),
            文字("• 加碼按 Kelly 權重，等待回檔再進",
                 size="xxs", color=C["text_subtle"], wrap=True),
            文字("• 黑天鵝來時用避險彈藥重押",
                 size="xxs", color=C["text_subtle"], wrap=True),
        ],
    })

    return {
        "type": "bubble", "size": "giga",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "16px",
            "contents": 內容,
        },
    }


# ─────────────────────────────────────────────
# CLI 自測
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=== Phase 20 集中模式規劃 ===\n")
    計畫 = 產生集中計畫(目標檔數=8, 目標報酬_pct=35, 時程_月=7)

    print(f"目標：{計畫['目標檔數']} 檔 / {計畫['時程_月']} 月內 "
          f"+{計畫['目標報酬_pct']}%")
    print()
    print(f"📐 現狀")
    print(f"  總資產 NT$ {計畫['現狀']['總資產_twd']:,.0f}")
    print(f"  現金 NT$ {計畫['現狀']['現金_twd']:,.0f}")
    print(f"  持股 {計畫['現狀']['持股檔數']} 檔 NT$ "
          f"{計畫['現狀']['持股市值_twd']:,.0f}")
    print()

    print(f"✅ 保留 {len(計畫['保留'])} 檔")
    print(f"{'代號':<14} {'Kelly':<7} {'現股':<6} {'加碼':<6} {'目標%':<6} "
          f"{'預估7月':<8} {'評分':<6}")
    for h in 計畫["保留"]:
        k = h["評分"].get("Kelly_pct")
        k_s = f"{k:.1f}%" if k else "n/a"
        print(f"  {h['symbol']:<12} {k_s:<7} {h['shares']:<6} "
              f"+{h['加碼股數']:<5} {h['目標佔比_pct']:>4.1f}% "
              f"+{h['預估7月報酬_pct']:>5.1f}% {h['評分']['分數']:>5.1f}")

    print()
    print(f"🪓 賣出 {len(計畫['賣出'])} 檔")
    print(f"釋出資金 NT$ {計畫['釋出資金_twd']:,.0f}")
    print(f"{'代號':<14} {'Kelly':<7} {'股數':<6} {'損益%':<7} {'市值':<10}")
    for h in 計畫["賣出"]:
        k = h["評分"].get("Kelly_pct")
        k_s = f"{k:.1f}%" if k else "n/a"
        print(f"  {h['symbol']:<12} {k_s:<7} {h['shares']:<6} "
              f"{h['未實現損益_pct']:+5.1f}% NT$ {h['市值_twd']:>9,.0f}")

    print()
    print(f"📊 預估 7 月後：NT$ "
          f"{計畫['現狀']['總資產_twd'] + 計畫['預估7月後報酬_twd']:,.0f} "
          f"({計畫['預估7月後報酬_pct']:+.1f}%)")
    print(f"   達標機率：{計畫['達標機率']}")
