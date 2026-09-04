# 雙北房價趨勢（House Price Trend）

互動式房價趨勢圖（GH Pages 靜態站）：依行政區 × 坪數 × 房數 × 統計期間篩選，看刊登行情中位價隨時間的走勢。

- 資料源：tw-house-daily 每日 08:00/20:00 `market_grid` 快照（asking 刊登價，n≥5）
- 網站：`docs/index.html` + `docs/data/*.json`（由 `scripts/export_trend_data.py` 產出）
- 更新：跑 export 後 commit push 即可；GH Pages 從 main 分支 `/docs` 自動發布

```bash
~/workspace/tw-house-daily/.venv/bin/python scripts/export_trend_data.py
```

注意：lvr（實價登錄成交）側自 2026-05 起無資料，圖表僅含 asking。
