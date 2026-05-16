"""
美股晚場推播（Phase 35）

時段：
  22:00 — 美股開盤前準備（台灣時間）
    內容：美股持股 + 大盤指標（QQQ/VOO/SMH/VIX）+ 隔夜新聞情緒
  04:00 — 美股收盤後總結
    內容：美股持股當日損益 + 預測明日台股傳導

排程：
  Windows Task Scheduler：
    LIS_美股_22:00  每天 22:00
    LIS_美股_04:00  每天 04:00
"""
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))
from dotenv import load_dotenv
load_dotenv(專案根.parent / "API" / ".env")

from modules import (capital_planner, line_push, flex_builder,
                     technical, forex, tw_us_correlation,
                     news_sentiment, fundamentals_engine,
                     us_action_card)

C = flex_builder.C
文字 = flex_builder.文字
分隔線 = flex_builder.分隔線


def 卡_美股持股() -> dict:
    """美股持股當前狀況"""
    cfg = capital_planner.載入資金設定()
    美股清單 = [
        p for p in cfg.get("current_positions", [])
        if not (p["symbol"].endswith(".TW") or
                p["symbol"].endswith(".TWO"))
        and p.get("symbol") != "AGGREGATE"
    ]

    匯率 = forex.取得USD_TWD匯率(
        fallback=cfg.get("currency_rates", {}).get("USD_TWD", 32.0))["rate"]

    持股詳細 = []
    總成本_usd = 0
    總市值_usd = 0
    for p in 美股清單:
        sym = p["symbol"]
        try:
            歷史, _ = technical.取得每日股價(sym, period="2d")
            if not 歷史:
                continue
            現價 = 歷史[0]["close"]
            昨收 = 歷史[1]["close"] if len(歷史) > 1 else 現價
            當日 = (現價 / 昨收 - 1) * 100
            成本 = p.get("avg_cost", 0)
            股數 = p.get("shares", 0)
            漲幅 = (現價 / 成本 - 1) * 100 if 成本 > 0 else 0
            市值_usd = 現價 * 股數
            總成本_usd += 成本 * 股數
            總市值_usd += 市值_usd
            持股詳細.append({
                "symbol": sym, "name": p.get("name", ""),
                "shares": 股數, "現價": 現價,
                "成本": 成本, "漲幅": 漲幅,
                "當日": 當日, "市值_usd": 市值_usd,
            })
        except Exception:
            continue

    持股詳細.sort(key=lambda r: -r["市值_usd"])

    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("🌙 美股持股", size="lg",
                 color=C["text_main"], weight="bold"),
            文字(f"{datetime.now():%m/%d %H:%M} · "
                 f"匯率 {匯率:.2f}",
                 size="xxs", color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())

    if 總成本_usd > 0:
        總損益 = 總市值_usd - 總成本_usd
        總損益率 = 總損益 / 總成本_usd * 100
        內容.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字("總市值", size="xs", color=C["text_dim"], flex=2),
                文字(f"${總市值_usd:,.2f}", size="md",
                     color=C["accent"], weight="bold", align="end", flex=4),
            ],
        })
        內容.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字("損益", size="xs", color=C["text_dim"], flex=2),
                文字(f"{總損益:+,.2f} ({總損益率:+.2f}%)",
                     size="sm",
                     color=C["bull"] if 總損益 >= 0 else C["bear"],
                     weight="bold", align="end", flex=4),
            ],
        })
        內容.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字("≈ TWD", size="xxs", color=C["text_dim"], flex=2),
                文字(f"NT$ {總市值_usd * 匯率:,.0f}",
                     size="xs", color=C["text_dim"], align="end", flex=4),
            ],
        })
    內容.append(分隔線())

    for h in 持股詳細[:8]:
        色 = C["bull"] if h["漲幅"] >= 0 else C["bear"]
        當日色 = C["bull"] if h["當日"] >= 0 else C["bear"]
        內容.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字(h["symbol"][:6], size="sm",
                     color=C["text_main"], weight="bold", flex=3),
                文字(f"{h['當日']:+.2f}%", size="xs",
                     color=當日色, align="center", flex=2),
                文字(f"{h['漲幅']:+.2f}%", size="sm",
                     color=色, align="end", weight="bold", flex=3),
            ],
        })

    return _bubble(內容)


def 卡_美股大盤() -> dict:
    """美股大盤 + VIX + 主要 ETF"""
    指標 = ["^GSPC", "^IXIC", "^DJI", "^VIX", "QQQ", "SMH", "VOO"]
    結果 = []
    for sym in 指標:
        try:
            歷史, _ = technical.取得每日股價(sym, period="3d")
            if not 歷史 or len(歷史) < 2:
                continue
            現價 = 歷史[0]["close"]
            昨 = 歷史[1]["close"]
            漲幅 = (現價 / 昨 - 1) * 100
            結果.append({
                "symbol": sym, "現價": 現價, "漲幅": 漲幅,
            })
        except Exception:
            continue

    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("📊 美股大盤", size="lg",
                 color=C["text_main"], weight="bold"),
            文字("S&P / NASDAQ / 道瓊 / VIX / ETF",
                 size="xxs", color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())

    name_map = {
        "^GSPC": "S&P 500", "^IXIC": "NASDAQ", "^DJI": "道瓊",
        "^VIX": "VIX 恐慌", "QQQ": "QQQ", "SMH": "費半 ETF",
        "VOO": "VOO",
    }
    for r in 結果:
        色 = (C["bear"] if (r["symbol"] == "^VIX" and r["現價"] > 25)
              else C["bull"] if r["漲幅"] >= 0 else C["bear"])
        內容.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字(name_map.get(r["symbol"], r["symbol"]),
                     size="sm", color=C["text_main"], flex=3),
                文字(f"{r['現價']:,.2f}", size="xs",
                     color=C["text_main"], align="center", flex=3),
                文字(f"{r['漲幅']:+.2f}%", size="sm",
                     color=色, align="end", weight="bold", flex=2),
            ],
        })

    return _bubble(內容)


