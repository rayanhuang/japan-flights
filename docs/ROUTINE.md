# 每日排程流程（省 token 版，2026-11-14 起）

## 為什麼改
11/14 那次排程用了約 15～17 萬 token，其中約 7 萬是「把整份舊網頁 HTML 讀進來兩次」，約 3 萬是「手寫整頁新 HTML」。
改成「資料（JSON）＋固定外框」後，每天只需要讀一份精簡摘要、改資料、跑程式產生網頁：

| 步驟 | 舊做法 | 新做法 |
|---|---|---|
| 了解前一天狀態 | 讀整個 Claude 網頁（約 80KB，讀兩次） | `python3 tools/build.py --summary`（約 2KB） |
| 產生網頁 | 手寫整頁 HTML（約 60KB） | 用小段 python 改 `data/report.json`，`python3 tools/build.py` 產生 |
| Claude 網頁 | 每次重送整頁 | 頁面只剩約 0.5KB 外框，每天只重送 `assets/content.js` |
| 計算請假、總價、排名、警報、促銷是否結束 | 人工 | 程式自動算並驗證（減少錯誤） |

預估每次可從約 16 萬降到約 6～8 萬 token（查價的 15 筆 Google Flights 輸出不變）。

## 檔案
- `data/report.json`：今天的內容（每個目的地的方案、今天重點、參考價、促銷、行李費、資料缺口、來源）。**每天要更新的就是這個檔**。
- `data/log.json`：📈 每日最低價紀錄（新到舊）。**不要手改**，`build.py` 會自動加今天那列、保留 30 天。
- `data/returns.json`：已確認的回程班次（航線、日期、航空、起飛時間、來源、確認日）。同航空同日期已確認過就沿用，不必再查。
- `assets/style.css`、`assets/app.js`：固定的樣式與互動版腳本（分頁、篩選、趨勢圖），**不要改**。
- `assets/content.js`、`index.html`、`build/artifact.html`、`build/notify.txt`：由 `tools/build.py` 產生。
- `tools/gflights.js`：Google Flights 精簡查價工具（不變）。

## report.json 每一列（dests[].rows[]）的欄位
```json
{"air":"台灣虎航","kind":"lcc","out":"2027-06-17","ret":"2027-06-22",
 "flights":"去 15:30→19:55 桃園→成田<br>回 20:45→23:25 成田→桃園",
 "retDep":"20:45","fare":9010,"bag":1900,"bagText":"約 1,900（估，950/段）","approx":true,
 "note":"Google Flights（2026-11-14）來回價…","gfLow":null}
```
- `kind`：`lcc`（廉航）／`fsc`（華航、長榮、星宇）／`other`（國泰、日航等）
- `retDep`：回程**日本當地起飛時間**，一定要是確認過的（Google 單程、`returns.json` 或官方班表）。查不到就不能當推薦，改寫進 `refList`，或整列加 `"ref":true`（只在該目的地沒有任何符合方案時才顯示）。
- `fare`：票價；`bag`：來回行李費（廉航必填，傳統航空 0）；`approx`：總價是估算時 true（顯示 ≈）。
- `gfLow`：gflights.js「分析：」那行寫「偏低…比平常便宜了 $N」時填 N（只填在那筆查詢的最便宜、而且符合條件的那一列），否則 null。
- 不用寫：星期、玩幾天、請假天數／日期、含行李總價、名次、🔥 標籤，都由程式算。
- 其他欄位：`updated`（"YYYY-MM-DD HH:MM"）、`subNote`、`takeaway`（今天重點，**不要**寫降價警報那段，程式會自動加在最前面）、`caveat`、`bestIntro`、`refList`、`promos`（`deadline` 填 YYYY-MM-DD，程式自動判斷「今天截止／明天截止／已結束」）、`promoNote`、`baggage`、`baggageNote`、`gaps`、`sources`、`logNote`、`windowExtras`（官網低價頁等「有價格但不在前三名」的省假窗口：`{"out","ret","label"}`，label 要寫查到的日期）、`notify.promo`、`notify.method`。

## build.py 會擋下的錯誤（看到「錯誤：」就修資料再跑一次）
出發日不在今天 +3～+12 個月內、玩不是 4～6 天、請假 > 4 天、回程早於 12:00 或沒填、廉航沒加行李費、同一航空同一出發＋回程日期重複、目的地順序或名稱不對、某目的地完全沒有方案。
「同一航空同一日期不重複列」解讀為「出發＋回程日期都相同」才算重複；同一天出發、不同天回來（例如 6/6–6/10 與 6/6–6/11）算不同方案。
國定假日目前只有 2027 年（`HOLIDAYS`）；範圍跨到 2028 年時程式會提示，查到 117 年辦公日曆表後加進 `HOLIDAYS` 並把 2028 加入 `KNOWN_YEARS`。

