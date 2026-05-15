"""
Streamlit Cloud 部署入口（Phase 33.2）

本機跑：照常讀 ../API/portfolio.json
雲端跑：從 st.secrets["PORTFOLIO_GIST_URL"] 抓 Gist 寫成本地暫存

執行流程：
  1. 試載入 secrets（有 = 雲端，沒 = 本機）
  2. 從 Gist 抓 portfolio.json 寫到 LIS_PORTFOLIO_PATH 環境變數指定的路徑
  3. exec web_dashboard.py
"""
import os
import sys
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def 載入雲端資料():
    """
    若有 st.secrets 就視為雲端：
      - 把 secrets 灌進 os.environ（給 LINE/Gemini 等模組用）
      - 從 PORTFOLIO_GIST_URL 抓最新 portfolio.json
      - 寫到 HERE/API/portfolio.json，並用 LIS_PORTFOLIO_PATH 環境變數告訴模組
    """
    try:
        import streamlit as st
    except ImportError:
        return False

    # 1. 灌環境變數
    secret_keys = [
        "LINE_CHANNEL_ACCESS_TOKEN", "LINE_USER_ID",
        "GEMINI_API_KEY", "FUGLE_MARKETDATA_API_KEY", "FUGLE_API_TOKEN",
        "ALPHA_VANTAGE_API_KEY", "NEWS_API_KEY",
    ]
    secrets_有設 = False
    for k in secret_keys:
        try:
            v = st.secrets.get(k, None)
        except Exception:
            v = None
        if v:
            os.environ[k] = str(v)
            secrets_有設 = True

    # 2. portfolio_gist
    try:
        url = st.secrets.get("PORTFOLIO_GIST_URL", None)
    except Exception:
        url = None
    if not url:
        return secrets_有設  # 沒 Gist URL → 本機跑

    # 3. 從 Gist 抓 portfolio.json
    try:
        import requests
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()

        # 寫到 HERE/API/portfolio.json（與本機相同 layout: 上一層 + API）
        # 雲端時 HERE.parent 可能只讀，所以 fallback 到 HERE / "API"
        for 候選 in [HERE.parent / "API" / "portfolio.json",
                     HERE / "API" / "portfolio.json"]:
            try:
                候選.parent.mkdir(parents=True, exist_ok=True)
                候選.write_text(
                    json.dumps(data, ensure_ascii=False),
                    encoding="utf-8")
                os.environ["LIS_PORTFOLIO_PATH"] = str(候選)
                st.sidebar.success(f"☁️ 雲端模式 — 從 Gist 載入 {len(data.get('current_positions', []))} 檔持股")
                return True
            except (PermissionError, OSError):
                continue
        st.sidebar.error("❌ 無法寫入 portfolio.json 暫存")
    except Exception as e:
        st.sidebar.error(f"❌ Gist 載入失敗：{e}")

    return True


載入雲端資料()


# 跳到實際 dashboard
exec(open(HERE / "web_dashboard.py", encoding="utf-8").read())