def 卡_AI巨頭() -> dict:
    """AI 龍頭股 NVDA / AVGO / MU / META 等"""
    AI股 = ["NVDA", "AVGO", "MU", "META", "GOOGL", "TSM", "AMD", "INTC"]
    結果 = []
    for sym in AI股:
        try:
            歷史, _ = technical.取得每日股價(sym, period="3d")
            if not 歷史 or len(歷史) < 2:
                continue
            現價 = 歷史[0]["close"]
            昨 = 歷史[1]["close"]
            漲幅 = (現價 / 昨 - 1) * 100
            結果.append({
                "symbol": sym, "現價": 現價, "漲幅": 漲幅,
            })
        except Exception:
            continue

    結果.sort(key=lambda r: -r["漲幅"])

    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("🚀 AI 龍頭", size="lg",
                 color=C["text_main"], weight="bold"),
            文字("台股傳導關鍵", size="xxs", color=C["text_dim"]),
        ],
    })
    內容.append(分隔線())

    for r in 結果:
        色 = C["bull"] if r["漲幅"] >= 0 else C["bear"]
        內容.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字(r["symbol"], size="sm",
                     color=C["text_main"], weight="bold", flex=3),
                文字(f"${r['現價']:,.2f}", size="xs",
                     color=C["text_main"], align="center", flex=3),
                文字(f"{r['漲幅']:+.2f}%", size="sm",
                     color=色, align="end", weight="bold", flex=2),
            ],
        })

    return _bubble(內容)


def 卡_台股傳導預測() -> dict:
    """台美連動 → 預測明日台股"""
    r = tw_us_correlation.台股傳導預測()

    內容 = []
    內容.append({
        "type": "box", "layout": "vertical", "spacing": "xs",
        "contents": [
            文字("🌐 明日台股傳導", size="lg",
                 color=C["text_main"], weight="bold"),
            文字(r["整體傾向"][:40], size="xxs",
                 color=C["text_dim"], wrap=True),
        ],
    })
    內容.append(分隔線())
    內容.append({
        "type": "box", "layout": "horizontal",
        "contents": [
            文字("美股平均", size="xs", color=C["text_dim"], flex=2),
            文字(f"{r['平均漲幅_pct']:+.2f}%", size="md",
                 color=C["bull"] if r['平均漲幅_pct'] >= 0 else C["bear"],
                 weight="bold", align="end", flex=3),
        ],
    })
    內容.append(分隔線())
    if r.get("最強上漲"):
        內容.append(文字(f"🔥 受惠台股（{r['最強上漲']} 帶動）",
                         size="xs", color=C["bull"], weight="bold"))
        for ts in r["傳導預測"][r['最強上漲']]["影響的台股"][:5]:
            內容.append(文字(f"  {ts['symbol']} {ts['name']}",
                             size="xxs", color=C["text_dim"], wrap=True))
    if r.get("最強下跌"):
        內容.append(分隔線())
        內容.append(文字(f"⚠️ 警告台股（{r['最強下跌']} 拖累）",
                         size="xs", color=C["bear"], weight="bold"))
        for ts in r["傳導預測"][r['最強下跌']]["影響的台股"][:3]:
            內容.append(文字(f"  {ts['symbol']} {ts['name']}",
                             size="xxs", color=C["text_dim"], wrap=True))
    return _bubble(內容)


def _bubble(內容):
    return {
        "type": "bubble", "size": "kilo",
        "body": {
            "type": "box", "layout": "vertical", "spacing": "sm",
            "backgroundColor": C["bg_dark"],
            "paddingAll": "12px",
            "contents": 內容,
        },
    }


def 主流程():
    開始 = datetime.now()
    時段 = ("🌙 開盤前" if 開始.hour < 4 or 開始.hour >= 21
              else "📊 收盤後")
    print(f"=== Phase 35 美股晚場 {時段} [{開始:%m/%d %H:%M}] ===")

    cards = []
    # Phase 33.2 — 第 0 張：今夜美股行動（最重要，最先看到）
    print("[0/5] 🌙 今夜美股行動（必看）...")
    try:
        行動 = us_action_card.組今夜行動()
        cards.append(us_action_card.建構Flex卡(行動))
    except Exception as e:
        print(f"     ⚠️ 行動卡失敗：{e}（跳過繼續）")

    print("[1/5] 美股持股...")
    cards.append(卡_美股持股())
    print("[2/5] 美股大盤...")
    cards.append(卡_美股大盤())
    print("[3/5] AI 龍頭...")
    cards.append(卡_AI巨頭())
    print("[4/5] 台股傳導...")
    cards.append(卡_台股傳導預測())

    carousel = {"type": "carousel", "contents": cards}
    alt = f"🌙 美股晚場 {時段} {開始:%H:%M}"
    line_push.推播Flex訊息(替代文字=alt, flex內容=carousel)
    print(f"✅ 已推 LINE：{alt}")

    try:
        import sync_to_gist
        if sync_to_gist.自動同步(silent=True):
            print("☁️ Gist 已同步")
    except Exception:
        pass


if __name__ == "__main__":
    主流程()
