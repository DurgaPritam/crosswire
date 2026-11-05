// Watches a live run on the Incident Console and screenshots each milestone as its event arrives (read-only: GETs and
// the SSE stream only; it never starts or changes anything).
//   node scripts/watch-live.mjs [outDir]     (waits up to 20 min for a run to start, follows it to the finale)
import fs from 'node:fs'; import path from 'node:path'; import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const BASE = process.env.CONSOLE_URL ?? 'http://127.0.0.1:7300';
const OUT = path.resolve(process.argv[2] ?? path.join(ROOT, 'docs/screenshots/live'));
const LOG = path.join(ROOT, '.tmp/live-watch.jsonl');
fs.mkdirSync(OUT, { recursive: true }); fs.writeFileSync(LOG, '');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const get = async (p) => (await fetch(BASE + p)).json();
const log = (o) => { fs.appendFileSync(LOG, JSON.stringify({ at: Date.now(), ...o }) + '\n'); console.log(new Date().toTimeString().slice(0, 8), JSON.stringify(o)); };

// milestone: [label, test(event), delay before the shot (ms: let the motion settle, inside the overlay's window)]
const MILESTONES = [
  ['report', (e) => e.kind === 'message' && e.who === 'sam', 1500],
  ['incident-opened', (e) => e.kind === 'incident_opened', 1500],
  ['salt', (e) => e.kind === 'salt', 1500],
  ['first-draft', (e) => e.kind === 'draft', 1500],
  ['first-approval', (e) => e.kind === 'approval', 1500],
  ['first-crossing', (e) => e.kind === 'disclosure_crossed', 900],
  ['refusal', (e) => e.kind === 'refusal', 1300],
  ['byte-diff', (e) => e.kind === 'notary_compare', 2600],
  ['root-cause', (e) => e.kind === 'status_change' && e.status === 'root-cause', 1500],
  ['fix-payco', (e) => e.kind === 'fix_done' && e.company === 'payco', 1500],
  ['fix-shopco', (e) => e.kind === 'fix_done' && e.company === 'shopco', 1500],
  ['finale', (e) => e.kind === 'status_change' && e.status === 'resolved', 3500],
];

log({ watch: 'waiting for a run to start', base: BASE });
const deadline = Date.now() + 20 * 60_000;
while (!(await get('/api/run').catch(() => ({}))).running) { if (Date.now() > deadline) { log({ watch: 'no run started' }); process.exit(1); } await sleep(2000); }
log({ watch: 'run started' });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
const errors = []; page.on('pageerror', (e) => errors.push(e.message));
await page.goto(`${BASE}/?theme=dark`, { waitUntil: 'load' }); await page.waitForTimeout(2000);  // live keeps an SSE stream open: never 'networkidle'

let n = 0; const done = new Set(); const queue = []; let armed = false;  // armed when the run's recording starts (after preflight)
const shoot = async (label) => { n += 1; const f = path.join(OUT, `${String(n).padStart(2, '0')}-${label}.png`); await page.screenshot({ path: f }); log({ shot: path.relative(ROOT, f) }); };

// follow the same SSE stream the page uses
const ctrl = new AbortController();
(async () => {
  const res = await fetch(BASE + '/api/events', { signal: ctrl.signal }); const reader = res.body.getReader(); const dec = new TextDecoder(); let buf = '';
  for (;;) {
    const { value, done: end } = await reader.read(); if (end) break; buf += dec.decode(value, { stream: true });
    let i; while ((i = buf.indexOf('\n\n')) >= 0) {
      const frame = buf.slice(0, i); buf = buf.slice(i + 2);
      const ev = /^event: (\w+)/m.exec(frame)?.[1]; const data = /^data: (.*)$/m.exec(frame)?.[1];
      if (ev === 'reset') { armed = true; log({ stream: 'reset (new recording): milestones armed' }); continue; }
      if (ev !== 'cw' || !data) continue;
      const e = JSON.parse(data);
      log({ event: e.kind, who: e.who, lane: e.lane, d: e.d_id ?? e.status ?? e.company ?? undefined, t: e.t });
      if (!armed) continue;  // preflight's own posts (PREFLIGHT drafts etc.) are not the run
      for (const [label, test, delay] of MILESTONES) if (!done.has(label) && test(e)) { done.add(label); queue.push([label, Date.now() + delay]); }
    }
  }
})().catch(() => {});

let lastPeriodic = Date.now(); let finishedAt = null;
while (Date.now() < deadline + 40 * 60_000) {
  const now = Date.now();
  for (const q of queue.filter((x) => x[1] <= now)) { queue.splice(queue.indexOf(q), 1); await shoot(q[0]); }
  if (armed && now - lastPeriodic > 90_000) { lastPeriodic = now; await shoot('t' + Math.round((now - Date.parse(new Date().toDateString())) / 1000)); }
  if (finishedAt === null && !(await get('/api/run').catch(() => ({ running: true }))).running) { finishedAt = now; log({ watch: 'run finished' }); }
  if ((done.has('finale') && queue.length === 0) || (finishedAt && now - finishedAt > 20_000 && queue.length === 0)) break;
  await sleep(500);
}
ctrl.abort(); await browser.close();
log({ watch: 'stopped', milestones: [...done], missing: MILESTONES.map((m) => m[0]).filter((l) => !done.has(l)), page_errors: errors.slice(0, 5) });
