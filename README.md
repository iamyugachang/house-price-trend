# 雙北房價趨勢（House Price Trend）

互動式房價頁（GH Pages 靜態站）：**單一組篩選器同時驅動「走勢圖 + 行情表」**——縣市/行政區(多選)/屋齡/類型/電梯/車位/主+陽/捷運/坪數/房數/統計期間/在售/資料源/分組(groupby)。分組值＝圖的一條線＝表的一列。

- 資料源：
  - asking = 平台刊登價（即時）；走勢線以「當月新上架(首見)」物件中位開價計
  - lvr = 內政部實價登錄成交（每季公布，揭露滯後 ~2 個月；`lvr_tx` 由 `tw-house lvr update` 匯入）；走勢線以交易月中位計
- 網站：`docs/index.html` 單頁 + `docs/data/`（由 `scripts/export_trend_data.py` 產出）
  - UI 讀取 fine pools：`listings-{region}.csv.gz`（asking）/ `listings-lvr-{region}.csv.gz`（成交），16 欄含 first_d
  - `trend-*.json`（market_grid 粗維度 run 序列）仍產出、供其他用途，頁面未使用

```bash
~/workspace/tw-house-daily/.venv/bin/python scripts/export_trend_data.py
```

自動化（Hermes cron）：
- 週一 04:30 `refresh_house_trend.sh`：重新 export + push（資料沒變就靜默）
- 每季 2/5/8/11 月 5 日 06:00 `update_lvr.sh`：`tw-house lvr update` 匯入最新實價登錄季

細維度行情水準資料（asking pool，`docs/data/listings-*.csv.gz`）欄位：
`src,district,type,elev,park,roof,age,m_acc,size,rooms,mrt,price,unit,last_d,act`
（type/elev/park/roof = -1 或空 = 未知；m_acc = 主+陽坪數）
