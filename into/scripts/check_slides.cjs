#!/usr/bin/env node
/* into slides 점검(브라우저). 설치하지 않는다: 이미 있는 puppeteer를 쓴다.
   node check_slides.cjs <slides.html> [--puppeteer <모듈 폴더>] [--chrome <실행 파일>] [--shots <폴더>]
   환경 변수: INTO_PUPPETEER, INTO_CHROME. 없으면 안내만 하고 0으로 끝난다(정적 점검은 check_slides.py).
   끝 코드: FAIL이 있으면 1. */
const fs = require('fs'), path = require('path');
const argv = process.argv.slice(2), opt = n => (i => i < 0 ? null : argv[i + 1])(argv.indexOf('--' + n));
const file = argv.find((a, i) => !a.startsWith('--') && !(argv[i - 1] || '').startsWith('--'));
if (!file || !fs.existsSync(file)) { console.error('쓰는 법: node check_slides.cjs <slides.html> [--puppeteer 경로] [--chrome 경로] [--shots 폴더]'); process.exit(2); }

function loadPuppeteer() {
  for (const m of [opt('puppeteer'), process.env.INTO_PUPPETEER, path.join(process.cwd(), 'node_modules/puppeteer'), 'puppeteer', 'puppeteer-core'])
    if (m) try { return require(m); } catch (e) { /* 다음 후보 */ }
  return null;
}
const chrome = opt('chrome') || process.env.INTO_CHROME || ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'].find(p => fs.existsSync(p));
const puppeteer = loadPuppeteer();
if (!puppeteer) { console.log('puppeteer가 없다. --puppeteer 나 INTO_PUPPETEER로 있는 모듈의 경로를 주거나 `python3 -I check_slides.py <slides.html>`(정적 점검)을 쓰고, 넘침은 브라우저에서 눈으로 본다.'); process.exit(0); }

const DIAGRAM = ['flow', 'sequence', 'motion-inline', 'timeline', 'map'], INTERACTIVE = ['sim', 'predict', 'compare', 'timeline', 'map'], MOTION = ['motion', 'motion-inline'];
const fails = [], warns = [], fail = m => fails.includes(m) || fails.push(m), warn = m => warns.includes(m) || warns.push(m);

