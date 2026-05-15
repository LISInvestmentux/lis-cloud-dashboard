"""
策略池系統（Phase 25）— 對標 ARK 方舟「ETF 價值區」「升溫區」這種策略命名

核心理念：
  不給用戶單一明牌，而是命名 N 個策略，每個策略獨立掃全 watchlist。
  用戶看「策略 A 今日入選 X 檔」「策略 B 入選 Y 檔」，自己選擇要跟哪幾個。

預設策略池：
  ETF_深價值區     位階 < 25 + ETF       → 罕見大跌的買點
  ETF_進入價值區   位階 25-45 + ETF      → 一般回檔加碼
  ETF_升溫區       順勢分 >= 70 + ETF    → 多頭軌道內加碼
  個股_深價值      位階 < 35 + 非ETF      → 個股急跌抄底
  個股_順勢突破    順勢分 >= 70 + 非ETF   → 個股動能加碼
  Kelly_TOP10      Kelly >= 6%           → 歷史高 IRR 標的
  黑天鵝_抄底      VIX>25 或 F-G<25 + 位階<35 → 大跌 ALL IN
  DCA_本月定額     in long_term_dca       → 不看訊號照月買

每個策略獨立過濾，獨立排序，獨立部位建議。
"""
import json
from typing import Optional, Callable
from pathlib import Path


專案根 = Path(__file__).resolve().parent.parent.parent


# ─────────────────────────────────────────────
# 策略定義
# ─────────────────────────────────────────────
def _過濾_深價值ETF(r: dict, 大盤: dict, 黑天鵝: dict) -> bool:
    return (r.get("是ETF") and r.get("位階") is not None and
            r["位階"] < 25)


def _過濾_進入價值ETF(r: dict, 大盤: dict, 黑天鵝: dict) -> bool:
    return (r.get("是ETF") and r.get("位階") is not None and
            25 <= r["位階"] < 45)


def _過濾_升溫ETF(r: dict, 大盤: dict, 黑天鵝: dict) -> bool:
    return (r.get("是ETF") and r.get("型態") == "順勢" and
            (r.get("順勢分") or 0) >= 70)


def _過濾_個股深價值(r: dict, 大盤: dict, 黑天鵝: dict) -> bool:
    return (not r.get("是ETF") and r.get("位階") is not None and
            r["位階"] < 35)


def _過濾_個股突破(r: dict, 大盤: dict, 黑天鵝: dict) -> bool:
    return (not r.get("是ETF") and r.get("型態") == "順勢" and
            (r.get("順勢分") or 0) >= 70)


def _過濾_Kelly10(r: dict, 大盤: dict, 黑天鵝: dict) -> bool:
    k = r.get("Kelly_pct")
    n = r.get("交易數") or 0
    return k is not None and k >= 6.0 and n >= 10


def _過濾_黑天鵝(r: dict, 大盤: dict, 黑天鵝: dict) -> bool:
    if 黑天鵝 is None or 黑天鵝.get("命中數", 0) < 2:
        return False
    return r.get("位階") is not None and r["位階"] < 35


def _過濾_DCA(r: dict, 大盤: dict, 黑天鵝: dict) -> bool:
    return r.get("_dca_標的", False)


def _過濾_法人共識買(r: dict, 大盤: dict, 黑天鵝: dict) -> bool:
    """外資+投信同向買 = 籌碼共識（Phase 22）"""
    法人 = r.get("法人籌碼")
    if not 法人:
        return False
    外 = 法人.get("外資", 0)
    投 = 法人.get("投信", 0)
    return 外 >= 1_000_000 and 投 >= 500_000  # 外資 1000 張 + 投信 500 張


def _過濾_外資大買(r: dict, 大盤: dict, 黑天鵝: dict) -> bool:
    法人 = r.get("法人籌碼")
    if not 法人:
        return False
    return 法人.get("外資", 0) >= 2_000_000  # 外資 2000 張


def _過濾_供需驅動(r: dict, 大盤: dict, 黑天鵝: dict) -> bool:
    """Phase 31：供需邏輯（億級講師派）"""
    return r.get("_供需事件數", 0) >= 1


