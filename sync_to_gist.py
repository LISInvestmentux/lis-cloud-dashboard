"""
portfolio.json 同步到 GitHub Gist（Phase 33.2 雲端輔助）

買賣後改完 portfolio.json，跑一次 → 自動更新 Gist → Streamlit Cloud 看新資料

使用：
  python sync_to_gist.py              # 同步 portfolio.json
  python sync_to_gist.py --sylvie     # 同步 sylvie_portfolio.json
  python sync_to_gist.py --all        # 兩個都同步

設定（API/.env）：
  GITHUB_TOKEN=ghp_xxx  (Personal Access Token，scope: gist)
  GIST_ID_PORTFOLIO=abc123
  GIST_ID_SYLVIE=def456

第一次：去 https://gist.github.com 建立 Secret Gist，貼 portfolio.json
        → 從 URL 抓 Gist ID 填進 .env
"""
import os
import sys
import json
import requests
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

專案根 = Path(__file__).resolve().parent.parent

from dotenv import load_dotenv
load_dotenv(專案根 / "API" / ".env")

GH_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GIST_PORTFOLIO = os.getenv("GIST_ID_PORTFOLIO", "").strip()
GIST_SYLVIE = os.getenv("GIST_ID_SYLVIE", "").strip()

API_BASE = "https://api.github.com"


def 更新Gist(gist_id: str, filename: str, content: str) -> bool:
    """PATCH 一個 Gist 的某個檔案"""
    if not GH_TOKEN:
        print("❌ 未設 GITHUB_TOKEN")
        return False
    if not gist_id:
        print(f"❌ 未設 Gist ID（{filename}）")
        return False

    url = f"{API_BASE}/gists/{gist_id}"
    headers = {
        "Authorization": f"token {GH_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "LIS-sync",
    }
    payload = {
        "files": {
            filename: {"content": content}
        }
    }
    r = requests.patch(url, headers=headers, json=payload, timeout=15)
    if r.status_code == 200:
        gist = r.json()
        print(f"✅ 已更新 Gist {gist_id}/{filename}")
        print(f"   URL: {gist['html_url']}")
        # raw URL
        raw_url = gist["files"][filename]["raw_url"]
        print(f"   Raw: {raw_url}")
        return True
    else:
        print(f"❌ Gist 更新失敗 ({r.status_code}): {r.text[:200]}")
        return False


def 同步portfolio() -> bool:
    path = 專案根 / "API" / "portfolio.json"
    if not path.exists():
        print(f"❌ 找不到 {path}")
        return False
    return 更新Gist(GIST_PORTFOLIO, "portfolio.json",
                    path.read_text(encoding="utf-8"))


def 自動同步(silent: bool = True) -> bool:
    """給 push 流程呼叫的 silent helper — 失敗也不爆推播流程"""
    import io, contextlib
    try:
        if silent:
            with contextlib.redirect_stdout(io.StringIO()):
                return 同步portfolio()
        return 同步portfolio()
    except Exception as e:
        if not silent:
            print(f"⚠️ auto sync 失敗（不影響推播）：{e}")
        return False


def 同步sylvie() -> bool:
    path = 專案根 / "數據" / "sylvie_portfolio.json"
    if not path.exists():
        print(f"❌ 找不到 {path}")
        return False
    return 更新Gist(GIST_SYLVIE, "sylvie_portfolio.json",
                    path.read_text(encoding="utf-8"))


def 建立新Gist(filename: str, content: str, public: bool = False) -> str:
    """第一次用：建立新 Gist，回傳 ID"""
    if not GH_TOKEN:
        print("❌ 未設 GITHUB_TOKEN")
        return ""
    url = f"{API_BASE}/gists"
    headers = {
        "Authorization": f"token {GH_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "LIS-sync",
    }
    payload = {
        "description": f"LIS {filename}（自動同步）",
        "public": public,
        "files": {filename: {"content": content}},
    }
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    if r.status_code == 201:
        g = r.json()
        print(f"✅ 已建立 Gist：{g['id']}")
        print(f"   填進 .env: GIST_ID_{filename.split('.')[0].upper()}={g['id']}")
        return g["id"]
    else:
        print(f"❌ 建立失敗 ({r.status_code}): {r.text[:200]}")
        return ""


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--init" in args:
        # 第一次用：建立兩個 Gist
        print("📋 第一次設定：建立 portfolio + sylvie 兩個 Secret Gist")
        p_path = 專案根 / "API" / "portfolio.json"
        s_path = 專案根 / "數據" / "sylvie_portfolio.json"
        if p_path.exists():
            建立新Gist("portfolio.json", p_path.read_text(encoding="utf-8"))
        if s_path.exists():
            建立新Gist("sylvie_portfolio.json", s_path.read_text(encoding="utf-8"))
        print("\n→ 把上面的 Gist ID 填進 API/.env 後，再跑：")
        print("   python sync_to_gist.py --all")
        sys.exit(0)

    成功 = []
    失敗 = []
    if "--sylvie" in args or "--all" in args:
        (成功 if 同步sylvie() else 失敗).append("sylvie")
    if "--sylvie" not in args or "--all" in args:
        (成功 if 同步portfolio() else 失敗).append("portfolio")

    print(f"\n📊 結果：成功 {成功} / 失敗 {失敗}")
    sys.exit(0 if not 失敗 else 1)
