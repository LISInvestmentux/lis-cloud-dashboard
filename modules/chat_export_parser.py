"""
LINE 對話記錄 TXT 解析（Phase 30）

LINE export 格式：
  [LINE] [群組名] 聊天記錄
  保存時間：2026/05/14 16:00

  2026/05/13(三)
  下午 02:30 可可  今天 00910 噴出，加碼 200 股
  下午 02:31 太太  我也加 0050 一張
  下午 02:35 ABC   早安大家
  ...

兩階段過濾（節省 Gemini API）：
  Stage 1: 關鍵詞過濾（快速，本地）
    - 留：買/賣/漲/跌/賺/賠/停損/停利/套牢/加碼/減碼/本金/部位/重押
    - 去：早安/晚安/吃飯/天氣/呵呵/笑死
  Stage 2: Gemini 結構化提取
    - 每段對話 → JSON {symbol, 動作, 金額, 報酬, 發言者}

「反CC」風險警示已嵌入回傳：
  weight: 0.1（低權重，避免過度信任）
  bias_warnings: ["survivorship", "groupthink"...]
"""
import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


專案根 = Path(__file__).resolve().parent.parent.parent


# 關鍵詞集合
有用_關鍵詞 = [
    # 動作
    "買", "賣", "加碼", "減碼", "停損", "停利", "出場", "進場",
    "重押", "佈局", "布局", "套牢", "解套",
    # 結果
    "漲", "跌", "賺", "賠", "報酬", "獲利", "套", "綠了", "紅了",
    # 部位
    "本金", "部位", "持股", "庫存", "現金", "閒錢",
    # 系統
    "ARK", "方舟", "升溫", "價值區", "離開", "進入",
    "Kelly", "倍率", "策略", "訊號",
    # 標的關鍵字
    "%", "張", "股",
]

# 過濾無用訊號
無用_關鍵詞 = [
    "早安", "晚安", "午安", "吃飯", "吃飽", "天氣", "下雨", "冷",
    "貼圖", "Photo", "Video", "已收回", "回覆", "PM",
    "謝謝", "感謝", "辛苦", "厲害", "強", "讚",
]


def 解析LINE_TXT(txt_content: str) -> list[dict]:
    """
    支援多種 LINE TXT 格式：
      新版：2022.06.17 星期五 / 17:57 Enjoy 內容
      舊版：2026/05/13(三) / 下午 02:30 名字 內容
      iOS/Android 都支援
    """
    訊息 = []
    當前日期 = None

    # 日期格式：2022.06.17 / 2022/06/17 / 2022年06月17日
    日期_pat = re.compile(
        r"^(20\d{2})[.\-/年](\d{1,2})[.\-/月](\d{1,2})"
    )
    # 訊息格式 1（新）：HH:MM 發言者 內容
    新格式 = re.compile(r"^(\d{1,2}):(\d{2})\s+(\S+(?:\s+\S+)?)\s+(.+)$")
    # 訊息格式 2（舊）：上午/下午 HH:MM 發言者\t內容
    舊格式_tab = re.compile(
        r"^(上午|下午)?\s*(\d{1,2}):(\d{2})\s+([^\t]+)\t(.+)$"
    )
    舊格式_空 = re.compile(
        r"^(上午|下午)\s+(\d{1,2}):(\d{2})\s+(\S+)\s+(.+)$"
    )

    for raw_line in txt_content.split("\n"):
        line = raw_line.rstrip()
        if not line:
            continue

        # 試解析日期行
        if re.match(r"^20\d{2}", line):
            m = 日期_pat.match(line)
            if m:
                當前日期 = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                continue

        if 當前日期 is None:
            continue

        # 試三種格式
        m_old_tab = 舊格式_tab.match(line)
        m_old_kong = 舊格式_空.match(line)
        m_new = 新格式.match(line)

        if m_old_tab:
            ampm, hr, mn, 發言者, 內容 = m_old_tab.groups()
            hr = int(hr)
            if ampm == "下午" and hr < 12:
                hr += 12
            elif ampm == "上午" and hr == 12:
                hr = 0
            時間 = f"{當前日期} {hr:02d}:{mn}"
        elif m_old_kong:
            ampm, hr, mn, 發言者, 內容 = m_old_kong.groups()
            hr = int(hr)
            if ampm == "下午" and hr < 12:
                hr += 12
            elif ampm == "上午" and hr == 12:
                hr = 0
            時間 = f"{當前日期} {hr:02d}:{mn}"
        elif m_new:
            hr, mn, 發言者_候選, 內容 = m_new.groups()
            時間 = f"{當前日期} {int(hr):02d}:{mn}"
            # 發言者可能含空白（如 "Xia Qi🌱夏亓"），用啟發式取第一個空白前
            # 但這個 regex 已經處理了
            發言者 = 發言者_候選
        else:
            continue

        訊息.append({
            "時間": 時間,
            "發言者": 發言者.strip(),
            "內容": 內容.strip(),
        })

    return 訊息


