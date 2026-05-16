"""
自動輪動推薦引擎（Phase 46 — 5/16）

賣出觸發時自動算「現在最該買的 Top 3」

對應另一個 AI 提的「出場後資金再投入效率」缺口

工作流程:
  1. user 賣 SATL 拿到 NT$ 5,900
  2. 引擎掃 watchlist 所有「非現有持股」標的
  3. 對每檔算進場勝率分數（Phase 45）
  4. 用 conviction + Kelly 算建議部位
  5. 排出 Top 3 推薦

整合既有模組:
  - entry_signal_scorer (Phase 45) — 進場勝率
  - conviction (Phase 40)             — 信念分
  - kelly (Phase 42)                  — 部位大小
  - oversold_filter (Phase 43)        — 錯殺加分
  - earnings_surprise (Phase 44)      — 驚喜加分（選用）
"""
import json
from pathlib import Path
from typing import Optional

專案根 = Path(__file__).resolve().parent.parent.parent


def 算輪動候選(可動資金_twd: float,
                cfg: dict,
                掃描結果: Optional[dict] = None,
                USD_TWD: float = 32.0,
                top_n: int = 5,
                抓驚喜: bool = False) -> dict:
    """
    給定可動資金 + watchlist 掃描結果 → 推薦 Top N 標的

    Args:
        可動資金_twd: 賣出後的可投入金額（NT$）
        cfg: portfolio.json（含 current_positions, swing_stocks, conviction_overrides 等）
        掃描結果: technical.掃描全部() 結果（含 regions.us/tw_stocks/tw_etfs.items）
        USD_TWD: 匯率
        top_n: 取前幾名
        抓驚喜: 是否同時跑 earnings_surprise（會慢，預設關）

    Returns:
        {
            "可動資金_twd": 5900,
            "候選": [
                {symbol, name, 分數, 等級, 建議股數, 建議金額_twd, 明細, ...},
                ...
            ],
            "推薦組合": "全押 X 股 Y / 平均分配 X 股 Y + X 股 Z",
        }
    """
    try:
        from . import entry_signal_scorer, conviction as _conv, kelly, bottom_detector
    except ImportError:
        import entry_signal_scorer, conviction as _conv, kelly, bottom_detector

    # 取黑天鵝命中
    try:
        sop = bottom_detector.即時底部判定()
        黑天鵝命中 = sop.get("命中數", 0)
    except Exception:
        黑天鵝命中 = 0

    # 取現有持股 set
    現有 = {p["symbol"] for p in cfg.get("current_positions", []) or []}

    # 從掃描結果拿 watchlist 標的（排除現有持股）
    候選symbols = []
    技術map = {}
    name_map = {}

    if 掃描結果:
        regions = 掃描結果.get("regions", {})
        for region_id, region_data in regions.items():
            items = region_data.get("items", []) if isinstance(region_data, dict) else []
            for item in items:
                sym = item.get("symbol", "")
                if not sym or sym in 現有 or item.get("error"):
                    continue
                候選symbols.append(sym)
                技術map[sym] = item
                name_map[sym] = item.get("name", "")[:10]

    if not 候選symbols:
        return {
            "可動資金_twd": 可動資金_twd,
            "候選": [],
            "推薦組合": "（掃描結果為空，無法輪動推薦）",
        }

    # 排序候選 — 用 Phase 45
    勝率排行 = entry_signal_scorer.排序候選清單(
        symbols=候選symbols,
        黑天鵝命中=黑天鵝命中,
        技術資料map=技術map,
        top_n=top_n * 2,  # 取多一點之後篩
        抓驚喜=抓驚喜,
    )

    # 對 top_n 算 Kelly 建議部位
    候選詳細 = []
    for r in 勝率排行[:top_n]:
        sym = r["symbol"]
        tech = 技術map.get(sym, {})
        is_us = not (sym.endswith(".TW") or sym.endswith(".TWO"))
        current_price = tech.get("close") or tech.get("current_price") or 0
        if current_price <= 0:
            continue

        # 用持股的 conviction 設定（沒持股就用預設 classify）
        位置假pos = {"symbol": sym}
        conv = _conv.取得信念分數(sym, cfg, 位置假pos)

        # Kelly 建議股數
        kelly_result = kelly.建議股數(
            總可動用_twd=可動資金_twd,
            conviction=conv,
            現價=current_price,
            is_us=is_us,
            USD_TWD=USD_TWD,
            最小股數=1,
        )

        候選詳細.append({
            "symbol": sym,
            "name": name_map.get(sym, ""),
            "is_us": is_us,
            "current_price": current_price,
            "分數": r["分數"],
            "等級": r["等級"],
            "明細": r["明細"],
            "conviction": conv,
            "kelly_pct": kelly_result["kelly_pct"],
            "建議股數": kelly_result["建議股數"],
            "建議金額_twd": kelly_result["建議金額_twd"],
            "建議金額_usd": kelly_result.get("建議金額_usd"),
        })

    # 推薦組合
    if 候選詳細:
        top1 = 候選詳細[0]
        if top1["建議金額_twd"] <= 可動資金_twd:
            推薦組合 = (f"🥇 全押 {top1['symbol']} ({top1['等級']}) — "
                       f"{top1['建議股數']} 股 ≈ NT$ {top1['建議金額_twd']:,.0f}")
        else:
            推薦組合 = "資金不足以買 Top 1 建議股數"
    else:
        推薦組合 = "（無高分候選）"

    return {
        "可動資金_twd": 可動資金_twd,
        "黑天鵝命中": 黑天鵝命中,
        "候選": 候選詳細,
        "推薦組合": 推薦組合,
    }


def 賣出觸發輪動建議(賣出info: dict, cfg: dict,
                       掃描結果: Optional[dict] = None,
                       USD_TWD: float = 32.0) -> dict:
    """
    user 賣出觸發時呼叫，自動給輪動建議

    Args:
        賣出info: {symbol, shares, price, is_us, 預估落袋_twd}
        cfg: portfolio.json
        掃描結果: technical 掃描全部

    Returns:
        包含「可動資金 + Top 3 候選 + 推薦組合」
    """
    可動 = 賣出info.get("預估落袋_twd", 0)
    return 算輪動候選(可動, cfg, 掃描結果, USD_TWD, top_n=3)


# CLI 測試
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=" * 60)
    print("自動輪動推薦測試")
    print("=" * 60)
    print("情境：user 賣 SATL 19 股 → 拿到 NT$ 5,900 → 推薦下一站")
    print()

    # 載入 cfg
    cfg_path = 專案根 / "API" / "portfolio.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    # 試一個簡單情境：可動 NT$ 5,900
    r = 算輪動候選(
        可動資金_twd=5900,
        cfg=cfg,
        掃描結果=None,  # 沒掃描資料 → 候選會是空
        USD_TWD=32.0,
        top_n=3,
    )
    print(f"可動資金: NT$ {r['可動資金_twd']:,.0f}")
    print(f"黑天鵝命中: {r.get('黑天鵝命中', 0)}/5")
    print(f"推薦組合: {r['推薦組合']}")
    print()
    print("⚠️ 因為沒給掃描結果，候選為空")
    print("   實際整合到 daily_5cards 時會傳入即時掃描資料")
    print()
    print("Phase 46 module 可用 ✓")
