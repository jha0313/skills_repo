// 시험용: 해 보기를 키보드로만 눌러 본다(브라우저 필요). 사용: node act.cjs <HTML 폴더>   — 스킬은 이 파일에 기대지 않는다.
// 1 단추를 누른 뒤에도 초점이 그 그림(카드) 안에 남는다  2 레인: 어느 단계·요청에서도 말이 1280×800 안  3 차트: 기준 없는 행은 열기만, 나머지는 이름에 적힌 답이 맞음  4 예측 카드에 지어낸 보기가 없다(walk는 보기를 손으로 쓴 예)  5 폭을 바꿔도 말의 모양이 같다
const fs = require('fs'), path = require('path');
const puppeteer = require(process.env.PUPPETEER || 'puppeteer');
const dir = process.argv[2];
(async () => {
  const b = await puppeteer.launch({ executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true, args: ['--no-sandbox'] });
  let bad = 0; const fail = t => { bad++; console.log('실패 ' + t); };
  for (const f of fs.readdirSync(dir).filter(x => /interactive.*\.html$/.test(x))) {
    const p = await b.newPage(); p.on('pageerror', e => fail(f + ' 오류 ' + e.message)); await p.setViewport({ width: 1280, height: 800 });
    const open = async () => { await p.goto('file://' + path.resolve(dir, f)); await new Promise(r => setTimeout(r, 200)); };
    await open(); let n = 0;
    const list = () => p.evaluate(() => [...document.querySelectorAll('.bt:not(:disabled)')].length);
    for (let i = 0; i < await list() && i < 60; i++) {
      const who = await p.evaluate(i => { const e = [...document.querySelectorAll('.bt:not(:disabled)')][i]; e.focus(); window.__in = e.closest('.fig,.pd'); return e.textContent; }, i);
      await p.keyboard.press('Enter'); n++; await new Promise(r => setTimeout(r, 15));
      if (!await p.evaluate(() => document.activeElement !== document.body && (!window.__in || window.__in.contains(document.activeElement)))) fail(f + ' 초점을 잃음: ' + who);
    }
    await open();
    if (!f.startsWith('walk') && await p.evaluate(() => [...document.querySelectorAll('.pd')].some(e => e.querySelectorAll('.bt').length > 1))) fail(f + ' 예측 카드에 보기가 있다');
    if (await p.$('.fig[data-part=lanes]')) {
      const low = () => p.evaluate(() => Math.round(document.querySelector('.fig[data-part=lanes] .say').getBoundingClientRect().bottom + scrollY)); let m = await low();
      for (let i = 0; i < 14; i++) { await p.evaluate(() => { const x = [...document.querySelectorAll('.bt')].find(e => /다음 단계/.test(e.textContent)); if (x) x.click(); }); m = Math.max(m, await low()); }
      const k = await p.evaluate(() => document.querySelector('.fig[data-part=lanes] .grp').querySelectorAll('.bt').length);
      for (let i = 0; i < k; i++) { await p.evaluate(i => document.querySelector('.fig[data-part=lanes] .grp').querySelectorAll('.bt')[i].click(), i); m = Math.max(m, await low()); }
      if (m > 800) fail(f + ' 말이 화면 아래로 밀림 ' + m);
    }
    await open(); { const t = () => p.evaluate(() => { const x = [...document.querySelectorAll('.bt')].find(e => /다음 단계/.test(e.textContent)); if (x) x.click(); return [...document.querySelectorAll('.say')].map(e => e.innerHTML).join('|'); }); const a = await t(); await p.setViewport({ width: 1072, height: 800 }); await new Promise(r => setTimeout(r, 500)); const b2 = await p.evaluate(() => [...document.querySelectorAll('.say')].map(e => e.innerHTML).join('|')); if (a !== b2) fail(f + ' 폭을 바꾸면 말의 모양이 바뀐다'); await p.setViewport({ width: 1280, height: 800 }); await open(); }
    if (f.startsWith('chart-base')) {
      const rows = await p.evaluate(() => [...document.querySelectorAll('.br')].map(r => [r.querySelector('.nm').textContent, [...r.querySelectorAll('.bt')].map(x => x.textContent).join()]));
      for (const [name, bs] of rows) {
        if (/열기만/.test(name) ? bs !== '열기' : bs !== '늘었다,비슷하다,줄었다') { fail(f + ' ' + name + ' 단추 ' + bs); continue; }
        const r = await p.evaluate(name => { const row = [...document.querySelectorAll('.br')].find(x => x.querySelector('.nm').textContent === name), want = (name.match(/늘었다|비슷하다|줄었다/) || ['열기'])[0]; [...row.querySelectorAll('.bt')].find(x => x.textContent === want).click(); return document.querySelector('.say').textContent; }, name);
        if (/열기만/.test(name) ? /^(맞음|다름)/.test(r) : !r.startsWith('맞음')) fail(f + ' ' + name + ' → ' + r);
      }
    }
    console.log(f + ' 단추 ' + n); await p.close();
  }
  await b.close(); console.log(bad ? '실패 ' + bad : '모두 통과'); process.exitCode = bad ? 1 : 0;
})();