/* 지금 보이는 장 하나를 잰다(브라우저 안에서 돈다) */
function measure(i) {
  const s = document.querySelectorAll('.slide')[i], R = s.getBoundingClientRect(), k = R.width / 1280, out = [];
  const name = e => (e.textContent || e.className || e.tagName).trim().replace(/\s+/g, ' ').slice(0, 28);
  const shown = e => { for (let x = e; x && x !== s; x = x.parentElement) { const c = getComputedStyle(x); if (c.display === 'none' || c.visibility === 'hidden' || +c.opacity === 0) return false; } return true; };
  const box = e => e.getBoundingClientRect(), hit = (a, b) => Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
  if (s.scrollHeight > 721 || s.scrollWidth > 1281) out.push('F 장 넘침 ' + s.scrollWidth + '×' + s.scrollHeight);
  if (document.documentElement.scrollWidth > innerWidth) out.push('F 가로 스크롤');
  const texts = [...s.querySelectorAll('*')].filter(e => !e.closest('.notes,script,svg') && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && shown(e));
  for (const e of texts) {
    const b = box(e), v = e.closest('.viz'), lim = v ? box(v) : R, pad = 5 * k;
    if (parseFloat(getComputedStyle(e).fontSize) < 12) out.push('F 12px보다 작은 글자: ' + name(e));
    if (b.width && (b.left < lim.left - pad || b.right > lim.right + pad || b.top < lim.top - pad || b.bottom > lim.bottom + pad)) out.push('F ' + (v ? '그림 칸' : '장') + ' 밖으로 나감: ' + name(e));
    const c = e.closest('button,.nd,.bk,.c,.outs>div,.gates div');
    if (c && (c.scrollWidth > c.clientWidth + 2 || c.scrollHeight > c.clientHeight + 2)) out.push('F 칸에서 잘림: ' + name(c));
  }
  const labs = [...s.querySelectorAll('.lb')].filter(shown), nds = [...s.querySelectorAll('.nd')];
  labs.forEach((a, x) => {
    const A = box(a), area = A.width * A.height;
    nds.forEach(n => { if (hit(A, box(n)) > area * .12) out.push('W 라벨이 노드와 겹침: ' + name(a)); });
    labs.slice(x + 1).forEach(b => { if (hit(A, box(b)) > Math.min(area, box(b).width * box(b).height) * .12) out.push('W 라벨끼리 겹침: ' + name(a) + ' / ' + name(b)); });
  });
  return out;
}
/* 장마다 글·자료(브라우저 안에서 돈다) */
function collect() {
  return window.INTO_SLIDES.list.map((l, i) => {
    const s = document.querySelectorAll('.slide')[i], c = s.cloneNode(true), q = x => (s.querySelector(x) || { textContent: '' }).textContent.trim();
    c.querySelectorAll('.viz,.notes,.src,.next-q,.kicker,.notice,script').forEach(e => e.remove());
    const sims = (l.sims || []).map(m => {
      let miss = 0, total = 0; const used = {};
      (function go(k, v) {
        if (k === m.controls.length) { total++; const r = m.find(v); r ? used[m.rules.indexOf(r)] = 1 : miss++; return; }
        m.controls[k].opts.forEach(o => go(k + 1, Object.assign({}, v, { [m.controls[k].id]: o })));
      })(0, {});
      return { miss, total, unused: m.rules.length - Object.keys(used).length };
    });
    const data = [...s.querySelectorAll('.viz>script')].map(x => { try { return JSON.parse(x.textContent); } catch (e) { return null; } });
    return { kinds: l.kinds, steps: l.steps, sims, data, title: q('h1,h2'), kicker: q('.kicker'), notes: q('.notes'), next: q('.next-q'), words: c.textContent.trim().split(/\s+/).filter(Boolean).length, hole: s.innerHTML.includes('{{'), labels: [...s.querySelectorAll('.viz')].every(v => v.getAttribute('aria-label')) };
  });
}

