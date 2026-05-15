"""
今日決策整合（Phase 11）
把所有訊號（真倉警示、HOLD 減碼、黑天鵝、全市場、AI 解釋）
整合成「**一張卡看完今天怎麼做**」。

輸出 3 類：
  🟢 建議買（含明確金額/股數）
  🔴 建議賣（含明確股數）
  ⚪ 待觀察

加碼模式：依 Enjoy + 黑天鵝判定是「平時」「衝刺」「黑天鵝 ALL IN」。
"""
from typing import Optional


def 整合今日決策(指數: Optional[dict] = None,
                  規劃: Optional[dict] = None,
                  真倉: Optional[dict] = None,
                  減碼: Optional[dict] = None,
                  黑天鵝: Optional[dict] = None,
                  全市場: Optional[dict] = None,
                  fire: Optional[dict] = None,
                  位階: Optional[dict] = None,
                  總資產_twd: float = 400000,
                  USD_TWD: float = 31.5,
                  集中模式: str = "balanced",
                  single_focus_symbols: Optional[list[str]] = None) -> dict:
    """
    回傳：
    {
      "加碼模式": "平時" / "衝刺" / "黑天鵝 ALL IN",
      "火力_pct": 10/30/70/80/90,
      "建議買": [{symbol, name, 金額, 股數, 原因, 出場條件}],
      "建議賣": [{symbol, name, 股數, 原因, 落袋}],
      "觀察": [{symbol, name, 原因}],
      "今日總結": str,
    }
    """
    enjoy = 指數.get("總分", 50) if 指數 else 50
    主動操作 = 指數.get("主動操作", "NEUTRAL") if 指數 else "NEUTRAL"
    黑天鵝清單 = 黑天鵝.get("黑天鵝清單", []) if 黑天鵝 else []
    市場恐慌等級 = 黑天鵝.get("市場恐慌等級", 0) if 黑天鵝 else 0

    # ───── 加碼模式判定 ─────
    if 市場恐慌等級 >= 2 and 黑天鵝清單:
        加碼模式 = "🌟 黑天鵝 ALL IN"
        火力 = 90
        建議火力說明 = "5 條件達 4+，這是錯殺機會，敢押的時候"
    elif enjoy >= 70:
        加碼模式 = "🚀 衝刺加碼"
        火力 = 規劃.get("火力比例", 80) if 規劃 else 80
        建議火力說明 = "市場恐慌、機會浮現，加碼日"
    elif enjoy >= 40:
        加碼模式 = "⚖️ 平時紀律"
        火力 = 規劃.get("火力比例", 30) if 規劃 else 30
        建議火力說明 = "情緒平衡，依紀律操作"
    else:
        加碼模式 = "🛑 過熱觀望"
        火力 = 規劃.get("火力比例", 10) if 規劃 else 10
        建議火力說明 = "市場過熱，主動減碼為主"

    建議買 = []
    建議賣 = []
    觀察 = []

    # ───── 建議賣（最高優先：守紀律）─────
    if 真倉 and 真倉.get("警示"):
        警示 = 真倉["警示"]
        # 破停損（最緊急）
        for r in 警示.get("破停損", []):
            建議賣.append({
                "symbol": r["symbol"],
                "name": r.get("name", ""),
                "股數": r["shares"],
                "原因": f"破 -5% 停損（{r['pnl_pct']:.2f}%）",
                "落袋_twd": r.get("market_value_twd", 0),
                "急": True,
            })
        # 達停利（D 策略 - 賣 50%）
        for r in 警示.get("達停利", []):
            D股數 = int(r["shares"] * 0.5)
            建議賣.append({
                "symbol": r["symbol"],
                "name": r.get("name", ""),
                "股數": D股數,
                "原因": f"達 +15% 停利（{r['pnl_pct']:.2f}%）→ D 策略賣 50%",
                "落袋_twd": (r.get("current_price", 0) * D股數
                               * (32 if r.get("is_us") else 1)),
                "急": False,
            })

    # ───── HOLD 減碼建議 ─────
    if 減碼 and 減碼.get("可執行"):
        for r in 減碼.get("減碼建議", []):
            if r.get("not_in_watchlist"):
                continue
            # 避免跟達停利重複
            if any(s["symbol"] == r["symbol"] for s in 建議賣):
                continue
            建議賣.append({
                "symbol": r["symbol"],
                "name": r.get("name", ""),
                "股數": r.get("建議減股數", 0),
                "原因": f"市場過熱 → {r.get('標籤', '減碼')}（漲 {r['pnl_pct']:.1f}%）",
                "落袋_twd": r.get("估入袋_twd", 0),
                "急": False,
            })

    # ───── Phase 13：每日加碼計算機（仿 ARK 邏輯）─────
    try:
        try:
            from . import daily_buyer
        except ImportError:
            import daily_buyer
        加碼 = daily_buyer.計算每日加碼(
            位階=位階, 黑天鵝=黑天鵝,
            總資產_twd=總資產_twd,
            加碼模式=加碼模式,
            USD_TWD=USD_TWD,
            集中模式=集中模式,
            single_focus_symbols=single_focus_symbols,
        )
        # Phase 33.2 — 雙軌制：位階 vs 風控 取小者
        try:
            try:
                from . import dual_track_sizing
            except ImportError:
                import dual_track_sizing
            有雙軌 = True
        except Exception:
            有雙軌 = False

        # 持股 dict（給雙軌算「已持市值」）
        持股dict = {p["symbol"]: p for p in (真倉.get("持股", []) if 真倉 else [])
                    if not p.get("error")}

        for c in 加碼.get("建議清單", []):
            雙軌結果 = None
            最終股數 = c.get("建議股數", 0)
            最終金額 = c.get("金額_twd", 0)
            雙軌備註 = ""

            if 有雙軌:
                sym = c["symbol"]
                現價 = c.get("現價") or 0
                幣別 = c.get("幣別", "TWD")
                現價_twd = 現價 * USD_TWD if 幣別 == "USD" else 現價
                已持_twd = 持股dict.get(sym, {}).get("market_value_twd", 0) or 0
                位階_d = (位階.get(sym, {}) if 位階 else {})
                位階分 = 位階_d.get("分數", 50) or 50
                順勢分 = 位階_d.get("順勢分", 0) or 0
                是ETF = sym.endswith("L.TW") or sym.startswith("00") or sym in ("0050.TW",)

                雙軌結果 = dual_track_sizing.雙軌計算(
                    symbol=sym, 位階分數=位階分, 順勢分=順勢分, 是ETF=是ETF,
                    現價_twd=現價_twd, 已持市值_twd=已持_twd,
                    總資產_twd=總資產_twd,
                    可動用彈藥_twd=加碼.get("彈藥_twd", 0))
                # 取雙軌建議與系統建議的較小者（避免雙軌反而放大）
                if 雙軌結果["最終股數"] > 0 and 雙軌結果["最終股數"] < 最終股數:
                    最終股數 = 雙軌結果["最終股數"]
                    最終金額 = 雙軌結果["最終金額_twd"]
                    雙軌備註 = f" [雙軌-{雙軌結果['決定軸']}軸]"

            # Phase 36.6 — Q5 Sylvie 非對稱權重
            try:
                try:
                    from . import sylvie_priority
                except ImportError:
                    import sylvie_priority
                權 = sylvie_priority.非對稱權重決策(c["symbol"])
                倍率 = 權.get("加碼倍率", 1.0)
                if 倍率 == 0:
                    最終股數 = 0
                    雙軌備註 += f" [{權['情境']} 攔截]"
                elif 倍率 > 1:
                    最終股數 = int(最終股數 * 倍率)
                    最終金額 = int(最終金額 * 倍率)
                    雙軌備註 += f" [{權['情境']} ×{倍率}]"
                c["sylvie_weight"] = 權
            except Exception:
                pass

            建議買.append({
                "symbol": c["symbol"],
                "name": c.get("name", ""),
                "金額_twd": 最終金額,
                "股數估算": 最終股數,
                "現價": c.get("現價"),
                "幣別": c.get("幣別", "TWD"),
                "幣號": c.get("幣號", "NT$"),
                "原因": f"{c.get('來源', '')} · 位階 {c.get('位階分數', '?')}{雙軌備註}",
                "出場條件": "達 +15% 賣 50% / -5% 全停損",
                "急": (c.get("來源") == "黑天鵝錯殺"),
                "雙軌": 雙軌結果,
            })
        彈藥資訊 = {
            "彈藥_twd": 加碼.get("彈藥_twd", 0),
            "比例_pct": 加碼.get("比例_pct", 0),
            "說明": 加碼.get("說明", ""),
        }
    except Exception as e:
        print(f"  ⚠️ 加碼計算失敗：{e}")
        彈藥資訊 = {"彈藥_twd": 0, "比例_pct": 0, "說明": ""}

    # 全市場發現（不直接買，放觀察）
    if 加碼模式 in ("🌟 黑天鵝 ALL IN", "🚀 衝刺加碼") and 全市場:
        for r in 全市場.get("Top", [])[:3]:
            if any(b["symbol"] == r["symbol"] for b in 建議買):
                continue
            觀察.append({
                "symbol": r["symbol"],
                "name": r.get("name", ""),
                "原因": f"系統挖到 {r.get('分數', 0)} 分 - "
                          + "、".join(r.get("條件", [])[:2]),
                "建議": "加入 watchlist 觀察 1 週再進",
            })

    # ───── 今日總結 ─────
    買數 = len(建議買)
    賣數 = len(建議賣)
    觀數 = len(觀察)

    if 買數 == 0 and 賣數 == 0:
        總結 = f"{加碼模式}：今日無明確進出訊號，續抱觀望"
    elif 賣數 > 買數:
        總結 = f"{加碼模式}：建議賣 {賣數} 檔（落袋為主，市場過熱）"
    elif 買數 > 賣數:
        總結 = f"{加碼模式}：建議買 {買數} 檔（錯殺機會，敢押）"
    else:
        總結 = f"{加碼模式}：買賣各 {買數}/{賣數} 檔（再平衡日）"

    return {
        "加碼模式": 加碼模式,
        "火力_pct": 火力,
        "火力說明": 建議火力說明,
        "建議買": 建議買,
        "建議賣": 建議賣,
        "觀察": 觀察,
        "今日總結": 總結,
        "彈藥": 彈藥資訊,
    }
