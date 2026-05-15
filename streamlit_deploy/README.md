# L.I.S 持股配置表單

L.I.S（Life Is Shit）投資系統的持股配置計算器。

幫你算出：**根據目前資金水位 + 模擬 Enjoy Index 分數 → 今日該動用多少子彈**。

## 用法

打開部署後的網址，填入：

- 台幣現金 / 美元現金 / 總資金
- 目前持股市值
- 策略模式（無腦 ETF / 一半存股一半短線 / 重壓一檔 / LIS 預設）

系統會依「Enjoy Index 三段火力」自動算出今日該動用的子彈金額。

## 本機跑

```bash
pip install -r requirements.txt
streamlit run portfolio_form.py
```

## 部署

推到 GitHub → 連 Streamlit Community Cloud（免費）→ 取得 https URL。
