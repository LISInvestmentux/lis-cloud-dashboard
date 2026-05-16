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
            text = event.get("message", {}).get("text", "")
            print(f"  message: {text[:50]}", flush=True)

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
