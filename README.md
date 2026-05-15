# L.I.S 投資系統 — 程式碼

> "Life Is Shit. I should enjoy it, be Happy."

## 資料夾結構

```
D:\LIS股票投資系統\
├─ 文件\         設計藍圖（已存在）
├─ 程式碼\       本資料夾（Python 程式）
│   ├─ modules\         各功能模組
│   │   ├─ fear_greed.py    CNN 恐慌貪婪指數
│   │   ├─ technical.py     技術面掃描（RSI/MA）
│   │   ├─ news_ai.py       新聞 AI 摘要
│   │   ├─ enjoy_index.py   Enjoy Index 計算
│   │   └─ line_push.py     LINE 推播
│   ├─ main.py              主程式：每天 8:00 跑這支
│   ├─ test_*.py            每個模組的單獨測試腳本
│   └─ requirements.txt     需要安裝的 Python 套件
├─ API\          API Key 設定檔（.env，請勿外流）
└─ 數據\         每日抓到的數據與紀錄
    ├─ daily\           每日 JSON 快照
    └─ logs\            執行紀錄
```

## 怎麼跑

每個階段都用 `python test_xxx.py` 單獨測試一個模組。全部跑通後再執行 `python main.py` 跑完整流程。