# 策略池總表
策略池 = {
    "ETF_深價值區": {
        "emoji": "🟢", "色彩": "bull",
        "說明": "ETF 罕見大跌，位階 <25，深度價值",
        "過濾": _過濾_深價值ETF,
        "排序": lambda r: r["位階"],  # 越低越前
        "建議": "★★★ 強烈買進，黑天鵝級買點",
    },
    "ETF_進入價值區": {
        "emoji": "✅", "色彩": "bull",
        "說明": "ETF 回檔到價值區（位階 25-45）",
        "過濾": _過濾_進入價值ETF,
        "排序": lambda r: r["位階"],
        "建議": "★★ 建議買進，分批佈局",
    },
    "ETF_升溫區": {
        "emoji": "🚀", "色彩": "bull",
        "說明": "ETF 多頭軌道內，順勢分 >=70",
        "過濾": _過濾_升溫ETF,
        "排序": lambda r: -(r.get("順勢分") or 0),
        "建議": "★ 順勢加碼（非追高，是趨勢確認）",
    },
    "個股_深價值": {
        "emoji": "💎", "色彩": "bull",
        "說明": "個股急跌進入抄底區（位階 <35）",
        "過濾": _過濾_個股深價值,
        "排序": lambda r: r["位階"],
        "建議": "★★ 個股反彈機會（高 Kelly 才買）",
    },
    "個股_順勢突破": {
        "emoji": "📈", "色彩": "wait",
        "說明": "個股動能加碼（順勢 >=70）",
        "過濾": _過濾_個股突破,
        "排序": lambda r: -(r.get("順勢分") or 0),
        "建議": "★ 注意個股風險，少量試單",
    },
    "Kelly_TOP10": {
        "emoji": "🏆", "色彩": "accent",
        "說明": "歷史回測 Kelly >=6% 且樣本 >=10",
        "過濾": _過濾_Kelly10,
        "排序": lambda r: -(r.get("Kelly_pct") or 0),
        "建議": "★★★ 數學驗證高 IRR，核心持股",
    },
    "黑天鵝_抄底": {
        "emoji": "🚨", "色彩": "bear",
        "說明": "VIX>25 或 F-G<25 + 位階<35",
        "過濾": _過濾_黑天鵝,
        "排序": lambda r: r["位階"],
        "建議": "★★★ 用避險預備金 ALL IN",
    },
    "DCA_本月定額": {
        "emoji": "📌", "色彩": "main",
        "說明": "月固定加碼，不看訊號",
        "過濾": _過濾_DCA,
        "排序": lambda r: r["symbol"],
        "建議": "✅ 自動扣款（每月 6 號）",
    },
    "法人_共識買": {
        "emoji": "🔥", "色彩": "accent",
        "說明": "外資+投信同向買 1000+/500+ 張（強訊號）",
        "過濾": _過濾_法人共識買,
        "排序": lambda r: -((r.get("法人籌碼") or {}).get("三大法人合計", 0)),
        "建議": "★★★ 籌碼共識，常為波段啟動點",
    },
    "外資_單獨大買": {
        "emoji": "📈", "色彩": "bull",
        "說明": "外資單日買超 2000+ 張",
        "過濾": _過濾_外資大買,
        "排序": lambda r: -((r.get("法人籌碼") or {}).get("外資", 0)),
        "建議": "★★ 外資看好，但投信沒同步",
    },
    "供需_事件驅動": {
        "emoji": "🎯", "色彩": "accent",
        "說明": "億級講師派：事件→產業→受惠股推導",
        "過濾": _過濾_供需驅動,
        "排序": lambda r: -(r.get("_供需事件數", 0)),
        "建議": "★★ 新聞事件直接驅動，跟講師思維對齊",
    },
}


