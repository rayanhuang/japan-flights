#!/usr/bin/env python3
"""日本機票監控：由 data/*.json 產生網頁（省 token 版，2026-11-14）。

用法：
  python3 tools/build.py --summary   # 印出精簡摘要（前次各目的地前三名日期、紀錄、已確認回程），排程開頭用，不必讀整個網頁
  python3 tools/build.py             # 驗證資料 → 產生 assets/content.js、index.html（公開網站）、build/artifact.html（Claude 網頁）、build/notify.txt

會自動計算（不要手算）：
  - 搜尋範圍（今天 +3～+12 個月）、每列的星期、玩幾天、請假天數與日期（依 2027 辦公日曆，見 HOLIDAYS）
  - 含行李總價＝票價＋行李費、每個目的地依總價（同價請假少優先）排序取前 3 名
  - 降價警報（跌幅 15%／30 天新低／Google 偏低 ≥ 2,000）、📈 每日紀錄（今天那列、保留 30 天）
  - 促銷是否已結束（依 deadline 與今天比較）、🗓️ 最省假窗口與有價格的窗口
驗證失敗（日期超出範圍、玩不是 4～6 天、請假 > 4 天、回程早於 12:00、同航空同日期重複…）會列出錯誤並以代碼 1 結束，不會產生網頁。
"""
import datetime as D
import html
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
ARTIFACT_URL = 'https://claude.ai/artifact/GnK4JjZSrefEVotecoMzQn'
PUBLIC_URL = 'https://rayanhuang.github.io/japan-flights/'
DESTS = ['東京', '大阪', '名古屋', '福岡', '熊本', '廣島', '鹿兒島', '沖繩', '北海道', '仙台']
NEW_RULES_FROM = '2026-11-13'  # 這天起才是新條件（玩 4～6 天、請假 ≤4 天），降價警報只跟這之後的紀錄比
WD = '一二三四五六日'
SHORT = {'台灣虎航': '虎航', '中華航空': '華航', '星宇航空': '星宇', '長榮航空': '長榮', '國泰航空': '國泰',
         '亞洲航空': '亞航', '捷星日本': '捷星', '泰國亞洲航空': '泰亞航', '日本航空': '日航', '全日空': '全日空'}

# 人事行政總處 116 年（2027）辦公日曆表：放假日（含補假），全年無補班。2028 公布後加在這裡並把年份加入 KNOWN_YEARS。
HOLIDAYS = {
    '元旦': ('2027-01-01', '2027-01-03'), '春節': ('2027-02-04', '2027-02-10'), '228': ('2027-02-27', '2027-03-01'),
    '兒童節＋清明': ('2027-04-03', '2027-04-06'), '勞動節': ('2027-04-30', '2027-05-02'), '端午': ('2027-06-09', '2027-06-09'),
    '中秋': ('2027-09-15', '2027-09-15'), '教師節': ('2027-09-28', '2027-09-28'), '國慶': ('2027-10-09', '2027-10-11'),
    '光復節': ('2027-10-23', '2027-10-25'), '行憲紀念日': ('2027-12-24', '2027-12-26'), '補假': ('2027-12-31', '2027-12-31'),
}
KNOWN_YEARS = {2027}
HOL = {}
for _n, (_a, _b) in HOLIDAYS.items():
    _d = D.date.fromisoformat(_a)
    while _d <= D.date.fromisoformat(_b):
        HOL[_d] = _n
        _d += D.timedelta(1)

esc = html.escape


def load(name):
    with open(os.path.join(DATA, name), encoding='utf8') as f:
        return json.load(f)


