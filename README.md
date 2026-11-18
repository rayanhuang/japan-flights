# japan-flights
日本機票監控（每日排程自動更新）：https://rayanhuang.github.io/japan-flights/

- `data/`：每日資料（report.json 今天內容、log.json 每日最低價紀錄、returns.json 已確認回程班次）
- `tools/build.py`：驗證資料並產生網頁（`--summary` 印出精簡摘要）
- `tools/gflights.js`：Google Flights 精簡查價工具
- `assets/`：樣式、互動腳本與產生的內容
- 每日流程與排程文字：[docs/ROUTINE.md](docs/ROUTINE.md)
