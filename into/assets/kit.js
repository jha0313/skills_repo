// into kit — html(보기)·interactive(해 보기)의 그림 부품. 데이터는 <script type="application/json" id="into"> 하나.
// 좌표는 받지 않는다: 글자 폭을 재서 상자를 정하고 층 배치로 놓는다. 외부 요청 0.
(function () {
'use strict';
const doc = document, NS = 'http://www.w3.org/2000/svg', RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
const D = JSON.parse(doc.getElementById('into').textContent), TRY = D.mode === 'interactive', FIGS = [], LEARN = [], PART = {}, PATHS = [];
const q = (s, e) => (e || doc).querySelector(s), qa = (s, e) => [].slice.call((e || doc).querySelectorAll(s));
const arr = v => Array.isArray(v) ? v : v == null || v === '' ? [] : [v], clamp = (v, a, b) => Math.max(a, Math.min(b, v)), sum = a => a.reduce((x, y) => x + y, 0), cp = (a, b) => Object.assign({}, a, b);
const max = (a, d) => a.length ? Math.max.apply(0, a) : d || 0, flat = a => [].concat.apply([], a), uniq = a => a.filter((x, i) => a.indexOf(x) === i);
const ERR = []; addEventListener('error', e => { ERR.push(e.message); });
const NUM = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫';
function tog(e, o) { for (const k in o) e.classList.toggle(k, !!o[k]); return e; }
function rich(e, t) { // 글자만 넣는다. `코드`와 줄바꿈만 해석한다
  e.textContent = '';
  String(t).split('`').forEach((p, i) => { if (!p) return; if (i % 2) { const c = e.appendChild(doc.createElement('code')); if (p.length < 11) c.style.whiteSpace = 'nowrap'; cut(c, p); return; }
    p.split('\n').forEach((l, j) => { if (j) e.appendChild(doc.createElement('br')); cut(e, i && !j && /^[가-힣]/.test(l) ? '\u2060' + l : l); }); });
  return e;
}
function cut(e, s) { // 긴 식별자는 _ . / :: 뒤, 더 길면 낱말 머리(aB)나 12자마다, 여는 괄호 앞에서만 줄을 바꾼다
  s.replace(/[\w.\/:-]{13,}/g, w => w.replace(/(?!^)(::|[_\/]|\.(?=[A-Za-z]))(?=\w)/g, '$1\n').replace(/[A-Za-z0-9]{17,}/g, x => x.replace(/([a-z0-9])(?=[A-Z])/g, '$1\n').replace(/[A-Za-z0-9]{20,}/g, y => y.replace(/.{12}(?=.{4})/g, '$&\n')))).replace(/([\w.]{8})\((?=[가-힣])/g, '$1\n(').replace(/[)>\]](?=[가-힣])/g, '$&\u2060').replace(/(^|[\s(])\/(?=\w)/g, '$1/\u2060').split('\n').forEach((x, i) => { if (i) e.appendChild(doc.createElement('wbr')); x.split(/(<[^<>\s]{1,14}>|[^\s·]·(?=\S))/).forEach((y, j) => { if (j % 2) e.appendChild(doc.createElement('span')).className = 'nb'; if (y) (j % 2 ? e.lastChild : e).appendChild(doc.createTextNode(y)); }); }); // 가운뎃점은 줄 머리에 오지 않고, <이름>은 갈리지 않는다
}
function el(tag, cls, par, txt) { const e = doc.createElement(tag); if (cls) e.className = cls; if (txt != null && txt !== '') rich(e, txt); if (par) par.appendChild(e); return e; }
function sv(tag, at, par) { const e = doc.createElementNS(NS, tag); for (const k in at) e.setAttribute(k, at[k]); return par.appendChild(e); }
function btn(par, cls, txt, fn) { return tap(el('button', cls, par, txt), fn); }
function tap(e, fn) { e.type = 'button'; e.dataset.act = '1'; e.addEventListener('click', ev => { ev.stopPropagation(); fn(e); }); return e; }
function plain(t) { return String(t || '').replace(/`/g, ''); }
function wide() { return innerWidth > 760; }
function tag(e, m) { if (m) el('span', 'tag', e, m); return e; }

/* ---- detail: 누르면 근거·조건 ---- */
let POP = null;
function closePop() { if (POP) { POP.e.remove(); POP.o.setAttribute('aria-expanded', 'false'); POP = null; } }
function openPop(o, lines, src) {
  const was = POP && POP.o === o; closePop(); if (was) return;
  const e = el('div', 'pop', doc.body); e.setAttribute('role', 'status');
  arr(lines).forEach(l => l && el('p', '', e, l)); if (src) el('p', 'src', e, '근거: ' + src);
  const r = rc(o), w = e.offsetWidth, h = e.offsetHeight, x = clamp(r.left, 8, Math.max(8, innerWidth - w - 8));
  let y = r.bottom + 6; if (y + h > innerHeight - 6 && r.top > h + 10) y = r.top - h - 6;
  e.style.left = x + scrollX + 'px'; e.style.top = y + scrollY + 'px'; o.setAttribute('aria-expanded', 'true'); POP = { e: e, o: o };
}
function detail(e, lines, src) {
  lines = arr(lines).filter(Boolean); if (!lines.length && !src) return e;
  e.classList.add('hasd'); e.setAttribute('aria-expanded', 'false');
  if (e.tagName !== 'BUTTON') { e.tabIndex = 0; e.setAttribute('role', 'button'); e.addEventListener('keydown', ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); e.click(); } }); }
  e.addEventListener('click', ev => { ev.stopPropagation(); openPop(e, lines, src); });
  return e;
}
doc.addEventListener('click', ev => { if (POP && !POP.e.contains(ev.target)) closePop(); });

/* ---- 방금 알게 된 것 ---- */
function learn(key, t) { if (!TRY || !t || LEARN.some(x => x.k === key || x.t === t)) return; LEARN.push({ k: key, t: t }); drawLearn(); }
let drawLearn = () => {};

/* ---- 그래프: 순환 풀기 → 층 → 순서 → 자리 → 선 ---- */
function structure(N, E, arcs, cap) {
  const id = {}, out = {}; N.forEach(n => { id[n.id] = n; out[n.id] = []; });
  E = E.filter(e => id[e.from] && id[e.to] && e.from !== e.to);
  const reach = (a, b, s) => a === b || (s[a] = 1, out[a].some(x => !s[x] && reach(x, b, s)));
  E.slice().sort((a, b) => (b.main ? 1 : 0) - (a.main ? 1 : 0)).forEach(e => { e.rev = reach(e.to, e.from, {}); out[e.rev ? e.to : e.from].push(e.rev ? e.from : e.to); });
  const pre = {}; N.forEach(n => { pre[n.id] = []; }); N.forEach(n => out[n.id].forEach(x => pre[x].push(n.id)));
  const L = {}, dep = v => L[v] != null ? L[v] : (L[v] = Math.max(id[v].rk || 0, pre[v].length ? 1 + max(pre[v].map(dep)) : 0));
  N.forEach(n => dep(n.id));
  for (let k = 0; k < 4; k++) N.forEach(n => { const v = n.id; if (out[v].length && out[v].length > pre[v].length) { const t = Math.min.apply(0, out[v].map(x => L[x])) - 1; if (t > L[v]) L[v] = t; } });
  for (let k = 0; cap && k < 3; k++) uniq(N.map(n => L[n.id])).forEach(r => { const at = N.filter(n => L[n.id] === r), ends = at.filter(n => !out[n.id].length); if (at.length > cap && ends.length > 1) ends.slice(Math.ceil(ends.length / 2)).forEach(n => { L[n.id]++; }); });
  const lo = N.some(n => n.rk != null) ? 0 : Math.min.apply(0, N.map(n => L[n.id])), M = max(N.map(n => L[n.id] -= lo)), R = [], links = [], cnt = {};
  for (let r = 0; r <= 2 * M; r++) R.push([]);
  E.forEach((e, i) => { // 왕복: 이웃한 층을 가는 선 하나와 오는 선 하나는 나란한 두 줄(짝). 먼저 적힌 것이 위(왼쪽)
    if (e.rev || e.mate || L[e.to] - L[e.from] !== 1) return; const f = E.map((x, j) => [Math.abs(i - j), x, j]).filter(x => x[1].rev && !x[1].mate && x[1].from === e.to && x[1].to === e.from).sort((a, b) => a[0] - b[0])[0];
    if (f) { e.mate = f[1]; f[1].mate = f[1].back = e; e.sd = i < f[2] ? -1 : 1; f[1].sd = -e.sd; } });
  const low = {}, A = E.filter(e => { // 되돌아오는 선: 층에 넣지 않고 바깥쪽 긴 호로
    if (e.mate) return false; e.sp = L[e.from] - L[e.to]; const both = E.filter(x => x !== e && (x.from === e.from && x.to === e.to || x.from === e.to && x.to === e.from)).length;
    e.arc = !!e.rev && (arcs || e.sp > 1 || both > 1) && [e.from, e.to].every(v => (low[L[v]] || v) === v); if (e.arc) low[L[e.from]] = e.from, low[L[e.to]] = e.to; return e.arc; }).sort((a, b) => a.sp - b.sp);
  N.forEach(n => { n.it = { n: n, r: 2 * L[n.id], a: [], b: [], low: low[L[n.id]] === n.id ? 1 : 0 }; R[n.it.r].push(n.it); });
  E.forEach(e => {
    const A = id[e.rev ? e.to : e.from], B = id[e.rev ? e.from : e.to], a = 2 * L[A.id], b = 2 * L[B.id]; let best = null; e.si = id[e.from].it; e.ti = id[e.to].it; if (e.arc || e.back) return;
    for (let r = a + 1; r < b; r += 2) { const c = (cnt[r] || 0) * 10 + Math.abs(r - (e.rev ? b : a)); if (best == null || c < best.c) best = { r: r, c: c }; }
    cnt[best.r] = (cnt[best.r] || 0) + 1; e.ch = [A.it];
    for (let r = a + 1; r < b; r++) { const it = { e: e, r: r, lab: r === best.r && !!(e.t || e.mate && e.mate.t), a: [], b: [] }; R[r].push(it); e.ch.push(it); }
    e.ch.push(B.it);
    for (let i = 0; i + 1 < e.ch.length; i++) { const l = { p: e.ch[i], q: e.ch[i + 1], e: e, w: (e.main ? 3 : 1) * ((e.ch[i].n ? 1 : 2) * (e.ch[i + 1].n ? 1 : 2)) }; links.push(l); l.p.b.push(l); l.q.a.push(l); }
  });
  const cr = o => { let c = 0; for (let r = 0; r + 1 < o.length; r++) { const ls = []; o[r].forEach(it => it.b.forEach(l => ls.push(l))); for (let i = 0; i < ls.length; i++) for (let j = i + 1; j < ls.length; j++) if ((ls[i].p.k - ls[j].p.k) * (ls[i].q.k - ls[j].q.k) < 0) c++; } return c; };
  const num = o => o.forEach(rk => rk.forEach((it, i) => { it.k = i; it.f = i - (rk.length - 1) / 2; }));
  let seed = 7, best = null; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  for (let t = 0; t < 40; t++) {
    const o = R.map(rk => t ? rk.map(x => [rnd(), x]).sort((a, b) => a[0] - b[0]).map(x => x[1]) : rk.slice()); num(o);
    for (let s = 0; s < 10; s++) {
      const dn = s % 2 === 0, rs = o.map((_, i) => i); if (!dn) rs.reverse();
      rs.forEach(r => { o[r].forEach(it => { const ls = dn ? it.a : it.b; it.v = ls.length ? sum(ls.map(l => (dn ? l.p : l.q).f)) / ls.length : it.f; }); o[r] = o[r].map((x, i) => [x, i]).sort((a, b) => (a[0].low || 0) - (b[0].low || 0) || a[0].v - b[0].v || a[1] - b[1]).map(x => x[0]); num([o[r]]); });
      const c = cr(o) * 1000 + sum(links.map(l => Math.abs(l.p.f - l.q.f) * l.w)) + sum(E.filter(e => e.main && e.ch).map(e => sum(e.ch.map(i => i.k)) * .02));
      if (!best || c < best.c - 1e-9) best = { c: c, o: o.map(x => x.slice()) };
    }
  }
  num(best.o);
  return { R: best.o, links: links, N: N, E: E, M: M, A: A };
}
const PD = 8; // 나란한 두 줄의 반 간격
function slot(l) { return l.e.mate ? 2 : 1; }
function ports(S, lr) { // 상자 한 변에 닿는 선을 벌린다
  S.N.forEach(n => ['a', 'b'].forEach(k => { const ls = n.it[k].slice().sort((x, y) => (k === 'a' ? x.p.k - y.p.k : x.q.k - y.q.k)), size = lr ? n.H : n.W, tot = sum(ls.map(slot)), st = tot > 1 ? Math.min(lr ? 17 : 30, size * .74 / (tot - 1)) : 0; let c = 0;
    ls.forEach(l => { l[k === 'a' ? 'oq' : 'op'] = (c + (slot(l) - tot) / 2) * st; c += slot(l); }); }));
}
function layout(S, lr, ss, cut) {
  const R = S.R; ports(S, lr); cut = cut || -1;
  R.forEach(rk => rk.forEach(it => { if (it.n) { it.m = lr ? it.n.W : it.n.H; it.up = it.dn = (lr ? it.n.H : it.n.W) / 2; } else if (it.lab && it.r !== cut && it.e.mate) { const u = it.e.sd < 0 ? it.e : it.e.mate, d = u.mate; it.m = (lr ? Math.max(u.LW, d.LW) : Math.max(u.LH, d.LH)) + 14; it.up = PD + 4 + (lr ? u.LH : u.LW); it.dn = PD + 4 + (lr ? d.LH : d.LW); } else if (it.lab && it.r !== cut) { if (lr) { it.m = it.e.LW + 14; it.up = it.e.LH + 4; it.dn = 5; } else { it.m = it.e.LH + 14; it.up = it.dn = it.e.LW / 2; } } else { it.m = 0; it.up = it.dn = 5; } }));
  const sep = (a, b) => a.dn + b.up + (a.n && b.n ? 24 : a.lab && b.lab ? 12 : a.n || b.n ? 16 : 9) * ss;
  function put(rk, want) { // 순서를 지키면서 바라는 자리에 가장 가깝게(PAV)
    const off = [0], bl = []; for (let i = 1; i < rk.length; i++) off[i] = off[i - 1] + sep(rk[i - 1], rk[i]);
    rk.forEach((it, i) => { let b = { s: (want[i].v - off[i]) * want[i].w, w: want[i].w, n: 1 }; while (bl.length && bl[bl.length - 1].s / bl[bl.length - 1].w > b.s / b.w) { const p = bl.pop(); b = { s: p.s + b.s, w: p.w + b.w, n: p.n + b.n }; } bl.push(b); });
    let i = 0; bl.forEach(b => { for (let k = 0; k < b.n; k++, i++) rk[i].c = b.s / b.w + off[i]; });
  }
  R.forEach(rk => { let t = 0; const w = rk.map((it, i) => { if (i) t += sep(rk[i - 1], it); return t; }); put(rk, w.map(v => ({ v: v - t / 2, w: 1 }))); });
  const ok = l => l.p.r !== cut && l.q.r !== cut, side = (it, k) => it[k].filter(ok).map(l => k === 'a' ? { v: l.p.c + (l.op || 0) - (l.oq || 0), w: l.w } : { v: l.q.c + (l.oq || 0) - (l.op || 0), w: l.w });
  for (let s = 0; s < 44; s++) {
    const rs = R.map((_, i) => i); if (s % 2) rs.reverse();
    rs.forEach(r => put(R[r], R[r].map(it => { const ls = s < 30 ? side(it, s % 2 ? 'b' : 'a') : side(it, 'a').concat(side(it, 'b')); const w = sum(ls.map(x => x.w)); return w ? { v: sum(ls.map(x => x.v * x.w)) / w, w: w } : { v: it.c, w: .05 }; })));
  }
  const groups = cut > 0 ? [[0, cut - 1], [cut + 1, R.length - 1]] : [[0, R.length - 1]], G = [], lanes = cut > 0 ? R[cut].slice() : [];
  groups.forEach(g => { let c0 = 1e9, c1 = -1e9; for (let r = g[0]; r <= g[1]; r++) R[r].forEach(it => { c0 = Math.min(c0, it.c - it.up); c1 = Math.max(c1, it.c + it.dn); }); G.push({ g: g, c0: c0, c1: c1 }); });
  const T = [], X = [], B = []; let tot = 0, top = 0;
  G.forEach(o => {
    let x = 0; for (let r = o.g[0]; r <= o.g[1]; r++) {
      T[r] = B[r] = Math.max(max(R[r].map(i => i.m)), r % 2 ? (lr ? 40 : 22) : 0, S.T && S.T[r] || 0); X[r] = x; x += T[r];
      if (r < o.g[1]) { const d = max(R[r].map(it => max(it.b.map(l => Math.abs(l.p.c + (l.op || 0) - l.q.c - (l.oq || 0)))))); x += lr ? S.T ? 20 : 11 + Math.min(26, d * .2) : 12 + Math.min(20, d * .12); }
    }
    o.len = x; o.dy = top - o.c0; top += o.c1 - o.c0; tot = Math.max(tot, x);
    if (cut > 0 && o === G[0]) { o.lane = top + 12; top += 12 + sum(lanes.map(it => (it.lab ? it.e.LH : 0) + 14)) + 16; }
  });
  S.A.forEach(e => { e.lane = top + 12 + (e.lab ? lr ? e.LH + 3 : e.LW / 2 : 0); top = e.lane + (lr || !e.lab ? 4 : e.LW / 2); });
  const mg = cut > 0 ? 12 + lanes.length * 9 : 0;
  return { R: R, T: T, X: X, B: B, G: G, w: lr ? tot + 2 * mg : top, h: lr ? top : tot, lr: lr, cut: cut, lanes: lanes, mg: mg };
}
function route(S, P) {
  const lr = P.lr, grp = r => P.cut > 0 && r > P.cut ? P.G[1] : P.G[0], cy = (it, o) => it.c + (o || 0) + grp(it.r).dy, pt = (m, c) => lr ? [m + P.mg, c] : [c, m];
  const order = P.lanes.slice().sort((a, b) => a.c - b.c), K = order.length; let yl = P.cut > 0 ? P.G[0].lane : 0;
  order.slice().reverse().forEach((it, i) => { it.e.lane = yl + (it.lab ? it.e.LH : 0) + 8; yl += (it.lab ? it.e.LH : 0) + 14; it.e.ox = 10 + i * 9; it.e.ix = 10 + (K - 1 - i) * 9; });
  S.E.forEach(e => {
    const sg = [], of = e.mate ? e.sd * PD : 0, me = e.back || e; let p = null;
    if (e.arc) { const i = S.A.indexOf(e), end = (it, s) => [P.X[it.r] + P.T[it.r] / 2 + s * Math.min(8 + 12 * i, it.m / 2 - 10), cy(it) + it.dn], a = end(e.si, 1), b = end(e.ti, -1); poly([a, [a[0], e.lane], [b[0], e.lane], b], sg); e.at = { x: (a[0] + b[0]) / 2, y: e.lane }; } else me.ch.forEach((it, i, ch) => {
      const first = !i, last = i === ch.length - 1, lk = first ? it.b.filter(l => l.e === me && l.q === ch[1])[0] : it.a.filter(l => l.e === me)[0];
      if (it.r === P.cut) { const t = ch[i + 1], lt = t.a.filter(l => l.e === e)[0], y2 = cy(t, t.n ? lt.oq : 0), W = P.G[0].len; e.cutPts = [[p[0], p[1]], [W + e.ox, p[1]], [W + e.ox, e.lane], [-e.ix, e.lane], [-e.ix, y2], [0, y2]];
        poly(e.cutPts, sg);
        e.at = { x: P.G[0].len / 2, y: e.lane }; p = [0, y2]; return; }
      const x0 = P.X[it.r] + (P.T[it.r] - (it.n ? it.m : P.B[it.r])) / 2, x1 = x0 + (it.n ? it.m : P.B[it.r]), c = cy(it, first ? lk.op : last ? lk.oq : 0) + of;
      if (first) { p = [x1, c]; return; }
      if (p[0] !== x0 || p[1] !== c) { const m = (p[0] + x0) / 2; sg.push([p, [m, p[1]], [m, c], [x0, c]]); }
      if (!last) { if (x1 > x0) sg.push([[x0, c], [x0, c], [x1, c], [x1, c]]); p = [x1, c]; if (it.lab) e.at = { x: (P.X[it.r] + P.X[it.r] + P.T[it.r]) / 2, y: c }; }
    });
    let s = sg.map(g => g.map(v => pt(v[0], v[1]))); if (e.rev && !e.arc) s = s.reverse().map(g => g.slice().reverse());
    e.sg = s; if (e.at && e.mate) { const a = pt(e.at.x, e.at.y), u = e.sd < 0; e.lx = lr ? a[0] - e.LW / 2 : u ? a[0] - 5 - e.LW : a[0] + 5; e.ly = !lr ? a[1] - e.LH / 2 : u ? a[1] - 3 - e.LH : a[1] + 3; } else if (e.at) { const a = pt(e.at.x, e.at.y); e.lx = a[0] - e.LW / 2; e.ly = lr ? a[1] - e.LH - 3 : a[1] - e.LH / 2; }
  });
  S.N.forEach(n => { const it = n.it, c = cy(it), m = P.X[it.r] + P.T[it.r] / 2, a = pt(m, c); n.x = a[0] - n.W / 2; n.y = a[1] - n.H / 2; });
}
function poly(pts, sg) { // 모서리를 둥글린 꺾은선
  for (let k = 0; k + 1 < pts.length; k++) { const a = pts[k], b = pts[k + 1], d = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, u = [(b[0] - a[0]) / d, (b[1] - a[1]) / d], s = Math.min(k ? 7 : 0, d / 2), f = Math.min(k < pts.length - 2 ? 7 : 0, d / 2), A = [a[0] + u[0] * s, a[1] + u[1] * s], B = [b[0] - u[0] * f, b[1] - u[1] * f]; if (k) sg.push([sg[sg.length - 1][3], a, a, A]); sg.push([A, A, B, B]); }
}
function pathOf(sg) { return sg.map((g, i) => (i ? '' : 'M' + g[0].map(r1)) + 'C' + [g[1], g[2], g[3]].map(p => p.map(r1).join(',')).join(' ')).join(''); }
function rc(e) { return e.getBoundingClientRect(); }
function r1(v) { return Math.round(v * 10) / 10; }
function bez(g, t) { const u = 1 - t; return [0, 1].map(k => u * u * u * g[0][k] + 3 * u * u * t * g[1][k] + 3 * u * t * t * g[2][k] + t * t * t * g[3][k]); }
function graph(stage, o) {
  const N = o.nodes.map(n => cp(n)), E = o.edges.map(e => cp(e)), W = o.W, H = o.H || 0, G = el('div', 'g', stage), NM = {}, EM = {};
  N.forEach(n => { NM[n.id] = n; n.el = el('div', 'nd' + (n.key ? ' key' : '') + (n.cls ? ' ' + n.cls : ''), G); el('b', '', n.el, n.t); if (n.s) el('small', '', n.el, n.s); if (n.fill) n.fill(n.el); n.el.dataset.id = n.id; });
  const S = structure(N, E, o.arcs, W < 480 && 3); S.T = o.T; S.E.forEach(e => { EM[e.id] = e; if (!e.t) { e.LW = e.LH = 0; return; } e.lab = el('span', 'lb' + (e.rev && !e.arc ? ' bk' : ''), G); if (e.num) el('i', '', e.lab, e.num); el('span', '', e.lab, e.t); if (e.guess && !/추정/.test(e.t)) el('em', '', e.lab, ' (추정)'); if (e.c) el('small', '', e.lab, e.c); });
  G.style.fontSize = '16px'; const word = (x, m) => { x.style.width = 'min-content'; const w = rc(x).width; x.style.width = ''; return Math.min(w, m); }; N.forEach(n => { n.mw = word(n.el, 210); }); S.E.forEach(e => { if (e.lab) e.mw = word(e.lab, 170); }); // 가장 긴 낱말의 폭(16px일 때): 낱말 가운데서 갈리지 않게
  const deg = k => n => sum(n.it[k].map(slot)), PRE = o.pre || { lr: [[176, 150], [146, 124], [118, 98], [100, 84], [84, 72]], tb: [[200, 190], [160, 140], [124, 110], [100, 84], [84, 72]] };
  function size(fs, nw, lw, lr) {
    G.style.fontSize = fs + 'px'; G.classList.toggle('lr', lr); const k = fs / 16;
    N.forEach(n => { const s = n.el.style; s.width = s.height = ''; s.maxWidth = Math.ceil(Math.max(nw * (n.t.length > 36 ? 1.5 : 1), n.mw * 1.04) * k) + 2 + 'px'; s.minHeight = lr ? Math.max(2.5 * fs, max([deg('a')(n), deg('b')(n)]) * 16) + 'px' : 2.5 * fs + 'px'; s.minWidth = lr ? '' : Math.max(3 * fs, max([deg('a')(n), deg('b')(n)]) * 22) + 'px'; s.width = 'max-content'; });
    S.E.forEach(e => { if (e.lab) { e.lab.style.maxWidth = Math.ceil(Math.max(lw * k * (!e.arc ? 1 : lr ? 2 : .75), e.mw * Math.max(k, e.c ? 1 : .91) * 1.04)) + 2 + 'px'; e.lab.style.width = 'max-content'; } });
    N.forEach(n => { n.W = Math.ceil(rc(n.el).width) + 1; n.H = Math.ceil(rc(n.el).height); });
    S.E.forEach(e => { if (e.lab) { const b = rc(e.lab); e.LW = Math.ceil(b.width) + 1; e.LH = Math.ceil(b.height); } });
    S.R.forEach((rk, r) => { if (r % 2) return; const ns = rk.filter(i => i.n).map(i => i.n), k2 = lr ? 'W' : 'H', m = max(ns.map(n => n[k2])); ns.forEach(n => { n[k2] = m; }); });
  }
  const fmax = o.fsMax || 20, fmin = o.fsMin || 13; let pick = null, fall = null;
  const dirs = o.dirs || (W < 640 ? ['tb', 'lr'] : ['lr', 'tb']);
  const tall = H > W * .62 && W >= 640 && !o.dirs; // 키 큰 칸에서는 위→아래부터
  for (let fs = fmax, top = tall; (fs >= fmin || top) && !pick; fs--) { if (top && fs < 16) { top = 0; fs = fmax; } (top ? ['tb'] : dirs).forEach(d => PRE[d].forEach((p, pi) => {
    const lr = d === 'lr'; if (pi > 3 && fs > 14) return; size(fs, p[0], p[1], lr);
    const mid = 2 * Math.floor(S.M / 2) + 1; [0].concat(lr && H && fs < 16 && S.M >= 3 && !S.A.length && !S.E.some(e => e.mate && e.ch && e.ch[1].r === mid) ? [1] : []).forEach(fold => {
      const cut = fold ? mid : 0, L = layout(S, lr, 1, cut), over = Math.max(L.w / W, H ? L.h / H : 0), c = { fs: fs, p: p, lr: lr, cut: cut, over: over, w: L.w, h: L.h };
      if (over <= 1) { const sc = (H ? Math.min(1.6, W / L.w, H / L.h) : 1) * (lr ? W < 640 ? .5 : 1.12 : 1) * (1 - .13 * PRE[d].indexOf(p)); if (!pick || sc > pick.sc) { c.sc = sc; pick = c; } }
      else { c.cost = (L.w > W + 1 ? 100 * L.w / W : 0) + (H ? L.h / H : L.h / 1e5); if (!fall || c.cost < fall.cost) fall = c; } // 다 안 들면 폭부터 맞춘다(옆으로 잘리지 않게)
    });
  })) }
  const C = pick || fall; size(C.fs, C.p[0], C.p[1], C.lr);
  let P = null; for (const ss of [3.4, 2.6, 2.1, 1.7, 1.35, 1]) { P = layout(S, C.lr, ss, C.cut); if (ss === 1 || P.w <= W && (H ? P.h <= H * .97 : ss <= 1.35)) break; }
  const T = C.lr && S.T, main = T ? sum(T) + 20 * (T.length - 1) : C.lr ? P.w : P.h, room = C.lr ? W : H; // 남는 길이는 선에 나눠 준다
  if (room && room > main) { const gaps = P.G.map(g => (g.g[1] - g.g[0]) / 2), k = T ? (T.length - 1) / 2 : max(gaps); if (k) { const add = Math.min((room - main) * .96 / k, C.lr ? 130 : 70); P.G.forEach(o2 => { let s = 0; for (let r = o2.g[0]; r <= o2.g[1]; r++) { P.X[r] += s; if (r % 2) { P.T[r] += add; s += add; } } o2.len += s; }); if (C.lr) P.w += add * max(gaps); else P.h += add * k; } }
  route(S, P); const w = Math.max(P.w, 40), h = P.h;
  G.style.width = w + 'px'; G.style.height = h + 'px'; if (H && h < H) G.style.marginTop = Math.floor((H - h) / 2) + 'px'; if (o.left) G.style.marginLeft = 0;
  stage.classList.toggle('scroll', w > W + 1);
  const svg = sv('svg', { width: w, height: h, 'aria-hidden': 'true' }, G);
  N.forEach(n => { const s = n.el.style; s.left = r1(n.x) + 'px'; s.top = r1(n.y) + 'px'; s.width = n.W + 'px'; s.height = n.H + 'px'; s.maxWidth = 'none'; });
  S.E.forEach(e => {
    const g = e.g = sv('g', { 'class': 'eg' + (e.main ? ' main' : '') + (e.guess ? ' guess' : '') }, svg), z = e.sg[e.sg.length - 1], a0 = e.sg[0];
    function head(tip, from) { const a = Math.atan2(tip[1] - from[1], tip[0] - from[0]), f = (r, s) => r1(tip[0] - Math.cos(a + s) * r) + ',' + r1(tip[1] - Math.sin(a + s) * r); sv('path', { 'class': 'hd', d: 'M' + tip.map(r1) + 'L' + f(11, .42) + 'L' + f(11, -.42) + 'Z' }, g); }
    const dirOf = s => s[2][0] === s[3][0] && s[2][1] === s[3][1] ? s[0] : s[2], back = s => [s[3], s[2], s[1], s[0]];
    e.ln = sv('path', { 'class': 'ln', d: pathOf(e.sg) }, g); head(z[3], dirOf(z)); if (e.both) head(a0[0], dirOf(back(a0)));
    if (e.lab) { e.lab.style.left = r1(e.lx) + 'px'; e.lab.style.top = r1(e.ly) + 'px'; e.lab.style.width = e.LW + 'px'; e.lab.style.maxWidth = 'none'; if (e.main) e.lab.classList.add('main'); }
  });
  let raf = 0, tok = null;
  const api = { el: G, fs: C.fs, w: w, h: h, lr: C.lr, T: C.lr && !C.cut && P.B, over: C.over, N: NM, E: EM, edges: S.E,
    node(id) { return NM[id] && NM[id].el; },
    cls(id, c) { const e = EM[id]; if (e) [e.g, e.lab].forEach(x => x && tog(x, c)); },
    ncls(id, c) { if (NM[id]) tog(NM[id].el, c); },
    light(es, ns, dim) { es = arr(es); ns = arr(ns).slice(); es.forEach(i => EM[i] && ns.push(EM[i].from, EM[i].to)); S.E.forEach(e => api.cls(e.id, { on: es.indexOf(e.id) >= 0, dim: dim && es.indexOf(e.id) < 0 })); N.forEach(n => tog(n.el, { on: ns.indexOf(n.id) >= 0, dim: dim && ns.indexOf(n.id) < 0 })); },
    run(es) { cancelAnimationFrame(raf); if (tok) tok.remove(); tok = null; const L = arr(es).map(i => EM[i]).filter(Boolean).map(e => e.ln); if (RM || !L.length) return; tok = sv('circle', { r: 6.5, 'class': 'tok', cx: -99, cy: -99 }, svg); let t0 = null; const dur = Math.max(1300, L.length * 850);
      raf = requestAnimationFrame(function f(t) { if (t0 == null) t0 = t; const u = ((t - t0) / dur) % 1 * L.length, i = Math.min(L.length - 1, u | 0); let v = clamp((u - i - .1) / .8, 0, 1); v = v * v * (3 - 2 * v); const p = L[i].getPointAtLength(L[i].getTotalLength() * v); if (!tok) return; tok.setAttribute('cx', p.x); tok.setAttribute('cy', p.y); if ((t - t0) < dur * 2.2) raf = requestAnimationFrame(f); else { tok.remove(); tok = null; } }); },
    check() { const w2 = [], bx = (x, y, W2, H2) => [x, y, x + W2, y + H2], hit = (a, b) => Math.min(a[2], b[2]) - Math.max(a[0], b[0]) > 1.5 && Math.min(a[3], b[3]) - Math.max(a[1], b[1]) > 1.5; const nb = N.map(n => ({ i: n.id, b: bx(n.x, n.y, n.W, n.H) })), lb = S.E.filter(e => e.lab).map(e => ({ i: e.t, e: e, b: bx(e.lx, e.ly, e.LW, e.LH) }));
      nb.concat(lb).forEach((a, i, all) => all.slice(i + 1).forEach(b => { if (hit(a.b, b.b)) w2.push('겹침: ' + a.i + ' × ' + b.i); }));
      S.E.forEach(e => { const bad = {}; e.sg.forEach(g => { for (let t = .05; t < 1; t += .1) { const p = bez(g, t); nb.forEach(n => { if (n.i !== e.from && n.i !== e.to && p[0] > n.b[0] + 2 && p[0] < n.b[2] - 2 && p[1] > n.b[1] + 2 && p[1] < n.b[3] - 2) bad[n.i] = 1; }); lb.forEach(l => { if (l.e !== e && p[0] > l.b[0] + 2 && p[0] < l.b[2] - 2 && p[1] > l.b[1] + 2 && p[1] < l.b[3] - 2) bad['라벨 ' + l.i] = 1; }); } }); Object.keys(bad).forEach(k => w2.push('선이 지남: ' + e.from + '→' + e.to + ' × ' + k)); });
      N.forEach(n => { if (n.el.scrollWidth > n.el.clientWidth + 1 || n.el.scrollHeight > n.el.clientHeight + 1) w2.push('상자 넘침: ' + n.t); });
      if (C.fs < 13) w2.push('글자 작음: ' + C.fs); if (w > W + 1 && W >= 640) w2.push('그림이 칸보다 넓다 ' + Math.round(w) + '>' + W); if (H && h > H + 2) w2.push('참고: 그림이 칸보다 높다 ' + Math.round(h) + '>' + Math.round(H)); return w2; } };
  return api;
}

/* ---- 칸 공통 ---- */
function Fig(host, d) { // 조작 줄 · 그림 · 말
  const F = { host: host, d: d, bar: el('div', 'bar', host), stage: el('div', 'stage', host), cap: el('div', 'cap', host), say: el('div', 'say', host), step: null, states: [], checks: [] };
  if (!F.d.title) {} else host.insertBefore(el('h2', '', null, F.d.title), F.bar);
  F.say.setAttribute('aria-live', 'polite');
  F.W = () => Math.floor(F.stage.clientWidth); F.H = () => wide() ? Math.max(TRY ? 280 : 120, Math.floor(F.stage.clientHeight)) : 0;
  F.tell = (k, t, src, cls) => { F.say.className = 'say ' + (cls || ''); F.say.textContent = ''; if (k) el('b', '', F.say, k); if (t) el('span', '', F.say, t); if (src) el('span', 'src', F.say, '근거: ' + src); };
  F.clear = () => { keep(F); F.stage.textContent = F.stage.style.minHeight = ''; F.stage.className = 'stage'; F.checks = []; };
  return F;
}
function keep(F) { // 지우고 다시 그려도 초점은 같은 단추에(없어졌으면 같은 글의 다음 단추, 같은 자리, 첫 단추 순)
  const a = doc.activeElement; if (F.kept || !a || !F.host.contains(a)) return; const c = a.className.split(' ')[0], all = () => qa('button,[role=button]', F.host).filter(e => e.className.split(' ')[0] === c && !e.disabled), same = L => L.filter(e => e.textContent === a.textContent), L = all(), n = same(L).indexOf(a), i = L.indexOf(a); F.kept = 1;
  queueMicrotask(() => { F.kept = 0; if (a.isConnected && !a.disabled) return; const M = all(), S = same(M), e = S[Math.min(n, S.length - 1)] || c !== 'bt' && M[i] || q('.bt:not(:disabled)', F.host); if (e) e.focus({ preventScroll: true }); });
}
function group(F, label, items, fn, cls) { // 하나 고르기. 숫자 키는 화면에 보이는 순서
  const g = el('div', 'grp', F.bar); if (label) el('span', '', g, label); g.setAttribute('role', 'group'); g.setAttribute('aria-label', label || '고르기');
  const bs = items.map((t, i) => btn(g, 'bt ' + (cls || ''), t, () => fn(i)));
  return { el: g, bs: bs, set(i) { bs.forEach((b, j) => b.setAttribute('aria-pressed', Array.isArray(i) ? i.indexOf(j) >= 0 : i === j)); } };
}
function fitText(box, H, hi, lo) { // 글자를 줄여 높이에 맞춘다(13px 밑으로는 내리지 않는다)
  const tight = () => qa('.opt td', box).some(c => c.scrollWidth > c.clientWidth + 1); box.classList.remove('brk');
  let f = H ? hi : Math.min(hi, 16); box.style.minHeight = ''; box.style.height = 'auto';
  for (; H && f > lo; f -= .5) { box.style.fontSize = f + 'px'; if (box.scrollHeight <= H && box.scrollWidth <= box.clientWidth + 1 && !tight()) break; }
  box.classList.toggle('brk', tight());
  box.style.fontSize = f + 'px'; if (H) { box.style.minHeight = H + 'px'; box.style.height = H + 'px'; if (box.scrollHeight > H + 1) box.style.height = 'auto'; }
  return f;
}
function nodesOf(d, es) { const used = {}; es.forEach(e => { used[e.from] = used[e.to] = 1; }); return (d.nodes || []).filter(n => used[n.id]); }
function legend(F, items) { items.forEach(x => { const s = el('span', '', F.cap), i = el('i', x[2] ? 'dash' : '', s); i.style.setProperty('--k', x[0]); s.appendChild(doc.createTextNode(x[1])); }); }
function tip(G, d) { (d.edges || []).forEach(e => { const x = G.E[e.id]; if (x && x.lab) detail(x.lab, [plain(G.N[e.from].t) + ' → ' + plain(G.N[e.to].t) + ': ' + plain(e.t)].concat(e.if ? '조건: ' + e.if : []), e.src); }); (d.nodes || []).forEach(n => { if (G.N[n.id] && (n.d || n.src)) detail(G.N[n.id].el, n.d, n.src); }); }

/* ---- beforeafter: 전 · 후 ---- */
PART.beforeafter = F => {
  const d = F.d, E = d.edges || [], cs = TRY ? d.cases || [] : [], vis = k => E.filter(e => !e.when || e.when === 'both' || e.when === k), cols = e => e.when === 'after' ? { add: 1 } : e.when === 'before' ? { del: 1 } : {}, KS = ['before', 'after'];
  let pick = -1, gs = [], out = [], cg; const RK = {}, U = nodesOf(d, E).map(n => cp(n)); structure(U, E.map(e => cp(e)), 1).N.forEach(n => { RK[n.id] = n.it.r / 2; });
  function draw() {
    F.clear(); const W = F.W(), H = F.H(), wd = W >= 640, rw = cs.length && wd ? 250 : 0, box = el('div', 'ba', F.stage);
    const gw = wd ? W - 60 - rw : W, gh = H ? (H - 10) / 2 - 2 : 0;
    let hs = [gh, gh]; const mk = (fx, T) => { box.textContent = ''; out = []; return KS.map((k, i) => { const p = el('div', (i ? 'aft' : 'bef') + (!wd ? '' : rw ? ' r3' : ' r2'), box); el('h3', '', p, i ? '후' : '전'); const g = graph(el('div', '', p), { nodes: nodesOf(d, vis(k)).map(n => cp(n, { rk: RK[n.id] })), edges: vis(k).map(e => cp(e, { main: 0 })), arcs: 1, W: gw, H: hs[i], fsMax: fx, left: wd, T: T }); if (cs.length) out.push(el('div', 'res', p)); vis(k).forEach(e => g.cls(e.id, cols(e))); tip(g, d); return g; }); };
    gs = mk(TRY ? 20 : 24); const low = () => Math.min(gs[0].fs, gs[1].fs) - max(gs.map(g => g.over > 1 ? g.over : 0)); if (H && wd) { const a = low(), k = clamp(gs[0].h / (gs[0].h + gs[1].h), .25, .75); hs = [gh * 2 * k, gh * 2 * (1 - k)]; gs = mk(TRY ? 20 : 24); if (low() < a) { hs = [gh, gh]; gs = mk(TRY ? 20 : 24); } }
    const m = Math.min(gs[0].fs, gs[1].fs); if (gs[0].fs !== gs[1].fs) gs = mk(m); for (let f = m; wd && gs[0].T && gs[1].T && f >= 13; f--) { if (f < m) gs = mk(f); const a = gs[0].T || [], b = gs[1].T || [], T = (a.length > b.length ? a : b).map((v, i) => Math.max(v, (a.length > b.length ? b : a)[i] || 0)); gs = mk(f, T); if (gs.every(g => g.lr && g.over <= 1 && g.fs === f)) break; gs = f > m - 3 ? mk(f) : mk(m); if (f <= m - 3) break; }
    F.need = wd ? Math.max(cs.length ? 210 : 0, sum(gs.map(g => g.h)) + 30) : 0; F.checks = gs.map(g => g.check); F.cap.textContent = ''; [['before', 'del', '빠짐'], ['after', 'add', '더해짐'], ['both', 'sub', '그대로']].forEach(x => { if (E.some(e => (e.when || 'both') === x[0])) legend(F, [['var(--' + x[1] + ')', x[2]]]); });
    if (cs.length) show();
  }
  function show() {
    cg.set(pick); const c = cs[pick], same = c && (c.same || plain(c.before) === plain(c.after)), only = c ? arr(c.edges) : [];
    gs.forEach((g, i) => { const es = vis(KS[i]).map(e => e.id).filter(x => only.indexOf(x) >= 0); g.light(es, [], !!c); g.run(es); const o = out[i]; o.className = 'res' + (!c ? '' : i && !same ? ' chg' : ' on'); o.textContent = ''; el('small', '', o, !c ? '결과' : i ? (same ? '전과 같다' : '달라진다') : '결과'); el('b', '', o, c ? (i ? c.after : c.before) || '원문에 없음' : '?'); });
    if (c) { F.tell(c.input, same ? '전과 후가 같다.' : '여기서 갈라진다.', c.src, same ? '' : 'ok'); learn('c' + pick, plain(c.input) + ': ' + (same ? '전·후가 같다 — ' + c.before : '전 “' + c.before + '” → 후 “' + c.after + '”')); } else F.tell('', '상황을 고르면 전과 후의 결과가 함께 열린다. (←→)');
  }
  if (cs.length) { cg = group(F, '이 상황이면', cs.map(c => c.input), i => { pick = pick === i ? -1 : i; show(); }); F.step = k => { pick = clamp(pick + k, -1, cs.length - 1); show(); }; }
  F.focus = ids => gs.forEach((g, i) => { const es = vis(KS[i]).map(e => e.id).filter(x => ids.indexOf(x) >= 0); g.light(es, [], es.length > 0); g.run(es); });
  cs.forEach(c => PATHS.push('상황 ' + plain(c.input) + ' · 전 → ' + c.before + ' · 후 → ' + c.after));
  return { draw: draw };
};

function order(E, has) { // 왕복이 있고 적힌 차례대로 이어지면(앞 선의 끝 = 다음 선의 시작) 그 길에 번호를 단다
  if (has || E.some(e => /[①-⑫]/.test(e.t))) return E; let b = [0, 0], a = 0; E.forEach((e, i) => { if (i && E[i - 1].to !== e.from) a = i; if (i - a >= b[1] - b[0]) b = [a, i + 1]; });
  const R = E.slice(b[0], b[1]); return R.length > 2 && R.some(e => R.some(x => x.from === e.to && x.to === e.from)) ? E.map((e, i) => i < b[0] || i >= b[1] ? e : cp(e, { num: NUM[i - b[0]] })) : E;
}
/* ---- flow · map: 관계 그림. 조건을 누르면 그 간선만, 길(path)이 있으면 한 칸씩 ---- */
PART.flow = PART.map = F => {
  const d = F.d, path = arr(d.path), Z = arr(d.zones), E = order(arr(d.edges).map(e => path.indexOf(e.id) < 0 ? e : cp(e, { main: true, num: NUM[path.indexOf(e.id)] })), path.length), old = E.filter(e => e.when === 'before');
  const N = nodesOf({ nodes: arr(d.nodes).map(n => { const z = Z.filter(x => x.id === n.id)[0]; return z ? cp(n, { s: n.s || z.does, src: n.src || z.src }) : n; }) }, E), rest = Z.filter(z => !N.some(n => n.id === z.id)), nb = id => E.filter(e => e.from === id || e.to === id).map(e => e.id);
  const qs = arr(d.flips).map(x => ({ q: x.if, a: x.then, edges: x.edges, nodes: x.nodes, part: x.part, src: x.src, flip: 1 })).concat(arr(d.qas)); let G, k = -1, f = -1, sel = null, qg;
  function draw() {
    F.clear(); const st = el('div', '', F.stage), z = rest.length ? el('div', 'zs', F.stage) : null;
    rest.forEach(x => { const c = el('div', 'cd', z); el('b', '', c, x.t); el('span', '', c, x.does); detail(c, x.grade ? '읽은 정도: ' + x.grade : [], x.src); });
    const zh = z ? z.offsetHeight + 10 : 0, H = F.H(), top = F.host.offsetHeight - F.stage.clientHeight; G = graph(st, { nodes: N, edges: E, W: F.W(), H: H && H - zh, fsMax: d.fsMax || (TRY ? path.length ? 18 : 21 : 24) }); F.need = G.lr ? G.h + zh : 0; if (H && G.h + zh > H + 2) { F.want = top + Math.ceil(G.h + zh); F.stage.style.minHeight = Math.ceil(G.h + zh) + 'px'; } F.checks = [G.check]; F.cap.textContent = ''; old.forEach(e => G.cls(e.id, { old: 1 }));
    if (E.some(e => e.main) && (path.length || E.some(e => !e.main && e.when !== 'before'))) legend(F, [['var(--accent)', path.length ? '요청 하나의 길 ' + NUM[0] + '→' + NUM[path.length - 1] : '핵심 길']]); if (old.length) legend(F, [['var(--sub)', '없어짐', 1]]); if (E.some(e => e.guess)) legend(F, [['var(--sub)', '추정', 1]]);
    tip(G, { edges: E, nodes: TRY ? [] : N }); if (!TRY) return;
    N.forEach(n => { const e = G.node(n.id), go = ev => { ev.stopPropagation(); sel = sel === n.id ? null : n.id; k = f = -1; show(); }; e.tabIndex = 0; e.setAttribute('role', 'button'); e.classList.add('hasd'); e.addEventListener('click', go); e.addEventListener('keydown', ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); go(ev); } }); }); show();
  }
  function show() {
    const x = qs[f], fe = x ? arr(x.edges) : [], i0 = path.findIndex(p => fe.indexOf(p) >= 0), stop = i0 < 0 ? 99 : i0, at = Math.min(k, stop), e = G.E[path[at]]; if (qg) qg.set(f);
    E.forEach(y => G.cls(y.id, { warn: x && x.flip && fe.indexOf(y.id) >= 0 }));
    if (sel) { const es = nb(sel), n = G.N[sel]; G.light(es, [sel], true); G.run(es); F.tell(n.t, n.d || es.map(i => { const y = G.E[i]; return (y.from === sel ? '→ ' + plain(G.N[y.to].t) : '← ' + plain(G.N[y.from].t)) + ' (' + plain(y.t) + ')'; }).join(' · '), n.src); }
    else if (x && (k < 0 || k >= stop || i0 < 0)) { const es = uniq(i0 < 0 ? fe : path.slice(0, stop + 1).concat(fe)), ns = arr(x.nodes); G.light(es, ns, es.length + ns.length > 0); G.run(es); F.tell(x.flip ? '→' : '답', x.a, x.src, x.flip ? 'wa' : ''); if (x.part) focusAll(arr(x.part), F); learn('q' + f, plain(x.q) + ' → ' + x.a); }
    else if (k >= 0) { G.light(path.slice(0, at + 1), [], true); G.run([path[at]]); F.tell(k + 1 + '/' + path.length, plain(G.N[e.from].t) + ' → ' + plain(G.N[e.to].t) + ': ' + e.t, e.src); if (k === path.length - 1) learn('path', '요청의 길: ' + path.map(i => plain(G.N[G.E[i].from].t)).concat(plain(G.N[e.to].t)).join(' → ')); }
    else { G.light([], [], false); G.run([]); F.tell('', path.length ? '▶를 눌러 요청을 한 칸씩 흘려 보낸다. 조건을 켜면 어디서 바뀌는지 보인다.' : qs.length ? '위 단추를 누르면 그때의 길이 켜진다. 상자를 눌러도 된다.' : '상자를 누르면 이어진 것이 켜진다.'); }
  }
  const mv = n => { sel = null; k = clamp(n, -1, path.length - 1); show(); };
  if (TRY && path.length) group(F, '요청', ['◀ 뒤로', '앞으로 ▶', '처음부터'], i => mv(i > 1 ? -1 : k + (i ? 1 : -1)));
  if (TRY && qs.length) qg = group(F, arr(d.flips).length ? '이러면' : '물어보기', qs.map(x => x.q), i => { f = f === i ? -1 : i; sel = null; show(); }, 'flip');
  if (TRY && (path.length || qs.length)) F.step = s => { if (path.length) mv(k + s); else { f = clamp(f + s, -1, qs.length - 1); sel = null; show(); } };
  F.focus = ids => { if (!G) return; const es = E.filter(e => ids.indexOf(e.id) >= 0).map(e => e.id), ns = N.filter(n => ids.indexOf(n.id) >= 0).map(n => n.id); G.light(es, ns, es.length + ns.length > 0); G.run(es); };
  qs.forEach(x => PATHS.push(plain(x.q) + ' → ' + x.a)); if (path.length) PATHS.push('길: ' + path.join(' → '));
  return { draw: draw };
};

/* ---- options: 선택지 × 기준 ---- */
PART.options = F => {
  const d = F.d, O = d.options || [], C = d.criteria || [], X = d.cells || [], cell = (o, c) => X.filter(x => x.o === o && x.c === c)[0], SG = { '+': ['p', '＋'], '-': ['m', '−'], '?': ['q', '?'] };
  let on = {}, g;
  function draw() {
    F.clear(); const box = el('div', 'rowsfill', F.stage), t = el('table', 't opt', box), h = el('tr', '', el('thead', '', t)), act = C.filter((_, i) => on[i]); el('th', '', h, '');
    const live = {}; O.forEach(o => { const bad = act.filter(c => { const x = cell(o.id, c.id); return x && x.sign === '-'; }); live[o.id] = bad; const th = el('th', (o.chosen ? 'ch' : '') + (bad.length ? ' off' : ''), h, o.t); if (o.chosen) el('span', 'tal', th, '← 고른 것'); if (act.length) { const n = s => act.filter(c => { const x = cell(o.id, c.id); return x && x.sign === s; }).length; el('span', 'tal', th, '＋' + n('+') + ' −' + n('-')); } detail(th, o.d || [], o.src); });
    const b = el('tbody', '', t); C.forEach((c, i) => { const r = el('tr', on[i] ? 'sel' : '', b); el('th', '', r, c.t); O.forEach(o => { const x = cell(o.id, c.id), td = el('td', (o.chosen ? 'ch' : '') + (!x ? ' none' : ''), r); td.dataset.o = o.t; if (!x) { td.textContent = '원문에 없음'; return; } const s = SG[x.sign]; if (s) el('span', 'sg ' + s[0], td, s[1]); el('span', '', td, x.t); detail(td, [], x.src); }); });
    if (arr(d.open).length) { const o = el('div', 'open', box); el('b', '', o, '아직 안 정함'); d.open.forEach(x => detail(el('span', '', o, x.t), [], x.src)); }
    const H = F.H(); fitText(box, H, 20, 13.5); if (H && box.scrollHeight <= H + 1) t.style.height = H - (q('.open', box) ? q('.open', box).offsetHeight : 0) - 2 + 'px';
    if (TRY) { g.set(C.map((_, i) => i).filter(i => on[i])); if (!act.length) F.tell('', '중요한 기준을 고른다. 문서가 든 이유로 무엇이 남는지 보인다.'); else { const left = O.filter(o => !live[o.id].length), drop = O.filter(o => live[o.id].length); F.tell('남는 것: ' + (left.length ? left.map(o => plain(o.t)).join(', ') : '없음'), drop.length ? '빠지는 것: ' + drop.map(o => plain(o.t) + '(' + live[o.id].map(c => plain(c.t)).join(', ') + ' −)').join(' · ') : '', '', left.some(o => o.chosen) ? 'ok' : 'wa'); learn('o' + act.map(c => c.id).join(), act.map(c => plain(c.t)).join(' + ') + ' → 남는 것: ' + (left.map(o => plain(o.t)).join(', ') || '없음')); } }
  }
  if (TRY) { g = group(F, '중요한 기준', C.map(c => c.t), i => { on[i] = !on[i]; draw(); }); C.forEach(c => PATHS.push('기준 ' + plain(c.t) + ': ' + O.map(o => { const x = cell(o.id, c.id); return plain(o.t) + ' ' + (x ? x.sign + ' ' + x.t : '원문에 없음'); }).join(' / '))); }
  return { draw: draw };
};

/* ---- claim: 결과 막대(묶음 = 지표, 막대 = 조건). 결과가 없으면 흐름 ---- */
PART.claim = PART.chart = F => {
  const d = F.d, R = d.results || []; if (!R.length) return PART.flow(F);
  const UN = { ns: 't1e-9', 'µs': 't1e-6', us: 't1e-6', ms: 't1e-3', '밀리초': 't1e-3', s: 't1', sec: 't1', '초': 't1', min: 't60', '분': 't60', h: 't3600', '시간': 't3600', KB: 'b1e3', MB: 'b1e6', GB: 'b1e9', TB: 'b1e12', k: 'n1e3', K: 'n1e3', M: 'n1e6', '천': 'n1e3', '만': 'n1e4', '억': 'n1e8' };
  const per = (a, b) => { if (a === b || !a || !b || a[0] === '%' && b[0] === '%') return 1; const x = UN[a], y = UN[b]; return x && y && x[0] === y[0] ? x.slice(1) / y.slice(1) : null; }; // 단위 a → b 배수. 바꿀 수 없으면 null
  const num = v => { const m = String(v == null ? '' : v).replace(/[−–]/g, '-').replace(/,/g, '').match(/([-+]?\d*\.?\d+)\s*([a-zA-Zµ가-힣%]*)/); return m ? [parseFloat(m[1]), m[2] === '%' || UN[m[2]] ? m[2] : ''] : [null, '']; };
  const numeric = b => typeof b === 'number' || /^\s*[-+−–]?\s*[\d.,]+\s*(%|[a-zA-Zµ가-힣]{0,3})\s*$/.test(String(b)), near = (a, b) => Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(a));
  R.forEach(r => { const a = num(r.value), b = numeric(r.base) && num(r.base); r.v = a[0]; r.u = a[1] || r.unit || ''; const k = b ? per(b[1] || r.u, r.u) : null; r.b = k == null || /^\s*\+/.test(String(r.value)) ? null : b[0] * k; r.sec = r.group ? r.label : ''; r.nm = r.group || r.label; }); // 기준을 값과 같은 단위로. ‘+5’처럼 적은 변화는 0과 견준다
  R.forEach(r => { const o = r.base && R.filter(x => x !== r && x.sec === r.sec && x.nm === r.base)[0], k = o && per(o.u, r.u); if (r.b == null && o && k != null && !/^\s*[-+−]/.test(String(r.value))) r.b = o.v * k; }); // 기준이 다른 항목의 이름이면 그 값
  const secs = uniq(R.map(r => r.sec)), major = {}; secs.forEach(s => { const u = R.filter(r => r.sec === s && !r.ref).map(r => r.u), n = x => u.filter(y => y === x).length; major[s] = uniq(u).sort((a, b) => n(b) - n(a))[0] || ''; });
  R.forEach(r => { const k = r.u && major[r.sec] ? per(r.u, major[r.sec]) : null; if (k != null && r.v != null) { r.v *= k; if (r.b != null) r.b *= k; r.u = major[r.sec]; } });
  const txtOnly = r => r.v == null && !r.flat && !/없음|비슷|같/.test(String(r.value) + (r.cond || '')) || r.u !== major[r.sec] || r.ref === true, bars = R.filter(r => !txtOnly(r)); bars.forEach(r => { if (r.v == null) r.v = r.b || 0; });
  const sg1 = r => r.b == null && (/^\s*[-+−]/.test(String(r.value)) || r.v < 0), same = r => r.flat || /차이 없|구별 안|유의하지|비슷/.test((r.cond || '') + ' ' + r.value), plus = r => r.b == null && /^\s*\+/.test(String(r.value)) && !/[°℃℉]/.test(r.value + (r.unit || '')), chg = r => plus(r) || r.b == null && (sg1(r) || same(r)) && bars.some(x => plus(x) && (x.sec === r.sec || x.base && x.base === r.base && x.u === r.u)), rel = r => r.b != null || chg(r), bad = r => r.b != null ? (r.lower ? r.v > r.b : r.v < r.b) : chg(r) && (r.lower ? r.v > 0 : r.v < 0), // 견줄 기준은 행마다: 기준값이 있거나, 변화량으로 적혀 있거나(+, 또는 같은 묶음·같은 기준에 +가 있는 −·차이 없음). 기준 이름만 있으면 기준 없음
    neg = bars.some(r => r.v < 0), lim = u => { const w = bars.filter(r => r.u === u), v = w.map(r => r.v).concat(w.map(r => r.b || 0)); return { hi: Math.max(0, max(v)), lo: Math.min(0, Math.min.apply(0, v)) }; };
  const shown = {};
  let sel = -1, gg, txt0 = '';
  const dir = r => same(r) || near(r.v, r.b || 0) ? 0 : r.v > (r.b || 0) ? 1 : -1; // ‘비슷하다’는 원문이 차이 없음이라 적었거나 값이 같을 때만
  const val = r => (r.show != null ? r.show : typeof r.value === 'number' ? (!r.ref && chg(r) && r.value > 0 ? '+' : '') + String(r.value).replace('-', '−') + (r.unit || '') : String(r.value) + (r.unit && /\d\s*$/.test(String(r.value)) ? r.unit : ''));
  function open(r, g) { shown[r.id] = 1; const ok = g == null ? null : g === dir(r); draw(); F.tell(ok == null ? val(r) : ok ? '맞음' : '다름', (r.sec ? r.sec + ' · ' : '') + plain(r.nm) + ' ' + val(r) + (r.cond ? ' (' + r.cond + ')' : ''), r.src, ok == null ? '' : ok ? 'ok' : 'no'); learn('r' + r.id, (r.sec ? r.sec + ' · ' : '') + plain(r.nm) + ': ' + val(r) + (r.cond ? ' (' + r.cond + ')' : '') + (r.base && r.b == null ? ' — 기준: ' + r.base : '')); }
  function draw() {
    F.clear(); const box = el('div', 'bars', F.stage); box.style.setProperty('--lw', wide() ? '9.5em' : '6.2em');
    secs.filter((_, i) => sel < 0 || sel === i).forEach(sc => { const gb = el('div', 'bg', box), rr = R.filter(r => r.sec === sc), bs = uniq(rr.map(r => r.base).filter(b => b != null && b !== '')), one = bs.length === 1 && bs[0], ln = rr.some(r => r.b != null); if (sc || one || ln) { const h = el('h4', '', gb, sc); if (one || ln) el('small', '', h, (ln ? ' 점선 = 기준' : rr.some(chg) && !(one && numeric(one)) ? ' 기준(0)' : ' 기준') + (!one ? '' : numeric(one) ? ' ' + one + (/[%a-zA-Z가-힣]/.test(one) ? '' : rr[0].unit || '') : ln ? '(' + one + ')' : ' = ' + one)); }
      rr.forEach(r => { const row = el('div', 'br', gb), nm = el('div', 'nm', row, r.nm), tr = el('div', 'tr', row); tag(nm, r.mark);
          const l = lim(r.u), span = (l.hi - l.lo) || 1, z = -l.lo / span, x0 = neg ? .02 : 0, xw = wide() ? .7 : .52, X = f => 'calc(' + r1((x0 + f * (xw - x0)) * 1000) / 10 + '%)';
          if (txtOnly(r)) { const t = el('div', 'tx ref', tr, val(r)); if (r.cond) el('small', '', t, r.cond); t.style.marginLeft = 'calc(' + X(z) + ' + 10px)'; detail(row, [], r.src); return; }
          el('div', 'ax', tr).style.left = X(z);
          if (TRY && !shown[r.id]) { const p = el('div', 'pre', tr); p.style.cssText = 'position:absolute;left:' + (wide() ? X(z) : 0) + ';padding-left:10px;z-index:1'; (rel(r) ? ['늘었다', '비슷하다', '줄었다'] : ['열기']).forEach((t, i) => { const b = btn(p, 'bt', t, () => open(r, rel(r) ? 1 - i : null)); }); return; }
          const a = Math.min(r.v, 0), b2 = Math.max(r.v, 0), dd = dir(r), f = el('div', 'fill', tr); f.style.setProperty('--k', dd === 0 && chg(r) || same(r) && rel(r) || R.some(x => x.b != null && x.base === r.nm) ? 'var(--sub)' : bad(r) ? 'var(--del)' : 'var(--accent)'); f.style.left = X((a - l.lo) / span); f.style.width = 'max(4px,' + (b2 - a) / span * (xw - x0) * 100 + '%)';
          if (r.b != null) { const m = el('div', 'bs', tr); m.style.left = X((r.b - l.lo) / span); }
          const tx = el('div', 'tx' + (bad(r) && !same(r) && (dd || !chg(r)) ? ' neg' : ''), tr, val(r)), at = X((Math.max(r.v, r.b || 0, 0) - l.lo) / span); if (r.cond) el('small', '', tx, r.cond); tx.style.marginLeft = 'calc(' + at + ' + 10px)'; detail(row, [r.b != null ? '점선 = 기준값 ' + r.base + (/[%a-zA-Z가-힣]/.test(r.base) ? '' : r.unit || '') : ''], r.src); });
    });
    fitText(box, F.H(), 21, 13.5);
    if (TRY) { if (gg) gg.set(sel + 1); if (!txt0) { txt0 = 1; F.tell('', bars.some(rel) ? '막대마다 먼저 고른다: 기준보다 늘었나, 비슷한가, 줄었나.' + (bars.every(rel) ? '' : ' 기준이 없는 막대는 열기만 한다.') : '크기를 먼저 떠올리고 연다.'); } }
  }
  if (TRY) { if (secs.length > 1) gg = group(F, '지표', ['모두'].concat(secs), i => { sel = i - 1; draw(); }); group(F, '', ['모두 열기', '다시 예측'], i => { bars.forEach(r => { if (i) delete shown[r.id]; else shown[r.id] = 1; }); draw(); F.tell('', i ? '막대마다 먼저 고른다.' : '모두 열었다.'); }); }
  R.forEach(r => PATHS.push((r.sec ? r.sec + ' · ' : '') + plain(r.nm) + ' → ' + val(r) + ' ' + (r.cond || '')));
  return { draw: draw };
};

/* ---- timeline: 시간줄 ---- */
PART.timeline = F => {
  const C = F.d.chapters || [], KD = uniq(C.map(c => c.kind || '설명')), kc = c => 'k' + ['설명', '시연', '의견'].indexOf(c.kind || '설명'), sec = s => { const p = String(s == null ? '' : s).replace(/[^\d:]/g, '').split(':').map(Number); return p.length < 2 ? (p[0] || 0) : p.reduce((a, b) => a * 60 + b, 0); };
  const GR = []; C.forEach((c, i) => { c.a = sec(c.at); const x = C.slice(i + 1).filter(y => sec(y.at) > c.a)[0], g = GR[GR.length - 1]; c.b = c.to ? sec(c.to) : x ? sec(x.at) : c.a + 60; if (g && C[g[0]].a === c.a) g.push(i); else GR.push([i]); c.g = GR[GR.length - 1]; }); const t0 = C.length ? C[0].a : 0, t1 = max(C.map(c => c.b)), opened = {}; let cur = -1, kg, kind = -1;
  function draw() {
    F.clear(); const W = F.W(), box = el('div', 'tl', F.stage), ax = el('div', 'tax', box), bar = el('div', 'tbar', box), n = C.length, per = !wide() ? 1 : n <= 6 ? n : Math.ceil(n / 2), wires = per === n && wide() ? el('div', 'wire', box) : null, cs = el('div', 'tcs', box); cs.style.gridTemplateColumns = 'repeat(' + per + ',minmax(0,1fr))';
    const gb = GR.map(g => { const c = C[g[0]], b = btn(bar, kc(c), g.map(i => i + 1).join(' · '), () => go(g.indexOf(cur) >= 0 ? g[(g.indexOf(cur) + 1) % g.length] : g[0])); b.style.flex = Math.max(max(g.map(i => C[i].b)) - c.a, 1) + ' 0 0'; b.setAttribute('aria-label', g.map(i => C[i].t).join(', ')); return b; }), bs = C.map(c => gb[GR.indexOf(c.g)]);
    C.forEach((c, i) => { if (c.g[0] !== i || i && (c.a - C[i - 1].a) / (t1 - t0) < .045) return; const s = el('span', '', ax, c.at); s.style.left = bs[i].offsetLeft + 'px'; });
    const cards = C.map((c, i) => { const e = el(TRY ? 'button' : 'div', 'tc ' + kc(c), cs), at = el('span', 'at', e); el('i', '', at, (i + 1) + ' · ' + (c.kind || '설명')); at.appendChild(doc.createTextNode(c.g[0] === i ? c.at + (c.to ? '–' + c.to : '') : '')); if (c.g.length > 1) el('span', '', at, '구간 안 ' + (c.g.indexOf(i) + 1) + '/' + c.g.length); el('b', '', e, c.t); if (TRY && !opened[i]) el('span', 'ask', e, c.q || '이 대목의 핵심은? 떠올리고 누른다'); else if (c.claim) { const p = el('p', '', e, c.claim); tag(p, c.mark); } if (TRY) { tap(e, () => { go(i); }); } else detail(e, [], c.src); return e; });
    const H = F.H(); fitText(box, H, TRY ? 18 : 20, 13.5); F.need = TRY ? 0 : sum([].map.call(box.children, x => x.offsetHeight + 8));
    if (wires) { const s = sv('svg', { 'aria-hidden': 'true' }, wires), x0 = rc(bar).left; C.forEach((c, i) => { const a = rc(bs[i]), b = rc(cards[i]), h = wires.clientHeight, xa = a.left + a.width * (c.g.indexOf(i) + 1) / (c.g.length + 1) - x0, xb = b.left + 14 - x0; sv('path', { d: 'M' + r1(xa) + ',0C' + r1(xa) + ',' + h * .7 + ' ' + r1(xb) + ',' + h * .3 + ' ' + r1(xb) + ',' + (h + 8), 'class': i === cur ? 'on' : '' }, s); }); }
    C.forEach((c, i) => { const off = kind >= 0 && (c.kind || '설명') !== KD[kind]; tog(cards[i], { on: i === cur, dim: off }); bs[i].classList.toggle('on', c.g.indexOf(cur) >= 0); bs[i].classList.toggle('off', off); });
    if (kg) kg.set(kind + 1); if (TRY && cur < 0) F.tell('', '시간줄이나 칸을 누르면 그 대목의 핵심이 열린다. (←→)');
  }
  function go(i) { cur = i; if (TRY) { opened[i] = 1; const c = C[i]; learn('t' + i, c.at + ' ' + plain(c.t) + (c.claim ? ': ' + c.claim : '')); draw(); F.tell(c.at + (c.to ? '–' + c.to : ''), c.t, c.src); } else { draw(); } }
  if (TRY) { if (KD.length > 1) kg = group(F, '보기', ['모두'].concat(KD), i => { kind = i - 1; draw(); }); F.step = s => go(clamp(cur + s, 0, C.length - 1)); }
  C.forEach(c => PATHS.push(c.at + ' ' + plain(c.t) + ' → ' + (c.claim || '')));
  return { draw: draw };
};

/* ---- ladder: 주장(모델 순서 그대로)과 근거 세기 이름표 ---- */
PART.ladder = F => {
  const K = F.d.claims || [], LV = ['측정', '인용', '사례', '주장만'], ALL = LV.concat(uniq(K.map(c => c.ev)).filter(e => e && LV.indexOf(e) < 0)), done = {}; let cur = TRY ? 0 : -1, g, hi = [];
  function chip(par, ev, cls) { const c = el('span', 'evc e' + LV.indexOf(ev) + (cls || ''), par), m = el('i', '', c); for (let i = 0; i < 4; i++) el('u', i < 4 - Math.max(0, LV.indexOf(ev)) ? 'f' : '', m); c.appendChild(doc.createTextNode(ev)); return c; }
  function draw() {
    F.clear(); const box = el('div', 'ld', F.stage);
    K.forEach((c, i) => { const e = el(TRY ? 'button' : 'div', 'lr', box), ok = done[c.id]; if (!TRY || ok != null) chip(e, c.ev, TRY ? (ok === c.ev ? ' ok' : ' no') : ''); else el('span', 'evc q', e, '근거?'); const m = el('span', 'lt', e); el('span', '', m, c.t); tag(m, c.mark); if (c.quote && TRY && ok != null) el('q', '', m, '“' + c.quote + '”'); if (c.pos) el('span', 'po', e, c.pos); tog(e, { on: TRY ? i === cur : hi.indexOf(c.id) >= 0, dim: hi.length && hi.indexOf(c.id) < 0 }); if (TRY) { tap(e, () => { cur = i; draw(); if (ok != null) F.tell(c.ev, c.t, c.src); else ask(); }); } else detail(e, c.quote ? ['“' + c.quote + '”'] : [], c.src); });
    fitText(box, F.H(), 18, 13.5); if (TRY && !F.say.textContent) ask();
  }
  function ask() { const c = K[cur]; if (c && done[c.id] == null) F.tell('이 주장의 근거는?', c.t); }
  function choose(i) { let c = K[cur]; if (!c || done[c.id] != null) { cur = K.findIndex(x => done[x.id] == null); c = K[cur]; } if (!c) return; done[c.id] = ALL[i]; const ok = ALL[i] === c.ev, was = c; const nx = K.findIndex(x => done[x.id] == null); cur = nx < 0 ? cur : nx; draw(); F.tell(ok ? '맞음' : '다름', '“' + plain(was.t) + '”의 근거는 ' + was.ev + '이다.', was.src, ok ? 'ok' : 'no'); learn('l' + was.id, was.ev + ' — ' + was.t); }
  if (TRY) { g = group(F, '이 주장을 무엇이 받치나?', ALL, choose); group(F, '', ['다시 하기'], () => { K.forEach(x => { delete done[x.id]; }); cur = 0; draw(); ask(); }); F.step = s => { cur = clamp(cur + s, 0, K.length - 1); draw(); const c = K[cur]; if (done[c.id] != null) F.tell(c.ev, c.t, c.src); else ask(); }; }
  F.focus = ids => { hi = K.filter(c => ids.indexOf(c.id) >= 0).map(c => c.id); draw(); };
  K.forEach(c => PATHS.push(plain(c.t) + ' → ' + c.ev));
  return { draw: draw };
};

/* ---- positions: 입장이 줄, 열은 어떻게 · 대가 · 어디. 왼쪽 고리 = 갈리는 사이 ---- */
PART.positions = F => {
  const d = F.d, P = d.positions || [], pm = {}, cost = P.some(p => p.cost), CL = (d.clashes || []).filter(c => P.some(p => p.id === c.a) && P.some(p => p.id === c.b)); P.forEach(p => { pm[p.id] = p; }); let cur = null, g, hi = []; const open = {};
  function draw() {
    F.clear(); const box = el('div', 'ps' + (cost ? ' c3' : '') + (CL.length && wide() ? ' arc' : ''), F.stage), vs = cur ? CL.filter(c => c.a === cur || c.b === cur) : [], rows = {};
    const h = el('div', 'ph', box); ['입장', '어떻게·왜', cost ? '대가' : null].forEach(t => t && el('span', '', h, t));
    P.forEach(p => { const e = el(TRY ? 'button' : 'div', 'pw', box); rows[p.id] = e; const a = el('span', 'pa', e); el('b', '', a, p.t); const n = el('span', 'n', a), v = parseInt(p.n, 10); if (v > 0 && v <= 14) { const u = el('u', '', n); for (let i = 0; i < v; i++) el('i', '', u); } const lab = [p.ev, /댓글|답글|본문/.test(p.src) && p.src].filter(Boolean); n.appendChild(doc.createTextNode(lab.join(' · ')));
      const m = el('span', 'pm', e, p.why); tag(m, p.mark); if (p.quote && TRY && open[p.id]) el('q', '', m, '“' + p.quote + '”'); if (cost) el('span', 'px' + (p.cost ? '' : ' none'), e, p.cost || '원문에 없음').dataset.h = '대가';
      tog(e, { on: p.id === cur || hi.indexOf(p.id) >= 0, vs: p.id !== cur && vs.some(c => c.a === p.id || c.b === p.id), dim: cur && p.id !== cur && !vs.some(c => c.a === p.id || c.b === p.id) });
      if (TRY) { tap(e, () => { pick(cur === p.id ? null : p.id); }); } else detail(e, p.quote ? ['“' + p.quote + '”'] : [], p.src); });
    if (arr(d.agree).length) { const a = el('div', 'agree', box); el('b', '', a, '겹친 말'); d.agree.forEach((x, i) => { if (i) a.appendChild(doc.createTextNode(' · ')); detail(el('span', '', a, x.t), [], x.src); }); }
    F.cap.textContent = ''; if (CL.length && wide()) legend(F, [['var(--warn)', '왼쪽 선 = 갈리는 사이']]);
    fitText(box, F.H(), 18, 13.5);
    if (CL.length && wide()) { const s = sv('svg', { 'class': 'arcs', 'aria-hidden': 'true' }, box), o = rc(box); CL.forEach((c, i) => { const f = id => { const r = rc(rows[id]); return r.top + r.height / 2 - o.top; }, y1 = f(c.a), y2 = f(c.b), x = 24 - (i % 3) * 8, on = cur && (c.a === cur || c.b === cur); sv('path', { d: 'M30,' + r1(y1) + 'H' + x + 'V' + r1(y2) + 'H30', 'class': on ? 'on' : '' }, s); }); }
    if (TRY) { if (g) g.set(P.findIndex(p => p.id === cur)); if (cur) { const p = pm[cur]; F.tell(vs.length ? '갈리는 쪽: ' + vs.map(c => plain(pm[c.a === cur ? c.b : c.a].t)).join(', ') : p.t, vs.length ? vs.map(c => c.on).join(' · ') : '읽은 범위에 반례 없음', p.src, vs.length ? 'wa' : ''); } else F.tell('', '입장을 고르면 대표 인용과 대가, 갈리는 쪽이 켜진다.'); }
  }
  function pick(id) { cur = id; if (cur) { open[cur] = 1; const p = pm[cur], vs = CL.filter(c => c.a === cur || c.b === cur); learn('p' + cur, plain(p.t) + ': ' + (p.why || '') + (p.cost ? ' — 대가: ' + p.cost : '') + (vs.length ? ' ↔ ' + vs.map(c => plain(pm[c.a === cur ? c.b : c.a].t)).join(', ') : '')); } draw(); }
  if (TRY) { g = group(F, '입장', P.map(p => p.t), i => pick(cur === P[i].id ? null : P[i].id)); F.step = s => pick(P[clamp(P.findIndex(p => p.id === cur) + s, 0, P.length - 1)].id); }
  F.focus = ids => { hi = P.filter(p => ids.indexOf(p.id) >= 0).map(p => p.id); draw(); };
  P.forEach(p => PATHS.push(plain(p.t) + ' → ' + (p.quote || p.why || ''))); CL.forEach(c => PATHS.push(plain(pm[c.a].t) + ' ↔ ' + plain(pm[c.b].t) + ': ' + c.on));
  return { draw: draw };
};

/* ---- anatomy: 파일 해부도 ---- */
PART.anatomy = F => {
  const d = F.d, P = d.parts || [], WI = d.whatif || [], len = p => { const m = String(p.range).match(/\d+/g) || [1]; return Math.max(1, (m[1] || m[0]) - m[0] + 1); }; let ask = TRY ? 0 : -1, done = {}, wi = -1, g, miss = -1;
  const order = P.map((_, i) => i).sort((a, b) => ((a * 7 + 3) % (P.length || 1)) - ((b * 7 + 3) % (P.length || 1)));
  function draw() {
    F.clear(); const box = el('div', 'an', F.stage);
    P.forEach((p, i) => { const s = el(TRY ? 'button' : 'div', 'sh' + (i ? '' : ' first') + (i === P.length - 1 ? ' last' : ''), box); s.style.gridColumn = 1; s.style.gridRow = i + 1; el('span', 'rg', s, p.range); el('b', '', s, p.t); const x = el('div', 'ds', box); x.style.gridColumn = 2; x.style.gridRow = i + 1; if (TRY && !done[i]) { x.classList.add('q'); x.textContent = '?'; } else tag(el('span', '', x, p.does), p.mark);
      if (TRY) { tap(s, () => { if (ask >= P.length || done[i]) { openPop(s, [p.does], p.src); return; } const ok = i === order[ask]; if (ok) { done[i] = 1; learn('a' + i, p.range + ' ' + plain(p.t) + ': ' + p.does); ask++; miss = -1; } else miss = i; draw(); F.tell(ok ? '맞음' : '아니다', ok ? (ask < P.length ? '다음: “' + P[order[ask]].does + '”' : '모두 맞혔다.') : '“' + P[order[ask]].does + '” — 다른 부분이다. 다시 고른다.', ok ? p.src : '', ok ? 'ok' : 'no'); }); } else detail(s, [], p.src);
      tog(s, { hit: TRY && done[i], miss: i === miss, warn: wi >= 0 && arr(WI[wi].part).indexOf(p.id) >= 0 }); });
    box.style.gridTemplateRows = P.map(p => 'minmax(min-content,' + r1(1 + Math.sqrt(len(p)) / 3) + 'fr)').join(' ');
    fitText(box, F.H(), 18, 13.5);
    if (TRY && g) g.set(wi); if (TRY && !F.say.textContent) tellAsk();
  }
  function tellAsk() { if (ask < P.length) F.tell('어느 부분이 하는 일인가?', '“' + P[order[ask]].does + '” — 왼쪽에서 고른다.'); }
  if (TRY) { if (WI.length) g = group(F, '바꾸면', WI.map(x => x.if), i => { wi = wi === i ? -1 : i; draw(); if (wi < 0) { tellAsk(); return; } F.tell('→', WI[i].then, WI[i].src, 'wa'); focusAll(arr(WI[i].edges), F); learn('w' + i, plain(WI[i].if) + ' → ' + WI[i].then); }, 'flip'); group(F, '', ['모두 열기', '다시 맞히기'], i => { P.forEach((_, k) => { if (i) delete done[k]; else done[k] = 1; }); ask = i ? 0 : P.length; miss = -1; draw(); if (i) tellAsk(); else F.tell('', '모두 열었다. 부분을 누르면 근거가 나온다.'); }); }
  F.focus = ids => qa('.sh', F.stage).forEach((e, i) => tog(e, { on: ids.indexOf(P[i].id) >= 0 }));
  WI.forEach(x => PATHS.push(plain(x.if) + ' → ' + x.then));
  return { draw: draw };
};

/* ---- lanes: 누가 하나 ---- */
PART.lanes = F => {
  const d = F.d, S = d.steps || [], LN = arr(d.lanes).length ? arr(d.lanes) : uniq(S.map(s => s.lane)), TR = d.triggers || [], keyLane = LN.findIndex(l => /에이전트|조율자|모델|agent/i.test(l)); let k = S.length, tr = -1, g, got = {}, rw = 0, rh = 0;
  function room1() { // 해 보기: 단추·레인·말이 한 화면에 들 레인 높이. 조작 줄과 말이 가장 길 때로 잰다
    if (rw !== innerWidth + 'x' + innerHeight) { rw = innerWidth + 'x' + innerHeight; const k0 = k, old = Array.from(F.say.childNodes), cls = F.say.className, hs = []; let bh = 0;
      for (k = 0; k <= S.length; k++) { ctl(); bh = Math.max(bh, F.bar.offsetHeight); } k = k0; ctl();
      S.forEach((s, i) => { F.tell(i + 1 + '/' + S.length, line(s), s.src); hs.push(F.say.offsetHeight); }); TR.forEach(x => { F.tell('→', x.route, x.src); hs.push(F.say.offsetHeight); });
      const rest = F.host.offsetHeight - F.stage.offsetHeight - F.bar.offsetHeight - F.say.offsetHeight; F.say.className = cls; F.say.replaceChildren(...old); rh = innerHeight - (F === FIGS[0] ? rc(F.host).top + scrollY : 16) - rest - bh - max(hs) - 10; }
    F.host.style.minHeight = '0'; F.host.style.flex = '0 0 auto'; return Math.max(220, rh);
  }
  const line = s => s.lane + ' — ' + s.do + (s.out ? ' → ' + s.out : '');
  function cardOf(par, s, i) { const e = el('button', 'st', par); e.type = 'button'; el('i', '', e, i + 1); el('span', '', e, s.do); tag(e, s.mark); if (s.out) el('small', '', e, '→ ' + s.out); detail(e, [s.if ? '조건: ' + s.if : ''], s.src); if (TRY) { const rt = tr >= 0 ? arr(TR[tr].steps) : []; tog(e, { on: tr < 0 && i === k - 1, dim: rt.length && rt.indexOf(s.id) < 0, ok: got[i] === 1, no: got[i] === 0 }); } return e; }
  function draw() {
    F.clear(); const v = !wide(), W = F.W(), H = TRY && !v ? room1() : F.H(), root = el('div', v ? 'v' : '', F.stage);
    const show = TRY ? S.slice(0, k) : S;
    if (v) { const b = el('div', 'lanes', root); show.forEach((s, i) => { const r = el('div', 'vst', b); el('div', 'ln-n', r, s.lane); cardOf(r, s, i); }); return; }
    const n = S.length, lw = 92, per = (W - lw) / n < 118 ? Math.ceil(n / 2) : n, bands = Math.ceil(n / per);
    const wrap = el('div', bands > 1 ? 'bands' : '', root); for (let b = 0; b < bands; b++) {
      const bx = el('div', 'lanes', wrap), st = S.slice(b * per, (b + 1) * per); const lanes = bands > 1 ? LN.filter(l => st.some(s => s.lane === l)) : LN; bx.style.gridTemplateRows = 'repeat(' + lanes.length + (TRY ? ',minmax(2.6em,auto))' : ',minmax(min-content,1fr))'); bx.style.height = 'auto';
      lanes.forEach((l, r) => { const bg = el('div', 'ln-bg' + (LN.indexOf(l) === keyLane ? ' k' : ''), bx); bg.style.gridRow = r + 1; const nm = el('div', 'ln-n', bx, l); nm.style.cssText = 'grid-row:' + (r + 1) + ';grid-column:1'; });
      const es = st.map((s, j) => { const i = b * per + j, e = cardOf(bx, s, i); e.style.gridRow = lanes.indexOf(s.lane) + 1; e.style.gridColumn = j + 2; return e; }); bx._es = es;
    }
    const cols = m => qa('.lanes', wrap).forEach(b => { b.style.gridTemplateColumns = lw + 'px repeat(' + per + ',minmax(' + m + ',1fr))'; }); cols('min-content');
    const whole = () => qa('.st', wrap).every(e => e.scrollWidth <= e.clientWidth + 1 && e.offsetLeft + e.offsetWidth <= W + 1), fits = () => !H || wrap.scrollHeight <= H && whole(); let f = 17; for (; f > 13; f -= .5) { wrap.style.fontSize = f + 'px'; if (fits()) break; } wrap.style.fontSize = f + 'px'; if (!fits()) wrap.classList.add('dense'); if (!whole()) { wrap.classList.add('brk'); cols('0'); }
    if (TRY) qa('.lanes', wrap).forEach((b, j) => { b.style.gridTemplateColumns = getComputedStyle(b).gridTemplateColumns; b._es = b._es.map((e, i) => { if (j * per + i < k) return e; e.remove(); return null; }); }); // 글자 크기와 칸 폭은 모든 단계로 정하고, 레인 높이는 나온 상자에만 맞춘다
    if (H && !TRY) qa('.lanes', wrap).forEach(b => { b.style.height = Math.max(b.offsetHeight, Math.floor((H - 18 * (bands - 1)) / bands) - 4) + 'px'; });
    qa('.lanes', wrap).forEach((bx, b, all) => { const p = b && d.order !== 'none' && all[b - 1]._es[per - 1], q2 = bx._es[0]; if (!p || !q2) return; // 줄을 바꾸는 선: 앞 줄 끝 칸의 아래 → 두 줄 사이 → 다음 줄 첫 칸의 왼쪽
      const s = sv('svg', { 'aria-hidden': 'true' }, bx), o = rc(bx), A = rc(p), B = rc(q2), x0 = A.left + A.width / 2 - o.left, x1 = B.left - o.left, y1 = B.top + B.height / 2 - o.top, g2 = sv('g', { 'class': 'eg wrap' }, s); sv('path', { 'class': 'ln', d: 'M' + r1(x0) + ',' + r1(A.bottom - o.top) + 'V-10H' + r1(x1 - 14) + 'V' + r1(y1) + 'H' + r1(x1 - 6) }, g2); sv('path', { 'class': 'hd', d: 'M' + r1(x1 - 1) + ',' + r1(y1) + 'l-9,-4.5v9Z' }, g2); });
    qa('.lanes', wrap).forEach(bx => { const s = sv('svg', { 'aria-hidden': 'true' }, bx), o = rc(bx); for (let j = 0; j + 1 < bx._es.length; j++) { const a = bx._es[j], c = bx._es[j + 1]; if (!a || !c || d.order === 'none') continue; const A = rc(a), B = rc(c), x0 = A.right - o.left, y0 = A.top + A.height / 2 - o.top, x1 = B.left - o.left, y1 = B.top + B.height / 2 - o.top, m = (x0 + x1) / 2 - 2, g2 = sv('g', { 'class': 'eg' }, s); sv('path', { 'class': 'ln', d: 'M' + x0 + ',' + y0 + 'H' + m + 'V' + y1 + 'H' + (x1 - 6) }, g2); sv('path', { 'class': 'hd', d: 'M' + (x1 - 1) + ',' + y1 + 'l-9,-4.5v9Z' }, g2); } });
  }
  function ctl() {
    keep(F); F.bar.textContent = ''; if (TR.length) { g = group(F, '이럴 때', TR.map(x => x.say), i => { tr = tr === i ? -1 : i; k = S.length; ctl(); draw(); if (tr < 0) { tell(); return; } F.tell('→', TR[i].route, TR[i].src, 'wa'); learn('tr' + i, plain(TR[i].say) + ' → ' + TR[i].route); }); g.set(tr); }
    group(F, '', ['◀', '▶ 다음 단계', '모두'], i => mv(i === 2 ? 99 : i ? 1 : -1));
    const s = S[k]; if (s && LN.length > 1) group(F, (k + 1) + '번 “' + plain(s.do) + '” — 누가?', LN, i => { got[k] = LN[i] === s.lane ? 1 : 0; const ok = got[k]; k++; ctl(); draw(); F.tell(ok ? '맞음' : '다름', s.lane + ': ' + s.do + (s.out ? ' → ' + s.out : ''), s.src, ok ? 'ok' : 'no'); learn('s' + s.id, s.lane + ': ' + s.do); });
  }
  function mv(n) { tr = -1; k = clamp(k + n, 0, S.length); ctl(); draw(); tell(); }
  function tell() { const s = S[k - 1]; if (s) { F.tell(k + '/' + S.length, line(s), s.src); learn('s' + s.id, s.lane + ': ' + s.do); } else F.tell('', '다음 단계를 누가 하는지 먼저 고른다. 요청을 고르면 어느 길로 가는지 보인다.'); }
  if (TRY) { k = Math.min(1, S.length); ctl(); F.step = mv; setTimeout(tell, 0); }
  S.forEach(s => PATHS.push(s.lane + ' → ' + s.do)); TR.forEach(x => PATHS.push(x.say + ' → ' + x.route));
  return { draw: draw };
};

/* ---- walk: 상황을 골라 한 단계씩(갈림길·상태) ---- */
PART.walk = F => {
  const d = F.d, SC = d.scenarios || [], E = d.edges || [], N = nodesOf(d, E), nid = N.map(n => n.id); let G, P, si = 0, path, got, pick, ended;
  const fits = (b, T) => arr(b.if).every(t => T.indexOf(t) >= 0) && !arr(b.not).some(t => T.indexOf(t) >= 0), endOf = (s, T) => { const e = arr(s.ends).filter(x => fits(x, T))[0]; return e ? e.text : s.end; };
  const eid = st => { const v = arr(st.edge), e = v.length < 2 ? v[0] : (E.filter(x => x.from === v[0] && x.to === v[1])[0] || {}).id; return e || null; };
  const full = (b, T, i, j) => b.max && T.filter(t => t === '#' + i + '/' + j).length >= b.max, put = (st, i, j) => arr(st.branches[j].set).concat('#' + i + '/' + j), here = () => path[path.length - 1], sg = group(F, '상황', SC.map(s => s.name), i => { si = i; begin(); show(); });
  function begin() { path = [0]; got = []; pick = null; ended = false; }
  function next() { const s = SC[si], i = here(), st = s.steps[i]; if (ended || st.branches && pick == null) return; const to = st.branches ? st.branches[pick].to : st.to != null ? st.to : i + 1; if (to < 0 || to >= s.steps.length) ended = true; else { got.push(st.branches ? put(st, i, pick) : []); path.push(to); pick = null; } show(); }
  function prev() { if (path.length > 1) { path.pop(); got.pop(); pick = null; ended = false; show(); } }
  function show() {
    const s = SC[si], T = flat(got), i = here(), st = s.steps[i], B = st.branches, bk = B && pick != null ? B[pick] : null; sg.set(si); keep(F); P.textContent = '';
    if (s.cond) el('p', 'muted', P, '시작 조건: ' + s.cond); const tl = el('ol', 'trail', P); s.steps.forEach((_, k) => el('li', path.indexOf(k) >= 0 ? 'on' : '', tl));
    el('h3', '', P, (i + 1) + '. ' + st.t); if (st.do) el('p', '', P, st.do); if (st.fail) el('p', 'fail', P, '✗ ' + st.fail); if (st.src) el('p', 'muted', P, '근거: ' + st.src);
    if (B) { el('b', '', P, '어느 쪽인가?'); const os = el('div', 'grp', P); B.forEach((b, j) => { const x = btn(os, 'bt', b.label, () => { pick = j; ended = b.to < 0; learn('b' + si + '/' + i + '/' + j, s.name + ' · ' + b.label + ' → ' + b.note); show(); }); x.setAttribute('aria-pressed', pick === j); x.disabled = !fits(b, T) || full(b, T, i, j); }); if (bk) el('p', '', P, bk.note); }
    if (ended) el('p', bk && bk.to < 0 && !bk.ok ? 'fail' : '', P, '끝. ' + (bk && bk.to < 0 ? '이 갈래는 여기서 끝난다.' : endOf(s, bk ? T.concat(arr(bk.set)) : T) || ''));
    const nv = el('div', 'nav', P), e = eid(st); btn(nv, 'bt', '◀ 이전', prev).disabled = path.length < 2; btn(nv, 'bt main', !ended && !B && i === s.steps.length - 1 ? '끝' : '다음 ▶', next).disabled = ended || !!B && pick == null;
    G.light(e ? [e] : [], arr(st.nodes), true); G.run(e ? [e] : []);
  }
  F.step = k => k > 0 ? next() : prev();
  function walk(s, lim) { // 끝까지 갈 수 있는 모든 길
    const out = [], stuck = []; let more = 0, cut = 0; const rep = Math.min(4, max(flat(s.steps.map(st => arr(st.branches))).map(b => (b.max || 0) + 1), 0) || 2) || 2;
    (function go(i, T, seen, t) { if (out.length >= lim) { more++; return; } const st = s.steps[i], k = cp(seen); k[i] = (k[i] || 0) + 1; if (!st) return; if (k[i] > Math.max(2, rep)) { cut++; return; } t += ' → ' + (i + 1) + ' ' + st.t;
      const leave = (to, U, u, b) => { if (to >= 0 && to < s.steps.length) go(to, U, k, u); else out.push(u + (b && to < 0 ? ' ⇒ 끝(' + (b.ok ? (b.ok === true ? '통과' : b.ok) : '중단') + '): ' + b.note : ' ⇒ 끝: ' + endOf(s, U))); };
      if (!st.branches) { leave(st.to != null ? st.to : i + 1, T, t); return; } const ok = st.branches.map((b, j) => [b, j]).filter(x => fits(x[0], T) && !full(x[0], T, i, x[1])); if (!ok.length) stuck.push(i + 1); ok.forEach(x => leave(x[0].to, T.concat(put(st, i, x[1])), t + ' [' + x[0].label + ']', x[0])); })(0, [], {}, s.name + (s.cond ? ' (' + s.cond + ')' : ''));
    return { out: out, stuck: stuck, more: more, cut: cut };
  }
  SC.forEach(s => { const w = walk(s, 150); PATHS.push('■ ' + s.name); w.out.forEach(x => PATHS.push(x)); if (w.more) PATHS.push('150개까지만 보였다'); if (w.cut) PATHS.push('되풀이가 길어 접은 길 ' + w.cut + '개'); });
  function check() {
    const w = G.check();
    SC.forEach(s => {
      const L = s.steps.length, at = i => s.name + ' ' + (i + 1) + '단계: ', bs = flat(s.steps.map(st => arr(st.branches))), sets = flat(bs.map(b => arr(b.set))), seen = {}, Q = [0]; let end = false;
      s.steps.forEach((st, i) => { arr(st.branches).forEach((b, j) => { if (!(b.to === -1 || b.to >= 0 && b.to < L && b.to % 1 === 0)) w.push(at(i) + '없는 곳으로 가는 갈래 ' + b.label); const k = st.branches.findIndex(x => x.to === b.to); if (b.to >= 0 && k < j && String(arr(st.branches[k].set)) === String(arr(b.set))) w.push('참고: ' + at(i) + '상태를 남기지 않고 합쳐지는 갈래'); }); if (!st.nodes && !st.edge) w.push(at(i) + '그림에서 켤 곳 없음'); if (st.edge && !E.some(e => e.id === eid(st))) w.push(at(i) + '없는 간선 ' + st.edge); arr(st.nodes).forEach(n => { if (nid.indexOf(n) < 0) w.push(at(i) + '없는 노드 ' + n); }); });
      bs.concat(arr(s.ends)).forEach(b => arr(b.if).concat(arr(b.not)).forEach(t => { if (sets.indexOf(t) < 0) w.push(s.name + ': 아무 갈래도 정하지 않는 상태 ' + t); }));
      while (Q.length) { const i = Q.pop(), st = s.steps[i]; if (seen[i] || !st) continue; seen[i] = 1; (st.branches ? st.branches.map(b => b.to) : [st.to != null ? st.to : i + 1]).forEach(t => { if (t < 0 || t >= L) end = true; else Q.push(t); }); }
      s.steps.forEach((_, i) => { if (!seen[i]) w.push(at(i) + '닿지 않는다'); }); if (!end) w.push(s.name + ': 끝나지 않음'); walk(s, 60).stuck.forEach(i => w.push(at(i - 1) + '앞의 선택과 맞는 갈래가 없다')); if (L > 10) w.push('참고: ' + s.name + ': 단계 ' + L + '개(한도 10)');
    });
    return w;
  }
  return { draw() { F.clear(); const bx = el('div', 'wk', F.stage), st = el('div', '', bx); P = el('div', 'wkp', bx); P.setAttribute('aria-live', 'polite'); G = graph(st, { nodes: N, edges: E, W: wide() ? F.W() - 350 : F.W(), H: wide() ? Math.max(380, F.H()) : 0 }); tip(G, d); F.checks = [check]; if (!path) begin(); show(); } };
};

/* ---- toggle: 왼쪽을 누르면 오른쪽이 열린다 ---- */
PART.toggle = F => {
  const it = F.d.items || [], on = {};
  function draw() { F.clear(); const u = el('ul', 'tgl', F.stage); it.forEach((x, i) => { const li = el('li', '', u), b = btn(li, 'bt', x.if, () => { on[i] = !on[i]; draw(); if (on[i]) { learn(F.d.key + i, plain(x.if) + ' → ' + x.then); focusAll(arr(x.ids).concat(arr(x.edges))); } }); b.setAttribute('aria-pressed', !!on[i]); el('span', on[i] ? '' : 'q', li, on[i] ? '→ ' + x.then : '→ ?'); if (on[i] && x.src) el('small', '', li, '근거: ' + x.src); }); }
  it.forEach(x => PATHS.push(plain(x.if) + ' → ' + x.then)); return { draw: draw };
};
PART.list = F => ({ draw() { F.clear(); const b = el('div', 'ld lst', F.stage); arr(F.d.items).forEach(x => { const m = String(x.t).split(/\s+[—–]\s+/), c = el('div', 'lr' + (m[1] ? '' : ' one'), b); if (m[1]) el('b', '', c, m[0]); tag(el('span', '', c, m[1] ? m.slice(1).join(' — ') : m[0]), x.mark); detail(c, [], x.src); }); fitText(b, F.H(), 20, 13.5); } });
function focusAll(ids, me) { FIGS.forEach(F => { if (F !== me && F.focus) F.focus(ids); }); }

/* ---- predict: 먼저 고르고 공개 ---- */
function predict(par, p, i) {
  const c = el('div', 'pd', par), qv = el('p', 'q', c); el('small', '', qv, '먼저 예측'); el('span', '', qv, p.q); const os = el('div', 'os', c), op = arr(p.opts), ans = p.a;
  function open(k) { const had = os.contains(doc.activeElement), was = q('.ans', c); if (was) was.remove(); qa('.bt', os).forEach((b, j) => { if (op.length) { tog(b, { hit: j === ans, miss: j === k && k !== ans }); b.disabled = true; } else b.remove(); }); const a = el('div', 'ans', c); a.setAttribute('aria-live', 'polite'); if (op.length) { const b = el('b', '', a, k === ans ? '맞음. ' : '다름. '); b.style.color = k === ans ? 'var(--add)' : 'var(--del)'; } tag(el('span', '', a, p.why || (op.length ? '답: ' + op[ans] : p.answer || '')), p.mark); if (p.src) el('span', 'src', a, '근거: ' + p.src); if (had) { a.tabIndex = -1; a.focus({ preventScroll: true }); } learn('pd' + i, p.say || plain(p.q) + ' → ' + plain(op.length ? op[ans] : p.answer || p.why)); }
  if (op.length) op.forEach((t, k) => { const b = btn(os, 'bt', t, () => open(k)); }); else { const b = btn(os, 'bt', '답을 떠올렸다 — 펼치기', () => open(0)); }
  PATHS.push('예측 ' + plain(p.q) + ' → ' + (op.length ? op[ans] : p.answer || p.why));
}

/* ---- 화면 ---- */
doc.title = plain(D.title || D.one);
const app = doc.getElementById('app') || el('main', '', doc.body), split = D.layout === 'split' && !TRY; app.className = 'page ' + (TRY ? 'interactive' : 'html') + (split ? ' split' : ''); app.textContent = '';
const hd = el('header', '', app); if (D.notice) el('p', 'notice', hd, D.notice); el('p', 'kicker', hd, [D.typeName, D.name].filter(Boolean).join(' · ')); { const h = D.head || {}, s = el('span', '', el('h1', '', hd), D.one); tag(s, h.mark); detail(s, [], h.src); }
if (arr(D.why).length) { const w = el('p', 'why', hd); el('b', '', w, D.whyLabel || '왜'); D.why.forEach((x, i) => { if (i) w.appendChild(doc.createTextNode(' · ')); const s = el('span', '', w, x.t); tag(s, x.mark); detail(s, [], x.src); }); }
if (TRY && D.hint) { const h = el('p', 'hint', hd); el('b', '', h, '눌러서 알게 되는 것'); h.appendChild(doc.createTextNode(D.hint)); }
const body = el('div', 'body', app), figs = el('div', 'figs', body), below = el('div', 'below', body);
if (arr(D.lead).length) { const p = el('p', 'lead', figs); D.lead.forEach(x => { el('b', '', p, x.label); const s = el('span', '', p, x.t); tag(s, x.mark); detail(s, [], x.src); }); }
if (TRY) arr(D.predicts).filter(p => p.slot === 'pic').forEach((x, i) => predict(el('div', 'pds one', figs), x, 'p' + i));
arr(D.figs).forEach(d => { const host = el('section', 'fig', figs); host.setAttribute('aria-label', d.aria || plain(D.one)); host.dataset.part = d.part; if (d.part === 'anatomy' && D.figs.length > 1 && wide()) figs.classList.add('pair'); if (d.part === 'toggle') host.style.flex = '0 0 auto'; FIGS.push(Fig(host, d)); });
function tableOf(par, t) { // 줄이 많고 열이 둘이면 두 단으로
  const bx = el('section', 'tb', par); el('h2', '', bx, t.label); const n = t.rows.length; if (t.cols.length > 2 || n > 4) bx.classList.add('full'); const two = !split && t.cols.length === 2 && n > 4 && wide(), hold = el('div', two ? 'tw' : '', bx);
  (two ? [t.rows.slice(0, Math.ceil(n / 2)), t.rows.slice(Math.ceil(n / 2))] : [t.rows]).forEach(rs => { const tb = el('table', 't' + (t.cols.length > 2 ? ' c3' : ''), hold); if (!two && t.cols.length > 2) { const h = el('tr', '', el('thead', '', tb)); t.cols.forEach(c => el('th', '', h, c)); } const y = el('tbody', '', tb); rs.forEach(r => { const x = el('tr', '', y), has = r.src || arr(r.ids).length; r.cells.forEach((c, i) => { const e = el(i ? 'td' : 'th', t.diff && i === 2 ? (/^(같음|그대로)/.test(c) || c === r.cells[1] ? 'same' : 'chg') : t.diff && i ? 'same' : '', x); el(!i && has ? 'button' : 'span', !i && has ? 'rb' : '', e, c || '원문에 없음'); if (i === r.cells.length - 1) tag(e, r.mark); }); if (has) { const b = q('.rb', x); b.type = 'button'; link(b, r); x.classList.add('hasd'); x.addEventListener('click', ev => { ev.stopPropagation(); b.click(); }); } }); });
  return bx;
}
function link(e, r) { detail(e, [], r.src); if (arr(r.ids).length) e.addEventListener('click', () => focusAll((r.src ? POP && POP.o === e : e.classList.toggle('lit')) ? r.ids : [])); }
function cardOf(par, c) {
  const b = el('section', 'chip ' + (c.slot === 'catch' && c.kind !== 'line' ? 'catch' : ''), par); el('b', '', b, c.label); const k = c.kind;
  if (k === 'code') c.items.forEach(x => { el('pre', '', b, '').textContent = x.code || x.t; });
  else if (k === 'steps' || k === 'list' && c.items.length > 1) { const u = el(k === 'steps' ? 'ol' : 'ul', '', b); c.items.forEach(x => { const l = el('li', '', u); el('span', '', l, x.t); tag(l, x.mark); link(l, x); }); }
  else c.items.forEach(x => { const p = el(k === 'quote' ? 'q' : 'p', k === 'number' ? 'num' : '', b, x.t); tag(p, x.mark); link(p, x); });
}
const safe = f => x => { try { f(below, x); } catch (e) { ERR.push(e.message); } };
arr(D.tables).forEach(safe(tableOf)); arr(D.cards).forEach(safe(cardOf));
if (!below.children.length) below.remove();
if (TRY && arr(D.predicts).some(p => p.slot !== 'pic')) { const p = el('div', 'pds', app); D.predicts.filter(x => x.slot !== 'pic').forEach((x, i) => predict(p, x, i)); }
if (TRY) { const L = el('section', 'lrn', app); el('h2', '', L, '방금 알게 된 것'); const u = el('ul', '', L); u.setAttribute('aria-live', 'polite'); drawLearn = () => { u.textContent = ''; LEARN.slice(-8).forEach(x => el('li', '', u, x.t)); if (!LEARN.length) el('li', 'no', u, '위를 누르면 한 줄씩 쌓인다.'); arr(D.learn).forEach(x => { const li = el('li', 'fin', u); if (x.label) el('b', '', li, x.label); el('span', '', li, x.t); tag(li, x.mark); link(li, x); }); }; drawLearn(); }
const ft = el('footer', '', app); if (D.order) el('p', '', ft, D.order); if (D.missing) el('p', '', ft, '빠진 디테일: ' + D.missing); if (D.source) { const p = el('p', '', ft, '출처: '); String(D.source).split(/(https?:\/\/[^\s)]+)/).forEach((s, i) => { if (i % 2) { const a = el('a', '', p); a.href = s; a.rel = 'noreferrer'; a.textContent = s; } else el('span', '', p, s); }); }
function room(need) { // 아래 글을 줄여 그림 자리를 낸다(13.5px까지)
  const f0 = q('.fig', figs), desk = wide() && innerHeight >= 600; FIGS.forEach(F => { F.host.style.flex = F.d.part === 'toggle' ? '0 0 auto' : ''; }); figs.style.minHeight = below.style.cssText = body.style.cssText = ''; FIGS.forEach(F => { F.clear(); F.say.textContent = F.say.textContent; });
  if (!desk) return; const IH = innerHeight;
  if (TRY) { const top = f0 ? rc(f0).top + scrollY : 0; FIGS.forEach((F, i) => { if (F.d.part === 'toggle') return; F.host.style.minHeight = Math.max(i ? 380 : 400, IH - (i ? 260 : top + 16)) + 'px'; }); return; }
  FIGS.forEach(F => { const m = Math.max(FIGS[1] && F.d.part === 'flow' ? 200 : 0, F.want || 0); if (m) F.host.style.minHeight = m + 'px'; });
  if (!below.isConnected) return; const fs = [18, 17, 16.5, 16, 15.5, 15, 14.5, 14, 13.5]; let k = 0;
  if (split) { for (const c of [1.62, 1.3, 1.05]) { body.style.gridTemplateColumns = 'minmax(0,' + c + 'fr) minmax(0,1fr)'; for (k = 0; k < fs.length; k++) { below.style.fontSize = fs[k] + 'px'; if (below.scrollHeight <= body.clientHeight + 1 && !over()) return; } } return; }
  for (const share of need ? [need / IH] : [.52, .46, .4, .34, .28, .22]) { figs.style.minHeight = IH * share + 'px'; for (k = 2; k < fs.length; k++) { below.style.fontSize = fs[k] + 'px'; if (!over()) return; } }
}
function over() { return doc.documentElement.scrollHeight > innerHeight; }
function fill() { // 그림이 덜 쓰는 높이를 아래 글에 준다
  const use = sum(FIGS.map(F => F.need ? F.need + F.host.offsetHeight - F.stage.clientHeight + 26 : F.host.offsetHeight)), f0 = below.style.fontSize; if (split || !below.isConnected || figs.offsetHeight - use < 40) return 0;
  FIGS.forEach(F => F.clear()); figs.style.minHeight = use + 'px'; for (const x of [[18, 9], [17.5, 8], [17, 7], [16.5, 6], [16, 5.5], [15.5, 5], [15, 4.5], [14.5, 4]]) { below.style.fontSize = x[0] + 'px'; below.style.setProperty('--v', x[1] + 'px'); if (!over()) return 1; } below.style.cssText = 'font-size:' + f0; figs.style.minHeight = ''; return 1;
}
function paint() { FIGS.forEach(F => { try { if (!F.api) { const f = PART[F.d.part]; if (!f) throw Error('모르는 부품: ' + F.d.part); F.api = f(F); } F.api.draw(); } catch (e) { F.err = e; console.error(e); asText(F); } }); }
function asText(F) { // 못 그린 그림은 글 목록으로
  const d = F.d, nm = {}; F.need = 0; F.checks = []; arr(d.nodes).forEach(n => { if (n) nm[n.id] = n.t; }); F.clear(); el('p', 'err', F.stage, '그림을 그리지 못해 글로 적었다'); const u = el('ul', 'fb', F.stage);
  ['edges', 'zones', 'results', 'options', 'cells', 'chapters', 'claims', 'positions', 'parts', 'steps', 'items'].forEach(k => arr(d[k]).forEach(x => { if (x) el('li', '', u, k === 'edges' ? (nm[x.from] || x.from) + ' → ' + (nm[x.to] || x.to) + ': ' + (x.t || '') : ['group', 'at', 'lane', 'range', 'label', 't', 'do', 'if', 'then', 'does', 'claim', 'value', 'unit', 'why', 'cost', 'out'].map(f => x[f]).filter(Boolean).join(' · ')); })); fitText(u, F.H(), 18, 13.5);
}
function drawAll() { app.classList.remove('tight'); FIGS.forEach(F => { F.want = 0; }); room(); paint(); if (!wide()) return; if (TRY) { const f = FIGS.filter(F => F.need && F.stage.clientHeight - F.need > 80); f.forEach(F => { F.host.style.minHeight = F.host.offsetHeight - F.stage.clientHeight + F.need + 50 + 'px'; F.host.style.flex = '0 0 auto'; }); if (f.length) paint(); return; } if (FIGS.some(F => F.want)) { room(); paint(); } else if (fill()) paint(); for (let k = 0; k < 2 && over(); k++) { const h = figs.offsetHeight; if (k) app.classList.add('tight'); room(h); paint(); } }
drawAll();
let last = innerWidth + 'x' + innerHeight, tm; function again() { clearTimeout(tm); tm = setTimeout(() => { const z = innerWidth + 'x' + (wide() ? innerHeight : ''); if (z === last) return; last = z; closePop(); drawAll(); }, 120); } addEventListener('resize', again);
if (doc.fonts && doc.fonts.ready) doc.fonts.ready.then(() => { if (doc.fonts.size) drawAll(); });
let act = FIGS.filter(F => F.step)[0] || FIGS[0]; FIGS.forEach(F => F.host.addEventListener('pointerdown', () => { act = F; }));
doc.addEventListener('keydown', ev => { if (ev.metaKey || ev.ctrlKey || ev.altKey) return; if (ev.key === 'Escape') closePop(); if (!act || !TRY) return; if (ev.key === 'ArrowRight' && act.step) { act.step(1); ev.preventDefault(); } else if (ev.key === 'ArrowLeft' && act.step) { act.step(-1); ev.preventDefault(); } else if (/^[1-9]$/.test(ev.key)) { const b = qa('.bar .bt:not(:disabled)', act.host)[ev.key - 1]; if (b) b.click(); } });

/* ---- 점검 ---- */
window.INTO_CHECK = () => {
  const w = ERR.map(x => '오류: ' + x); FIGS.forEach(F => { if (F.err) w.push('그림 오류: ' + F.err.message); F.checks.forEach(c => c().forEach(x => w.push(F.d.part + ' · ' + x)));
    const ids = (F.d.nodes || []).map(n => n.id); (F.d.edges || []).forEach(e => { if (ids.length && (ids.indexOf(e.from) < 0 || ids.indexOf(e.to) < 0)) w.push(F.d.part + ' · 없는 노드 간선 ' + e.id); if (!e.t) w.push(F.d.part + ' · 라벨 없는 간선 ' + e.id); }); });
  const bs = qa('.st,.tc,.lr,.pw,.tx,.res', figs), rs = bs.map(rc); bs.forEach((e, i) => { if (e.scrollWidth > e.clientWidth + 2 || rs[i].right > innerWidth + 2) w.push('칸 넘침: ' + e.textContent.slice(0, 30)); rs.slice(i + 1).forEach((b, j) => { const a = rs[i]; if (!e.contains(bs[i + 1 + j]) && Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 2) w.push('칸 겹침: ' + e.textContent.slice(0, 20)); }); });
  if (doc.documentElement.scrollWidth > innerWidth + 1) w.push('페이지 가로 스크롤 ' + doc.documentElement.scrollWidth + '>' + innerWidth);
  if (!TRY && innerWidth >= 900 && doc.documentElement.scrollHeight > innerHeight + 2) w.push('한 화면을 넘음 ' + doc.documentElement.scrollHeight + '>' + innerHeight);
  const tw = doc.createTreeWalker(app, NodeFilter.SHOW_TEXT); let n; const small = {}; while ((n = tw.nextNode())) { if (!n.textContent.trim()) continue; const p = n.parentElement, f = parseFloat(getComputedStyle(p).fontSize); if (f < (p.closest('footer,.lb,.tag,kbd') ? 12 : 12.9)) small[f + ' ' + n.textContent.trim().slice(0, 20)] = 1; } Object.keys(small).forEach(k => w.push('작은 글자 ' + k));
  if (TRY && FIGS[0]) { const b = q('[data-act]', FIGS[0].host); if (!b) w.push('조작 없음'); else if (rc(b).top + scrollY > innerHeight) w.push('첫 화면에 조작이 없다'); }
  return w;
};
window.INTO_PATHS = () => PATHS.slice();
})();
