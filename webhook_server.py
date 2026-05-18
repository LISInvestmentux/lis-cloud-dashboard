"""
LIS LINE Bot Webhook Server (Phase 38)

接 LINE postback events，根據 data 推對應細節卡。

部署到 Render / Fly.io / Railway 等 PaaS。

環境變數（從 .env 或 Render env vars）：
  LINE_CHANNEL_SECRET      — LINE Channel Secret（驗 signature 用）
  LINE_CHANNEL_ACCESS_TOKEN — LINE Bot push token

本機跑：
  uvicorn webhook_server:app --host 0.0.0.0 --port 8000

健康檢查：
  GET / → {"status": "ok"}
  GET /health → {"status": "healthy", "time": ...}
"""
import os
import sys
import hmac
import hashlib
import base64
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request, Header, HTTPException

專案根 = Path(__file__).resolve().parent.parent
程式碼根 = Path(__file__).resolve().parent
sys.path.insert(0, str(程式碼根))

# 載入 .env（本機開發用，Render 上會直接讀 env vars）
try:
    from dotenv import load_dotenv
    load_dotenv(專案根 / "API" / ".env")
except Exception:
    pass

LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "").strip()
ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
DEFAULT_USER_ID = os.getenv("LINE_USER_ID", "").strip()

# ════════════════════════════════════════════
# Phase 39 (5/16) — 雲端啟動時從 Gist 抓 portfolio.json / sylvie / watchlist
# 因為 .gitignore 排除 portfolio.json，Render 從 GitHub clone 沒這檔案
# 解法：啟動時 HTTP GET Gist raw URL 下載到 /tmp 或 API/
# user 在 Render 設 env vars:
#   PORTFOLIO_GIST_URL=https://gist.githubusercontent.com/.../raw/portfolio.json
#   SYLVIE_GIST_URL=https://gist.githubusercontent.com/.../raw/sylvie_portfolio.json (可選)
# ════════════════════════════════════════════
def _從Gist下載到本地():
    """雲端啟動時抓 portfolio.json 寫到本地。本機開發跳過。"""
    import requests as _r
    import tempfile

    # portfolio
    portfolio_url = os.getenv("PORTFOLIO_GIST_URL", "").strip()
    if portfolio_url:
        try:
            r = _r.get(portfolio_url, timeout=10)
            r.raise_for_status()
            # 寫到專案 API/ 跟 /tmp（雙保險）
            candidates = [
                Path(__file__).resolve().parent.parent / "API" / "portfolio.json",
                Path(tempfile.gettempdir()) / "lis_portfolio.json",
            ]
            saved = None
            for cand in candidates:
                try:
                    cand.parent.mkdir(parents=True, exist_ok=True)
                    cand.write_text(r.text, encoding="utf-8")
                    saved = cand
                    break
                except (PermissionError, OSError):
                    continue
            if saved:
                os.environ["LIS_PORTFOLIO_PATH"] = str(saved)
                print(f"✓  portfolio.json 從 Gist 下載 → {saved}", flush=True)
        except Exception as e:
            print(f"❌ portfolio Gist 下載失敗：{e}", flush=True)

    # sylvie
    sylvie_url = os.getenv("SYLVIE_GIST_URL", "").strip()
    if sylvie_url:
        try:
            r = _r.get(sylvie_url, timeout=10)
            r.raise_for_status()
            sylvie_path = (Path(__file__).resolve().parent.parent /
                           "數據" / "sylvie_portfolio.json")
            sylvie_path.parent.mkdir(parents=True, exist_ok=True)
            sylvie_path.write_text(r.text, encoding="utf-8")
            print(f"✓  sylvie_portfolio.json 從 Gist 下載", flush=True)
        except Exception as e:
            print(f"⚠️  sylvie Gist 下載失敗（非必要）：{e}", flush=True)


_從Gist下載到本地()

app = FastAPI(title="LIS Webhook Server")


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "LIS Webhook Server",
        "version": "Phase 38",
        "time": datetime.now().isoformat(timespec="seconds"),
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "secret_set": bool(LINE_CHANNEL_SECRET),
        "token_set": bool(ACCESS_TOKEN),
        "time": datetime.now().isoformat(timespec="seconds"),
    }