(async () => {
  const b = await puppeteer.launch({ executablePath: chrome || undefined, args: ['--allow-file-access-from-files', '--no-sandbox'] }), dir = path.dirname(path.resolve(file));
  let list, step = '';
  for (const [w, h] of [[1280, 720], [1920, 1080]]) {
    const p = await b.newPage();
    await p.setViewport({ width: w, height: h });
    p.on('console', m => m.type() === 'error' && fail('콘솔 오류: ' + m.text().slice(0, 120)));
    p.on('pageerror', e => fail('스크립트 오류: ' + e.message.slice(0, 120)));
    p.on('request', r => { if (!/^(file|data|blob|about):/.test(r.url())) fail('외부 요청: ' + r.url().slice(0, 100)); });
    p.on('requestfailed', r => { if (r.url().startsWith('file:') && !/ABORTED/.test((r.failure() || {}).errorText || '')) fail('없는 파일: ' + decodeURIComponent(r.url()).slice(-60)); });
    await p.emulateMediaFeatures([{ name: 'prefers-reduced-motion', value: 'reduce' }]);
    await p.goto('file://' + path.resolve(file));
    if (!await p.evaluate(() => !!window.INTO_SLIDES)) { fail('v2 템플릿의 동작 코드가 없다(window.INTO_SLIDES)'); break; }
    list = list || await p.evaluate(collect);
    for (let i = 0; i < list.length; i++) for (let k = 0; k <= list[i].steps; k++) {
      await p.evaluate((i, k) => window.INTO_SLIDES.show(i, k), i, k);
      await new Promise(r => setTimeout(r, 40));
      for (const m of await p.evaluate(measure, i)) { step = `${i + 1}장 ${k}단계 ${w}×${h}: ${m.slice(2)}`; m[0] === 'F' ? fail(step) : w === 1280 && warn(step); }
      if (opt('shots') && w === 1280 && k === list[i].steps) { fs.mkdirSync(opt('shots'), { recursive: true }); await p.screenshot({ path: path.join(opt('shots'), 's' + String(i + 1).padStart(2, '0') + '.png') }); }
    }
    await p.close();
  }
  await b.close();

  const n = (list || []).length, kinds = {}, short = n < 8, need = (ok, m) => ok || (short ? warn : fail)(m);
  (list || []).forEach((s, i) => {
    const at = `${i + 1}장`, sum = /정리/.test(s.kicker);
    s.kinds.forEach(k => kinds[k] = (kinds[k] || 0) + 1);
    if (!s.kinds.length) sum ? 0 : fail(at + ': 그림이 없다');
    if (!s.title) fail(at + ': 제목이 없다');
    if (s.words > 60) fail(at + `: 본문 ${s.words}단어`); else if (s.words > 40) warn(at + `: 본문 ${s.words}단어(35단어 안팎)`);
    if (!s.notes) fail(at + ': 발표자 노트가 없다'); else if (!/근거/.test(s.notes)) warn(at + ': 노트에 근거 위치가 없다');
    if (!s.next && i < n - 1) warn(at + ': 다음 질문이 없다');
    if (!s.labels) warn(at + ': 그림에 aria-label이 없다');
    if (s.hole) fail(at + ': 자리 표시 {{…}}가 남았다');
    s.sims.forEach(m => { if (m.miss) fail(at + `: sim 조합 ${m.total}개 중 ${m.miss}개에 규칙이 없다`); if (m.unused) warn(at + `: sim에서 한 번도 안 걸리는 규칙 ${m.unused}개`); });
    s.data.forEach((d, j) => {
      const k = s.kinds[j]; if (!d) return fail(at + ': JSON을 못 읽는다');
      if (k === 'sim' && !d.scope) fail(at + ': sim에 scope(범위·뺀 조건)가 없다');
      if (k === 'chart' && !d.axis) warn(at + ': chart에 axis(무엇·분모·시점)가 없다');
      if (k === 'motion') [d.src, d.poster].forEach(f => { const q = path.join(dir, f || '?'); if (!fs.existsSync(q)) fail(at + ': 파일이 없다 ' + f); else if (fs.statSync(q).size > 3e6) warn(at + `: ${f} ${(fs.statSync(q).size / 1e6).toFixed(1)}MB(2MB 안팎)`); });
    });
  });
  const cnt = L => (list || []).filter(s => s.kinds.some(k => L.includes(k))).length;
  need(Object.keys(kinds).length >= 5, `그림 종류 ${Object.keys(kinds).length}가지(5가지 이상)`);
  need(cnt(DIAGRAM) >= 3, `다이어그램 ${cnt(DIAGRAM)}장(3장 이상)`);
  need(cnt(INTERACTIVE) >= 3, `상호작용 ${cnt(INTERACTIVE)}장(3장 이상)`);
  need(cnt(MOTION) >= 2, `모션 ${cnt(MOTION)}장(2장 이상)`);
  if (!kinds.chart) warn('차트가 없다: 원문에 비교할 수가 2개 이상이면 넣고, 없으면 이유를 적는다');
  if (!kinds.motion) warn('MP4 영상이 없다: 영상 도구가 있으면 1개 이상');

  console.log(`${path.basename(file)}: ${n}장, ${(fs.statSync(file).size / 1024).toFixed(1)}KB`);
  (list || []).forEach((s, i) => console.log(`  ${String(i + 1).padStart(2)} ${(s.kinds.join('+') || '-').padEnd(14)} 단계 ${s.steps}  본문 ${s.words}단어  ${s.title.slice(0, 46)}`));
  console.log('그림: ' + Object.entries(kinds).map(([k, v]) => k + ' ' + v).join(', ') + ` | 다이어그램 ${cnt(DIAGRAM)} · 상호작용 ${cnt(INTERACTIVE)} · 모션 ${cnt(MOTION)}장`);
  fails.forEach(m => console.log('FAIL ' + m));
  warns.forEach(m => console.log('WARN ' + m));
  console.log(`결과: FAIL ${fails.length}, WARN ${warns.length}`);
  process.exit(fails.length ? 1 : 0);
})();
