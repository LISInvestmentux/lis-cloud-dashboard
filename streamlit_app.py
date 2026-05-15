"""
Streamlit Cloud 部署入口（Phase 33.2）

Streamlit Cloud 預期 streamlit_app.py 當入口 — 這個檔導向實際的 web_dashboard.py。

雲端 vs 本機差異：
- 本機 → 讀 ../API/portfolio.json
- 雲端 → 讀 st.secrets["PORTFOLIO_GIST_URL"]（私密 Gist）

部署步驟見 程式碼/DEPLOY.md
"""
import os
import sys
from pathlib import Path

# 加入專案根
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Streamlit Cloud 偵測（環境變數 STREAMLIT_RUNTIME）
IS_CLOUD = os.getenv("HOSTNAME", "").startswith("streamlit") or \
           os.getenv("STREAMLIT_SERVER_PORT") == "8501"


def 載入雲端資料():
    """雲端模式：從 Streamlit secrets 拉資料"""
    import streamlit as st
    import requests
    import json

    try:
        # portfolio.json 從 Gist
        url = st.secrets.get("PORTFOLIO_GIST_URL", "")
        if url:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            portfolio_data = r.json()
            # 寫成暫存檔讓既有模組讀得到
            tmp_dir = HERE.parent / "API"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            (tmp_dir / "portfolio.json").write_text(
                json.dumps(portfolio_data, ensure_ascii=False),
                encoding="utf-8")

        # 環境變數從 secrets
        for k in ["LINE_CHANNEL_ACCESS_TOKEN", "LINE_USER_ID",
                  "GEMINI_API_KEY", "FUGLE_API_TOKEN"]:
            v = st.secrets.get(k, "")
            if v:
                os.environ[k] = str(v)
    except Exception as e:
        st.warning(f"⚠️ 雲端 secrets 載入問題：{e}")


if IS_CLOUD:
    載入雲端資料()

# 跳到實際 dashboard
exec(open(HERE / "web_dashboard.py", encoding="utf-8").read())