def 驗證簽章(body: bytes, signature: str) -> bool:
    """驗證 X-Line-Signature header"""
    if not LINE_CHANNEL_SECRET:
        # 沒設 secret 就跳過驗證（dev mode）
        return True
    if not signature:
        return False
    hash_value = hmac.new(
        LINE_CHANNEL_SECRET.encode("utf-8"),
        body, hashlib.sha256
    ).digest()
    expected = base64.b64encode(hash_value).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def 處理postback(event: dict) -> None:
    """處理 postback event — 根據 data view= 推對應細節卡"""
    user_id = event.get("source", {}).get("userId", DEFAULT_USER_ID)
    postback_data = event.get("postback", {}).get("data", "")

    parsed = parse_qs(postback_data)
    view = parsed.get("view", [""])[0]
    print(f"[{datetime.now():%H:%M:%S}] postback view={view} from {user_id[:8]}...",
          flush=True)

    if not view:
        return

    # lazy import 避免啟動時載入太多
    try:
        from modules import daily_5cards_detail, line_push
    except Exception as e:
        print(f"❌ import 失敗：{e}", flush=True)
        return

    # 根據 view 路由
    builder_map = {
        "action_full": daily_5cards_detail.卡_完整今日行動,
        "portfolio_detail": daily_5cards_detail.卡_完整持股,
        "kol_consensus": daily_5cards_detail.卡_完整KOL,
        # 兼容舊的（已棄用但保留以免 LINE 中還有舊卡）
        "opportunities": daily_5cards_detail.卡_完整今日行動,
        "us_close": daily_5cards_detail.卡_完整持股,
    }
    builder = builder_map.get(view)
    if not builder:
        print(f"⚠️ 未知 view: {view}", flush=True)
        return

    try:
        flex = builder()
        alt = f"📖 詳細 — {view}"
        line_push.推播Flex訊息(替代文字=alt, flex內容=flex, user_id=user_id)
        print(f"✅ 推 {view} 細節卡成功", flush=True)
    except Exception as e:
        import traceback
        print(f"❌ 推 {view} 失敗：{e}", flush=True)
        traceback.print_exc()
        # 推 fallback 訊息讓 user 知道失敗（不要 silent fail）
        try:
            line_push.推播文字訊息(
                f"⚠️ 細節卡 {view} 載入失敗：\n{type(e).__name__}: {str(e)[:80]}\n\n"
                f"可能原因：Render 端缺 portfolio.json (要設 PORTFOLIO_GIST_URL env var)",
                user_id=user_id)
        except Exception:
            pass


