"""
L.I.S 投資系統 — 主程式 Phase 2.5
每天早上 8:00 由 Windows 工作排程器執行此檔。

Phase 2.5 變更：
- LINE 推播改為 Flex Message（卡片風格，方舟視覺）
- 新增資金規劃模組（依資金水位算建議部位 / 股數）
- 新增震盪低點偵測（在區域卡裡標記 + 建議股數）
- 新聞摘要也用獨立卡片呈現
"""
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))

from dotenv import load_dotenv
load_dotenv(專案根.parent / "API" / ".env")
LIFF_URL = os.getenv("LIFF_URL", "")

from modules import (fear_greed, technical, news_ai,
                     enjoy_index, capital_planner,
                     flex_builder, line_push,
                     chart_generator, image_uploader,
                     kol_aggregator, relative_strength,
                     fire_calculator, risk_dashboard,
                     tw_announcements, portfolio_tracker,
                     ai_explainer, portfolio_health,
                     industry_heatmap, forex, black_swan,
                     daily_decision, us_market_analyzer,
                     dca_planner, positional_signal,
                     signal_tracker, ark_dashboard)


數據根 = 專案根.parent / "數據"
日誌根 = 數據根 / "logs"
每日資料夾 = 數據根 / "daily"
每日資料夾.mkdir(parents=True, exist_ok=True)
日誌根.mkdir(parents=True, exist_ok=True)


def _合併個股(掃描結果: dict) -> list[dict]:
    全部 = []
    for 區id, 區 in 掃描結果["regions"].items():
        for r in 區["items"]:
            r2 = dict(r)
            r2["_region"] = 區id
            全部.append(r2)
    return 全部