def 關鍵詞過濾(訊息列表: list[dict]) -> list[dict]:
    """
    Stage 1 過濾：留下含投資關鍵詞的訊息。
    回傳：[{時間, 發言者, 內容, 命中關鍵詞: [...]}]
    """
    結果 = []
    for m in 訊息列表:
        內容 = m["內容"]
        if len(內容) < 4:  # 太短沒意義
            continue
        # 先排除明顯廢話
        if any(kw in 內容 for kw in 無用_關鍵詞) and len(內容) < 15:
            continue
        # 找投資關鍵詞
        命中 = [kw for kw in 有用_關鍵詞 if kw in 內容]
        # 含「股票代號 4 碼」也算
        if re.search(r"\b\d{4,5}[A-Z]?\b", 內容):
            命中.append("含股票代號")
        # 含「%」也算
        if "%" in 內容:
            命中.append("含百分比")

        if 命中:
            結果.append({**m, "命中關鍵詞": 命中})
    return 結果


def Regex結構化提取(訊息批次: list[dict]) -> list[dict]:
    """
    無 AI 模式 — 純 regex 提取（無限額、無延遲）
    """
    # 台股代號嚴格：4 位數（1xxx-9xxx）或 5 位數（00xxx）+ 選擇性 A/B/L 等後綴
    sym_pat = re.compile(r"(?<!\d)(\b(?:0[0-9]\d{3}|[1-9]\d{3})[A-Z]?\b)(?!\d)")
    買賣_pat = re.compile(r"(買|賣|加碼|減碼|停損|停利|套|賺|賠|抱|減持|加倉)")
    報酬_pat = re.compile(r"([+\-]?\d+\.?\d*)\s*%")
    張數_pat = re.compile(r"(\d+)\s*張")

    結果 = []
    for m in 訊息批次:
        內容 = m["內容"]
        syms = sym_pat.findall(內容)
        syms = [s for s in syms if not (
            s.startswith("20") and len(s) == 4 and 1990 < int(s) < 2100
        )]
        if not syms:
            continue
        動作m = 買賣_pat.search(內容)
        if not 動作m:
            continue
        動作 = 動作m.group(1)
        if 動作 in ("買", "加碼", "加倉", "抱"):
            類型 = "BUY"
        elif 動作 in ("賣", "減碼", "減持", "停損", "停利"):
            類型 = "SELL"
        else:
            類型 = "HOLD"
        報酬m = 報酬_pat.search(內容)
        報酬 = float(報酬m.group(1)) if 報酬m else None
        張數m = 張數_pat.search(內容)
        張數 = int(張數m.group(1)) if 張數m else None
        重要度 = 3
        if 張數 and 張數 >= 5:
            重要度 = 4
        if 張數 and 張數 >= 10:
            重要度 = 5
        if 報酬 and abs(報酬) >= 10:
            重要度 = max(重要度, 4)
        for s in syms[:2]:
            if len(s) in (4, 5):
                sym_norm = s + ".TW"
            else:
                sym_norm = s
            結果.append({
                "時間": m["時間"],
                "發言者": m["發言者"],
                "原文": 內容[:120],
                "有訊號": True,
                "symbol": sym_norm,
                "類型": 類型,
                "動作詞": 動作,
                "報酬_pct": 報酬,
                "張數": 張數,
                "重要度": 重要度,
                "說明": f"{動作} {sym_norm}" + (f" {張數}張" if 張數 else "") + (f" {報酬}%" if 報酬 else ""),
                "_提取方式": "regex",
            })
    return 結果


def AI結構化提取(訊息批次: list[dict],
                  社群名: str = "未知群") -> list[dict]:
    """
    Stage 2：用 Gemini 提取結構化資料。
    一次處理 30-50 則（API 經濟）。
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return [{**m, "AI": None} for m in 訊息批次]

    try:
        from google import genai
    except ImportError:
        return [{**m, "AI": None} for m in 訊息批次]

    # 組訊息文字
    文字 = "\n".join(
        f"[{m['時間']}] {m['發言者']}: {m['內容']}"
        for m in 訊息批次[:50]
    )

    prompt = f"""
你是台美股投資情報分析師。
以下是 LINE 社群「{社群名}」的對話（已預過濾關鍵詞）。