def 處理截圖(message_id: str, reply_token: str):
    """
    Phase 79b — LINE 接到截圖後:
    1. 用 LINE Content API 下載圖片
    2. 餵 Gemini Vision 解析
    3. Reply 回 LINE 告訴 user 結果
    4. 如果是國泰庫存/委託/成交、自動更新 cache
    """
    import requests
    import os
    import json
    import re
    from io import BytesIO

    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    if not token:
        print("  ❌ LINE_CHANNEL_ACCESS_TOKEN 未設", flush=True)
        return

    # 1. 下載圖片
    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code != 200:
            print(f"  ❌ 下載失敗 {r.status_code}", flush=True)
            return
        圖片_bytes = r.content
        print(f"  ✓ 下載 {len(圖片_bytes)/1024:.0f} KB", flush=True)
    except Exception as e:
        print(f"  ❌ 下載例外: {e}", flush=True)
        return

    # 2. Gemini Vision 解析
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        line_push.推播文字訊息(
            "⚠️ 收到圖片但 GEMINI_API_KEY 未設、無法 OCR")
        return

    try:
        import PIL.Image
        from google import genai
        image = PIL.Image.open(BytesIO(圖片_bytes))
        client = genai.Client(api_key=api_key)
        prompt = """你是國泰證券 app 截圖解析專家。請識別截圖類型 + 解析內容、輸出純 JSON:
{
  "類型": "庫存查詢 / 委託清單 / 成交明細 / 對帳單 / 其他",
  "信心": 0-100,
  "紀錄": [
    {"股票名稱": "...", "股票代號": "...", "現股": 0, "零股": 0,
     "委託價": 0, "成交價": 0, "股數": 0, "方向": "現買/現賣",
     "狀態": "完全成交/委託成功/委託失敗/委託已取消"}
  ],
  "備註": "..."
}
不要 ```json 包裝、直接 JSON。不確定欄位用 null。"""
        resp = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[prompt, image],
        )
        text = resp.text.strip()
        text = re.sub(r'^```json\s*|\s*```$', '', text, flags=re.MULTILINE).strip()
        text = re.sub(r'^```\s*|\s*```$', '', text, flags=re.MULTILINE).strip()
        data = json.loads(text)
    except Exception as e:
        print(f"  ❌ Gemini 解析失敗: {e}", flush=True)
        line_push.推播文字訊息(f"⚠️ 截圖 OCR 失敗: {str(e)[:100]}")
        return

    # 3. 組 Reply 訊息
    類型 = data.get("類型", "?")
    信心 = data.get("信心", 0)
    紀錄 = data.get("紀錄", [])

    lines = [f"📸 截圖已解析 ({類型}、信心 {信心}/100)"]
    lines.append("─" * 12)
    for i, r in enumerate(紀錄[:8], 1):
        name = r.get("股票名稱") or r.get("股票代號") or "?"
        if 類型 == "庫存查詢":
            股 = (r.get("現股") or 0) + (r.get("零股") or 0)
            lines.append(f"{i}. {name}: 持 {股} 股")
        elif 類型 == "委託清單":
            價 = r.get("委託價") or 0
            股 = r.get("股數") or 0
            方 = r.get("方向") or ""
            狀 = r.get("狀態") or ""
            lines.append(f"{i}. {name} {方} {股}股 @{價} ({狀})")
        elif 類型 == "成交明細":
            價 = r.get("成交價") or 0
            股 = r.get("股數") or 0
            方 = r.get("方向") or ""
            lines.append(f"{i}. {name} {方} {股}股 @{價}")
        else:
            lines.append(f"{i}. {name}")
    if len(紀錄) > 8:
        lines.append(f"...還有 {len(紀錄) - 8} 筆")
    lines.append("")
    lines.append("💡 之後會自動 sync portfolio.json")
    lines.append("（目前只解析、未自動寫入）")

    line_push.推播文字訊息("\n".join(lines))
    print(f"  ✅ 回 LINE: {類型}、{len(紀錄)} 筆", flush=True)


@app.get("/webhook")
def webhook_get():
    """LINE Verify 機制可能會先用 GET 確認 endpoint 存在 — 回 200 OK"""
    return {"status": "ready", "method": "POST 才是真正的 webhook"}


