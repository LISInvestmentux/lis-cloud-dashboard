"""
LINE Messaging API 推播模組
用 push message 主動發送訊息給指定 userId。
"""
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


# 從專案根目錄的 API 資料夾載入 .env
專案根 = Path(__file__).resolve().parent.parent.parent
load_dotenv(專案根 / "API" / ".env")

ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
DEFAULT_USER_ID = os.getenv("LINE_USER_ID", "").strip()

PUSH_API = "https://api.line.me/v2/bot/message/push"

# Phase 33.3 — 測試模式（避免爆 LINE 額度）
# 在 .env 加 LIS_TEST_MODE=true 或 export 環境變數即啟用
# 啟用後：所有推播只印到 console，不真的打 LINE API
def _測試模式() -> bool:
    return os.getenv("LIS_TEST_MODE", "").lower() in ("true", "1", "yes", "on")


def 推播文字訊息(訊息: str, user_id: str | None = None) -> dict:
    """
    主動推送純文字訊息到指定 LINE 用戶。

    Args:
        訊息: 要推播的文字內容（單則上限 5000 字元）
        user_id: 目標 userId；省略時用 .env 裡的 LINE_USER_ID

    Returns:
        LINE API 回傳的 JSON（成功時通常是 {}）

    Raises:
        ValueError: Token 或 userId 沒設好
        requests.HTTPError: API 回傳非 200
    """
    if _測試模式():
        print(f"[TEST_MODE] 跳過推播文字（節省額度）：{訊息[:100]}...",
              file=sys.stderr)
        return {"test_mode": True}

    if not ACCESS_TOKEN:
        raise ValueError("LINE_CHANNEL_ACCESS_TOKEN 未設定，請檢查 API/.env")

    目標 = user_id or DEFAULT_USER_ID
    if not 目標:
        raise ValueError("LINE_USER_ID 未設定，請檢查 API/.env")

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": 目標,
        "messages": [{"type": "text", "text": 訊息[:5000]}],
    }
    resp = requests.post(PUSH_API, headers=headers, json=payload, timeout=15)
    if resp.status_code != 200:
        print(f"[LINE] HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
    resp.raise_for_status()
    return resp.json() if resp.text else {}


def _淨化Flex(節點):
    """
    遞迴掃 flex 樹，把 type=text 但 text 為空/None 的修成 " "。
    LINE 不接受空 text，會回 400 Bad Request。
    """
    if isinstance(節點, dict):
        if 節點.get("type") == "text":
            t = 節點.get("text")
            if t is None or (isinstance(t, str) and t == "") or not isinstance(t, str):
                節點["text"] = " " if t in (None, "") else str(t)
        for v in 節點.values():
            _淨化Flex(v)
    elif isinstance(節點, list):
        for item in 節點:
            _淨化Flex(item)


def _寫推播狀態(alt: str, status_code: int, size_kb: float,
                err: str | None = None) -> None:
    """5/16 新增：每次推播都寫 jsonl 狀態 log，給 user 透明可見。
    路徑：數據/logs/push_status_YYYY-MM-DD.jsonl
    Console emoji 在 PowerShell 5.1 會被吃掉，所以必須有純文字 log。
    """
    try:
        from pathlib import Path
        from datetime import datetime
        import json as _json
        log_dir = Path(__file__).resolve().parent.parent.parent / "數據" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        path = log_dir / f"push_status_{today}.jsonl"
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "alt": (alt or "")[:80],
            "status": status_code,
            "size_kb": round(size_kb, 1),
            "ok": status_code == 200,
        }
        if err:
            record["error"] = str(err)[:200]
        with open(path, "a", encoding="utf-8") as f:
            f.write(_json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # log 寫失敗絕不影響主流程


def 推播Flex訊息(替代文字: str, flex內容: dict,
                  user_id: str | None = None) -> dict:
    """
    推送一則 Flex Message。
    Args:
        替代文字: 用戶 LINE App 不支援 Flex 時顯示的純文字（也用在通知欄）
        flex內容: bubble 或 carousel 物件
    """
    if _測試模式():
        # 仍跑淨化驗證 flex 結構 OK，但不真的推
        _淨化Flex(flex內容)
        print(f"[TEST_MODE] 跳過推播 Flex（節省額度）：{替代文字[:100]}",
              file=sys.stderr)
        return {"test_mode": True}

    if not ACCESS_TOKEN:
        raise ValueError("LINE_CHANNEL_ACCESS_TOKEN 未設定")
    目標 = user_id or DEFAULT_USER_ID
    if not 目標:
        raise ValueError("LINE_USER_ID 未設定")

    # Phase 33.2 — 推送前自動修空 text（防 400 Bad Request）
    _淨化Flex(flex內容)

    payload = {
        "to": 目標,
        "messages": [{
            "type": "flex",
            "altText": (替代文字 or " ")[:400],  # altText 上限 400
            "contents": flex內容,
        }],
    }
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    # 算 size 給 log 用
    import json as _j
    size_kb = len(_j.dumps(payload, ensure_ascii=False).encode("utf-8")) / 1024
    resp = requests.post(PUSH_API, headers=headers, json=payload, timeout=15)
    if resp.status_code != 200:
        print(f"[LINE Flex] HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
        _寫推播狀態(替代文字, resp.status_code, size_kb, err=resp.text[:200])
    else:
        _寫推播狀態(替代文字, 200, size_kb)
    resp.raise_for_status()
    return resp.json() if resp.text else {}


def 推播多則訊息(訊息陣列: list[str], user_id: str | None = None) -> dict:
    """
    一次推送多則訊息（LINE push API 單次最多 5 則）。
    超過 5 則自動分批呼叫 API。
    """
    if not 訊息陣列:
        return {}
    最後結果 = {}
    for i in range(0, len(訊息陣列), 5):
        批次 = 訊息陣列[i:i + 5]
        目標 = user_id or DEFAULT_USER_ID
        headers = {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "to": 目標,
            "messages": [{"type": "text", "text": m[:5000]} for m in 批次],
        }
        resp = requests.post(PUSH_API, headers=headers, json=payload, timeout=15)
        if resp.status_code != 200:
            print(f"[LINE] HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
        resp.raise_for_status()
        最後結果 = resp.json() if resp.text else {}
    return 最後結果


def 拆分長訊息(完整訊息: str, 上限: int = 4500) -> list[str]:
    """
    把長訊息切成多則。從段落（雙換行）切，盡量保持完整。
    上限留 4500（不是 5000）給 safety margin。
    """
    if len(完整訊息) <= 上限:
        return [完整訊息]
    段落 = 完整訊息.split("\n\n")
    結果 = []
    當前 = ""
    for p in 段落:
        加上後長度 = len(當前) + len(p) + 2
        if 加上後長度 <= 上限 or not 當前:
            當前 = (當前 + "\n\n" + p) if 當前 else p
        else:
            結果.append(當前)
            當前 = p
    if 當前:
        結果.append(當前)
    return 結果


if __name__ == "__main__":
    測試訊息 = (
        "🎉 L.I.S 投資系統 — LINE 推播測試成功！\n"
        "\n"
        "Life Is Shit. I should enjoy it, be Happy.\n"
        "\n"
        "✅ 通道：LIS 投資助理\n"
        "✅ 階段：MVP 第一階段建置中\n"
        "✅ 模組 A 已通過：CNN 恐慌貪婪指數抓取\n"
        "✅ 模組 D 已通過：LINE 推播\n"
        "\n"
        "下一步：技術面掃描（Alpha Vantage）"
    )
    print("正在推播測試訊息...")
    結果 = 推播文字訊息(測試訊息)
    print(f"推播成功 ✅  回傳：{結果}")