## 降價警報（程式自動判斷，規則同排程第三之二節）
1. 今天第 1 名比 `log.json` 最近一次有數字的那天便宜 ≥15%，或低於最近 30 天最低值（只看 2026-11-13 起的新條件紀錄）。
2. 符合條件的列 `gfLow` ≥ 2,000。
觸發時自動：今天重點最前面加「🔥 降價警報：…」、該列備註加 🔥 降價、📈 紀錄加 🔥、`build/notify.txt` 第一行改成「🔥 降價警報 YYYY-MM-DD」。

---

## 貼到排程的新版第五～八節（取代原本的第五～八節，第一～四節不變）

> 下面這段是建議的排程文字，請自行貼到排程設定裡（Claude 沒辦法改排程內容）。

```
## 五、怎麼查（2026-11-14 更新：資料檔＋程式產生網頁，省用量）
0. 先準備 repo（見第七節第 2 步），然後執行 python3 <repo>/tools/build.py --summary。這份摘要就是「前一天的狀態」：各目的地前三名的日期與價格、最近一天的紀錄、已確認的回程班次、進行中的促銷。不要為了看前一天的內容去讀整個 Claude 網頁或 index.html，也不要整份讀 data/report.json（只用 python 印出需要的欄位）。
A. 主要方法：tools/gflights.js（用法、次數上限 15 筆、BLOCKED 就停、判讀方式都和之前一樣）。挑日期：摘要裡每個目的地的日期（超出範圍的要換），以及 build.py 算出的省假窗口。回程時間：摘要的「已確認的回程班次」同航空同日期可以沿用；新確認的班次用 python 加進 data/returns.json（route、date、air、deps、src、checked）。
B. 不要用：Skyscanner、Trip.com、攜程、Google Flights 優惠頁。
C. 補充方法（A 沒結果的目的地才用）：WebSearch／WebFetch，每個目的地最多 2 頁、整次最多 8 頁；促銷只用 1～2 次 WebSearch。
- 不要杜撰價格或班機時間；回程時間沒確認的不能當推薦（改列參考價）。

## 六、更新資料並產生網頁（每次都要做）
1. 用一小段 python（json.load → 修改 → json.dump(ensure_ascii=False, indent=1)）更新 <repo>/data/report.json：updated、subNote、takeaway（不要寫降價警報那段，程式會自動加）、caveat、dests（10 個目的地、每個最多 3 列符合條件的方案；欄位說明見 docs/ROUTINE.md）、refList、promos（deadline 用 YYYY-MM-DD）、gaps、sources、logNote、windowExtras、notify.promo、notify.method。不要手改 data/log.json。
2. 執行 python3 <repo>/tools/build.py。有「錯誤：」就修正資料再跑，直到沒有錯誤；「注意：」要在備註或資料缺口說明。程式會產生 assets/content.js、index.html、build/artifact.html、build/notify.txt，並自動算好請假天數、總價、排名、降價警報、每日紀錄、促銷是否結束、省假窗口。不要手寫或手改這些產生出來的檔案。
3. 更新 Claude 網頁 https://claude.ai/artifact/GnK4JjZSrefEVotecoMzQn（不要建立新網頁）：先用 Artifact 工具 action "read" 讀一次（現在頁面只有約 0.5KB 外框），再 publish：url 同上、file_path 為 <repo>/build/artifact.html、files 為 {"assets/content.js": "<repo>/assets/content.js"}、label 填今天日期。只有 assets/style.css 或 assets/app.js 有改時才一起送。版本衝突就重新 read 再發佈。失敗不要建立新網頁，在通知中說明，並繼續第七節。

## 七、同步到公開網站（https://rayanhuang.github.io/japan-flights/）
1. 公開版已由 build.py 產生（repo 根目錄 index.html＋assets/），不用另外包。
2. 準備 repo：同之前（找現成 clone；找不到才 add_repo）。拿到後 cd <repo> && git fetch origin main && git checkout -B <分支> origin/main，再做第五節。分支名稱用執行環境指定的開發分支；沒有指定才用 daily-flights-YYYYMMDD-HHMM。
3. 若找不到 add_repo 或沒有權限：不要重試、不要建 repo，在通知中說明原因。
4. git add index.html assets/content.js data/report.json data/log.json data/returns.json。沒有變更就不 commit，通知寫「公開網站無變更」。有變更就 commit（訊息「更新日本機票監控（M/D）」）並 push；失敗不要重試，在通知中說明。
5. 建立 PR（base main，標題同 commit，內文「每日自動更新機票價格頁；價格為查詢時價格，以訂票頁為準」），可用 GitHub MCP 工具或 gh api REST。
6. 自行合併（我本人同意）：PR 只動到 index.html、assets/content.js、data/report.json、data/log.json、data/returns.json，mergeable_state 為 clean，沒有失敗的檢查，就 squash 合併並註明公開網站約 1–2 分鐘後更新。動到其他檔案（例如 tools/、assets/style.css、assets/app.js）就不要合併，在通知中附 PR 連結請我看。合併被擋就附 PR 連結。

## 八、通知
用 PushNotification（或 SendUserMessage）傳 <repo>/build/notify.txt 的內容（第一行已自動處理降價警報），最後補上 GitHub PR 連結或同步失敗原因。完整報告（每個目的地前三名）放在最後的回覆中。
```