# ─────────────────────────────────────────────
# 主入口：掃全部策略
# ─────────────────────────────────────────────
def 掃描策略池(全部標的: list[dict],
                大盤: Optional[dict] = None,
                黑天鵝: Optional[dict] = None,
                持股代號集: Optional[set] = None,
                DCA清單: Optional[list[str]] = None) -> dict:
    """
    輸入：
      全部標的 — 已含 {symbol, 名稱, 位階, 順勢分, 型態, 是ETF, Kelly_pct, 交易數, 現價}
      大盤 — {VIX, fear_greed_score}
      黑天鵝 — {命中數}
      持股代號集 — 現有持股，方便標記「加碼」vs「新進場」
      DCA清單 — long_term_dca 中的代號

    回傳：
      {
        "策略名": {
          "說明": ..., "建議": ..., "emoji": ...,
          "入選": [{symbol, name, 位階, 順勢, Kelly, 現價, 在持股}],
          "總數": N,
        }, ...
      }
    """
    持股代號集 = 持股代號集 or set()
    DCA清單 = DCA清單 or []

    # 標記 DCA
    for r in 全部標的:
        r["_dca_標的"] = r["symbol"] in DCA清單

    結果 = {}
    for 策略名, 設定 in 策略池.items():
        過濾 = 設定["過濾"]
        入選 = []
        for r in 全部標的:
            try:
                if 過濾(r, 大盤, 黑天鵝):
                    rec = dict(r)
                    rec["在持股"] = r["symbol"] in 持股代號集
                    入選.append(rec)
            except Exception:
                continue

        # 排序
        try:
            入選.sort(key=設定["排序"])
        except Exception:
            pass

        結果[策略名] = {
            "策略名": 策略名,
            "emoji": 設定["emoji"],
            "色彩": 設定["色彩"],
            "說明": 設定["說明"],
            "建議": 設定["建議"],
            "入選": 入選,
            "總數": len(入選),
        }

    return 結果


# ─────────────────────────────────────────────
# 從 positional_state + win_rate_db 組裝標的清單
# ─────────────────────────────────────────────
def 組裝標的清單(取得現價: Optional[Callable] = None,
                  含法人籌碼: bool = True) -> list[dict]:
    """從現有資料源組合成 strategy_pool 能吃的格式（Phase 22 含法人籌碼）"""
    state_path = 專案根 / "數據" / "positional_state.json"
    db_path = 專案根 / "數據" / "win_rate_db.json"

    # Phase 22: 載入法人籌碼
    法人表 = {}
    if 含法人籌碼:
        try:
            from . import institutional_tracker as it
            from datetime import datetime
            r = it.抓今日法人籌碼(datetime.now().strftime("%Y%m%d"))
            if not r.get("資料"):
                from datetime import timedelta
                昨 = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
                r = it.抓今日法人籌碼(昨)
            for sym_純, d in r.get("資料", {}).items():
                # TWSE 用純代號，補 .TW
                法人表[sym_純 + ".TW"] = d
                法人表[sym_純] = d
        except Exception as e:
            print(f"法人籌碼載入失敗：{e}")

    state = json.loads(state_path.read_text(encoding="utf-8"))
    scores = state["scores"]
    details = state.get("details", {})

    db = json.loads(db_path.read_text(encoding="utf-8"))
    db_標的 = db.get("標的", {})

    # 抓 watchlist 補名稱
    wl_path = 專案根 / "API" / "watchlist.json"
    wl = json.loads(wl_path.read_text(encoding="utf-8"))
    name_map = {}
    for r in wl.get("regions", []):
        for s in r.get("stocks", []):
            name_map[s["symbol"]] = s.get("name", "")

    全部 = []
    for sym, 位階 in scores.items():
        if sym.startswith("^"):
            continue  # 排除指數
        d = details.get(sym, {})
        db_r = db_標的.get(sym, {})
        統計 = db_r.get("統計", {}) if "error" not in db_r else {}

        現價 = None
        if 取得現價:
            try:
                現價 = 取得現價(sym)
            except Exception:
                pass

        全部.append({
            "symbol": sym,
            "name": name_map.get(sym, db_r.get("name", "")),
            "位階": 位階,
            "順勢分": d.get("順勢分"),
            "型態": d.get("型態"),
            "是ETF": d.get("是ETF", False),
            "Kelly_pct": 統計.get("Kelly_pct"),
            "勝率": 統計.get("勝率"),
            "交易數": 統計.get("交易數"),
            "現價": 現價,
            "法人籌碼": 法人表.get(sym),  # Phase 22
        })

    return 全部


