// 시험용: 1280×800 라이트·다크, 390×844를 찍고 INTO_CHECK·INTO_PATHS를 돌린다. 해 보기는 조작을 모두 눌러 본다.
// 사용: node shot.cjs <HTML 폴더> <png 폴더> [이름에 든 말]   — 스킬은 이 파일에 기대지 않는다.
const fs = require('fs'), path = require('path');
const puppeteer = require(process.env.PUPPETEER || 'puppeteer');
const [, , dir, out, only] = process.argv;
const sizes = [['light', 1280, 800], ['dark', 1280, 800], ['mobile', 390, 844]];
(async () => {
  fs.mkdirSync(out, { recursive: true });
  const b = await puppeteer.launch({ executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true, args: ['--no-sandbox'] });
  for (const f of fs.readdirSync(dir).filter(x => x.endsWith('.html') && (!only || x.includes(only)))) {
    const name = f.replace(/\.html$/, ''), tr = /interactive/.test(name), log = [];
    for (const [tag, w, h] of sizes) {
      const p = await b.newPage(); const errs = [], net = [];
      p.on('pageerror', e => errs.push(e.message)); p.on('console', m => m.type() === 'error' && errs.push(m.text())); p.on('request', r => { if (!/^(file|data):/.test(r.url())) net.push(r.url()); });
      await p.setViewport({ width: w, height: h, deviceScaleFactor: tag === 'mobile' ? 2 : 1.5 });
      await p.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: tag === 'dark' ? 'dark' : 'light' }]);
      await p.goto('file://' + path.resolve(dir, f)); await new Promise(r => setTimeout(r, 250));
      await p.screenshot({ path: path.join(out, name + '-' + tag + '.png'), fullPage: tag === 'mobile' });
      const ck = await p.evaluate(() => INTO_CHECK()); ck.forEach(x => log.push(tag + ': ' + x)); errs.forEach(x => log.push(tag + ' 오류: ' + x)); net.forEach(x => log.push(tag + ' 외부 요청: ' + x));
      if (tag === 'light') {
        const i = await p.evaluate(() => { const q = x => document.querySelector(x), n = e => e ? e.innerText.replace(/\s+/g, '').length : 0, g = q('.figs'); return { chars: n(q('#app')) - n(q('footer')), share: Math.round(g.offsetHeight * g.offsetWidth / 10240), fs: [...document.querySelectorAll('.fig')].map(f => f.dataset.part + ' ' + (parseFloat((f.querySelector('.g,.stage>div') || f).style.fontSize) || '')).join(' · '), paths: INTO_PATHS().length, h: document.documentElement.scrollHeight, acts: document.querySelectorAll('[data-act]').length }; });
        log.unshift('글자 ' + i.chars + ' · 그림 ' + i.share + '% · ' + i.fs + ' · 높이 ' + i.h + ' · 조작 ' + i.acts + ' · 길 ' + i.paths);
      }
      if (tr && tag !== 'dark') { // 조작을 모두 누르고 다시 본다
        const r = await p.evaluate(async () => {
          const bad = [], seen = new Set(), sleep = t => new Promise(r => setTimeout(r, t)); let n = 0;
          for (let round = 0; round < 60; round++) {
            const b = [...document.querySelectorAll('[data-act]:not(:disabled)')].find(x => { const k = (x.closest('.fig,.pd') || {}).className + '|' + x.textContent; return !seen.has(k); }); if (!b) break;
            seen.add((b.closest('.fig,.pd') || {}).className + '|' + b.textContent); b.click(); n++; await sleep(15);
            for (const x of INTO_CHECK()) if (!bad.includes(x)) bad.push(x);
          }
          for (const k of ['ArrowRight', 'ArrowRight', 'ArrowLeft', '1', '2']) { document.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true })); await sleep(15); }
          return { n, bad, learned: document.querySelectorAll('.lrn li:not(.no):not(.fin)').length };
        });
        log.push(tag + ' 누름 ' + r.n + '번 · 알게 된 것 ' + r.learned + '줄' + (errs.length ? ' · 오류 ' + errs[0] : '')); r.bad.forEach(x => { if (!ck.includes(x)) log.push(tag + ' 누른 뒤: ' + x); });
        await p.evaluate(() => scrollTo(0, 0)); await new Promise(r => setTimeout(r, 250));
        await p.screenshot({ path: path.join(out, name + '-' + tag + '-used.png'), fullPage: true });
      }
      await p.close();
    }
    console.log('== ' + name + '\n   ' + log.join('\n   '));
  }
  await b.close();
})();
