# 雙北房價趨勢（House Price Trend）

互動式房價趨勢圖（GH Pages 靜態站）：依行政區 × 坪數 × 房數 × 統計期間篩選，**刊登價 vs 實價登錄成交價** 雙線比較。

- 資料源：tw-house-daily 每日 08:00/20:00 `market_grid` 快照
  - asking = 平台刊登價（即時）
  - lvr = 內政部實價登錄成交（每季公布，揭露滯後 ~2 個月；`lvr_tx` 由 `tw-house lvr update` 匯入）
- 網站：`docs/index.html` 單頁 = 長期走勢圖（刊登 vs 成交）+ 行情水準表（屋齡/類型/電梯/車位/主+陽/捷運 細維度過濾、刊登/成交並排）＋ `docs/data/*.json|csv.gz`（由 `scripts/export_trend_data.py` 產出）
- 更新：跑 export 後 commit push 即可；GH Pages 從 main 分支 `/docs` 自動發布

```bash
~/workspace/tw-house-daily/.venv/bin/python scripts/export_trend_data.py
```

自動化（Hermes cron）：
- 週一 04:30 `refresh_house_trend.sh`：重新 export + push（資料沒變就靜默）
- 每季 2/5/8/11 月 5 日 06:00 `update_lvr.sh`：`tw-house lvr update` 匯入最新實價登錄季

細維度行情水準資料（asking pool，`docs/data/listings-*.csv.gz`）欄位：
`src,district,type,elev,park,roof,age,m_acc,size,rooms,mrt,price,unit,last_d,act`
（type/elev/park/roof = -1 或空 = 未知；m_acc = 主+陽坪數）