# ─────────────────────────────────────────────
# Flex 卡建構（策略池 Carousel）
# ─────────────────────────────────────────────
def 建構策略池Carousel(策略結果: dict, 現金: float = 0,
                        最多策略: int = 6,
                        每策略最多標的: int = 6) -> Optional[dict]:
    """
    回傳 carousel — 每個策略一張 bubble。
    """
    from . import flex_builder
    文字 = flex_builder.文字
    分隔線 = flex_builder.分隔線
    C = flex_builder.C

    色映射 = {
        "bull": C["bull"], "bear": C["bear"],
        "wait": C["wait"], "main": C["text_main"],
        "accent": C["accent"],
    }

    cards = []

    # 篩選有入選的策略
    有效策略 = [(名, 設) for 名, 設 in 策略結果.items()
                if 設["總數"] > 0]
    if not 有效策略:
        return None

    # 按入選數排序，前 N 個出卡
    有效策略.sort(key=lambda x: -x[1]["總數"])
    有效策略 = 有效策略[:最多策略]

    for 策略名, 設 in 有效策略:
        色 = 色映射.get(設["色彩"], C["text_main"])
        內容 = []

        # Header
        內容.append({
            "type": "box", "layout": "vertical", "spacing": "xs",
            "contents": [
                文字(f"{設['emoji']} {策略名}",
                     size="lg", color=色, weight="bold"),
                文字(設["說明"], size="xs", color=C["text_dim"],
                     wrap=True),
            ],
        })
        內容.append(分隔線())

        # 入選數
        內容.append({
            "type": "box", "layout": "horizontal",
            "contents": [
                文字("今日入選", size="sm", color=C["text_dim"], flex=3),
                文字(f"{設['總數']} 檔", size="lg", color=色,
                     weight="bold", align="end", flex=2),
            ],
        })
        內容.append(分隔線())

        # 入選清單
        for r in 設["入選"][:每策略最多標的]:
            標記 = "🔄" if r.get("在持股") else "🆕"
            位 = r.get("位階")
            順 = r.get("順勢分")
            k = r.get("Kelly_pct")
            底 = (f"位 {位:.0f}" if 位 is not None else "")
            if 順:
                底 += f" 順 {順:.0f}"
            if k:
                底 += f" K {k:.1f}%"

            內容.append({
                "type": "box", "layout": "vertical", "spacing": "xs",
                "paddingTop": "xs",
                "contents": [
                    {
                        "type": "box", "layout": "horizontal",
                        "contents": [
                            文字(f"{標記} {r['symbol']}", size="sm",
                                 color=C["text_main"], weight="bold",
                                 flex=4),
                            文字(底, size="xxs",
                                 color=色, align="end", flex=5),
                        ],
                    },
                    {
                        "type": "box", "layout": "horizontal",
                        "contents": [
                            文字(r.get("name", "")[:14], size="xxs",
                                 color=C["text_subtle"], flex=4),
                            文字(f"{r['現價']:.2f}" if r.get("現價") else "",
                                 size="xxs", color=C["text_dim"],
                                 align="end", flex=3),
                        ],
                    },
                ],
            })

        if 設["總數"] > 每策略最多標的:
            內容.append(文字(f"... 還有 {設['總數'] - 每策略最多標的} 檔",
                             size="xxs", color=C["text_subtle"]))

        內容.append(分隔線())
        內容.append(文字(設["建議"], size="xxs", color=色, wrap=True))

        cards.append({
            "type": "bubble", "size": "kilo",
            "body": {
                "type": "box", "layout": "vertical", "spacing": "sm",
                "backgroundColor": C["bg_dark"],
                "paddingAll": "12px",
                "contents": 內容,
            },
        })

    if not cards:
        return None

    return {"type": "carousel", "contents": cards}


# ─────────────────────────────────────────────
# CLI 自測
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=== Phase 25 策略池系統測試 ===\n")
    全部 = 組裝標的清單()
    print(f"組裝到 {len(全部)} 檔標的（含分數+順勢+Kelly）\n")

    結果 = 掃描策略池(全部, 大盤={"VIX": None, "fear_greed_score": None},
                        黑天鵝=None,
                        DCA清單=["0050.TW", "00646.TW"])

    for 名, 設 in 結果.items():
        print(f"\n{設['emoji']} {名}（{設['總數']} 檔）")
        print(f"  {設['說明']}")
        for r in 設["入選"][:8]:
            位 = r.get("位階")
            順 = r.get("順勢分")
            k = r.get("Kelly_pct")
            print(f"    {r['symbol']:<14} {r.get('name','')[:14]:<14} "
                  f"位 {位:.0f}" if 位 is not None else "位 -",
                  f"順 {順:.0f}" if 順 else "",
                  f"K {k:.1f}%" if k else "")