def 主流程() -> int:
    今日字串 = datetime.now().strftime("%Y-%m-%d")
    開始 = datetime.now()
    print(f"=== L.I.S Phase 2.5 每日報表 [{開始:%Y-%m-%d %H:%M:%S}] ===")

    # 1. 情緒
    print("[1/5] CNN Fear & Greed...")
    情緒 = fear_greed.取得恐慌貪婪指數()
    print(f"     score={情緒['score']} ({情緒['label_zh']})")

    # 2. 技術面
    print("[2/5] 掃描全部觀察清單...")
    掃描結果 = technical.掃描全部觀察清單()
    print(f"     指數 {len(掃描結果['indices'])} + 個股/ETF (含 RS 計算前)")

    # Phase 7.2：相對強度（個股漲幅 vs 大盤漲幅）
    try:
        rs統計 = relative_strength.為掃描結果加上RS(掃描結果)
        print(f"     [RS] 大盤台股 {rs統計.get('台股大盤20日漲幅')}% / "
              f"美股 {rs統計.get('美股大盤20日漲幅')}%")
        print(f"     [RS] 強勢 {rs統計.get('強勢',0)} / "
              f"中性 {rs統計.get('中性',0)} / "
              f"弱勢 {rs統計.get('弱勢',0)} / "
              f"資料不足 {rs統計.get('資料不足',0)}")
        if rs統計.get("強勢清單"):
            top5 = rs統計["強勢清單"][:5]
            print(f"     [RS] 強勢前 5：" +
                  ", ".join(f"{x['symbol']}(+{x['rs_20d']}pp)" for x in top5))
    except Exception as e:
        print(f"     ⚠️ RS 計算失敗（不影響主流程）：{e}")
        rs統計 = None

    全部個股 = _合併個股(掃描結果)
    print(f"     指數 {len(掃描結果['indices'])} + 個股/ETF {len(全部個股)}")

    # 3. 新聞
    print("[3/5] 抓新聞 + Gemini AI 摘要...")
    新聞摘要 = news_ai.取得每日新聞摘要()
    print(f"     {新聞摘要['新聞筆數']} 則新聞")

    # 3b. KOL 觀點（Phase 2.8）
    print("[3b] KOL 觀點匯整（Gemini grounding）...")
    try:
        kol結果 = kol_aggregator.取得今日KOL觀點()
        命中數 = len(kol結果.get("watchlist_hits", {}))
        print(f"     {len(kol結果['kols'])} 位 KOL，watchlist 命中 {命中數} 檔")
    except Exception as e:
        print(f"     ⚠️ KOL 抓取失敗：{e}")
        kol結果 = None

    # 4. Enjoy Index
    print("[4/5] 計算 Enjoy Index...")
    指數 = enjoy_index.計算Enjoy指數(情緒, 掃描結果["indices"], 全部個股)
    print(f"     總分 {指數['總分']} → {指數['建議']}")

    # 5. 資金規劃 + FIRE 聯動
    print("[5/5] 計算今日資金規劃 + FIRE 聯動...")
    資金 = capital_planner.載入資金設定()

    # Phase 9：先算 FIRE 拿到生命週期階段（給 capital_planner modifier 用）
    fire = fire_calculator.從portfolio計算(資金)
    fire_modifier = fire["生命週期"] if fire else None
    if fire_modifier:
        print(f"     生命週期：{fire_modifier['階段']} → "
              f"BE_HAPPY {fire_modifier['be_happy_modifier']:+d}% / "
              f"WAIT {fire_modifier['wait_modifier']:+d}% / "
              f"HOLD {fire_modifier['hold_modifier']:+d}%")

    規劃 = capital_planner.計算今日資金規劃(指數["總分"], 資金,
                                              fire_modifier=fire_modifier)
    # Phase 9.6：動態 USD/TWD 匯率（覆蓋 portfolio.json 固定值）
    匯率資訊 = forex.取得USD_TWD匯率(fallback=規劃["USD_TWD"])
    USD_TWD = 匯率資訊["rate"]
    print(f"     💱 USD/TWD = {USD_TWD} ({匯率資訊['source']})")
    # 每檔可分配預算 = 子彈 / 觸發訊號股數（保守估）
    觸發數 = sum(1 for r in 全部個股
                  if r.get("shakeout_low") or r.get("bull_signal"))
    每檔預算 = min(規劃["單檔上限_twd"],
                   規劃["今日可動用子彈_twd"] / max(觸發數, 3))
    調整字 = f" (原始 {規劃['原始火力']:.0f}% {規劃['FIRE調整']:+d}%)" if 規劃.get('FIRE調整') else ""
    print(f"     今日子彈 NT$ {規劃['今日可動用子彈_twd']:,.0f}（每檔約 NT$ {每檔預算:,.0f}）")
    print(f"     火力 {規劃['火力比例']:.0f}%{調整字} | 主動操作：{規劃['主動操作']}")

    # Phase 6.0：HOLD 時的減碼建議（只 print，未來再接卡片）
    減碼 = capital_planner.計算減碼建議(規劃["主動操作"], 全部個股, 資金)
    if 規劃["主動操作"] == "SELL_TAKE":
        if 減碼["可執行"]:
            print(f"     📉 減碼建議（{len(減碼['減碼建議'])} 檔）：")
            for r in 減碼["減碼建議"]:
                print(f"        {r['symbol']} ({r.get('name','')}) "
                      f"+{r['pnl_pct']}% → {r.get('標籤')}：減 {r.get('建議減股數', 0)} 股")
        else:
            print(f"     ⚠️ {減碼['原因']}")

    # Phase 6.2：風控 5 儀表
    print("\n[6.2] 風控 5 儀表計算...")
    風控 = None
    try:
        公告 = tw_announcements.取得公告清單()
        風控 = risk_dashboard.從main流程計算(
            fear_greed=情緒,
            indices=掃描結果["indices"],
            全部個股=全部個股,
            外資前20=公告.get("外資前20", []),
        )
        print(f"     總體分數 {風控['總體分數']} → {風控['建議']}")
        for 名, 儀 in 風控["儀表"].items():
            分 = 儀["分數"]
            分_str = f"{分:.0f}" if 分 is not None else "n/a"
            print(f"        {名:>10}: {分_str:>4} ({儀['副標']})")
    except Exception as e:
        print(f"     ⚠️ 風控儀表計算失敗：{e}")

    # Phase 7.1：AI 訊號解釋 + 今日心法
    print("\n[7.1] AI 訊號解釋（Gemini）...")
    ai_解釋 = []
    心法 = ai_explainer.今日心法()
    print(f"     📚 今日心法 Day {心法['day']}：{心法['標題']} — {心法['心法']}")
    try:
        ai_解釋 = ai_explainer.解釋關鍵訊號(全部個股, 上限=3)
        if ai_解釋:
            for r in ai_解釋:
                print(f"     🤖 {r['symbol']} ({r['類型']}): {r['解釋']}")
        else:
            print("     （今日無關鍵訊號需 AI 解釋）")
    except Exception as e:
        print(f"     ⚠️ AI 解釋失敗（不影響主流程）：{e}")

    # Phase 10：載入最新全市場掃描結果（如果有）
    全市場 = None
    全市場更新時間 = ""
    try:
        market_scan_path = 數據根 / "market_scan_latest.json"
        if market_scan_path.exists():
            with open(market_scan_path, "r", encoding="utf-8") as f:
                全市場 = json.load(f)
            全市場更新時間 = 全市場.get("updated_at", "")[:10]
            print(f"\n[10] 載入全市場掃描（更新 {全市場更新時間}）："
                  f"Top {len(全市場.get('Top', []))} 黃金錯殺")
    except Exception as e:
        print(f"  ⚠️ 全市場掃描載入失敗：{e}")

    # Phase 12：位階監測（ARK 思路）
    print("\n[12] 位階監測掃描...")
    位階 = None
    try:
        位階 = positional_signal.掃描位階(全部個股)
        統 = 位階.get("統計", {})
        print(f"     {位階['總檔數']} 檔：深 {統.get('深價值區',0)} / "
              f"入 {統.get('進入價值區',0)} / 中 {統.get('中性',0)} / "
              f"出 {統.get('離開價值區',0)} / 超漲 {統.get('超漲區',0)}")
        if 位階["今日_進入價值區"]:
            print(f"     ⭐ 今日新進入價值區：" +
                  ", ".join(r["symbol"] for r in 位階["今日_進入價值區"]))
        if 位階["今日_離開價值區"]:
            print(f"     ⚠️ 今日新離開價值區：" +
                  ", ".join(r["symbol"] for r in 位階["今日_離開價值區"]))
    except Exception as e:
        print(f"     ⚠️ 位階監測失敗：{e}")

    # Phase 7.2b：連鎖恐慌偵測（黑天鵝機會）
    print("\n[7.2b] 連鎖恐慌偵測...")
    黑天鵝 = None
    try:
        黑天鵝 = black_swan.掃描黑天鵝(
            全部個股, 掃描結果["indices"], 情緒.get("score"),
        )
        print(f"     全市場：{黑天鵝['全市場警示']}")
        if 黑天鵝["黑天鵝清單"]:
            for r in 黑天鵝["黑天鵝清單"][:5]:
                print(f"     🌟 {r['symbol']} ({r.get('name','')}) "
                      f"{r['符合條件數']}/5 條件: {', '.join(r['命中條件'])}")
        else:
            print("     （無個股達 4 條件）")
    except Exception as e:
        print(f"     ⚠️ 黑天鵝偵測失敗：{e}")

    # Phase 8.3：真倉部位追蹤
    print("\n[8.3] 真倉部位追蹤...")
    真倉 = None
    try:
        真倉 = portfolio_tracker.追蹤真倉(資金, 全部個股, USD_TWD=USD_TWD)
        總 = 真倉["總計"]
        print(f"     {總['總檔數']} 檔（賺 {總['賺檔數']} / 賠 {總['賠檔數']}）"
              f" 損益 NT$ {總['損益_twd']:+,.0f}（{總['損益率_pct']:+.2f}%）")
        警示 = 真倉["警示"]
        if 真倉["有警示"]:
            if 警示["達停利"]:
                print(f"     🎯 達停利 {len(警示['達停利'])} 檔: "
                      + ", ".join(r["symbol"] for r in 警示["達停利"]))
            if 警示["破停損"]:
                print(f"     💀 破停損 {len(警示['破停損'])} 檔: "
                      + ", ".join(r["symbol"] for r in 警示["破停損"]))
            if 警示["接近停利"]:
                print(f"     📈 接近停利 {len(警示['接近停利'])} 檔")
            if 警示["接近停損"]:
                print(f"     📉 接近停損 {len(警示['接近停損'])} 檔")
    except Exception as e:
        print(f"     ⚠️ 真倉追蹤失敗：{e}")

    # Phase 6.3：產業氣溫表（watchlist 聚合）
    print("\n[6.3] 產業氣溫聚合...")
    產業氣溫 = None
    try:
        產業氣溫 = industry_heatmap.聚合產業氣溫(全部個股)
        最熱 = 產業氣溫.get("最熱")
        最冷 = 產業氣溫.get("最冷")
        print(f"     {產業氣溫['產業數']} 產業 "
              f"最熱:{最熱['產業'] if 最熱 else '—'} "
              f"(RSI {最熱['平均RSI'] if 最熱 else '—'}) | "
              f"最冷:{最冷['產業'] if 最冷 else '—'}")
    except Exception as e:
        print(f"     ⚠️ 產業氣溫失敗：{e}")

    # Phase 7.3：持股健康檢查
    print("\n[7.3] 持股健康檢查...")
    健康 = None
    try:
        健康 = portfolio_health.診斷持股健康(資金, 真倉, USD_TWD)
        print(f"     {健康['警示等級']} {健康['持股數']} 檔 / "
              f"{健康['產業數']} 產業 / 最大占比 {健康['最大占比_pct']:.1f}%")
        if 健康["重複曝險"]:
            for r in 健康["重複曝險"][:3]:
                標的 = "/".join(x["symbol"].replace(".TW", "").replace(".TWO", "")
                                 for x in r["標的"][:5])
                print(f"     ⚠️ {r['產業']} × {r['檔數']} 檔 "
                      f"({r['占比_pct']:.1f}%): {標的}")
    except Exception as e:
        print(f"     ⚠️ 健康檢查失敗：{e}")

    # Phase 6.1：離職倒數（已在前面 [5/5] 算過，這裡只 print）
    print("\n[6.1] 離職倒數摘要...")
    if fire:
        print(f"     FIRE 目標 NT$ {fire['FIRE_目標']:,.0f} | "
              f"進度 {fire['達標進度_pct']}%")
        if fire["達標年數"] is not None:
            print(f"     倒數（{fire['情境']} {fire['年化報酬率_pct']}%）："
                  f"{fire['剩餘_年']} 年 {fire['剩餘_月']} 月 {fire['剩餘_日']} 日 "
                  f"→ {fire['達標日期']}")
        # Phase 9：階段目標進度
        目標 = fire.get("階段目標", {})
        for 段, d in 目標.items():
            if d and d.get("目標_twd"):
                狀 = "✅ 達標" if d.get("已達標") else f"差 NT$ {d['差距_twd']:,.0f}"
                print(f"     [{段}] {d.get('目標名', '')}: "
                      f"NT$ {d['目標_twd']:,.0f} - 進度 {d['進度_pct']}% ({狀})")

    # 6. 找 VIX
    vix項 = next((r for r in 掃描結果["indices"]
                   if (r.get("original_symbol") or r.get("symbol")) == "^VIX"
                   and "error" not in r), None)
    vix值 = vix項["close"] if vix項 else None

    # 7. 生成真圓環 PNG 並上傳
    print("\n生成真圓環圖表並上傳...")
    enjoy圖URL = None
    vix圖URL = None
    capital圖URL = None
    try:
        enjoy_png = chart_generator.生成Enjoy圓環(
            指數["總分"],
            指數["建議"].lstrip("🔴🟢🟡⚪ ").strip(),
        )
        enjoy圖URL = image_uploader.上傳圖片(enjoy_png, f"enjoy_{今日字串}.png")
        print(f"  Enjoy 圓環：{enjoy圖URL or '上傳失敗→fallback 文字版'}")
    except Exception as e:
        print(f"  Enjoy 圓環失敗：{e}")

    try:
        vix_png = chart_generator.生成VIX半圓(vix值)
        vix圖URL = image_uploader.上傳圖片(vix_png, f"vix_{今日字串}.png")
        print(f"  VIX 半圓：{vix圖URL or '上傳失敗→fallback 文字版'}")
    except Exception as e:
        print(f"  VIX 半圓失敗：{e}")

    try:
        cap_png = chart_generator.生成資金規劃圓環(
            規劃["火力比例"], 規劃["今日可動用子彈_twd"], 規劃["建議"])
        capital圖URL = image_uploader.上傳圖片(cap_png, f"capital_{今日字串}.png")
        print(f"  資金圓環：{capital圖URL or '上傳失敗→fallback 文字版'}")
    except Exception as e:
        print(f"  資金圓環失敗：{e}")

    # 8. 組 Flex Carousel（有 URL 就用圖片版，無則 fallback 文字版）
    日期文字 = datetime.now().strftime("%Y/%m/%d (%a)")

    風險卡 = (flex_builder.建構風險指針卡_圖片版(vix值, vix圖URL)
              if vix圖URL else flex_builder.建構風險指針卡(vix值))
    enjoy卡 = (flex_builder.建構Enjoy主卡_圖片版(指數, 日期文字, enjoy圖URL)
               if enjoy圖URL else flex_builder.建構Enjoy主卡(指數, 日期文字))
    資金卡 = (flex_builder.建構資金規劃卡_圖片版(規劃, capital圖URL)
              if capital圖URL else flex_builder.建構資金規劃卡(規劃))

    # Phase 6.1：離職倒數卡（在第一輪最後）
    fire卡 = None
    try:
        fire卡 = flex_builder.建構離職倒數卡(fire)
    except Exception as e:
        print(f"  ⚠️ 離職倒數卡建構失敗：{e}")

    # Phase 6.2：風控 5 儀表卡
    風控卡 = None
    try:
        if 風控:
            風控卡 = flex_builder.建構風控5儀表卡(風控)
    except Exception as e:
        print(f"  ⚠️ 風控卡建構失敗：{e}")

    # Phase 6.0：HOLD 減碼建議卡（只有 SELL_TAKE 才出卡）
    減碼卡 = None
    try:
        減碼卡 = flex_builder.建構HOLD減碼建議卡(減碼)
    except Exception as e:
        print(f"  ⚠️ 減碼卡建構失敗：{e}")

    # Phase 8.0d：處置股警示卡（只警示你「實際持股」命中，watchlist 命中只 log）
    處置警示卡 = None
    try:
        from modules.capital_planner import 規範化代號
        公告_cache = tw_announcements.取得公告清單()

        # 1. 持股命中（高警示）
        持股symbols = set()
        for p in 資金.get("current_positions", []):
            sym = p.get("symbol")
            if sym and sym != "AGGREGATE":
                持股symbols.add(規範化代號(sym))

        # 2. watchlist 命中（低警示，只 log 不上卡）
        watchlist_symbols = {r.get("symbol") for r in 全部個股
                              if r.get("symbol")}

        持股命中 = []
        watchlist命中 = []
        for sym in (持股symbols | watchlist_symbols):
            r = tw_announcements.是否處置股(sym, 今日字串, 公告_cache)
            if not r["是否處置"]:
                continue
            code = sym.replace(".TW", "").replace(".TWO", "")
            公告r = next((x for x in 公告_cache.get("處置股", [])
                           if x["code"] == code), None)
            if not 公告r:
                continue
            紀錄 = {
                "symbol": sym,
                "name": 公告r.get("name", ""),
                "measure": 公告r.get("measure", ""),
                "reason": 公告r.get("reason", ""),
                "end_date": 公告r.get("end_date", ""),
            }
            if sym in 持股symbols:
                持股命中.append(紀錄)
            else:
                watchlist命中.append(紀錄)

        if 持股命中:
            處置警示卡 = flex_builder.建構處置股警示卡(持股命中)
            print(f"  🚨 處置股警示（持股中）：{len(持股命中)} 檔 → 上卡")
        if watchlist命中:
            print(f"  ℹ️ 處置股（watchlist 中，不上卡）：{len(watchlist命中)} 檔 "
                  + "(" + ", ".join(r["symbol"] for r in watchlist命中) + ")")
    except Exception as e:
        print(f"  ⚠️ 處置股警示卡建構失敗：{e}")

    # Phase 8.3：持股總覽卡
    持股總覽卡 = None
    try:
        持股總覽卡 = flex_builder.建構持股總覽卡(真倉)
    except Exception as e:
        print(f"  ⚠️ 持股總覽卡建構失敗：{e}")

    # Phase 7.3：持股健康檢查卡
    健康卡 = None
    try:
        健康卡 = flex_builder.建構持股健康檢查卡(健康)
    except Exception as e:
        print(f"  ⚠️ 健康檢查卡建構失敗：{e}")

    # Phase 8.4：真倉紀律警示卡（有觸發才出）
    真倉警示卡 = None
    try:
        真倉警示卡 = flex_builder.建構真倉警示卡(真倉)
    except Exception as e:
        print(f"  ⚠️ 真倉警示卡建構失敗：{e}")

    # Phase 8.5：煙火協議卡（達 +15% 停利時放爆破特效）
    煙火卡 = None
    try:
        達標 = []
        if 真倉 and 真倉.get("警示", {}).get("達停利"):
            for r in 真倉["警示"]["達停利"]:
                達標.append({
                    "symbol": r["symbol"],
                    "name": r.get("name", ""),
                    "pnl_pct": r["pnl_pct"],
                    "pnl_twd": r.get("pnl_twd", 0),
                    "source": "real",
                    "reason": "真倉達 +15% 停利",
                })
        # 也加模擬盤今日 TAKE_PROFIT
        try:
            from modules import sim_ledger
            今日達標 = [r for r in sim_ledger.查詢當日新增(今日字串)
                         if r.get("closed_reason") == "TAKE_PROFIT"]
            for r in 今日達標:
                達標.append({
                    "symbol": r["symbol"],
                    "name": r.get("name", ""),
                    "pnl_pct": r.get("realized_pnl_pct", 0),
                    "source": "sim",
                    "reason": "模擬盤達 +15% 平倉",
                })
        except Exception:
            pass

        if 達標:
            煙火卡 = flex_builder.建構煙火協議卡(達標)
            print(f"  🎆 煙火協議觸發：{len(達標)} 檔達 +15% 停利")
    except Exception as e:
        print(f"  ⚠️ 煙火卡建構失敗：{e}")

    # Phase 14b：ARK 風控對標
    ark = None
    try:
        ark = ark_dashboard.從main流程計算(風控, 真倉, 資金, USD_TWD)
        print(f"  🎛 ARK 風控對標：建議水位 {ark['建議水位_pct']:.1f}% / "
              f"實際 {ark['實際水位_pct']:.2f}% → {ark['狀態']}")
        if ark.get("建議布局金額_twd", 0) != 0:
            print(f"     → 建議布局 NT$ {ark['建議布局金額_twd']:,.0f}")
    except Exception as e:
        print(f"  ⚠️ ARK 風控計算失敗：{e}")

    # Phase 14：訊號狀態追蹤
    訊號狀態 = None
    try:
        訊號狀態 = signal_tracker.追蹤關心標的(資金, 位階)
        新進 = 訊號狀態.get("今日新進入", [])
        新消 = 訊號狀態.get("今日新消失", [])
        if 新進:
            print(f"  ⭐ 今日新進入價值區：" + ", ".join(r["symbol"] for r in 新進))
        if 新消:
            print(f"  ⚠️ 今日訊號消失：" + ", ".join(r["symbol"] for r in 新消))
    except Exception as e:
        print(f"  ⚠️ 訊號追蹤失敗：{e}")

    # Phase 11+13：今日決策卡（整合所有訊號 + 每日加碼計算機）— 放最前面
    決策卡 = None
    try:
        # Phase 14：取得集中模式設定
        集中設定 = 資金.get("concentration_mode", {})
        集中模式 = 集中設定.get("mode", "balanced")
        single_focus = 集中設定.get("single_focus_symbols", [])
        print(f"     [集中模式] {集中模式}" + (f" → 單押 {single_focus}" if single_focus else ""))

        決策 = daily_decision.整合今日決策(
            指數=指數, 規劃=規劃, 真倉=真倉,
            減碼=減碼, 黑天鵝=黑天鵝, 全市場=全市場, fire=fire,
            位階=位階, 總資產_twd=資金.get("total_capital_twd", 400000),
            USD_TWD=USD_TWD,
            集中模式=集中模式, single_focus_symbols=single_focus,
        )
        決策卡 = flex_builder.建構今日決策卡(決策)
        if 決策卡:
            print(f"\n[11] 今日決策：{決策.get('今日總結')}")
    except Exception as e:
        print(f"  ⚠️ 今日決策卡建構失敗：{e}")

    第一輪內容 = []
    if 決策卡:
        第一輪內容.append(決策卡)   # 最重要的放最前
    第一輪內容 += [風險卡, enjoy卡]
    if 風控卡:
        第一輪內容.append(風控卡)
    第一輪內容 += [
        資金卡,
        flex_builder.建構大盤指標卡(掃描結果["indices"]),
    ]
    if 持股總覽卡:
        第一輪內容.append(持股總覽卡)
    if 健康卡:
        第一輪內容.append(健康卡)
    if 煙火卡:
        第一輪內容.append(煙火卡)
    if 真倉警示卡:
        第一輪內容.append(真倉警示卡)
    if 減碼卡:
        第一輪內容.append(減碼卡)
    if 處置警示卡:
        第一輪內容.append(處置警示卡)
    if fire卡:
        第一輪內容.append(fire卡)

    carousels = [
        {
            "type": "carousel",
            "contents": 第一輪內容,
        },
        # 第二輪 carousel（個股區域 + AI 解釋 + 心法 + 新聞 + LIFF 入口）
        {
            "type": "carousel",
            "contents": [
                flex_builder.建構區域卡(
                    掃描結果["regions"]["us"],
                    "🌙 美股觀察", "昨夜收盤",
                    預算_twd=每檔預算, USD_TWD=USD_TWD),
                flex_builder.建構區域卡(
                    掃描結果["regions"]["tw_stocks"],
                    "📋 台股觀察", "今日操作參考",
                    預算_twd=每檔預算, USD_TWD=USD_TWD),
                flex_builder.建構區域卡(
                    掃描結果["regions"]["tw_etfs"],
                    "📋 台股 ETF", "今日操作參考",
                    預算_twd=每檔預算, USD_TWD=USD_TWD),
            ]
            # Phase 14b：ARK 風控對標卡（核心！）
            + ([flex_builder.建構ARK風控卡(ark)]
                if ark and ark.get("狀態") != "資料不足" else [])
            # Phase 14：訊號狀態追蹤卡（你關心的標的）
            + ([flex_builder.建構訊號狀態卡(訊號狀態)]
                if 訊號狀態 else [])
            # Phase 12：位階監測卡（ARK 思路）
            + ([flex_builder.建構位階監測卡(位階)]
                if 位階 else [])
            # Phase 7.2b：黑天鵝機會卡（有錯殺才出）
            + ([flex_builder.建構黑天鵝機會卡(黑天鵝)]
                if 黑天鵝 and 黑天鵝.get("黑天鵝清單") else [])
            # Phase 10：全市場發現卡（週掃描結果，有的話）
            + ([flex_builder.建構全市場發現卡(全市場, 全市場更新時間)]
                if 全市場 and 全市場.get("Top") else [])
            # Phase 6.3：產業氣溫表
            + ([flex_builder.建構產業氣溫卡(產業氣溫)]
                if 產業氣溫 else [])
            # Phase 7.1：AI 訊號解釋（有解釋才加）
            + ([flex_builder.建構AI訊號解釋卡(ai_解釋)] if ai_解釋 else [])
            + [
                # Phase 7.1：今日心法（永遠加）
                flex_builder.建構今日心法卡(心法),
            ]
            # Phase 9：階段性目標進度卡
            + ([flex_builder.建構階段目標卡(fire)] if fire and fire.get("階段目標") else [])
            + [
                flex_builder.建構新聞摘要卡(新聞摘要),
            ]
            + ([flex_builder.建構LIFF入口卡(LIFF_URL)] if LIFF_URL else []),
        },
    ]

    # 第三輪 carousel：KOL 觀點（如果有抓到）
    if kol結果 and kol結果.get("kols"):
        carousels.append(flex_builder.建構KOL_Carousel(kol結果))

    # Phase 11b：自動拆分超過 50KB 的 carousel（LINE 上限）
    def _拆分carousel(c: dict, 上限_kb: int = 35) -> list[dict]:
        """若 carousel JSON > 45KB（留 5KB buffer），拆成多個小 carousel。"""
        contents = c.get("contents", [])
        if not contents:
            return [c]
        # 試完整 size
        total_size = len(json.dumps(c, ensure_ascii=False).encode("utf-8"))
        if total_size <= 上限_kb * 1024:
            return [c]
        # 按一半切，遞迴
        mid = len(contents) // 2
        前半 = {"type": "carousel", "contents": contents[:mid]}
        後半 = {"type": "carousel", "contents": contents[mid:]}
        return _拆分carousel(前半, 上限_kb) + _拆分carousel(後半, 上限_kb)

    # 重組推播清單（自動拆超大 carousel）
    push_清單 = []
    for c in carousels:
        push_清單.extend(_拆分carousel(c))

    # ⭐ Phase 37 (5/16) — 新版 5 張主卡上線，main.py 推播完全停用
    # 但 main.py 還要跑：掃描、Enjoy、ledger、快照（資料給其他模組用）
    # 推播改由 push_5cards.py（在 LIS全套晨報.py 跑）統一處理
    _no_push = os.getenv("LIS_NO_PUSH", "true").lower() in ("true", "1", "yes")
    if _no_push:
        print(f"\n⏸️ LIS_NO_PUSH=true — 跳過 main.py 的 {len(push_清單)} 輪推播")
        print(f"   （Phase 37：改由 push_5cards.py 推 5 張主卡）")
        push_清單 = []

    # 舊版 emergency limit（LIS_NO_PUSH=false 時用）
    _limit = int(os.getenv("LIS_PUSH_LIMIT", "3"))
    if push_清單 and _limit > 0 and len(push_清單) > _limit:
        略過數 = len(push_清單) - _limit
        print(f"\n⚠️ Emergency limit: 推播限制前 {_limit} 輪，"
              f"略過後 {略過數} 輪")
        push_清單 = push_清單[:_limit]

    print(f"\n推播 {len(push_清單)} 輪 Flex Carousel 到 LINE...")
    for i, c in enumerate(push_清單, 1):
        卡數 = len(c['contents'])
        size_kb = len(json.dumps(c, ensure_ascii=False).encode("utf-8")) / 1024
        alt = f"L.I.S 報表第 {i} 輪 — Enjoy {指數['總分']} {指數['建議']}"
        try:
            line_push.推播Flex訊息(替代文字=alt, flex內容=c)
            print(f"  ✅ 第 {i} 輪推播完成（{卡數} 卡, {size_kb:.1f}KB）")
        except Exception as e:
            print(f"  ❌ 第 {i} 輪推播失敗（{卡數} 卡, {size_kb:.1f}KB）：{e}")
            traceback.print_exc()

    # 8.5 寫入模擬盤 ledger（Phase 8.0 — 全 watchlist 訊號記錄，含對照組）
    print("\n[8.5] 寫入模擬盤 ledger...")
    try:
        from modules import sim_ledger
        pushed_iso = datetime.now().isoformat(timespec="seconds")
        ledger結果 = sim_ledger.寫入今日全部訊號(
            全部個股=全部個股,
            enjoy_index_總分=指數["總分"],
            每檔預算=int(每檔預算),
            pushed_time=pushed_iso,
        )
        print(f"     BUY {ledger結果['BUY']} / "
              f"WATCH {ledger結果['WATCH']} / "
              f"NONE {ledger結果['NONE']} / "
              f"失敗 {ledger結果['失敗']}")
    except Exception as e:
        print(f"  ⚠️ ledger 寫入失敗（不影響主流程）：{e}")
        traceback.print_exc()

    # 9. 存快照
    快照 = {
        "date": 今日字串,
        "generated_at": 開始.isoformat(timespec="seconds"),
        "fear_greed": 情緒,
        "indices": 掃描結果["indices"],
        "regions": {
            區id: [
                {k: v for k, v in r.items() if k != "_region"}
                for r in 區["items"]
            ]
            for 區id, 區 in 掃描結果["regions"].items()
        },
        "news": {
            "count": 新聞摘要["新聞筆數"],
            "time_range_hours": 新聞摘要["時間範圍小時"],
            "summary": 新聞摘要["摘要"],
        },
        "enjoy_index": 指數,
        "capital_plan": 規劃,
        "減碼建議": 減碼,  # Phase 6.0
        "相對強度統計": rs統計,  # Phase 7.2（暫用，連鎖恐慌另算）
        "FIRE": fire,  # Phase 6.1
        "風控儀表": 風控,  # Phase 6.2
        "真倉": 真倉,  # Phase 8.3 / 8.4
        "AI_解釋": ai_解釋,  # Phase 7.1
        "今日心法": 心法,
        "產業氣溫": 產業氣溫,  # Phase 6.3
        "持股健康": 健康,  # Phase 7.3
        "kol_summary": (
            {"hits_count": len(kol結果.get("watchlist_hits", {})),
             "watchlist_hits": kol結果.get("watchlist_hits", {})}
            if kol結果 else None
        ),
    }
    快照路徑 = 每日資料夾 / f"{今日字串}.json"
    with open(快照路徑, "w", encoding="utf-8") as f:
        json.dump(快照, f, ensure_ascii=False, indent=2)
    print(f"✅ 快照已存：{快照路徑}")

    耗時 = (datetime.now() - 開始).total_seconds()
    print(f"=== 完成（耗時 {耗時:.1f} 秒）===")
    return 0


if __name__ == "__main__":
    try:
        exit_code = 主流程()
    except Exception as e:
        錯誤摘要 = f"{type(e).__name__}: {e}"
        print(f"❌ 主流程失敗：{錯誤摘要}", file=sys.stderr)
        traceback.print_exc()
        錯誤日誌 = 日誌根 / f"error_{datetime.now():%Y%m%d_%H%M%S}.log"
        with open(錯誤日誌, "w", encoding="utf-8") as f:
            f.write(f"時間：{datetime.now().isoformat()}\n錯誤：{錯誤摘要}\n\n")
            traceback.print_exc(file=f)
        try:
            line_push.推播文字訊息(
                f"⚠️ L.I.S 系統執行失敗\n"
                f"錯誤：{錯誤摘要[:300]}\n"
                f"請檢查 {錯誤日誌}"
            )
        except Exception:
            pass
        exit_code = 1
    sys.exit(exit_code)
