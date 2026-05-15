"""
Streamlit Cloud 部署入口（Phase 33.2 v2）

關鍵：完全不要在 set_page_config 之前呼叫任何 st 函式（會 raise StreamlitAPIException）
做法：
  1. 直接 print 訊息到 logs（不用 st.xxx）
  2. 讀 secrets + 灌環境變數
  3. 從 Gist 抓 portfolio.json 寫到 /tmp（保證可寫）
  4. exec web_dashboard.py（它自己會 set_page_config）

雲端紀錄看：Streamlit Cloud → Manage app → Logs
"""
import os
import sys
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def 載入雲端資料():
    """
    雲端：從 st.secrets 拉 + 從 Gist 抓 portfolio.json
    本機：跳過（st.secrets 為空 / 沒有 PORTFOLIO_GIST_URL）

    全程不呼叫 st.xxx 函式，避免 set_page_config 衝突。
    """
    try:
        import streamlit as st
    except ImportError:
        print("[streamlit_app] streamlit 未安裝", file=sys.stderr)
        return

    # 1. 灌環境變數
    secret_keys = [
        "LINE_CHANNEL_ACCESS_TOKEN", "LINE_USER_ID",
        "GEMINI_API_KEY", "FUGLE_MARKETDATA_API_KEY", "FUGLE_API_TOKEN",
        "ALPHA_VANTAGE_API_KEY", "NEWS_API_KEY",
    ]
    secret_count = 0
    for k in secret_keys:
        try:
            v = st.secrets.get(k, None) if hasattr(st, "secrets") else None
        except Exception:
            v = None
        if v:
            os.environ[k] = str(v)
            secret_count += 1
    print(f"[streamlit_app] 灌入 {secret_count} 個環境變數", file=sys.stderr)

    # 2. portfolio_gist URL
    try:
        url = st.secrets.get("PORTFOLIO_GIST_URL", None) if hasattr(st, "secrets") else None
    except Exception:
        url = None

    if not url:
        print("[streamlit_app] 無 PORTFOLIO_GIST_URL → 本機模式", file=sys.stderr)
        return

    # 3. 從 Gist 抓 portfolio.json
    try:
        import requests
        print(f"[streamlit_app] 從 Gist 抓 portfolio.json: {url[:80]}...", file=sys.stderr)
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        持股數 = len(data.get("current_positions", []))
        print(f"[streamlit_app] ✅ Gist 抓取成功：{持股數} 檔持股", file=sys.stderr)

        # 4. 寫到可寫位置（多個 fallback）
        候選清單 = [
            HERE.parent / "API" / "portfolio.json",         # 跟本機 layout 一樣
            HERE / "API" / "portfolio.json",                 # repo 內 fallback
            Path(tempfile.gettempdir()) / "lis_portfolio.json",  # /tmp 保證可寫
        ]
        for 候選 in 候選清單:
            try:
                候選.parent.mkdir(parents=True, exist_ok=True)
                候選.write_text(
                    json.dumps(data, ensure_ascii=False),
                    encoding="utf-8")
                os.environ["LIS_PORTFOLIO_PATH"] = str(候選)
                print(f"[streamlit_app] ✅ 寫入 portfolio.json → {候選}", file=sys.stderr)
                return
            except (PermissionError, OSError) as e:
                print(f"[streamlit_app] ⚠️ {候選} 寫入失敗: {e}", file=sys.stderr)
                continue
        print("[streamlit_app] ❌ 所有候選路徑都無法寫入", file=sys.stderr)

    except Exception as e:
        print(f"[streamlit_app] ❌ Gist 載入失敗: {e}", file=sys.stderr)


def 建立雲端placeholder():
    """
    雲端缺的資料檔（本機才有）建立空 placeholder，避免 FileNotFoundError。
    這些檔案在本機由排程任務每天更新，雲端用空 placeholder + 即時 yfinance 取代。
    """
    candidates = [
        # path, default_content
        (HERE.parent / "數據" / "positional_state.json",
         {"scores": {}, "details": {}, "_說明": "雲端 placeholder（本機才有真實資料）"}),
        (HERE.parent / "數據" / "win_rate_db.json",
         {"標的": {}, "_說明": "雲端 placeholder"}),
        (HERE.parent / "數據" / "sylvie_portfolio.json",
         {"持股": [], "已實現": [], "_說明": "雲端 placeholder"}),
        (HERE.parent / "數據" / "sylvie_snapshot.json",
         {"持股": [], "已實現": []}),
        (HERE.parent / "數據" / "cache" / "fg_history.json",
         []),
        (HERE.parent / "API" / "watchlist.json",
         {"regions": [], "_說明": "雲端 placeholder — 請從本機推 watchlist 到 Gist"}),
    ]
    for path, default in candidates:
        if path.exists():
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(default, ensure_ascii=False),
                encoding="utf-8")
            print(f"[streamlit_app] placeholder 建立: {path.name}", file=sys.stderr)
        except (PermissionError, OSError) as e:
            print(f"[streamlit_app] placeholder 失敗 {path.name}: {e}", file=sys.stderr)


# 先載入再 exec（這時 web_dashboard 自己會跑 set_page_config）
載入雲端資料()
建立雲端placeholder()

# exec 實際 dashboard
dashboard_path = HERE / "web_dashboard.py"
exec(open(dashboard_path, encoding="utf-8").read())