請對每段訊息判斷：
1. 含具體股票訊號？（買賣、報酬、部位）
2. 如有，提取：
   - symbol: 股票代號（台股加 .TW、上櫃加 .TWO、美股直接）
   - 類型: BUY/SELL/HOLD/ASK
   - 報酬_pct: 如有提到 +X% 或 -X%
   - 金額_twd: 如有提到金額
   - 重要度: 1-5（5 = 明確大單）

對話：
{文字[:4500]}

請回傳 JSON 陣列（純文字，不含 markdown）：
[
  {{"時間": "...", "發言者": "...", "原文": "...",
    "有訊號": true/false,
    "symbol": "...",
    "類型": "BUY|SELL|HOLD|ASK|NONE",
    "報酬_pct": null 或數字,
    "金額_twd": null 或數字,
    "重要度": 1-5,
    "說明": "20字內"}},
  ...
]
"""
    try:
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )
        text = resp.text or "[]"
        # 找 JSON
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            data = json.loads(m.group())
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"AI 提取失敗：{e}")
    return []


def 處理對話TXT(txt_path: Path, 社群名: str = None,
                 weight: float = 0.1,
                 近期天數: Optional[int] = 60,
                 重點發言者: Optional[list] = None,
                 最大訊號數: int = 500,
                 用AI: bool = False) -> dict:
    """
    主入口：處理 LINE 對話 TXT 匯出檔。

    參數：
      weight: 此來源的權重（0.1-0.5）
      近期天數: 只處理近 N 天的訊息（None = 全部）
      重點發言者: 高優先的發言者清單（其他人降權）
      最大訊號數: 防爆量保護
    """
    if not txt_path.exists():
        return {"error": f"檔不存在：{txt_path}"}

    txt = txt_path.read_text(encoding="utf-8", errors="replace")
    社群名 = 社群名 or txt_path.stem

    # 解析
    所有訊息 = 解析LINE_TXT(txt)
    print(f"  解析到 {len(所有訊息)} 則訊息")

    # 時間範圍篩選
    if 近期天數:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=近期天數)
                  ).strftime("%Y-%m-%d %H:%M")
        所有訊息 = [m for m in 所有訊息 if m["時間"] >= cutoff]
        print(f"  時間篩選（近 {近期天數} 天）：{len(所有訊息)} 則")

    # Stage 1：關鍵詞過濾
    篩 = 關鍵詞過濾(所有訊息)
    print(f"  關鍵詞過濾後：{len(篩)} 則")

    # 重點發言者標記
    if 重點發言者:
        篩 = [m for m in 篩
              if any(s in m["發言者"] for s in 重點發言者)]
        print(f"  重點發言者過濾：{len(篩)} 則")

    # 防爆量（regex 模式可放大量，AI 模式才嚴格限）
    限額 = 最大訊號數 if 用AI else 最大訊號數 * 50  # regex 放 50 倍
    if len(篩) > 限額:
        篩 = 篩[-限額:]
        print(f"  限量保護：取最近 {限額} 則")

    if not 篩:
        return {
            "社群名": 社群名, "總筆數": len(所有訊息),
            "處理筆數": 0, "提取訊號": [],
        }

    # Stage 2：結構化提取（預設 regex，無 AI 限額）
    if 用AI:
        所有訊號 = []
        for i in range(0, len(篩), 30):
            batch = 篩[i:i + 30]
            ai_results = AI結構化提取(batch, 社群名)
            所有訊號.extend(ai_results)
    else:
        所有訊號 = Regex結構化提取(篩)

    # 統計
    有效訊號 = [s for s in 所有訊號 if s.get("有訊號") and s.get("symbol")]
    買 = [s for s in 有效訊號 if s.get("類型") == "BUY"]
    賣 = [s for s in 有效訊號 if s.get("類型") == "SELL"]
    # Phase 30 修：AI 偶爾返回字串，強制轉 float
    報酬 = []
    for s in 有效訊號:
        v = s.get("報酬_pct")
        if v is None:
            continue
        try:
            報酬.append(float(v))
        except (ValueError, TypeError):
            continue

    sym_count = {}
    for s in 有效訊號:
        sym = s.get("symbol", "")
        if sym:
            sym_count[sym] = sym_count.get(sym, 0) + 1

    最常 = sorted(sym_count.items(), key=lambda x: -x[1])[:10]

    結果 = {
        "社群名": 社群名,
        "處理日": datetime.now().strftime("%Y-%m-%d"),
        "總筆數": len(所有訊息),
        "過濾後": len(篩),
        "有效訊號數": len(有效訊號),
        "提取訊號": 有效訊號[:100],  # 只存前 100 筆
        "統計": {
            "買_次數": len(買),
            "賣_次數": len(賣),
            "提到報酬數": len(報酬),
            "平均提報酬_pct": round(sum(報酬) / len(報酬), 2) if 報酬 else None,
            "最常提標的": 最常,
        },
        "weight": weight,
        "反CC警告": [
            "⚠️ 倖存者偏差：群組只 PO 賺錢的訊號",
            "⚠️ 從眾偏差：一人帶風向，全群跟著說",
            "⚠️ 時效偏差：歷史訊號 ≠ 今日有效",
            "⚠️ 此資料 weight 僅 0.1，當參考不當決策",
        ],
    }

    # 同步到 external_signal_tracker（低權重）
    try:
        from . import external_signal_tracker as ext
        for s in 有效訊號:
            if s.get("重要度", 0) >= 3:  # 只 log 中高重要度
                ext.記錄外部訊號(
                    來源=f"群組_{社群名}_低權",
                    symbol=s.get("symbol", ""),
                    類型=s.get("類型", "BUY"),
                    進場價=0,  # 群組通常沒給確切價
                    說明=s.get("說明", ""),
                    時間=s.get("時間", "") + ":00" if "時間" in s else "",
                    metadata={
                        "weight": weight,
                        "發言者": s.get("發言者"),
                        "重要度": s.get("重要度"),
                        "報酬_pct": s.get("報酬_pct"),
                        "_反CC": "低權重，倖存者偏差",
                    },
                )
    except Exception as e:
        print(f"同步外部訊號失敗：{e}")

    # 存歷史
    歷史_path = 專案根 / "數據" / "chat_export_history.json"
    if 歷史_path.exists():
        歷史 = json.loads(歷史_path.read_text(encoding="utf-8"))
    else:
        歷史 = {"處理記錄": []}
    歷史["處理記錄"].append({
        "處理時間": datetime.now().isoformat(timespec="seconds"),
        "社群": 社群名,
        "統計": 結果["統計"],
    })
    歷史_path.parent.mkdir(parents=True, exist_ok=True)
    歷史_path.write_text(
        json.dumps(歷史, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return 結果


# ─────────────────────────────────────────────
# CLI 自測
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from dotenv import load_dotenv
    load_dotenv(專案根 / "API" / ".env")

    print("=== Phase 30 LINE TXT 解析器 ===\n")

    # 模擬一段 LINE 對話
    模擬TXT = """[LINE] 可可投資群 聊天記錄

