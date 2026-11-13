// Google Flights 精簡查價工具（排程用）。
// 用法：node tools/gflights.js "TPE OKA 2027-02-13 2027-02-18" "OKA TPE 2027-02-18" ...
//   4 個欄位 = 來回（出發地 目的地 去程日 回程日），列出去程班次與「來回票價」
//   3 個欄位 = 單程（出發地 目的地 日期），用來確認回程班次的起飛時間與單程價
// 每筆輸出一行一班：起飛-抵達(24h) 航空 價格；被 Google 擋下時印出 BLOCKED 並以代碼 2 結束。
// 注意：同一台機器短時間查約 15～20 次會被 Google 暫時擋下（顯示異常流量），每次執行請控制在 15 次以內。
// 價格為 1 位成人經濟艙、新台幣含稅；廉航不含託運行李。
const { chromium } = require('playwright');

const MAX_ROWS = Number(process.env.GF_ROWS || 8);
const PAUSE_MS = Number(process.env.GF_PAUSE || 6000);

function to24(s) {
  const m = s.match(/(清晨|凌晨|上午|中午|下午|晚上)?\s*(\d{1,2}):(\d{2})/);
  if (!m) return s.trim();
  let h = +m[2];
  const ap = m[1] || '';
  if ((ap === '下午' || ap === '晚上') && h < 12) h += 12;
  if (ap === '中午' && h < 11) h += 12;
  if ((ap === '凌晨' || ap === '清晨' || ap === '上午') && h === 12) h = 0;
  return String(h).padStart(2, '0') + ':' + m[3];
}

function parseRow(text) {
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
  const times = lines.filter((l) => /(清晨|凌晨|上午|中午|下午|晚上)\s*\d{1,2}:\d{2}/.test(l));
  const price = (text.match(/\$[\d,]+/) || [''])[0];
  const stopIdx = lines.findIndex((l) => /直達|轉機/.test(l));
  const stop = stopIdx >= 0 ? lines[stopIdx] : '';
  const route = lines.find((l) => /^[A-Z]{3}–[A-Z]{3}$/.test(l)) || '';
  const dur = lines.find((l) => /小時|分鐘/.test(l) && !/總交通/.test(l)) || '';
  const durIdx = lines.indexOf(dur);
  const air = durIdx > 0 ? lines[durIdx - 1] : '';
  if (times.length < 2 || !price) return null;
  const next = /\+1/.test(text) ? '+1' : '';
  return `${to24(times[0])}-${to24(times[1])}${next} ${air} ${route} ${stop} ${price}`.replace(/\s+/g, ' ').trim();
}

(async () => {
  const queries = process.argv.slice(2);
  if (!queries.length) { console.error('需要查詢參數'); process.exit(1); }
  const browser = await chromium.launch();
  const page = await browser.newPage({ locale: 'zh-TW', timezoneId: 'Asia/Taipei' });
  let blocked = false;
  for (const q of queries) {
    const f = q.trim().split(/\s+/);
    const text = f.length >= 4
      ? `Flights from ${f[0]} to ${f[1]} on ${f[2]} through ${f[3]}`
      : `One way flights from ${f[0]} to ${f[1]} on ${f[2]}`;
    const url = 'https://www.google.com/travel/flights?hl=zh-TW&curr=TWD&gl=TW&q=' + encodeURIComponent(text);
    console.log(`## ${q}（${f.length >= 4 ? '來回票價，列去程班次' : '單程'}）`);
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await page.waitForSelector('li.pIav2d', { timeout: 20000 }).catch(() => {});
      await page.waitForTimeout(1500);
      const body = await page.evaluate(() => document.body.innerText);
      if (/unusual traffic|異常流量|流量有異常|為何顯示此頁|recaptcha|我不是機器人/i.test(body) || /sorry\/index/.test(page.url())) {
        console.log('BLOCKED'); blocked = true; break;
      }
      const rows = await page.$$eval('li.pIav2d', (els) => els.map((e) => e.innerText));
      const seen = new Set(); let n = 0;
      for (const r of rows) {
        const line = parseRow(r);
        if (line && !seen.has(line)) { seen.add(line); console.log(line); if (++n >= MAX_ROWS) break; }
      }
      if (!n) console.log('（沒有結果）頁面：' + body.replace(/\s+/g, ' ').slice(0, 160));
      const note = body.match(/目前的(票價|價格)[^\n]*/);
      if (note) console.log('分析：' + note[0]);
    } catch (e) {
      console.log('ERROR ' + e.message.split('\n')[0]);
    }
    await page.waitForTimeout(PAUSE_MS);
  }
  await browser.close();
  process.exit(blocked ? 2 : 0);
})();
