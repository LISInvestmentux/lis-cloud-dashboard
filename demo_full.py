"""
LIS 全功能 Demo（Phase 8.0 + 6.0 + 6.1 + 6.2 之後）
一鍵展示：
  C. 跑模擬盤對帳（daily_reconcile）
  B. 用今日快照重算新模組，建 6 卡新版第一輪 carousel，存 JSON
  A. 真推這 6 卡到你 LINE

執行方式：
   python demo_full.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent
sys.path.insert(0, str(專案根))

# 載入 .env
from dotenv import load_dotenv
load_dotenv(專案根.parent / "API" / ".env")

from modules import (
    enjoy_index, capital_planner, fire_calculator,
    risk_dashboard, tw_announcements, portfolio_tracker,
    ai_explainer, portfolio_health, industry_heatmap,
    forex, black_swan, daily_decision,
    us_market_analyzer, dca_planner, positional_signal,
    signal_tracker, ark_dashboard,
    flex_builder, line_push,
)

數據根 = 專案根.parent / "數據"
preview_dir = 數據根 / "preview"
preview_dir.mkdir(parents=True, exist_ok=True)


def 段標題(text: str) -> None:
    print()
    print("=" * 60)
    print(text)
    print("=" * 60)


# ─────────────────────────────────────────────
# C. 跑模擬盤對帳
# ─────────────────────────────────────────────
段標題("【C】跑模擬盤對帳")
import daily_reconcile
daily_reconcile.主流程()


# ─────────────────────────────────────────────
# B. 從今日快照重算新模組
# ─────────────────────────────────────────────
段標題("【B】從今日快照重算新模組（避免重抓 API）")

# 找最新的 daily snapshot
daily_dir = 數據根 / "daily"
snapshots = sorted([p for p in daily_dir.glob("*.json")
                    if not p.stem.startswith("kol_")])
if not snapshots:
    print("❌ 找不到任何 daily snapshot")
    sys.exit(1)

最新snapshot = snapshots[-1]
print(f"使用快照：{最新snapshot.name}")

with open(最新snapshot, "r", encoding="utf-8") as f:
    snap = json.load(f)

情緒 = snap["fear_greed"]
indices = snap["indices"]
全部個股 = []
for 區id, items in snap["regions"].items():
    for r in items:
        r2 = dict(r)
        r2["_region"] = 區id
        全部個股.append(r2)

print(f"  情緒 F&G={情緒['score']} | 指數 {len(indices)} | 個股 {len(全部個股)}")

# 重算 enjoy_index（拿到新的「主動操作」欄位）
指數 = enjoy_index.計算Enjoy指數(情緒, indices, 全部個股)
print(f"  Enjoy={指數['總分']} {指數['建議']} → 主動操作={指數['主動操作']}")

# 重算 capital_planner（拿到新的「主動操作」欄位）
資金 = capital_planner.載入資金設定()
規劃 = capital_planner.計算今日資金規劃(指數["總分"], 資金)
USD_TWD = 規劃["USD_TWD"]
print(f"  資金規劃：{規劃['建議']} {規劃['火力比例']}% "
      f"主動操作={規劃['主動操作']}")
# Phase 9.6：動態匯率
匯率資訊 = forex.取得USD_TWD匯率(fallback=USD_TWD)
USD_TWD = 匯率資訊["rate"]
print(f"  💱 USD/TWD = {USD_TWD} ({匯率資訊['source']})")

# 減碼建議
減碼 = capital_planner.計算減碼建議(規劃["主動操作"], 全部個股, 資金)
if 規劃["主動操作"] == "SELL_TAKE":
    if 減碼["可執行"]:
        print(f"  📉 減碼建議 {len(減碼['減碼建議'])} 檔")
    else:
        print(f"  ⚠️ {減碼['原因']}")
else:
    print(f"  ℹ️ 主動操作={規劃['主動操作']}，不減碼")

# 6.1 離職倒數
fire = fire_calculator.從portfolio計算(資金)
if fire:
    print(f"  📅 離職倒數：{fire['剩餘_年']} 年 {fire['剩餘_月']} 月 "
          f"{fire['剩餘_日']} 日 → {fire['達標日期']}")
    print(f"     進度 {fire['達標進度_pct']}% / 目標 NT$ {fire['FIRE_目標']:,.0f}")

# 6.2 風控 5 儀表
公告 = tw_announcements.取得公告清單()
風控 = risk_dashboard.從main流程計算(
    fear_greed=情緒,
    indices=indices,
    全部個股=全部個股,
    外資前20=公告.get("外資前20", []),
)
print(f"  🎛 風控總體 {風控['總體分數']} → {風控['建議']}")
for 名, 儀 in 風控["儀表"].items():
    分 = 儀["分數"]
    分_str = f"{分:.0f}" if 分 is not None else "n/a"
    print(f"     {名:>10}: {分_str:>4} ({儀['副標']})")

# ─────────────────────────────────────────────
# 建 6 卡新版第一輪 carousel
# ─────────────────────────────────────────────
段標題("組 6 卡新版第一輪 carousel")

# 找 VIX
vix項 = next((r for r in indices
              if (r.get("original_symbol") or r.get("symbol")) == "^VIX"
              and "error" not in r), None)
vix值 = vix項["close"] if vix項 else None

日期文字 = datetime.now().strftime("%Y/%m/%d (%a)")

# 6 卡（無圖版，避免重抓圖床）
風險卡 = flex_builder.建構風險指針卡(vix值)
enjoy卡 = flex_builder.建構Enjoy主卡(指數, 日期文字)
資金卡 = flex_builder.建構資金規劃卡(規劃)
大盤卡 = flex_builder.建構大盤指標卡(indices)
fire卡 = flex_builder.建構離職倒數卡(fire)
風控卡 = flex_builder.建構風控5儀表卡(風控)

# Phase 8.3 真倉追蹤
print("\n  [8.3] 真倉追蹤...")
真倉 = portfolio_tracker.追蹤真倉(資金, 全部個股, USD_TWD=USD_TWD)
總 = 真倉["總計"]
print(f"     {總['總檔數']} 檔 損益 NT$ {總['損益_twd']:+,.0f}（{總['損益率_pct']:+.2f}%）")
警示 = 真倉["警示"]
for 類, 清單 in 警示.items():
    if 清單:
        print(f"     {類}: " + ", ".join(r["symbol"] for r in 清單))

# Phase 7.3 健康檢查
健康 = portfolio_health.診斷持股健康(資金, 真倉, USD_TWD=USD_TWD)
print(f"  🩺 {健康['警示等級']} 最大占比 {健康['最大占比_pct']}% 重複曝險 {len(健康['重複曝險'])} 個產業")

# Phase 6.3 產業氣溫
產業氣溫 = industry_heatmap.聚合產業氣溫(全部個股)
print(f"  🌡 {產業氣溫['產業數']} 產業 最熱={產業氣溫['最熱']['產業'] if 產業氣溫['最熱'] else '—'}")

# Phase 7.2b 黑天鵝偵測
黑天鵝 = black_swan.掃描黑天鵝(全部個股, indices, 情緒.get("score"))
print(f"  🌟 全市場：{黑天鵝['全市場警示']}（{len(黑天鵝['黑天鵝清單'])} 檔達 4 條件）")

# Phase 7.1 AI 解釋 + 心法
心法 = ai_explainer.今日心法()
print(f"  📚 今日心法 Day {心法['day']}：{心法['標題']}")
print(f"  🤖 跑 Gemini 解釋...")
ai_解釋 = ai_explainer.解釋關鍵訊號(全部個股, 上限=3)
print(f"     {len(ai_解釋)} 則解釋完成")

持股總覽卡 = flex_builder.建構持股總覽卡(真倉)
健康卡 = flex_builder.建構持股健康檢查卡(健康)
真倉警示卡 = flex_builder.建構真倉警示卡(真倉)
產業氣溫卡 = flex_builder.建構產業氣溫卡(產業氣溫)
ai卡 = flex_builder.建構AI訊號解釋卡(ai_解釋)
心法卡 = flex_builder.建構今日心法卡(心法)
階段目標卡 = flex_builder.建構階段目標卡(fire)  # Phase 9

# Phase 11：今日決策整合
全市場_demo = None
try:
    msp = 數據根 / "market_scan_latest.json"
    if msp.exists():
        with open(msp, "r", encoding="utf-8") as f:
            全市場_demo = json.load(f)
except Exception:
    pass

# Phase 12 位階監測（要在決策之前算）
print(f"  📊 位階監測掃描...")
位階 = positional_signal.掃描位階(全部個股)
位階卡 = flex_builder.建構位階監測卡(位階)
統_pos = 位階.get("統計", {})
print(f"     {位階['總檔數']} 檔：深 {統_pos.get('深價值區',0)} / 入 {統_pos.get('進入價值區',0)} / 中 {統_pos.get('中性',0)} / 出 {統_pos.get('離開價值區',0)} / 超漲 {統_pos.get('超漲區',0)}")
if 位階["今日_進入價值區"]:
    print(f"     ⭐ 今日新進入：" + ", ".join(r["symbol"] for r in 位階["今日_進入價值區"][:5]))
if 位階["今日_離開價值區"]:
    print(f"     ⚠️ 今日新離開：" + ", ".join(r["symbol"] for r in 位階["今日_離開價值區"][:5]))

# Phase 14b：ARK 風控對標
ark = ark_dashboard.從main流程計算(風控, 真倉, 資金, USD_TWD)
ark卡 = flex_builder.建構ARK風控卡(ark)
print(f"  🎛 ARK 風控：建議水位 {ark.get('建議水位_pct', 0):.1f}% / "
      f"實際 {ark.get('實際水位_pct', 0):.2f}%")
print(f"     {ark.get('狀態', '')} · {ark.get('動作', '')}")

# Phase 14：訊號狀態追蹤
訊號狀態 = signal_tracker.追蹤關心標的(資金, 位階)
訊號狀態卡 = flex_builder.建構訊號狀態卡(訊號狀態)
print(f"  📡 訊號狀態追蹤")
新進_demo = 訊號狀態.get("今日新進入", [])
新消_demo = 訊號狀態.get("今日新消失", [])
if 新進_demo:
    print(f"     ⭐ 今日新進入：" + ", ".join(r["symbol"] for r in 新進_demo[:5]))
if 新消_demo:
    print(f"     ⚠️ 今日訊號消失：" + ", ".join(r["symbol"] for r in 新消_demo[:5]))

# 集中模式設定
集中設定 = 資金.get("concentration_mode", {})
集中模式 = 集中設定.get("mode", "balanced")
single_focus = 集中設定.get("single_focus_symbols", [])
print(f"  🎯 集中模式：{集中模式}" + (f" → 單押 {single_focus}" if single_focus else ""))

決策 = daily_decision.整合今日決策(
    指數=指數, 規劃=規劃, 真倉=真倉,
    減碼=減碼, 黑天鵝=黑天鵝, 全市場=全市場_demo, fire=fire,
    位階=位階,
    總資產_twd=資金.get("total_capital_twd", 400000),
    USD_TWD=USD_TWD,
    集中模式=集中模式, single_focus_symbols=single_focus,
)
決策卡 = flex_builder.建構今日決策卡(決策)
print(f"  📋 今日決策：{決策['今日總結']}")
print(f"     建議買 {len(決策['建議買'])} 檔 / 賣 {len(決策['建議賣'])} 檔 / 觀察 {len(決策['觀察'])} 檔")

# Phase 11：美股盤勢深度
print(f"  🌎 美股盤勢分析...")
美股清單 = [r for r in 全部個股 if r.get("_region") == "us"]
美股盤勢 = us_market_analyzer.美股盤勢綜合(indices, 美股清單)
美股盤勢卡 = flex_builder.建構美股盤勢卡(美股盤勢)
print(f"     整體：{美股盤勢['整體判斷']} / 建議火力 {美股盤勢['建議火力_pct']}%")

# Phase 11：零股長期清單
print(f"  📌 零股長期清單抓即時價...")
零股 = dca_planner.建立零股清單(月可投_twd=5000)
零股卡 = flex_builder.建構零股長期清單卡(零股)
print(f"     本月建議定期定額 NT$ {零股['月總投入_twd']:,.0f}")
for r in 零股["清單"]:
    if r.get("現價"):
        print(f"       {r['symbol'].replace('.TW','')}: {r.get('加碼訊號')} 買 {r.get('建議買股數')} 股")
黑天鵝卡 = flex_builder.建構黑天鵝機會卡(黑天鵝) if 黑天鵝 and 黑天鵝.get("黑天鵝清單") else None  # Phase 7.2b

# Phase 10：載入週掃描結果
全市場卡 = None
try:
    msp = 數據根 / "market_scan_latest.json"
    if msp.exists():
        with open(msp, "r", encoding="utf-8") as f:
            全市場 = json.load(f)
        全市場卡 = flex_builder.建構全市場發現卡(全市場, 全市場.get("updated_at", "")[:10])
        print(f"  🔍 全市場發現卡：Top {len(全市場.get('Top', []))} 黃金錯殺")
except Exception as e:
    print(f"  ⚠️ 全市場卡載入失敗：{e}")

# Phase 8.5 煙火協議
達標 = []
if 真倉 and 真倉.get("警示", {}).get("達停利"):
    for r in 真倉["警示"]["達停利"]:
        達標.append({
            "symbol": r["symbol"], "name": r.get("name", ""),
            "pnl_pct": r["pnl_pct"], "pnl_twd": r.get("pnl_twd", 0),
            "source": "real", "reason": "真倉達 +15% 停利",
        })
煙火卡 = flex_builder.建構煙火協議卡(達標) if 達標 else None

# Phase 6.0：減碼建議卡
減碼卡 = flex_builder.建構HOLD減碼建議卡(減碼)

# Phase 8.0d：處置股警示（只警示「實際持股」命中）
今日str = datetime.now().strftime("%Y-%m-%d")
from modules.capital_planner import 規範化代號

持股symbols = {規範化代號(p["symbol"])
                for p in 資金.get("current_positions", [])
                if p.get("symbol") and p["symbol"] != "AGGREGATE"}
watchlist_symbols = {r["symbol"] for r in 全部個股 if r.get("symbol")}

持股命中 = []
watchlist命中 = []
for sym in (持股symbols | watchlist_symbols):
    r = tw_announcements.是否處置股(sym, 今日str, 公告)
    if not r["是否處置"]:
        continue
    code = sym.replace(".TW", "").replace(".TWO", "")
    公告r = next((x for x in 公告.get("處置股", []) if x["code"] == code), None)
    if not 公告r:
        continue
    紀錄 = {
        "symbol": sym, "name": 公告r.get("name", ""),
        "measure": 公告r.get("measure", ""),
        "reason": 公告r.get("reason", ""),
        "end_date": 公告r.get("end_date", ""),
    }
    if sym in 持股symbols:
        持股命中.append(紀錄)
    else:
        watchlist命中.append(紀錄)

處置警示卡 = flex_builder.建構處置股警示卡(持股命中) if 持股命中 else None
if 處置警示卡:
    print(f"  🚨 處置股警示（持股中）：{len(持股命中)} 檔")

# LINE Carousel 每輪最多 12 卡，分兩輪推
第一輪 = []
if 決策卡:
    第一輪.append(決策卡)   # 最重要：今日決策放第一張
    print(f"  📋 今日決策卡已加入（最前面）")
第一輪 += [風險卡, enjoy卡, 風控卡, 資金卡, 大盤卡]
if 持股總覽卡:
    第一輪.append(持股總覽卡)
if 健康卡:
    第一輪.append(健康卡)
if 煙火卡:
    第一輪.append(煙火卡)
if 真倉警示卡:
    第一輪.append(真倉警示卡)
if 減碼卡:
    第一輪.append(減碼卡)
if 處置警示卡:
    第一輪.append(處置警示卡)
print(f"\n第一輪 carousel：{len(第一輪)} 卡")

第二輪 = []
if 美股盤勢卡:
    第二輪.append(美股盤勢卡)
    print(f"  🌎 美股盤勢深度卡已加入")
if 零股卡:
    第二輪.append(零股卡)
    print(f"  📌 零股長期清單卡已加入")
if ark卡:
    第二輪.append(ark卡)
    print(f"  🎛 ARK 風控對標卡已加入")
if 訊號狀態卡:
    第二輪.append(訊號狀態卡)
    print(f"  📡 訊號狀態追蹤卡已加入")
if 位階卡:
    第二輪.append(位階卡)
    print(f"  📊 位階監測卡已加入")
if 黑天鵝卡:
    第二輪.append(黑天鵝卡)
    print(f"  🌟 黑天鵝機會卡已加入（{len(黑天鵝['黑天鵝清單'])} 檔）")
if 全市場卡:
    第二輪.append(全市場卡)
    print(f"  🔍 全市場發現卡已加入")
if 產業氣溫卡:
    第二輪.append(產業氣溫卡)
if ai卡:
    第二輪.append(ai卡)
第二輪.append(心法卡)
if 階段目標卡:
    第二輪.append(階段目標卡)
    print(f"  🎯 階段目標卡已加入")
第二輪.append(fire卡)
print(f"第二輪 carousel：{len(第二輪)} 卡")

carousel1 = {"type": "carousel", "contents": 第一輪}
carousel2 = {"type": "carousel", "contents": 第二輪}

# 存 JSON（兩輪分開）
ts = f"{datetime.now():%Y%m%d_%H%M%S}"
for i, c in enumerate([carousel1, carousel2], 1):
    p = preview_dir / f"demo_carousel{i}_{ts}.json"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)
    print(f"  ✅ 第 {i} 輪 JSON 存檔：{p.name}")


# ─────────────────────────────────────────────
# A. 真推 LINE（自動拆分超大 carousel）
# ─────────────────────────────────────────────
def _拆分carousel(c: dict, 上限_kb: int = 35) -> list[dict]:
    contents = c.get("contents", [])
    if not contents:
        return [c]
    total_size = len(json.dumps(c, ensure_ascii=False).encode("utf-8"))
    if total_size <= 上限_kb * 1024:
        return [c]
    mid = len(contents) // 2
    前半 = {"type": "carousel", "contents": contents[:mid]}
    後半 = {"type": "carousel", "contents": contents[mid:]}
    return _拆分carousel(前半, 上限_kb) + _拆分carousel(後半, 上限_kb)

push清單 = []
for c in [carousel1, carousel2]:
    push清單.extend(_拆分carousel(c))

段標題(f"【A】真推 LINE（{len(push清單)} 輪）")
for i, c in enumerate(push清單, 1):
    卡數 = len(c['contents'])
    size_kb = len(json.dumps(c, ensure_ascii=False).encode("utf-8")) / 1024
    try:
        alt = f"LIS Demo 第{i}輪 — Enjoy {指數['總分']} {指數['建議']} {datetime.now():%H:%M}"
        line_push.推播Flex訊息(替代文字=alt, flex內容=c)
        print(f"  ✅ 第 {i} 輪推播成功（{卡數} 卡, {size_kb:.1f}KB）")
    except Exception as e:
        print(f"  ❌ 第 {i} 輪失敗（{size_kb:.1f}KB）：{e}")

段標題("Demo 完成")
print("總覽：")
print(f"  C 模擬盤對帳：完成（上方 console 輸出）")
print(f"  B Flex JSON 存檔：demo_carousel1_{ts}.json + demo_carousel2_{ts}.json")
print(f"  A LINE 推播：兩輪 carousel 已送出（共 {len(第一輪) + len(第二輪)} 卡）")