2026/05/14(四)
下午 02:30 可可	今天 00910 升溫區噴了，加碼 200 股 @ 73
下午 02:31 太太	0050 我也加 1 張 @ 96
下午 02:32 路人A	早安大家
下午 02:35 可可	00911 又連 3 買，外資看好
下午 02:38 路人B	貼圖
下午 02:40 太太	2330 別追，外資賣
下午 02:42 可可	@路人B 對啊
下午 02:45 路人C	我 NVDA 漲了 5% 賺死
下午 02:50 太太	那個 ETF 我抱了 1 年 +30%
下午 03:00 可可	大家保重 我去吃飯
下午 03:30 路人D	00876 套牢中 該停損嗎
下午 03:35 可可	看 -5% 才停
"""
    # 存到測試檔
    import tempfile
    test_path = Path(tempfile.gettempdir()) / "test_chat.txt"
    test_path.write_text(模擬TXT, encoding="utf-8")

    r = 處理對話TXT(test_path, 社群名="可可投資群")
    print(f"\n📊 社群：{r['社群名']}")
    print(f"   總訊息 {r['總筆數']} / 過濾後 {r['過濾後']} / 有效訊號 {r['有效訊號數']}")
    print(f"\n📈 統計：")
    print(f"   買 {r['統計']['買_次數']} / 賣 {r['統計']['賣_次數']}")
    print(f"   提報酬 {r['統計']['提到報酬數']} 次 / 平均 {r['統計']['平均提報酬_pct']}%")
    print(f"\n🎯 最常提標的：")
    for sym, cnt in r["統計"]["最常提標的"][:5]:
        print(f"   {sym:<10} 被提 {cnt} 次")
    print(f"\n⚠️ 反CC 警告：")
    for w in r["反CC警告"]:
        print(f"   {w}")
    print(f"\n📝 提取訊號（前 5）：")
    for s in r["提取訊號"][:5]:
        print(f"   [{s.get('時間','')}] {s.get('發言者','')}: "
              f"{s.get('symbol','-')} {s.get('類型','-')} "
              f"重要度{s.get('重要度','-')}")