@app.post("/webhook")
async def webhook(request: Request,
                  x_line_signature: str = Header(None, alias="X-Line-Signature")):
    """LINE webhook 主入口"""
    body_bytes = await request.body()

    # 先解析 body 看是否是 LINE Verify（events 為空）
    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except Exception as e:
        print(f"[{datetime.now():%H:%M:%S}] ❌ JSON parse 失敗：{e}", flush=True)
        print(f"  body (前 200 bytes): {body_bytes[:200]}", flush=True)
        return {"ok": False}

    events = data.get("events", [])
    destination = data.get("destination", "")

    # ⭐ LINE Verify 機制：送 destination + 空 events 來測試 webhook
    # 跳過 signature 驗證直接回 200（不會觸發任何推播動作，安全）
    if not events:
        print(f"[{datetime.now():%H:%M:%S}] 🔍 LINE Verify ping "
              f"(destination={destination[:8] if destination else 'none'}...)",
              flush=True)
        # 記錄 signature debug 資訊（給之後 debug 用）
        if LINE_CHANNEL_SECRET and x_line_signature:
            expected = base64.b64encode(
                hmac.new(LINE_CHANNEL_SECRET.encode("utf-8"),
                         body_bytes, hashlib.sha256).digest()
            ).decode("utf-8")
            match = "✓" if hmac.compare_digest(expected, x_line_signature) else "✗"
            print(f"  signature 比對: {match}", flush=True)
            print(f"  LINE 送的: {x_line_signature[:20]}...", flush=True)
            print(f"  我算的:   {expected[:20]}...", flush=True)
            print(f"  secret 長度: {len(LINE_CHANNEL_SECRET)} chars", flush=True)
        return {"ok": True}

    # 真實 events：必須驗 signature
    if not 驗證簽章(body_bytes, x_line_signature):
        # 加 debug log 看 signature 哪裡不對
        if LINE_CHANNEL_SECRET:
            expected = base64.b64encode(
                hmac.new(LINE_CHANNEL_SECRET.encode("utf-8"),
                         body_bytes, hashlib.sha256).digest()
            ).decode("utf-8")
            print(f"[{datetime.now():%H:%M:%S}] ❌ Signature mismatch", flush=True)
            print(f"  LINE 送的: {x_line_signature[:20]}...", flush=True)
            print(f"  我算的:   {expected[:20]}...", flush=True)
            print(f"  body 前 100 bytes: {body_bytes[:100]}", flush=True)
        raise HTTPException(status_code=403, detail="Invalid signature")

    print(f"[{datetime.now():%H:%M:%S}] ✓ 收到 {len(events)} 個 events", flush=True)

    for event in events:
        evt_type = event.get("type", "")
        if evt_type == "postback":
            處理postback(event)
        elif evt_type == "message":
            msg = event.get("message", {})
            msg_type = msg.get("type", "")
            if msg_type == "text":
                text = msg.get("text", "")
                print(f"  message: {text[:50]}", flush=True)
            elif msg_type == "image":
                # ⭐ Phase 79b (5/18 10:45) — LINE 圖片接收、自動 OCR
                msg_id = msg.get("id")
                reply_token = event.get("replyToken")
                print(f"  image received: {msg_id}", flush=True)
                try:
                    處理截圖(msg_id, reply_token)
                except Exception as e:
                    print(f"  ❌ 截圖處理失敗: {e}", flush=True)

    return {"ok": True}


# ════════════════════════════════════════════
# Startup 健康驗證（給 Render Logs 看）
# ════════════════════════════════════════════
def _驗證啟動環境():
    print("=" * 50, flush=True)
    print("🚀 LIS Webhook Server 啟動驗證", flush=True)
    print("=" * 50, flush=True)

    # LINE_CHANNEL_SECRET
    if not LINE_CHANNEL_SECRET:
        print("⚠️  LINE_CHANNEL_SECRET 未設定（會跳過 signature 驗證）", flush=True)
    else:
        l = len(LINE_CHANNEL_SECRET)
        print(f"✓  LINE_CHANNEL_SECRET: {l} 字元", flush=True)
        if l != 32:
            print(f"⚠️  正常 LINE_CHANNEL_SECRET 應為 32 字元，目前 {l}", flush=True)
        # 確認是 hex 格式（LINE secret 通常是）
        try:
            int(LINE_CHANNEL_SECRET, 16)
            print(f"   格式: hex ✓", flush=True)
        except ValueError:
            print(f"   ⚠️ 不是 hex 格式（可能複製錯）", flush=True)
        # 印前 4 字元 + 後 4 字元（不洩漏完整 secret）
        if l >= 8:
            print(f"   前 4: {LINE_CHANNEL_SECRET[:4]}...{LINE_CHANNEL_SECRET[-4:]}", flush=True)

    # LINE_CHANNEL_ACCESS_TOKEN
    if not ACCESS_TOKEN:
        print("❌ LINE_CHANNEL_ACCESS_TOKEN 未設定（無法推 LINE）", flush=True)
    else:
        l = len(ACCESS_TOKEN)
        print(f"✓  LINE_CHANNEL_ACCESS_TOKEN: {l} 字元", flush=True)
        if l < 100:
            print(f"⚠️  ACCESS_TOKEN 通常 > 100 字元，目前 {l}（可能複製錯）", flush=True)

    # LINE_USER_ID
    if not DEFAULT_USER_ID:
        print("⚠️  LINE_USER_ID 未設定（postback 用 event source 的 userId）", flush=True)
    else:
        print(f"✓  LINE_USER_ID: {DEFAULT_USER_ID[:6]}...{DEFAULT_USER_ID[-4:]}", flush=True)

    print("=" * 50, flush=True)


_驗證啟動環境()


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    print(f"🚀 LIS Webhook Server starting on port {port}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port)
