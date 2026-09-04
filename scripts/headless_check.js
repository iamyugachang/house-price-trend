#!/usr/bin/env node
/* Headless QA for the house-price-trend page (run after every UI change).
   Usage: node scripts/headless_check.js [url]
   Asserts: no pageerror, chart canvas present, trend series >0, table rows >0,
   region switch (taipei -> newtaipei) works. Prints PASS/FAIL + state. */
const fs = require('fs');
const os = require('os');
let pw;
try { pw = require('playwright-core'); } catch (e) { pw = require('/tmp/pw/node_modules/playwright-core'); }
const { chromium } = pw;

(async () => {
  const url = process.argv[2] || 'http://127.0.0.1:8099/docs/';
  // find installed chromium
  const cache = `${os.homedir()}/.cache/ms-playwright`;
  const dirs = fs.existsSync(cache) ? fs.readdirSync(cache).filter(d => d.startsWith('chromium-')) : [];
  const exe = dirs.length
    ? `${cache}/${dirs.sort().pop()}/chrome-linux64/chrome`
    : null;
  const browser = await chromium.launch({ executablePath: exe, headless: true,
    args: ['--no-sandbox', '--disable-gpu'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errs = [];
  page.on('pageerror', e => errs.push(e.message));
  await page.goto(url, { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(14000);
  const snap = () => page.evaluate(() => {
    const g = id => document.getElementById(id);
    return { err: g('errBox').textContent, canvases: g('chart').querySelectorAll('canvas').length,
             hint: g('dataHint').textContent, cnt: g('cntHint').textContent,
             rows: document.querySelectorAll('#tbody tr').length };
  });
  const checks = [['taipei', await snap()]];
  await page.selectOption('#region', 'newtaipei');
  await page.waitForTimeout(18000);
  checks.push(['newtaipei', await snap()]);
  await page.selectOption('#groupby', 'age');
  await page.selectOption('#age', '5-10');
  await page.waitForTimeout(1000);
  checks.push(['newtaipei+age', await snap()]);
  await browser.close();

  let fail = false;
  for (const [name, s] of checks) {
    const ok = !s.err && s.canvases >= 1 && s.rows >= 1 && !errs.length;
    if (!ok) fail = true;
    console.log(`${ok ? 'PASS' : 'FAIL'} ${name}: err="${s.err}" canvases=${s.canvases} rows=${s.rows} ${s.hint} | ${s.cnt}`);
  }
  if (errs.length) console.log('PAGEERRORS:', errs.join(' | '));
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('FATAL', e); process.exit(1); });
