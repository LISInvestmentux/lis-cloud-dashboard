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


@app.post("/webhook")
async def webhook(request: Request,
                  x_line_signature: str = Header(None, alias="X-Line-Signature")):
    """LINE webhook 主入口"""
    body_bytes = await request.body()

    if not 驗證簽章(body_bytes, x_line_signature):
        print(f"❌ 簽章驗證失敗", flush=True)
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except Exception as e:
        print(f"❌ JSON parse 失敗：{e}", flush=True)
        return {"ok": False}

    events = data.get("events", [])
    print(f"[{datetime.now():%H:%M:%S}] 收到 {len(events)} 個 events", flush=True)

    for event in events:
        evt_type = event.get("type", "")
        if evt_type == "postback":
            處理postback(event)
        elif evt_type == "message":
            # 收到文字訊息 — 可日後擴充對話功能
            text = event.get("message", {}).get("text", "")
            print(f"  message: {text[:50]}", flush=True)

    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    print(f"🚀 LIS Webhook Server starting on port {port}")
    print(f"   LINE_CHANNEL_SECRET: {'✓' if LINE_CHANNEL_SECRET else '✗'}")
    print(f"   LINE_CHANNEL_ACCESS_TOKEN: {'✓' if ACCESS_TOKEN else '✗'}")
    uvicorn.run(app, host="0.0.0.0", port=port)