def save(name, obj):
    with open(os.path.join(DATA, name), 'w', encoding='utf8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write('\n')


def add_months(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    m += 1
    import calendar
    return D.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def today_tw():
    return D.datetime.now(ZoneInfo('Asia/Taipei')).date()


def leave_days(a, b):
    out, d = [], a
    while d <= b:
        if d.weekday() < 5 and d not in HOL:
            out.append(d)
        d += D.timedelta(1)
    return out


def md(d):
    return f'{d.month}/{d.day}'


def mdw(d):
    return f'{d.month}/{d.day}（{WD[d.weekday()]}）'


def fmt(n):
    return f'{n:,}'


def leave_text(lv):
    if not lv:
        return '不用請假'
    return '請 ' + '、'.join(md(x) for x in lv)


def short(air):
    return SHORT.get(air, air)


def range_of(today):
    return add_months(today, 3), add_months(today, 12)


# ---------------------------------------------------------------- 驗證與計算
def prepare(rep, today):
    lo, hi = range_of(today)
    errs, warns = [], []
    names = [d['name'] for d in rep['dests']]
    if names != DESTS:
        errs.append(f'dests 順序或名稱要是 {DESTS}，目前是 {names}')
    for dest in rep['dests']:
        seen = set()
        for r in dest['rows']:
            tag = f"{dest['name']} {r.get('air')} {r.get('out')}"
            if r.get('out'):
                a, b = D.date.fromisoformat(r['out']), D.date.fromisoformat(r['ret'])
                r['_a'], r['_b'] = a, b
                r['_days'] = (b - a).days + 1
                r['_leave'] = leave_days(a, b)
                if a.year not in KNOWN_YEARS or b.year not in KNOWN_YEARS:
                    warns.append(f'{tag}：{a.year} 年國定假日未知，只用週末計算請假')
                if not r.get('ref'):
                    if not (lo <= a <= hi):
                        errs.append(f'{tag}：出發日不在搜尋範圍 {lo}～{hi}')
                    if not 4 <= r['_days'] <= 6:
                        errs.append(f'{tag}：玩 {r["_days"]} 天，要 4～6 天')
                    if len(r['_leave']) > 4:
                        errs.append(f'{tag}：要請 {len(r["_leave"])} 天，超過 4 天')
            elif not r.get('ref'):
                errs.append(f'{tag}：非參考價一定要有 out/ret 日期')
            if not r.get('ref'):
                if not r.get('retDep') or not re.fullmatch(r'\d{2}:\d{2}', r['retDep']):
                    errs.append(f'{tag}：retDep（回程起飛 HH:MM）未填；查不到回程時間的請放 refList 或設 ref:true')
                elif r['retDep'] < '12:00':
                    errs.append(f'{tag}：回程 {r["retDep"]} 起飛早於 12:00，不符合條件')
                if r['kind'] == 'lcc' and not r.get('bag'):
                    errs.append(f'{tag}：廉航要加來回行李費 bag')
                key = (r['air'], r.get('out'), r.get('ret'))
                if key in seen:
                    errs.append(f'{tag}：同一航空、同一出發＋回程日期重複')
                seen.add(key)
            for k in ('fare', 'bag'):
                if not isinstance(r.get(k, 0), int):
                    errs.append(f'{tag}：{k} 要是整數')
            r['_total'] = r['fare'] + r.get('bag', 0)
        ok = [r for r in dest['rows'] if not r.get('ref')]
        ok.sort(key=lambda r: (r['_total'], len(r['_leave'])))
        refs = [r for r in dest['rows'] if r.get('ref')]
        if len(ok) > 3:
            warns.append(f"{dest['name']}：符合條件的有 {len(ok)} 筆，只保留前 3 名")
            ok = ok[:3]
        if not ok and not refs:
            errs.append(f"{dest['name']}：沒有任何方案，至少放一筆參考價（ref:true）")
        if len(ok) < 3:
            warns.append(f"{dest['name']}：只有 {len(ok)} 個符合條件的方案，記得在備註與資料缺口寫原因")
        dest['_ok'] = ok
        dest['_rows'] = ok + (refs if not ok else [])
    return errs, warns


def compute_alerts(rep, log, today):
    ts = today.isoformat()
    alerts = []
    for dest in rep['dests']:
        if not dest['_ok']:
            continue
        top = dest['_ok'][0]
        v = top['_total']
        reasons = []
        hist = [(e['date'], e['cells'].get(dest['name'], {}).get('v')) for e in log
                if NEW_RULES_FROM <= e['date'] < ts]
        hist = [(d, x) for d, x in hist if x]
        if hist:
            hist.sort()
            prev = hist[-1][1]
            if v <= prev * 0.85:
                reasons.append(f'比前次便宜 {round((prev - v) / prev * 100)}%')
            lo30 = (today - D.timedelta(30)).isoformat()
            m30 = [x for d, x in hist if d >= lo30]
            if m30 and v < min(m30):
                reasons.append(f'創 30 天新低（前低 {fmt(min(m30))}）')
        for r in dest['_ok']:
            if (r.get('gfLow') or 0) >= 2000:
                reasons.append(f'Google 判定偏低，比平常便宜 ${fmt(r["gfLow"])}' + ('' if r is top else f'（{short(r["air"])}）'))
                r['_alert'] = True
        if reasons:
            top['_alert'] = True
            alerts.append((dest, top, reasons))
    return alerts


def update_log(rep, log, today, alerts):
    ts = today.isoformat()
    alerted = {d['name'] for d, _, _ in alerts}
    prev_entry = next((e for e in log if e['date'] < ts), None)
    cells = {}
    for dest in rep['dests']:
        n = dest['name']
        if dest['_ok']:
            t = dest['_ok'][0]
            pv = (prev_entry or {}).get('cells', {}).get(n, {}).get('v') if prev_entry and prev_entry['date'] >= NEW_RULES_FROM else None
            seen_before = any(e['date'] >= NEW_RULES_FROM and e['date'] < ts and e['cells'].get(n, {}).get('v') for e in log)
            chg = '（首筆）' if not seen_before else '' if pv is None else (' 持平' if pv == t['_total'] else (f' ↑{fmt(t["_total"] - pv)}' if t['_total'] > pv else f' ↓{fmt(pv - t["_total"])}'))
            note = f'{short(t["air"])} {md(t["_a"])}–{md(t["_b"])}{chg}' + (' 🔥' if n in alerted else '')
            cells[n] = {'v': t['_total'], 'approx': bool(t.get('approx')), 'note': note}
        else:
            ref = dest['_rows'][0] if dest['_rows'] else None
            cells[n] = {'v': None, 'approx': False, 'note': f'無符合方案（參考 {fmt(ref["_total"])}）' if ref else '無資料'}
    log = [e for e in log if e['date'] != ts]
    log.insert(0, {'date': ts, 'cells': cells})
    log.sort(key=lambda e: e['date'], reverse=True)
    return log[:30]


# ---------------------------------------------------------------- 產生 HTML
def tag(kind, text):
    return f'<span class="tag t-{kind}">{text}</span>'


def total_text(r):
    if r.get('ref'):
        return f'參考價 {fmt(r["_total"])}'
    return ('≈ ' if r.get('approx') else '') + f'NT${fmt(r["_total"])}'


def best_rows(rep):
    out = []
    for dest in rep['dests']:
        for i, r in enumerate(dest['_rows']):
            rank = '參考' if r.get('ref') else f'第 {i + 1} 名'
            if r.get('_a'):
                a, b = r['_a'], r['_b']
                dt = f'{a.year}/{mdw(a)}～{mdw(b)}' if a.year == b.year else f'{a.year}/{mdw(a)}～{b.year}/{mdw(b)}'
                days = f'{r["_days"]} 天'
                lv = r['_leave']
                n = len(lv)
                lt = (tag('best', f'請 {n} 天') if n <= 2 else f'請 {n} 天') + ('<br>' + '、'.join(md(x) for x in lv) if lv else '')
            else:
                dt, days, lt = r.get('dateText') or '—', '—', '—'
            note = (tag('warn', '🔥 降價') + ' ' if r.get('_alert') else '') + r.get('note', '')
            bag = r.get('bagText') or ('一般已含（請確認）' if r['kind'] != 'lcc' else fmt(r.get('bag', 0)))
            out.append(
                f'    <tr><td class="dest"><b>{dest["name"]}</b></td><td class="air">{tag(r["kind"], r["air"])} {rank}</td>'
                f'<td data-label="日期">{dt}</td><td data-label="天數">{days}</td><td data-label="請假">{lt}</td>'
                f'<td data-label="班次">{r["flights"]}</td><td class="num" data-label="票價">{fmt(r["fare"])}</td>'
                f'<td data-label="行李費">{bag}</td><td class="num total" data-label="含行李總價">{total_text(r)}</td>'
                f'<td data-label="備註">{note}</td></tr>')
    return '\n'.join(out)


def log_rows(log):
    out = []
    for e in log:
        tds = ''.join(
            f'<td class="num" data-label="{n}">' +
            ((('≈' if c.get('approx') else '') + fmt(c['v'])) if c.get('v') else '—') +
            (f'<br><span class="small">{c["note"]}</span>' if c.get('note') else '') + '</td>'
            for n in DESTS for c in [e['cells'].get(n, {})])
        out.append(f'    <tr><td class="date"><b>{e["date"]}</b></td>{tds}</tr>')
    return '\n'.join(out)


def promo_rows(rep, today):
    out = []
    for p in rep['promos']:
        dl = p.get('deadline')
        txt = p.get('deadlineText') or ''
        if dl:
            d = D.date.fromisoformat(dl)
            if d < today:
                txt = tag('warn', f'{txt} 已結束')
            elif d == today:
                txt = tag('warn', f'{txt} 今天截止')
            elif d == today + D.timedelta(1):
                txt = tag('warn', f'{txt}（明天截止）')
        note = f'<br><span class="small">{p["deadlineNote"]}</span>' if p.get('deadlineNote') else ''
        out.append(f'    <tr><td data-label="航空">{tag(p["kind"], p["air"])}</td><td data-label="內容">{p["content"]}</td>'
                   f'<td class="num" data-label="購票期限">{txt}{note}</td><td data-label="出發日">{p.get("dep", "")}</td></tr>')
    return '\n'.join(out)


def windows(rep, today):
    lo, hi = range_of(today)
    wins = []
    d = lo
    while d <= hi:
        for n in (4, 5, 6):
            b = d + D.timedelta(n - 1)
            lv = leave_days(d, b)
            if len(lv) <= 4:
                wins.append((d, b, lv))
        d += D.timedelta(1)
    price = {}
    for dest in rep['dests']:
        for r in dest['_ok']:
            price.setdefault((r['_a'], r['_b']), []).append((r['_total'], f'{short(r["air"])}{dest["name"]} ' + ('≈' if r.get('approx') else '') + fmt(r['_total'])))
    for x in rep.get('windowExtras', []):
        a, b = D.date.fromisoformat(x['out']), D.date.fromisoformat(x['ret'])
        if lo <= a <= hi:
            price.setdefault((a, b), []).append((10 ** 9, x['label']))
    cnt = {}
    for _, _, lv in wins:
        cnt[len(lv)] = cnt.get(len(lv), 0) + 1

    def hol_names(a, b):
        s = []
        x = a
        while x <= b:
            if x in HOL and HOL[x] not in s:
                s.append(HOL[x])
            x += D.timedelta(1)
        return s

    def card(a, b, lv):
        ps = [t for _, t in sorted(price.get((a, b), []))]
        bits = [f'玩 {(b - a).days + 1} 天', leave_text(lv)] + hol_names(a, b) + (['、'.join(ps)] if ps else [])
        return f'    <div class="win{" one" if ps else ""}"><div class="d">{mdw(a)} → {mdw(b)}</div><div class="l">{"・".join(bits)}</div></div>'

    g = {k: [] for k in range(5)}
    for a, b, lv in wins:
        n = len(lv)
        has_p = (a, b) in price
        if n <= 1 or has_p or (n == 2 and (b - a).days + 1 >= 5 and hol_names(a, b)):
            g[n].append(card(a, b, lv))
    yrs = sorted({lo.year, hi.year} - KNOWN_YEARS)
    yr_note = f'範圍跨到 {"、".join(map(str, yrs))} 年，該年國定假日尚未納入，只用週末計算。' if yrs else '範圍內的國定假日都已納入。'
    parts = [
        '<div class="card" data-tab="leave">',
        '  <h2>🗓️ 最省假的出發窗口（玩 4～6 天）</h2>',
        f'  <p class="small" style="margin-top:0">依人事行政總處 116 年（2027）辦公日曆表，週末與國定假日都不用請假；出發日、回程日如果是上班日也算請假。範圍 {lo.year}/{md(lo)}–{hi.year}/{md(hi)} 內，符合「玩 4～6 天、請假 ≤4 天」的窗口共 {len(wins)} 個：'
        + '、'.join(f'請 {k} 天 {cnt.get(k, 0)} 個' for k in range(5)) + f'。{yr_note}綠框是有實際票價的窗口（由 tools/build.py 自動計算）。</p>',
        '  <h3>不用請假 / 只要請 1 天 ⭐</h3>', '  <div class="grid">', *(g[0] + g[1]), '  </div>',
        '  <h3>請 2 天（玩 5～6 天的連假窗口，以及有價格的窗口）</h3>', '  <div class="grid">', *g[2], '  </div>',
        '  <p style="margin:6px 0 4px">另外，一般週只要「玩 4 天且包含週末」都只請 2 天：四→日、五→一、六→二。</p>',
        '  <h3>請 3 天（有價格的窗口）</h3>', '  <div class="grid">', *(g[3] or ['    <p class="small">今天沒有請 3 天的價格</p>']), '  </div>',
        '  <p style="margin:6px 0 4px">一般週玩 5 天（包含一個週末）請 3 天：三→日、四→一、五→二、六→三、日→四；玩 4 天的三→六、日→三也是請 3 天。</p>',
        '  <h3>請 4 天（有價格的窗口）</h3>', '  <div class="grid">', *(g[4] or ['    <p class="small">今天沒有請 4 天的價格</p>']), '  </div>',
        '  <p style="margin:6px 0 4px">一般週玩 6 天（包含一個週末）請 4 天；玩 4 天全落在平日（例如二→五）也是請 4 天。週一出發週五回（玩 5 天）、週一到週六或週日到週五（玩 6 天）都要請 5 天，一律排除。</p>',
        '</div>']
    return '\n'.join(parts)


def content_html(rep, log, today, alerts):
    lo, hi = range_of(today)
    upd = D.datetime.fromisoformat(rep['updated'])
    alert_txt = ''
    if alerts:
        alert_txt = '🔥 降價警報：' + '；'.join(
            f'{d["name"]} {total_text(t)}（{t["air"]}、{md(t["_a"])}–{md(t["_b"])}，玩 {t["_days"]} 天・請 {len(t["_leave"])} 天，{"、".join(rs)}）'
            for d, t, rs in alerts) + '。'
    lis = lambda xs: '\n'.join(f'    <li>{x}</li>' for x in xs)
    return f'''<header>
  <h1>✈️ 日本機票監控</h1>
  <div class="sub">最後更新：{upd:%Y-%m-%d}（週{WD[upd.weekday()]}）{upd:%H:%M} 台北時間（{rep.get("subNote", "")}）</div>
  <div class="chips">
    <span class="chip">桃園出發（松山、高雄附帶）</span>
    <span class="chip">10 個目的地：{"・".join(DESTS)}</span>
    <span class="chip">玩 4～6 天</span>
    <span class="chip">最多請 4 天・見紅就休</span>
    <span class="chip">回程日本 12:00 後起飛</span>
    <span class="chip">每條航線前三名</span>
    <span class="chip">出發日 {lo.year}/{md(lo)} – {hi.year}/{md(hi)}</span>
    <span class="chip">含託運行李 20kg</span>
    <span class="chip">去程時段不限（可紅眼）</span>
  </div>
</header>

<div class="card" data-tab="overview">
  <div class="take">💬 今天重點：{alert_txt}{rep["takeaway"]}</div>
  <p class="small" style="margin:10px 0 0">{rep["caveat"]}</p>
</div>

<div class="card" data-tab="prices">
  <h2>🏆 各目的地前三名優惠（含行李）</h2>
  <p class="small" style="margin-top:0">{rep["bestIntro"]}</p>
  <div class="scroll">
  <table class="rt rt-best">
    <tr class="hd"><th>目的地</th><th>航空</th><th>出發～回程</th><th>天數</th><th>請假</th><th>去回班次時間</th><th>票價</th><th>行李費</th><th>含行李總價</th><th>備註</th></tr>
{best_rows(rep)}
  </table>
  </div>
  <details class="fold"><summary>參考價（回程時間未確認、要轉機、日期不符或只有起價，只供判斷行情）</summary>
  <ul class="small">
{lis(rep["refList"])}
  </ul></details>
</div>

<div class="card" data-tab="trend">
  <h2>📈 每日最低價紀錄（含行李，NT$）</h2>
  <div class="scroll">
  <table class="rt rt-log">
    <tr class="hd"><th>日期</th>{"".join(f"<th>{n}</th>" for n in DESTS)}</tr>
{log_rows(log)}
  </table>
  </div>
  <p class="small">{rep["logNote"]}</p>
</div>

<div class="card" data-tab="promo">
  <h2>🔥 促銷情報</h2>
  <div class="scroll">
  <table class="rt rt-promo">
    <tr class="hd"><th>航空</th><th>內容</th><th>購票期限</th><th>適用出發日</th></tr>
{promo_rows(rep, today)}
  </table>
  </div>
  <p class="small">{rep["promoNote"]}</p>
</div>

<div class="card" data-tab="info">
  <h2>🧳 廉航託運行李費參考（訂位時加購，每段 20kg）</h2>
  <ul>
{lis(rep["baggage"])}
  </ul>
  <p class="small">{rep["baggageNote"]}</p>
</div>

<div class="card" data-tab="info">
  <h2>🧩 資料缺口</h2>
  <ul>
{lis(rep["gaps"])}
  </ul>
</div>

<div class="card" data-tab="info">
  <h2>🔗 來源</h2>
  <ul class="small">
{lis(rep["sources"])}
  </ul>
</div>

{windows(rep, today)}

<footer>所有價格都是查詢時價格，實際以各航空訂票頁為準。本頁每天由排程任務自動更新。<span id="pub-link"></span></footer>
'''


def page(public):
    flag = '<script>window.PUBLIC_SITE=1</script>\n' if public else ''
    note = ('<!-- 本頁內容在 assets/content.js（由 GitHub rayanhuang/japan-flights 的 tools/build.py 產生）。'
            '每日更新請照 repo 的 docs/ROUTINE.md：改 data/*.json → python3 tools/build.py → 發佈，不要手寫整頁 HTML。 -->\n')
    head = ('<!DOCTYPE html>\n<html lang="zh-Hant-TW">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '<title>日本機票票價監控</title>\n<link rel="stylesheet" href="assets/style.css">\n</head>\n<body>\n') if public else (
            '<title>日本機票票價監控</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
            '<link rel="stylesheet" href="assets/style.css">\n')
    body = (note + '<div class="wrap" id="wrap"><noscript>這個頁面需要開啟 JavaScript。</noscript></div>\n' + flag +
            '<script src="assets/content.js"></script>\n<script src="assets/app.js"></script>\n')
    return head + body + ('</body>\n</html>\n' if public else '')


def notify_text(rep, alerts, today):
    lines = []
    if alerts:
        lines.append(f'🔥 降價警報 {today}')
        for d, t, rs in alerts:
            lines.append(f'{d["name"]}：{total_text(t)}（{t["air"]}、{md(t["_a"])}–{md(t["_b"])}），{"、".join(rs)}')
    else:
        lines.append(f'✈️ 日本機票監控 {today}')
    for dest in rep['dests']:
        if dest['_ok']:
            t = dest['_ok'][0]
            lines.append(f'{dest["name"]}：第 1 名 {total_text(t)}（{t["air"]}、{md(t["_a"])}–{md(t["_b"])}、玩 {t["_days"]} 天・請 {len(t["_leave"])} 天、回程 {t["retDep"]} 起飛）')
        else:
            r = dest['_rows'][0]
            lines.append(f'{dest["name"]}：無符合條件方案（{total_text(r)}）')
    n = rep.get('notify', {})
    lines += [f'促銷：{n.get("promo", "")}', f'查價方式：{n.get("method", "")}',
              f'網頁：{ARTIFACT_URL}', f'公開網站：{PUBLIC_URL}']
    return '\n'.join(lines)


def summary(rep, log, today):
    lo, hi = range_of(today)
    print(f'今天 {today}；搜尋範圍 {lo}～{hi}；資料更新於 {rep["updated"]}')
    for dest in rep['dests']:
        bits = []
        for r in dest['rows']:
            bits.append(f'{short(r["air"])} {r.get("out")}~{r.get("ret")} 回{r.get("retDep")} {r["fare"]}+{r.get("bag", 0)}' + (' [參考]' if r.get('ref') else '') + (' [超出範圍]' if r.get('out') and r['out'] < lo.isoformat() else ''))
        print(f'- {dest["name"]}：' + '；'.join(bits))
    if log:
        e = log[0]
        print(f'最近紀錄 {e["date"]}：' + '、'.join(f'{n} {e["cells"].get(n, {}).get("v") or "—"}' for n in DESTS))
    try:
        rets = load('returns.json')
        print('已確認的回程班次（同航空同日期可沿用）：')
        for x in rets:
            print(f'  {x["route"]} {x["date"]} {x["air"]}：{"、".join(x["deps"])}（{x["src"]}，{x["checked"]}）')
    except FileNotFoundError:
        pass
    for p in rep['promos']:
        if p.get('deadline') and D.date.fromisoformat(p['deadline']) >= today:
            print(f'促銷進行中：{p["air"]} 到 {p["deadline"]}')


def main():
    today = D.date.fromisoformat(os.environ['TODAY']) if os.environ.get('TODAY') else today_tw()
    rep, log = load('report.json'), load('log.json')
    if '--summary' in sys.argv:
        summary(rep, log, today)
        return
    errs, warns = prepare(rep, today)
    for w in warns:
        print('注意：' + w)
    if errs:
        print('\n'.join('錯誤：' + e for e in errs))
        sys.exit(1)
    alerts = compute_alerts(rep, log, today)
    log = update_log(rep, log, today, alerts)
    save('log.json', log)
    c = content_html(rep, log, today, alerts)
    js = ('/* 由 tools/build.py 產生，不要手動修改 */\n(function(){var w=document.getElementById("wrap");w.innerHTML=' +
          json.dumps(c, ensure_ascii=False).replace('</', '<\\/') +
          ';if(window.PUBLIC_SITE){var p=document.getElementById("pub-link");if(p)p.innerHTML="<br>完整版（需登入 Claude）：' + ARTIFACT_URL + '";}})();\n')
    with open(os.path.join(ROOT, 'assets', 'content.js'), 'w', encoding='utf8') as f:
        f.write(js)
    with open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf8') as f:
        f.write(page(True))
    os.makedirs(os.path.join(ROOT, 'build'), exist_ok=True)
    with open(os.path.join(ROOT, 'build', 'artifact.html'), 'w', encoding='utf8') as f:
        f.write(page(False))
    nt = notify_text(rep, alerts, today)
    with open(os.path.join(ROOT, 'build', 'notify.txt'), 'w', encoding='utf8') as f:
        f.write(nt + '\n')
    print(nt)


if __name__ == '__main__':
    main()
